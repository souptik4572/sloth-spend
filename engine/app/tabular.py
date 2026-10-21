"""TabPFN models (spec §7.6, IMPL §2 #21). Stub until M4: it reports status only.

Version ladder (M4): no Prior Labs key → TabPFN v2 (open weights, downloaded once, no account);
a stored key (TABPFN_TOKEN) → TabPFN-3.5, falling back to v2 if that upgrade fails.
"""


class Tabular:
    def __init__(self) -> None:
        # cold | downloading | warming | ready | unavailable | error
        self.status = "cold"
        # tabpfn-v2 | tabpfn-3.5 | tabpfn-3.5-fast, once a model is loaded
        self.model_name: str | None = None
        self.error: str | None = None
        # The optional TabPFN-3.5 upgrade: none | downloading | active | failed
        self.upgrade_state = "none"
        self.upgrade_error: str | None = None

    def warm_up(self) -> None:
        # M4 downloads/loads TabPFN v2 (or 3.5 with a key) here (IMPL M4.3).
        self.status = "unavailable"
        self.error = "TabPFN loading arrives in M4. Until then, a simple rule scores charges."

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def health(self) -> dict:
        return {
            "status": self.status,
            "model": self.model_name,
            "error": self.error,
            "upgrade": {"state": self.upgrade_state, "error": self.upgrade_error},
        }


tabular = Tabular()
