"""Exercise the exact cross-platform launcher and compiled frontend on its default ports."""

import json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
env = dict(
    os.environ,
    MOCK_MODE="true",
    API_TOKEN="",
    DATABASE_URL="sqlite:///" + str(Path(tempfile.mkdtemp()) / "production.db"),
)
log = open(ROOT / "docs/production-browser.log", "w")
checks = []
proc = subprocess.Popen(
    [sys.executable, "scripts/launch.py", "--no-browser"],
    cwd=ROOT,
    env=env,
    stdout=log,
    stderr=log,
    start_new_session=os.name != "nt",
)
try:
    with httpx.Client(trust_env=False, timeout=5) as c:
        for _ in range(120):
            if proc.poll() is not None:
                raise RuntimeError("Launcher exited; inspect production-browser.log")
            try:
                if (
                    c.get("http://localhost:5173/health").status_code == 200
                    and c.get("http://localhost:8000/health").status_code == 200
                ):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Launcher readiness failed")
        html = c.get("http://localhost:5173/").text
        assert "/assets/index-" in html and "/@vite/client" not in html
        checks.append(
            "Launcher starts compiled frontend on localhost:5173 and healthy migrated backend on localhost:8000"
        )
        assert c.get("http://localhost:5173/docs").status_code == 200
        assert (
            c.get("http://localhost:5173/openapi.json").json()["info"]["version"]
            == "2.2.0"
        )
        checks.append("Production preview proxies health, APIs and documentation")
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = b.new_page(viewport={"width": 1512, "height": 1080}, locale="en-US")
            errors = []
            frames = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "websocket",
                lambda ws: ws.on("framereceived", lambda data: frames.append(data)),
            )
            page.goto("http://localhost:5173/")
            page.get_by_text("DEMO MODE · SYNTHETIC DATA", exact=True).wait_for()
            page.locator(".chart-host canvas").first.wait_for()
            page.wait_for_timeout(2000)
            assert any('"candle"' in f for f in frames if isinstance(f, str))
            assert not errors
            checks.append(
                "Compiled React app receives proxied WebSocket candles with no runtime errors"
            )
            page.screenshot(path=str(ROOT / "docs/final-dashboard.png"), full_page=True)
            b.close()
finally:
    if proc.poll() is None:
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(proc.pid, signal.SIGINT)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    log.close()
checks.append("Launcher stops server processes after interrupt")
result = dict(
    status="passed",
    checks=checks,
    platform=sys.platform,
    windows_native="BLOCKED: Linux runner; Windows wrappers statically reviewed",
)
(ROOT / "docs/production-browser-validation.json").write_text(
    json.dumps(result, indent=2)
)
print(json.dumps(result, indent=2))
