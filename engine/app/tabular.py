"""TabPFN-3.5 models (spec §7.6). M1 stub: reports status only; the real models arrive in M4."""


class Tabular:
    def __init__(self) -> None:
        self.status = "cold"  # cold | warming | ready | missing_weights | error
        self.model_name: str | None = None
        self.error: str | None = None

    def warm_up(self) -> None:
        # M4 checks for cached weights or TABPFN_TOKEN and loads the models (IMPL M4.3).
        self.status = "missing_weights"

    @property
    def ready(self) -> bool:
        return self.status == "ready"


tabular = Tabular()
