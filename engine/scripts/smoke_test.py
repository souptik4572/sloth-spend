"""Smoke-test the PyInstaller engine binary (spec §12.3). Exit code 0 = pass.

Checks, in order:
  1. `--self-check`: torch, tabpfn and friends import inside the frozen bundle.
  2. Boot: /health answers {"engine": "ok"} within 90 s; a request without the token gets 401.
  3. Graceful exit: POST /shutdown makes the process exit.
  4. Watchdog: closing stdin (what happens when Electron dies) makes the process exit.

usage: python engine/scripts/smoke_test.py [path/to/slothspend-engine]
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
EXE = "slothspend-engine.exe" if os.name == "nt" else "slothspend-engine"
TOKEN = "smoke-test-token"
BOOT_TIMEOUT = 90
EXIT_TIMEOUT = 15


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def request(port: int, path: str, *, method: str = "GET", token: str | None = TOKEN) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    if token:
        req.add_header("X-Sloth-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def start(binary: Path, data_dir: str, port: int) -> subprocess.Popen:
    env = {
        **os.environ,
        "SLOTH_PORT": str(port),
        "SLOTH_TOKEN": TOKEN,
        "SLOTH_DATA_DIR": data_dir,
        "TABPFN_MODEL_CACHE_DIR": str(Path(data_dir) / "tabpfn-weights"),
        "PYTHONUNBUFFERED": "1",
    }
    env.pop("TABPFN_TOKEN", None)
    return subprocess.Popen([str(binary)], env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def wait_healthy(proc: subprocess.Popen, port: int) -> dict:
    deadline = time.monotonic() + BOOT_TIMEOUT
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"engine exited during boot with code {proc.returncode}")
        try:
            status, body = request(port, "/health")
            if status == 200 and body.get("engine") == "ok":
                return body
        except OSError:
            pass
        time.sleep(0.5)
    raise SystemExit(f"engine not healthy after {BOOT_TIMEOUT}s")


def wait_exit(proc: subprocess.Popen, what: str) -> None:
    try:
        proc.wait(timeout=EXIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise SystemExit(f"engine did not exit after {what} within {EXIT_TIMEOUT}s")


def log_tail(proc: subprocess.Popen) -> str:
    out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
    return "\n".join(out.strip().splitlines()[-15:])


def main() -> None:
    binary = Path(sys.argv[1]) if len(sys.argv) > 1 else ENGINE_DIR / "dist" / "slothspend-engine" / EXE
    if not binary.exists():
        raise SystemExit(f"engine binary not found: {binary}")
    print(f"binary: {binary}")

    t = time.monotonic()
    check = subprocess.run([str(binary), "--self-check"], capture_output=True, text=True, timeout=300)
    print(check.stdout.strip())
    if check.returncode != 0:
        raise SystemExit(f"1/4 self-check failed:\n{check.stderr[-2000:]}")
    print(f"1/4 self-check ok ({time.monotonic() - t:.1f}s)")

    with tempfile.TemporaryDirectory(prefix="sloth-smoke-") as data_dir:
        port = free_port()
        proc = start(binary, data_dir, port)
        t = time.monotonic()
        try:
            health = wait_healthy(proc, port)
            assert request(port, "/health", token=None)[0] == 401, "/health must reject a missing token"
            print(f"2/4 healthy in {time.monotonic() - t:.1f}s · ollama={health['ollama']['status']} "
                  f"· tabpfn={health['tabpfn']['status']} · 401 without token")
            request(port, "/shutdown", method="POST")
            wait_exit(proc, "POST /shutdown")
            print("3/4 POST /shutdown → exited")
        except BaseException:
            proc.kill()
            print(log_tail(proc))
            raise

        port = free_port()
        proc = start(binary, data_dir, port)
        try:
            wait_healthy(proc, port)
            proc.stdin.close()  # what Electron's death looks like to the engine
            wait_exit(proc, "stdin EOF")
            print("4/4 stdin EOF (parent gone) → exited")
        except BaseException:
            proc.kill()
            print(log_tail(proc))
            raise

    print("smoke test passed")


if __name__ == "__main__":
    main()
