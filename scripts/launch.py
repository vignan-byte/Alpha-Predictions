"""Cross-platform launcher for the compiled local application (Vite preview + FastAPI).
Run with the project's virtual-environment Python. --check performs readiness checks only.
"""

import argparse
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def preflight(port=8000):
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10 or later is required")
    # Check network ports before build artifacts so diagnostics identify the
    # immediate operational blocker deterministically.
    for candidate in (port, 5173):
        with socket.socket() as sock:
            if os.name != "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", candidate))
            except OSError as exc:
                raise RuntimeError(
                    f"Port {candidate} is already occupied. Close the existing server before starting another instance."
                ) from exc
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise RuntimeError(
            "Compiled frontend missing. Run setup.bat (Windows) or bash scripts/setup.sh."
        )
    if not shutil.which("node"):
        raise RuntimeError("Node.js not found; install Node.js 22 or later")
    if not (ROOT / "frontend/node_modules/vite/bin/vite.js").is_file():
        raise RuntimeError("Frontend dependencies missing. Run setup.bat first.")
    for module in ("uvicorn", "fastapi", "pandas", "sklearn", "sqlalchemy", "alembic"):
        __import__(module)
    return {
        "python": sys.version.split()[0],
        "frontend": "built",
        "port": port,
        "host": "127.0.0.1",
        "real_execution": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    print(json.dumps(preflight()), flush=True)
    if args.check:
        return
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=ROOT / "backend",
    )
    frontend = subprocess.Popen(
        [
            shutil.which("node"),
            str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
            "preview",
            "--host",
            "127.0.0.1",
            "--port",
            "5173",
            "--strictPort",
        ],
        cwd=ROOT / "frontend",
    )
    url = "http://127.0.0.1:5173"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for _ in range(120):
            if child.poll() is not None or frontend.poll() is not None:
                raise RuntimeError("Backend exited during startup; see the error above")
            try:
                with opener.open(url + "/health", timeout=1) as response:
                    health = json.load(response)
                if health.get("database") == "connected":
                    with opener.open(url, timeout=1) as page:
                        if page.status == 200:
                            break
            except (OSError, ValueError):
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Backend did not become ready within 60 seconds")
        print(
            f"\nAlphaPredictorsAI ready: {url}\nData mode: {health['mode'].upper()} | Real execution OFF\nKeep this window open. Press Ctrl+C to stop.\n",
            flush=True,
        )
        if not args.no_browser:
            webbrowser.open(url)
        while child.poll() is None and frontend.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping AlphaPredictorsAI…", flush=True)
    finally:
        for proc in (frontend, child):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        sys.exit(1)
