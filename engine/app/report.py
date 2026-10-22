"""The audit pipeline (spec §7.8, IMPL M4.6).

parse → normalize → detect → features → score → forecast → flags → summary → done.
`start_pipeline` runs as a task that writes SSE events into a queue, so an audit finishes and persists
even if the window reloads mid-way. `rescore` re-runs detect…flags without the LLM (labels, edits, a
TabPFN upgrade) and must stay within ~5 s.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import db, detectors, ingest, llm_summary, normalize, ollama_setup, reminders, user_settings
from .config import settings
from .detectors import RECURRING, kind_of
from .features import CADENCES, FEATURES, next_step_row, regression_rows, series_extras, series_features
from .money import money
from .state import runtime
from .tabular import Q10, Q50, Q90, tabular

log = logging.getLogger(__name__)

STAGES = ("parse", "normalize", "detect", "features", "score", "forecast", "flags", "summary", "done")
FLAG_IDS = ("duplicate_charge", "price_creep", "overlap", "possible_annual", "zombie_suspect")
EXCLUDED = {"not_subscription", "user_cancelled"}
FORECAST_DAYS = 30
STEP = {"weekly": pd.DateOffset(days=7), "biweekly": pd.DateOffset(days=14), "monthly": pd.DateOffset(months=1),
        "quarterly": pd.DateOffset(months=3), "annual": pd.DateOffset(years=1)}


class PipelineBusy(Exception):
    pass


def _step(cadence: str, median_interval: float | None) -> pd.DateOffset:
    if cadence in STEP:
        return STEP[cadence]
    days = median_interval if median_interval and not np.isnan(median_interval) else 30.44
    return pd.DateOffset(days=max(1, round(days)))


def _period_days(cadence: str, median_interval: float | None) -> float:
    if cadence in CADENCES:
        return CADENCES[cadence][0]
    return float(median_interval) if median_interval and not np.isnan(median_interval) else 30.44


def _clean(value):
    """JSON-safe: numpy scalars → Python, NaN → None."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


# ── context ─────────────────────────────────────────────────────────────────

@dataclass
class Context:
    report_date: pd.Timestamp
    currency: str
    debits: pd.DataFrame
    statuses: dict[str, str]
    labels: list[dict]
    series: dict[str, dict] = field(default_factory=dict)  # merchants with ≥ 2 charges
    singles: dict[str, dict] = field(default_factory=dict)  # merchants charged once
    duplicate_ids: set[int] = field(default_factory=set)
    scorer: str = "heuristic"
    rows: list[dict] = field(default_factory=list)  # what gets persisted to `series`
    meta: dict = field(default_factory=dict)
    summary: str = ""
    summary_source: str = "template"

    @classmethod
    def load(cls) -> "Context":
        debits = db.debits_frame()
        if debits.empty:
            raise ValueError("There are no transactions to audit yet.")
        missing = debits["merchant"].isna()
        debits.loc[missing, "merchant"] = debits.loc[missing, "desc_key"].map(
            lambda k: normalize.rule_fallback(k)["merchant"])
        debits["category"] = debits["category"].fillna("Other")
        imports = db.list_imports()
        currency = (imports[-1]["currency"] if imports else None) or user_settings.load().currency
        return cls(report_date=pd.Timestamp(db.max_tx_date()), currency=currency, debits=debits,
                   statuses=db.series_statuses(), labels=db.user_labels())


def _merchant_info(g: pd.DataFrame) -> tuple[str, bool, str]:
    """(category, subscription_like, source) across all description keys of one merchant."""
    category = str(g["category"].value_counts().idxmax())
    sources = set(g["source"])
    source = "user" if "user" in sources else "llm" if "llm" in sources else "rule"
    return category, bool(g["subscription_like"].max()), source


# ── stages ──────────────────────────────────────────────────────────────────

def detect(ctx: Context) -> None:
    ctx.series, ctx.singles, ctx.duplicate_ids = {}, {}, set()
    for merchant, g in ctx.debits.groupby("merchant", sort=True):
        g = g.sort_values(["tx_date", "id"])
        category, sub_like, source = _merchant_info(g)
        entry = {"merchant": merchant, "category": category, "sub_like": sub_like, "source": source,
                 "kind": kind_of(category), "g_all": g, "status": ctx.statuses.get(merchant, "active"), "dups": []}
        if len(g) >= 2:
            entry["dups"] = detectors.duplicate_charges(g, detectors.raw_cadence_days(g))
            ctx.duplicate_ids |= {p["tx_ids"][1] for p in entry["dups"]}
            ctx.series[merchant] = entry
        else:
            ctx.singles[merchant] = entry


def features(ctx: Context) -> None:
    for merchant, s in list(ctx.series.items()):
        g = s["g_all"][~s["g_all"]["id"].isin(ctx.duplicate_ids)]
        if len(g) < 2:  # only duplicates of one charge: treat as a single
            ctx.singles[merchant] = ctx.series.pop(merchant)
            continue
        s["g"] = g
        s["feats"] = series_features(g, ctx.report_date, s["category"], s["sub_like"])
        s.update(series_extras(s["g_all"], g, s["feats"]["amount_cv"]))


def score(ctx: Context) -> None:
    ctx.scorer = tabular.scorer
    if not ctx.series:
        return
    names = list(ctx.series)
    X = pd.DataFrame([ctx.series[m]["feats"] for m in names])[FEATURES]
    labels = pd.DataFrame(ctx.labels) if ctx.labels else None
    probs = tabular.recurring_prob(X, labels)
    similar = tabular.nearest_archetypes(X)
    by_label = {lab["merchant"]: lab["label"] for lab in ctx.labels}
    for merchant, prob, sim in zip(names, probs, similar, strict=True):
        s = ctx.series[merchant]
        if ctx.scorer == "heuristic" and merchant in by_label:
            prob = float(by_label[merchant])  # IMPL M4.9: a rule can't learn, so pin the user's answer
        s["prob"], s["similar"] = float(prob), sim
        s["recurring"] = (s["prob"] >= RECURRING and s["status"] not in EXCLUDED) or s["status"] == "keep"


def forecast(ctx: Context) -> None:
    recurring = [s for s in ctx.series.values() if s.get("recurring")]
    history, queries = [], []
    for s in recurring:
        f = s["feats"]
        step = _step(f["cadence"], f["median_interval"])
        due = pd.Timestamp(s["g"]["tx_date"].iloc[-1]) + step
        while due <= ctx.report_date:
            due += step
        s["next_due"], s["step"] = due, step
        history.append(regression_rows(s["g"], f["cadence"], s["category"]))
        queries.append(next_step_row(s["g"], f["cadence"], s["category"], due.month))
    ctx_rows = pd.concat(history, ignore_index=True) if history else pd.DataFrame()
    ratios = tabular.ratio_quantiles(ctx_rows, pd.DataFrame(queries)) if queries else np.ones((0, 19))

    window_end = ctx.report_date + pd.Timedelta(days=FORECAST_DAYS)
    totals = {"all": np.zeros(3), "subscriptions": np.zeros(3)}
    for s, row in zip(recurring, ratios, strict=True):
        last = float(s["g"]["amount"].iloc[-1])
        s["quantiles"] = [round(last * r, 2) for r in row]
        s["fc"] = (round(last * row[Q10], 2), round(last * row[Q50], 2), round(last * row[Q90], 2))
        s["hike_prob"] = float(np.mean(row > 1.02))
        due, occurrences = s["next_due"], 0
        while due <= window_end:
            occurrences += 1
            due += s["step"]
        totals["all"] += occurrences * np.array(s["fc"])
        if s["kind"] == "subscription":
            totals["subscriptions"] += occurrences * np.array(s["fc"])
    ctx.meta["forecast"] = {k: {"q10": round(v[0], 2), "q50": round(v[1], 2), "q90": round(v[2], 2)}
                            for k, v in totals.items()}


def flags(ctx: Context) -> None:
    rows: list[dict] = []
    for s in ctx.series.values():
        f = s["feats"]
        last = float(s["g"]["amount"].iloc[-1])
        s["flags"], s["details"] = [], {}
        if s["dups"]:
            s["flags"].append("duplicate_charge")
            s["details"]["duplicate_charge"] = s["dups"]
        creep = detectors.price_creep(s["g"], f["cadence_fit"]) if s["recurring"] else None
        if creep:
            s["flags"].append("price_creep")
            s["details"]["price_creep"] = creep
        s["monthly_equiv"] = round(last * 30.44 / _period_days(f["cadence"], f["median_interval"]), 2) \
            if s["recurring"] else 0.0
        s["n_charges"] = len(s["g_all"])

    overlap = detectors.overlaps([{"merchant": m, "recurring": s["recurring"], "status": s["status"],
                                   "category": s["category"]} for m, s in ctx.series.items()])
    for merchant, detail in overlap.items():
        ctx.series[merchant]["flags"].append("overlap")
        ctx.series[merchant]["details"]["overlap"] = detail

    for s in ctx.series.values():
        because = detectors.zombie_reasons(s)
        if because:
            s["flags"].append("zombie_suspect")
            s["details"]["zombie_suspect"] = {"because": because}
        f = s["feats"]
        rows.append({
            "merchant": s["merchant"], "category": s["category"], "kind": s["kind"],
            "features_json": json.dumps(_clean(f)), "n_charges": s["n_charges"],
            "first_date": str(s["g_all"]["tx_date"].iloc[0]), "last_date": str(s["g"]["tx_date"].iloc[-1]),
            "cadence": f["cadence"], "cadence_days": _clean(f["median_interval"]),
            "last_amount": round(float(s["g"]["amount"].iloc[-1]), 2), "monthly_equiv": s["monthly_equiv"],
            "recurring_prob": round(s["prob"], 4), "scorer": ctx.scorer,
            "similar_json": json.dumps(_clean(s["similar"])),
            "next_due_date": s["next_due"].date().isoformat() if s.get("next_due") is not None else None,
            "fc_q10": s.get("fc", (None,) * 3)[0], "fc_q50": s.get("fc", (None,) * 3)[1],
            "fc_q90": s.get("fc", (None,) * 3)[2], "hike_prob": s.get("hike_prob"),
            "flags_json": json.dumps(s["flags"]), "flag_details_json": json.dumps(_clean(s["details"])),
            "priority": detectors.priority(s["monthly_equiv"], s["flags"]) if s["recurring"] else 0.0,
            "cancellable": int(s["kind"] == "subscription"), "status": s["status"],
            "dom_median": s["dom_median"], "amount_varies": int(s["amount_varies"]),
            "monthly_hist_json": json.dumps(s["monthly_hist"]),
            "quantiles_json": json.dumps(s["quantiles"]) if s.get("quantiles") else None,
            "_recurring": s["recurring"],
        })

    for s in ctx.singles.values():  # possible annual plans (spec §7.7)
        g = s["g_all"]
        amount, when = round(float(g["amount"].iloc[-1]), 2), pd.Timestamp(g["tx_date"].iloc[-1])
        if s["status"] in EXCLUDED or not detectors.possible_annual(amount, s["category"], s["sub_like"]):
            continue
        due = when + pd.Timedelta(days=365)
        while due <= ctx.report_date:
            due += pd.Timedelta(days=365)
        monthly_equiv = round(amount * 30.44 / 365.25, 2)
        rows.append({
            "merchant": s["merchant"], "category": s["category"], "kind": s["kind"], "features_json": None,
            "n_charges": 1, "first_date": when.date().isoformat(), "last_date": when.date().isoformat(),
            "cadence": "single", "cadence_days": None, "last_amount": amount, "monthly_equiv": monthly_equiv,
            "recurring_prob": None, "scorer": ctx.scorer, "similar_json": None,
            "next_due_date": due.date().isoformat(), "fc_q10": None, "fc_q50": None, "fc_q90": None,
            "hike_prob": None, "flags_json": json.dumps(["possible_annual"]),
            "flag_details_json": json.dumps({"possible_annual": {"next_due": due.date().isoformat()}}),
            "priority": detectors.priority(monthly_equiv, ["possible_annual"]), "cancellable": 1,
            "status": s["status"], "dom_median": float(when.day), "amount_varies": 0,
            "monthly_hist_json": json.dumps({when.strftime("%Y-%m"): amount}), "quantiles_json": None,
            "_recurring": False,
        })
    ctx.rows = rows
    _meta(ctx)


def _meta(ctx: Context) -> None:
    recurring = [r for r in ctx.rows if r["_recurring"]]
    flagged = lambda r, f: f in json.loads(r["flags_json"])  # noqa: E731
    zombies = [r for r in ctx.rows if flagged(r, "zombie_suspect")]
    dispute = round(sum(p["amount"] for s in ctx.series.values() for p in s["dups"]), 2)

    months = pd.period_range(end=ctx.report_date.to_period("M"), periods=12, freq="M")
    contributors = recurring + [r for r in ctx.rows if r["cadence"] == "single"]
    events: dict[str, list[str]] = {}
    extras: dict[str, list[str]] = {}
    for s in ctx.series.values():
        for p in s["dups"]:
            events.setdefault(p["second"][:7], []).append(f"{s['merchant']} charged twice")
        creep = s["details"].get("price_creep")
        if creep:
            extras.setdefault(creep["since"][:7], []).append(f"{s['merchant']}’s price rise")
    for r in ctx.rows:
        if r["cadence"] == "single":
            events.setdefault(r["first_date"][:7], []).append(
                f"{r['merchant']}’s {money(r['last_amount'], ctx.currency)} annual charge")
    month_end = ctx.report_date + pd.offsets.MonthEnd(0)
    monthly = []
    for p in months:
        key = str(p)
        hist = [(r, json.loads(r["monthly_hist_json"]).get(key, 0.0)) for r in contributors]
        highlights = (extras.get(key, []) + events[key]) if key in events else []
        monthly.append({"month": key,
                        "subscriptions": round(sum(v for r, v in hist if r["kind"] == "subscription"), 2),
                        "all": round(sum(v for _, v in hist), 2),
                        "partial": p == months[-1] and ctx.report_date.normalize() != month_end.normalize(),
                        "highlights": highlights})

    fc = ctx.meta.get("forecast", {"all": {"q10": 0, "q50": 0, "q90": 0},
                                   "subscriptions": {"q10": 0, "q50": 0, "q90": 0}})
    ctx.meta.update({
        "generated_at": db.now_iso(), "report_date": ctx.report_date.date().isoformat(), "currency": ctx.currency,
        "scorer": ctx.scorer,
        "monthly_recurring": round(sum(r["monthly_equiv"] for r in recurring), 2),
        "monthly_subscriptions": round(sum(r["monthly_equiv"] for r in recurring if r["kind"] == "subscription"), 2),
        "monthly_bills": round(sum(r["monthly_equiv"] for r in recurring if r["kind"] == "bill"), 2),
        "fc30_q10": fc["all"]["q10"], "fc30_q50": fc["all"]["q50"], "fc30_q90": fc["all"]["q90"],
        "fc30_sub_q10": fc["subscriptions"]["q10"], "fc30_sub_q50": fc["subscriptions"]["q50"],
        "fc30_sub_q90": fc["subscriptions"]["q90"],
        "potential_savings": round(sum(r["monthly_equiv"] for r in zombies), 2),
        "dispute_total": dispute, "monthly_json": json.dumps(monthly),
    })


def summary_facts(ctx: Context) -> dict:
    facts = {"currency": ctx.currency, "monthly_recurring": ctx.meta["monthly_recurring"],
             "monthly_subscriptions": ctx.meta["monthly_subscriptions"]}
    creeps = [(s, s["details"]["price_creep"]) for s in ctx.series.values() if "price_creep" in s["details"]]
    if creeps:
        s, c = max(creeps, key=lambda sc: sc[1]["to"] - sc[1]["from"])
        same_month = any(p["second"][:7] == c["since"][:7] for p in s["dups"])
        facts["creep"] = {**c, "merchant": s["merchant"], "duplicate_same_month": same_month}
    dups = [(s, p) for s in ctx.series.values() for p in s["dups"]]
    if dups:
        s, p = dups[0]
        facts["dispute"] = {"merchant": s["merchant"], "amount": p["amount"], "first": p["first"]}
    groups: dict[str, list[str]] = {}
    for s in ctx.series.values():
        if "overlap" in s["details"]:
            groups[s["details"]["overlap"]["category"]] = s["details"]["overlap"]["merchants"]
    if groups:
        category, merchants = next(iter(sorted(groups.items())))
        facts["overlap"] = {"category": category, "merchants": merchants}
    return facts


def persist(ctx: Context) -> None:
    db.save_series([{k: v for k, v in r.items() if not k.startswith("_")} for r in ctx.rows])
    db.mark_duplicates(ctx.duplicate_ids)
    db.save_report_meta({**ctx.meta, "executive_summary": ctx.summary, "summary_source": ctx.summary_source})


# ── reading the report ──────────────────────────────────────────────────────

def series_out(s: dict) -> dict:
    flags = s["flags_json"] or []
    return {
        "id": s["id"], "merchant": s["merchant"], "category": s["category"], "kind": s["kind"],
        "n_charges": s["n_charges"], "first_date": s["first_date"], "last_date": s["last_date"],
        "cadence": s["cadence"], "cadence_days": s["cadence_days"], "dom_median": s["dom_median"],
        "last_amount": s["last_amount"], "monthly_equiv": s["monthly_equiv"],
        "amount_varies": bool(s["amount_varies"]), "recurring_prob": s["recurring_prob"], "scorer": s["scorer"],
        "next_due_date": s["next_due_date"], "fc_q10": s["fc_q10"], "fc_q50": s["fc_q50"], "fc_q90": s["fc_q90"],
        "hike_prob": s["hike_prob"], "flags": flags, "flag_details": s["flag_details_json"] or {},
        "priority": s["priority"], "cancellable": bool(s["cancellable"]), "status": s["status"],
    }


def _is_recurring(s: dict) -> bool:
    prob = s["recurring_prob"]
    return (prob is not None and prob >= RECURRING and s["status"] not in EXCLUDED) or s["status"] == "keep"


def load_report() -> dict | None:
    meta = db.report_meta()
    if meta is None:
        return None
    series = db.list_series()
    # Recurring first by priority, then flagged one-offs, then the rest by score (D-Main's order).
    series.sort(key=lambda s: (0 if _is_recurring(s) else 1 if s["flags_json"] else 2, -(s["priority"] or 0),
                               -(s["recurring_prob"] or 0), s["merchant"]))
    flag_counts = {f: sum(f in (s["flags_json"] or []) for s in series) for f in FLAG_IDS}
    imports = [{k: imp[k] for k in ("id", "file_name", "row_count", "skipped_rows", "period_start", "period_end",
                                    "imported_at", "verified_count")} for imp in db.list_imports()]
    q = lambda p: {"q10": meta[f"{p}q10"], "q50": meta[f"{p}q50"], "q90": meta[f"{p}q90"]}  # noqa: E731
    return {
        "meta": {
            "generated_at": meta["generated_at"], "report_date": meta["report_date"], "currency": meta["currency"],
            "scorer": meta["scorer"], "monthly_recurring": meta["monthly_recurring"],
            "monthly_subscriptions": meta["monthly_subscriptions"], "monthly_bills": meta["monthly_bills"],
            "fc30": q("fc30_"), "potential_savings": meta["potential_savings"],
            "zombie_count": flag_counts["zombie_suspect"], "dispute_total": meta["dispute_total"],
            "flag_counts": flag_counts, "flagged_merchants": sum(bool(s["flags_json"]) for s in series),
            "executive_summary": meta["executive_summary"], "summary_source": meta["summary_source"],
            "imports": imports,
        },
        "series": [series_out(s) for s in series],
        "monthly": meta["monthly_json"],
        "forecast_next": {"subscriptions": q("fc30_sub_"), "all": q("fc30_")},
    }


def live_forecast(days: int = FORECAST_DAYS) -> dict | None:
    """Ask Sloth's forecast_spend (spec §7.9): run the regressor *now* on every recurring series.

    Same maths as the pipeline's forecast stage, over a window of `days` from the report date. Each series'
    q10/q50/q90 is summed over the charges due inside the window. None before the first audit.
    """
    meta = db.report_meta()
    if meta is None:
        return None
    report_date = pd.Timestamp(meta["report_date"])
    window_end = report_date + pd.Timedelta(days=days)
    history, queries, plans = [], [], []
    for s in db.list_series():
        if not _is_recurring(s) or s["cadence"] == "single":
            continue
        txs = [t for t in db.merchant_transactions(s["merchant"]) if not t["is_duplicate"]]
        if len(txs) < 2:
            continue
        g = pd.DataFrame(txs)[["tx_date", "amount"]]
        step = _step(s["cadence"], s["cadence_days"])
        due = pd.Timestamp(g["tx_date"].iloc[-1]) + step
        while due <= report_date:
            due += step
        history.append(regression_rows(g, s["cadence"], s["category"]))
        queries.append(next_step_row(g, s["cadence"], s["category"], due.month))
        plans.append((s, float(g["amount"].iloc[-1]), due, step))
    ctx_rows = pd.concat(history, ignore_index=True) if history else pd.DataFrame()
    ratios = tabular.ratio_quantiles(ctx_rows, pd.DataFrame(queries)) if queries else np.ones((0, 19))
    out = []
    for (s, last, due, step), row in zip(plans, ratios, strict=True):
        charges, when = 0, due
        while when <= window_end:
            charges += 1
            when += step
        out.append({"merchant": s["merchant"], "kind": s["kind"], "next_due": due.date().isoformat(),
                    "charges": charges, "q10": round(charges * last * row[Q10], 2),
                    "q50": round(charges * last * row[Q50], 2), "q90": round(charges * last * row[Q90], 2)})
    return {"report_date": report_date.date().isoformat(), "window_end": window_end.date().isoformat(),
            "currency": meta["currency"], "scorer": tabular.scorer, "series": out}


# ── running it ──────────────────────────────────────────────────────────────

def _ev(name: str, **data) -> dict:
    return {"event": name, "data": json.dumps(_clean(data))}


async def gemma_model() -> str | None:
    status = await ollama_setup.status(settings.ollama_host, settings.preferred_model)
    return status["model"] if status["status"] == "ready" else None


def busy() -> bool:
    return runtime.pipeline_lock.locked()


async def start_pipeline(import_id: int, opts: dict) -> asyncio.Queue:
    """Start an audit of a pending import; returns the queue its SSE events arrive on (None = end)."""
    if busy():
        raise PipelineBusy
    queue: asyncio.Queue = asyncio.Queue()

    async def job() -> None:
        stage = "parse"
        async with runtime.pipeline_lock:
            try:
                await queue.put(_ev("stage", stage="parse", done=0, total=1))
                default_currency = user_settings.load().currency
                res = await asyncio.to_thread(ingest.commit, import_id, opts, default_currency)
                note = f"{res.rows} rows"
                if res.skipped_dates:
                    note += f" · {res.skipped_dates} skipped (unreadable dates)"
                if res.skipped_overlap:
                    note += f" · {res.skipped_overlap} already imported"
                await queue.put(_ev("stage", stage="parse", done=1, total=1, note=note))

                stage = "normalize"
                model = await gemma_model()
                stats = [normalize.KeyStat(r["desc_key"], r["n"], r["total"], r["largest"])
                         for r in await asyncio.to_thread(db.debit_key_stats)]
                norm = normalize.Normalizer(stats, model, host=settings.ollama_host)
                async for done, total in norm.run():
                    await queue.put(_ev("stage", stage="normalize", done=done, total=total,
                                        source="gemma" if model else "rule"))
                await asyncio.to_thread(db.apply_merchant_map)

                ctx = await asyncio.to_thread(Context.load)
                for stage, fn in (("detect", detect), ("features", features), ("score", score),
                                  ("forecast", forecast), ("flags", flags)):
                    await queue.put(_ev("stage", stage=stage, done=0, total=1))
                    await asyncio.to_thread(fn, ctx)
                    await queue.put(_ev("stage", stage=stage, done=1, total=1,
                                        source=ctx.scorer if stage in ("score", "forecast") else None))

                stage = "summary"
                await queue.put(_ev("stage", stage="summary", done=0, total=1))
                ctx.summary, ctx.summary_source = await llm_summary.write(summary_facts(ctx), model,
                                                                          settings.ollama_host)
                await queue.put(_ev("stage", stage="summary", done=1, total=1, source=ctx.summary_source))

                stage = "done"
                await queue.put(_ev("stage", stage="done", done=0, total=1))
                await asyncio.to_thread(persist, ctx)
                verified = await reminders.verify_after_import()
                await asyncio.to_thread(db.finish_import, import_id, verified_count=verified)
                await queue.put(_ev("stage", stage="done", done=1, total=1))
                if norm.deferred and model:
                    runtime.normalize_task = asyncio.create_task(
                        normalize.finish_deferred(norm.deferred, model, settings.ollama_host))
                await queue.put(_ev("done", report=await asyncio.to_thread(load_report)))
            except ingest.ImportProblem as exc:
                await queue.put(_ev("error", stage=stage, message=exc.message, status=exc.status))
            except Exception as exc:  # noqa: BLE001 — surface it in the UI, keep the engine up
                log.exception("audit failed at %s", stage)
                await queue.put(_ev("error", stage=stage,
                                    message=f"Something went wrong while auditing ({stage}): {exc}"))
            finally:
                await queue.put(None)

    runtime.pipeline_task = asyncio.create_task(job())
    return queue


async def rescore() -> dict:
    """Re-run detect…flags with the current scorer and labels — no LLM, so the summary becomes the template."""
    async with runtime.pipeline_lock:
        def run() -> dict:
            ctx = Context.load()
            for fn in (detect, features, score, forecast, flags):
                fn(ctx)
            ctx.summary, ctx.summary_source = llm_summary.template(summary_facts(ctx)), "template"
            persist(ctx)
            return load_report()

        return await asyncio.to_thread(run)
