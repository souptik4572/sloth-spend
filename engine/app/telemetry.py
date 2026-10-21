"""Opt-in Sentry tracing (spec §7.11). Stretch work (M10): until then init() never sends anything."""

import os

SENTRY_DSN = os.environ.get("SLOTH_SENTRY_DSN", "")


def init() -> None:
    if os.environ.get("SLOTH_TELEMETRY") != "1" or not SENTRY_DSN:
        return  # spans become no-ops
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=1.0,
        send_default_pii=False,  # never send prompts, responses or CSV content
        release=os.environ.get("SLOTH_VERSION", "dev"),
    )
