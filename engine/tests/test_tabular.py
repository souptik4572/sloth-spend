"""TabPFN version ladder (IMPL §2 #21), friendly errors, heuristic and nearest-archetype explanations."""

import pandas as pd
import pytest

from app import tabular as tab
from app.tabular import Tabular, heuristic_prob


@pytest.fixture()
def t() -> Tabular:
    return Tabular()


def test_ladder_defaults_to_v2_and_upgrades_with_a_key(t, monkeypatch):
    monkeypatch.delenv("TABPFN_TOKEN", raising=False)
    assert t.ladder() == ["v2"]
    monkeypatch.setenv("TABPFN_TOKEN", "a-key")
    monkeypatch.setattr(tab, "_device", lambda: "mps")
    assert t.ladder() == ["v3.5", "v2"]
    monkeypatch.setattr(tab, "_device", lambda: "cpu")
    assert t.ladder() == ["v3.5-fast", "v2"]


def test_failed_upgrade_falls_back_to_v2(t, monkeypatch):
    monkeypatch.delenv("SLOTH_DISABLE_TABPFN", raising=False)
    monkeypatch.setenv("TABPFN_TOKEN", "bad-key")
    monkeypatch.setattr(tab, "_device", lambda: "mps")
    loaded = []

    def fake_load(version, *, upgrade):
        if version != "v2":
            raise RuntimeError("TabPFN requires a one-time license acceptance... browser login is disabled")
        loaded.append(version)

    monkeypatch.setattr(t, "_load", fake_load)
    t.warm_up()
    assert loaded == ["v2"] and t.status == "ready" and t.model_name == "tabpfn-v2"
    assert t.upgrade_state == "failed" and "license" in t.upgrade_error
    assert t.health()["model"] == "tabpfn-v2" and t.scorer == "tabpfn-v2"


def test_offline_first_run_is_unavailable_not_broken(t, monkeypatch):
    monkeypatch.delenv("SLOTH_DISABLE_TABPFN", raising=False)
    monkeypatch.delenv("TABPFN_TOKEN", raising=False)

    def offline(version, *, upgrade):
        raise OSError("Failed to download: Max retries exceeded (connection refused)")

    monkeypatch.setattr(t, "_load", offline)
    t.warm_up()
    assert t.status == "unavailable" and "Connect to the internet" in t.error
    assert t.scorer == "heuristic" and t.health()["model"] is None


def test_disabled_in_tests(t):
    t.warm_up()
    assert t.status == "unavailable" and not t.ready


def test_inference_without_a_model_falls_back(t):
    X = pd.DataFrame([{"n_charges": 12, "span_days": 330, "median_interval": 30, "interval_cv": 0.02,
                       "cadence": "monthly", "cadence_fit": 1.0, "dom_std": 0.5, "amount_cv": 0.0,
                       "modal_amount_share": 1.0, "log_amount": 2.8, "days_since_last": 3,
                       "category": "Streaming", "subscription_like": 1}])
    assert t.recurring_prob(X)[0] == pytest.approx(1.0)
    assert t.ratio_quantiles(pd.DataFrame(), pd.DataFrame([{}])).tolist() == [[1.0] * 19]
    sim = t.nearest_archetypes(X)[0]
    assert sim["archetype"] == "monthly fixed-price subscription" and sim["k"] == 5


def test_heuristic_prob_bounds():
    X = pd.DataFrame({"cadence_fit": [1.0, 0.0], "modal_amount_share": [1.0, 0.0], "n_charges": [12, 2],
                      "subscription_like": [1, 0]})
    assert heuristic_prob(X).tolist() == [1.0, 0.0]


def test_context_stays_under_the_cpu_limit(t):
    """TabPFN refuses > 1000 training rows on CPU by default (M4 spike); priors + labels must fit."""
    assert len(t.priors) <= tab.MAX_CONTEXT and len(t.hikes) <= tab.MAX_CONTEXT


def test_license_cache_is_sandboxed(tmp_path):
    """A bad key must never delete — and a good key never write — files in the user's home (IMPL M4.3)."""
    from pathlib import Path

    from tabpfn import browser_auth

    original = (browser_auth._CACHE_DIR, browser_auth._TOKEN_FILE, browser_auth._CLIENT_TOKEN_FILE,
                browser_auth.save_token)
    try:
        tab.sandbox_license_cache(tmp_path / "lic")
        home = Path.home()
        for path in (browser_auth._CACHE_DIR, browser_auth._TOKEN_FILE, browser_auth._CLIENT_TOKEN_FILE):
            assert home not in path.parents and str(path).startswith(str(tmp_path))
        browser_auth.save_token("secret-key")
        assert not any((tmp_path / "lic").iterdir())  # the key is never written to disk
        browser_auth.delete_cached_token()  # harmless now: only ever touches the private folder
    finally:
        (browser_auth._CACHE_DIR, browser_auth._TOKEN_FILE, browser_auth._CLIENT_TOKEN_FILE,
         browser_auth.save_token) = original
