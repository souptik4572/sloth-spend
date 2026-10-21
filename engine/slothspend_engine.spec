# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir build of the engine (spec §12.1). Build from engine/:
#   pyinstaller slothspend_engine.spec --noconfirm --clean
# Output: dist/slothspend-engine/{slothspend-engine[.exe], _internal/}
import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []
# skrub (and mlx on Apple Silicon) are tabpfn dependencies with data files and no PyInstaller hook.
for pkg in ["tabpfn", "sentry_sdk", "ollama", "sse_starlette", "skrub", "mlx"]:
    if importlib.util.find_spec(pkg) is None:
        continue  # mlx only exists on macOS arm64
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# Bundled CSVs (priors, sample and follow-up statements) arrive in M3; ship whatever exists.
for csv in sorted(Path("app/data").glob("*.csv")):
    datas.append((str(csv), "app/data"))

hiddenimports += collect_submodules("uvicorn") + collect_submodules("app")
# Imported lazily (inside functions) by the app or by tabpfn; listed so the bundle always has them.
hiddenimports += ["torch", "huggingface_hub", "python_multipart"]

a = Analysis(
    ["run_engine.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "IPython", "pytest"],  # not matplotlib: tabpfn imports it at module level
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="slothspend-engine",
    console=True,  # windowless mode leaves sys.stdout/stderr = None and breaks uvicorn; main spawns with windowsHide
    upx=False,  # UPX breaks torch DLLs and triggers antivirus false positives
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="slothspend-engine")
