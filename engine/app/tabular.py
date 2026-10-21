"""TabPFN models (spec §7.6, IMPL M4.3 and §2 #21).

Version ladder: no Prior Labs key → TabPFN v2 (open weights, ~70 MB from Hugging Face once, then offline).
A stored key (TABPFN_TOKEN) → TabPFN-3.5 (3.5-fast without a GPU); if that upgrade fails, fall back to v2
and say why. With no model at all (first run offline), a heuristic scores charges, labelled as such.

Model A (classifier): P(recurring) from series features; context = simulated priors + the user's corrections ×3.
Model B (regressor): next/last price ratio as 19 quantiles; context = sampled hike priors + the user's own steps.
"""

import logging
import os
import threading
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURES, REG_FEATURES
from .paths import DATA

log = logging.getLogger(__name__)

QUANTILES = [round(q, 2) for q in np.arange(0.05, 0.951, 0.05)]
Q10, Q50, Q90 = QUANTILES.index(0.1), QUANTILES.index(0.5), QUANTILES.index(0.9)
# TabPFN refuses > 1000 training rows on CPU by default (found in the M4 spike); stay under it everywhere.
MAX_CONTEXT = 950
HIKE_SAMPLE = 800
LABEL_REPEATS = 3
NUMERIC = [f for f in FEATURES if f not in ("cadence", "category")]
# "Looks like" compares billing *pattern* and price level, not how long the history is.
PATTERN = ["median_interval", "interval_cv", "cadence_fit", "dom_std", "amount_cv", "modal_amount_share",
           "log_amount", "subscription_like"]

MODEL_NAMES = {"v2": "tabpfn-v2", "v3.5": "tabpfn-3.5", "v3.5-fast": "tabpfn-3.5-fast"}
WEIGHT_PATTERNS = {"v2": ["tabpfn-v2-classifier*.ckpt", "tabpfn-v2-regressor*.ckpt"],
                   "v3.5": ["tabpfn-v3.5-2*.safetensors"], "v3.5-fast": ["tabpfn-v3.5-fast*.safetensors"]}


def _device() -> str:
    override = os.environ.get("SLOTH_TABPFN_DEVICE")
    if override:
        return override
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _friendly(exc: Exception, version: str) -> str:
    """One calm sentence for the Boot screen instead of a stack trace."""
    text = str(exc)
    if version != "v2":
        if "reach the license server" in text:
            return "couldn’t reach Prior Labs to check the key — are you offline?"
        if "browser login" in text or "not accepted" in text or "license" in text.lower():
            return ("the key wasn’t accepted, or the TabPFN-3.5 license isn’t accepted yet — "
                    "accept it at ux.priorlabs.ai, then try again")
        return text.splitlines()[0][:160] if text else type(exc).__name__
    if any(w in text.lower() for w in ("connection", "resolve", "offline", "timed out", "failed to download",
                                       "max retries", "network")):
        return "Couldn’t download TabPFN v2 (about 70 MB, one time). Connect to the internet, then retry."
    return f"TabPFN v2 failed to load: {text.splitlines()[0][:160] if text else type(exc).__name__}"


def sandbox_license_cache(private_dir: Path) -> None:
    """Keep tabpfn's license step inside SlothSpend's own folder (IMPL M4.3).

    Out of the box, tabpfn's browser_auth module reads ~/.cache/tabpfn/auth_token and ~/.tabpfn/token,
    *deletes* the first when a key fails verification, and saves a verified key there in plain text.
    SlothSpend keeps the key encrypted (Electron safeStorage) and passes it in as TABPFN_TOKEN on every
    launch, so: point those paths at a private folder, and never write the key to disk.
    """
    from tabpfn import browser_auth

    private_dir.mkdir(parents=True, exist_ok=True)
    browser_auth._CACHE_DIR = private_dir
    browser_auth._TOKEN_FILE = private_dir / "auth_token"
    browser_auth._CLIENT_TOKEN_FILE = private_dir / "client_token"
    browser_auth.save_token = lambda token: None


class Tabular:
    def __init__(self) -> None:
        self.status = "cold"  # cold | downloading | warming | ready | unavailable | error
        self.model_name: str | None = None  # tabpfn-v2 | tabpfn-3.5 | tabpfn-3.5-fast
        self.error: str | None = None
        self.upgrade_state = "none"  # none | downloading | active | failed
        self.upgrade_error: str | None = None
        self._lock = threading.Lock()
        self._clf = None
        self._reg = None
        self.priors = pd.read_csv(DATA / "priors_recurring.csv")
        hikes = pd.read_csv(DATA / "priors_hikes.csv")
        self.hikes = hikes.sample(min(HIKE_SAMPLE, len(hikes)), random_state=0).reset_index(drop=True)
        self._mean = self.priors[NUMERIC].mean()
        self._std = self.priors[NUMERIC].std().replace(0, 1.0)

    # ── loading ─────────────────────────────────────────────────────────────

    def ladder(self) -> list[str]:
        """Versions to try, best first (IMPL §2 #21)."""
        if os.environ.get("TABPFN_TOKEN"):
            return ["v3.5" if _device() != "cpu" else "v3.5-fast", "v2"]
        return ["v2"]

    @staticmethod
    def weights_present(version: str) -> bool:
        from tabpfn.model_loading import get_cache_dir

        cache = get_cache_dir()
        return all(any(cache.glob(p)) for p in WEIGHT_PATTERNS[version])

    def warm_up(self) -> None:
        """Background thread at engine start: load the best available version (never blocks /health)."""
        if os.environ.get("SLOTH_DISABLE_TABPFN"):  # tests and CI: heuristic only, no downloads
            self.status, self.error = "unavailable", "TabPFN is turned off (SLOTH_DISABLE_TABPFN)."
            return
        for version in self.ladder():
            upgrade = version != "v2"
            try:
                self._load(version, upgrade=upgrade)
                self.model_name = MODEL_NAMES[version]
                self.status, self.error = "ready", None
                if upgrade:
                    self.upgrade_state, self.upgrade_error = "active", None
                log.info("TabPFN ready: %s", self.model_name)
                return
            except Exception as exc:  # noqa: BLE001 — every failure becomes a status, never a crash
                log.warning("TabPFN %s failed to load: %s", version, exc)
                if upgrade:
                    self.upgrade_state, self.upgrade_error = "failed", _friendly(exc, version)
                    continue
                self.status = "unavailable" if "download" in _friendly(exc, version) else "error"
                self.error = _friendly(exc, version)

    def _load(self, version: str, *, upgrade: bool) -> None:
        from tabpfn import TabPFNClassifier, TabPFNRegressor
        from tabpfn.constants import ModelVersion

        from .config import settings

        sandbox_license_cache(settings.data_dir / "tabpfn-license")
        downloading = not self.weights_present(version)
        self.status = "downloading" if downloading else "warming"
        if upgrade:
            self.upgrade_state = "downloading" if downloading else "none"
        device = _device()
        mv = ModelVersion(version)
        clf = TabPFNClassifier.create_default_for_version(mv, device=device)
        reg = TabPFNRegressor.create_default_for_version(mv, device=device)
        sample = self.priors.sample(40, random_state=0)
        hikes = self.hikes.head(40)
        with self._lock:  # touching both downloads any missing weights, then proves they run
            clf.fit(sample[FEATURES], sample["label"])
            self.status = "warming"
            clf.predict_proba(sample[FEATURES].head(2))
            reg.fit(hikes[REG_FEATURES], hikes["ratio"])
            reg.predict(hikes[REG_FEATURES].head(2), output_type="quantiles", quantiles=QUANTILES)
            self._clf, self._reg = clf, reg

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    @property
    def scorer(self) -> str:
        return self.model_name if self.ready and self.model_name else "heuristic"

    def health(self) -> dict:
        return {"status": self.status, "model": self.model_name if self.ready else None, "error": self.error,
                "upgrade": {"state": self.upgrade_state, "error": self.upgrade_error}}

    # ── inference ───────────────────────────────────────────────────────────

    def recurring_prob(self, X: pd.DataFrame, labels: pd.DataFrame | None = None) -> np.ndarray:
        if not self.ready or len(X) == 0:
            return heuristic_prob(X)
        extra = [labels[FEATURES + ["label"]]] * LABEL_REPEATS if labels is not None and len(labels) else []
        n_extra = sum(len(e) for e in extra)
        priors = self.priors
        if len(priors) + n_extra > MAX_CONTEXT:
            priors = priors.sample(max(MAX_CONTEXT - n_extra, 100), random_state=0)
        ctx = pd.concat([priors[FEATURES + ["label"]], *extra], ignore_index=True)
        with self._lock:
            self._clf.fit(ctx[FEATURES], ctx["label"])
            proba = self._clf.predict_proba(X[FEATURES])
        return proba[:, list(self._clf.classes_).index(1)]

    def ratio_quantiles(self, ctx: pd.DataFrame, query: pd.DataFrame) -> np.ndarray:
        """(n_query, 19) predicted next/last price ratios; all ones without a model."""
        if not self.ready or len(query) == 0:
            return np.ones((len(query), len(QUANTILES)))
        ctx = ctx.tail(MAX_CONTEXT // 2)  # the user's most recent steps
        hikes = self.hikes.head(MAX_CONTEXT - len(ctx))
        full = pd.concat([hikes, ctx[REG_FEATURES + ["ratio"]]], ignore_index=True)
        with self._lock:
            self._reg.fit(full[REG_FEATURES], full["ratio"])
            qs = self._reg.predict(query[REG_FEATURES], output_type="quantiles", quantiles=QUANTILES)
        return np.vstack(qs).T

    def nearest_archetypes(self, X: pd.DataFrame, k: int = 5) -> list[dict]:
        """Explanation without SHAP (spec §7.6): the majority archetype among the k nearest priors."""
        mean, std = self._mean[PATTERN], self._std[PATTERN]
        Q = ((X[PATTERN].astype(float) - mean) / std).fillna(0).to_numpy(float)
        out = []
        for row, cadence in zip(Q, X["cadence"], strict=True):
            # Compare with priors of the same rhythm when there are enough of them.
            pool = self.priors[self.priors["cadence"] == cadence]
            if len(pool) < k:
                pool = self.priors
            P = ((pool[PATTERN] - mean) / std).fillna(0).to_numpy(float)
            nearest = np.argsort(((P - row) ** 2).sum(axis=1))[:k]
            counts = pool["archetype"].iloc[nearest].value_counts()
            out.append({"archetype": counts.index[0], "count": int(counts.iloc[0]), "k": k,
                        "runner_up": counts.index[1] if len(counts) > 1 else None})
        return out


def heuristic_prob(X: pd.DataFrame) -> np.ndarray:
    """Fallback when no TabPFN model is available. Clearly labelled 'heuristic' in the UI."""
    score = (0.55 * X["cadence_fit"].fillna(0)
             + 0.25 * X["modal_amount_share"].fillna(0)
             + 0.10 * (X["n_charges"] >= 4)
             + 0.10 * X["subscription_like"].fillna(0))
    return score.clip(0, 1).to_numpy()


tabular = Tabular()


def cache_dir() -> Path:
    from tabpfn.model_loading import get_cache_dir

    return get_cache_dir()
