"""SQLite storage. M1 only prepares the data folder; the schema and helpers arrive in M3 (IMPL M3.3)."""

from .config import settings

DB_PATH = settings.data_dir / "slothspend.db"


def init() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
