"""Opt-in live Binance end-to-end test; public data only, no orders or keys.
Run from root: python tests/live_browser_smoke.py
Requires Playwright/Chromium and installed frontend dependencies. Uses temporary DB.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
env = dict(
    os.environ,
    MOCK_MODE="false",
    DATABASE_URL="sqlite:///" + str(Path(tempfile.mkdtemp()) / "live.db"),
    OMP_NUM_THREADS="1",
    OPENBLAS_NUM_THREADS="1",
)
log = open(ROOT / "docs" / "live-browser-test.log", "w")
backend = subprocess.Popen(
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
    env=env,
    stdout=log,
    stderr=log,
)
frontend = subprocess.Popen(
    [
        "node",
        str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
        "--host",
        "127.0.0.1",
        "--port",
        "5173",
        "--strictPort",
    ],
    cwd=ROOT / "frontend",
    env=env,
    stdout=log,
    stderr=log,
)
checks = []
try:
    with httpx.Client(trust_env=False, timeout=90) as client:
        for _ in range(60):
            if backend.poll() is not None or frontend.poll() is not None:
                raise RuntimeError("A test server exited before readiness")
            try:
                if (
                    client.get("http://127.0.0.1:8000/health").status_code == 200
                    and client.get("http://127.0.0.1:5173").status_code == 200
                ):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Servers failed to start")
        assert client.get("http://127.0.0.1:8000/health").json()["mode"] == "live"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(
                viewport={"width": 1512, "height": 1080}, locale="en-US"
            )
            page.add_init_script(
                "window.canvasDraws=0; const nativeFill=CanvasRenderingContext2D.prototype.fillRect; CanvasRenderingContext2D.prototype.fillRect=function(...args){window.canvasDraws++;return nativeFill.apply(this,args)}; window.marketSockets=[]; const NativeWebSocket=window.WebSocket; window.WebSocket=class extends NativeWebSocket { constructor(...args){ super(...args); window.marketSockets.push(this); } };"
            )
            frames = []
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))

            def frame_received(payload):
                try:
                    data = json.loads(payload)
                    if data.get("type") == "candle" and data.get("source") == "binance":
                        frames.append(data)
                except (ValueError, TypeError):
                    pass

            page.on("websocket", lambda ws: ws.on("framereceived", frame_received))
            page.goto("http://127.0.0.1:5173", wait_until="domcontentloaded")
            page.get_by_text("LIVE DATA MODE", exact=True).wait_for(timeout=90000)
            page.wait_for_function(
                "document.querySelector('.state-regime')?.textContent !== 'Awaiting data'",
                timeout=90000,
            )
            for _ in range(45):
                page.wait_for_timeout(1000)
                if len(frames) >= 2:
                    break
            assert len(frames) >= 2, "No real Binance candle frames reached the browser"
            assert all(f["status"] == "live" for f in frames)
            checks.append(
                "Real Binance WebSocket candle frames relayed through FastAPI and Vite to browser"
            )
            first = page.locator(".chart-host").screenshot()
            before_draws = page.evaluate("window.canvasDraws")
            initial = len(frames)
            for _ in range(12):
                page.wait_for_timeout(1000)
                if len(frames) > initial + 1:
                    break
            second = page.locator(".chart-host").screenshot()
            assert (
                first != second or page.evaluate("window.canvasDraws") > before_draws
            ), "Chart canvas did not redraw after streamed market updates"
            checks.append(
                "Candlestick/volume canvas redraw verified after live frames (pixel change is not required for unchanged quotes)"
            )
            last = frames[-1]
            displayed = page.locator(".live-price").inner_text()
            assert any(
                f"{f['candle']['close']:,.2f}" in displayed for f in frames[-5:]
            ), (
                displayed,
                last["candle"]["close"],
            )
            checks.append("Displayed live price matches a received Binance close")
            analysis = client.get("http://127.0.0.1:8000/api/analysis/BTCUSDT").json()
            assert (
                analysis["source"] == "binance"
                and analysis["indicators"]["rsi"] is not None
            )
            assert analysis["asof"] <= last["timestamp"]
            assert (
                analysis["asof"] <= last["candle"]["time"]
            ), "Developing candle leaked into analysis"
            checks.append(
                "Live closed-candle analysis generated indicators and structure without the developing candle"
            )
            result = client.get(
                "http://127.0.0.1:8000/api/predictions/BTCUSDT?horizon=1h"
            ).json()
            assert result["source"] == "binance"
            assert result["status"] == "unavailable" and result["probability"] is None
            assert len(result["scenarios"]) == 3 and result["explanation"]
            checks.append(
                "Live prediction pipeline generated evidence-backed scenarios and correctly withheld unvalidated ML probability"
            )
            previous_frames = len(frames)
            previous_sockets = page.evaluate(
                "window.marketSockets.filter(s=>s.url.includes('/ws/market/')).length"
            )
            page.evaluate(
                "window.marketSockets.filter(s=>s.readyState===1 && s.url.includes('/ws/market/')).forEach(s=>s.close())"
            )
            for _ in range(30):
                page.wait_for_timeout(1000)
                if (
                    len(frames) > previous_frames
                    and page.evaluate(
                        "window.marketSockets.filter(s=>s.url.includes('/ws/market/')).length"
                    )
                    > previous_sockets
                ):
                    break
            assert (
                len(frames) > previous_frames
                and page.evaluate(
                    "window.marketSockets.filter(s=>s.url.includes('/ws/market/')).length"
                )
                > previous_sockets
            )
            checks.append(
                "Browser reconnects after WebSocket closure and receives fresh Binance frames"
            )
            page.get_by_text("Awaiting validated model", exact=True).wait_for(
                timeout=30000
            )
            page.screenshot(
                path=str(ROOT / "docs" / "live-dashboard.png"), full_page=True
            )
            assert not errors, errors
            checks.append(
                "Live browser displayed honest prediction status with no runtime errors"
            )
            summary = {
                "status": "passed",
                "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "checks": checks,
                "stream_frames": len(frames),
                "stream_source": "binance",
                "analysis_asof": analysis["asof"],
                "prediction_status": result["status"],
                "note": "No promoted live model in fresh installation. Unvalidated probabilities are intentionally withheld; live training metrics are documented separately.",
            }
            (ROOT / "docs" / "live-browser-validation.json").write_text(
                json.dumps(summary, indent=2)
            )
            print(json.dumps(summary, indent=2), flush=True)
            browser.close()
finally:
    for process in (frontend, backend):
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    log.close()
