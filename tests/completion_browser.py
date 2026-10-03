"""Release regression of auth, native filled zones and paper account lifecycle.
Uses explicitly labeled synthetic data in an isolated DB; never submits real orders.
"""

import json, os, subprocess, sys, tempfile, time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "browser-fixture-token-not-a-production-secret"
env = dict(
    os.environ,
    MOCK_MODE="true",
    API_TOKEN=TOKEN,
    DATABASE_URL="sqlite:///" + str(Path(tempfile.mkdtemp()) / "completion.db"),
    OMP_NUM_THREADS="1",
    OPENBLAS_NUM_THREADS="1",
)
log = open(ROOT / "docs/completion-browser.log", "w")
processes = []
checks = []
errors = []
try:
    processes.append(
        subprocess.Popen(
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
    )
    processes.append(
        subprocess.Popen(
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
    )
    with httpx.Client(
        trust_env=False, timeout=90, headers={"Authorization": "Bearer " + TOKEN}
    ) as client:
        for _ in range(60):
            if any(p.poll() is not None for p in processes):
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
            raise RuntimeError("Servers not ready")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                viewport={"width": 1512, "height": 1080},
                locale="en-US",
                permissions=["notifications"],
            )
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.add_init_script(
                """window.zoneDraws=0;const original=CanvasRenderingContext2D.prototype.fillRect;CanvasRenderingContext2D.prototype.fillRect=function(...args){if(Math.abs(this.globalAlpha-.14)<.002||Math.abs(this.globalAlpha-.045)<.002)window.zoneDraws++;return original.apply(this,args)};"""
            )
            page.goto("http://127.0.0.1:5173")
            page.get_by_role("button", name="Unlock workspace", exact=True).wait_for()
            assert page.locator("nav").count() == 0
            page.get_by_label("Access token", exact=True).fill(TOKEN)
            page.get_by_role("button", name="Unlock workspace", exact=True).click()
            page.get_by_text("DEMO MODE · SYNTHETIC DATA", exact=True).wait_for()
            checks.append(
                "Optional authentication hides application until login; signed session cookie authorizes HTTP and WebSocket"
            )

            def nav(name):
                page.locator("nav").get_by_role("button", name=name, exact=True).click()

            nav("Chart")
            page.locator(".chart-host canvas").first.wait_for()
            page.get_by_role("button", name="FVG", exact=True).click()
            page.get_by_role("button", name="Blocks", exact=True).click()
            page.get_by_role("button", name="Sessions", exact=True).click()
            page.get_by_role("button", name="OTE", exact=True).click()
            page.get_by_role(
                "button", name="Breakers / inverse FVG", exact=True
            ).click()
            page.wait_for_function("window.zoneDraws > 0")
            n = page.evaluate("window.zoneDraws")
            box = page.locator(".chart-host").bounding_box()
            page.mouse.move(box["x"] + 300, box["y"] + 140)
            page.mouse.wheel(0, -400)
            page.wait_for_timeout(500)
            assert page.evaluate("window.zoneDraws") > n
            page.mouse.down()
            page.mouse.move(box["x"] + 480, box["y"] + 140, steps=6)
            page.mouse.up()
            page.get_by_role("button", name="Fit view", exact=True).click()
            page.screenshot(path=str(ROOT / "docs/chart-zones.png"), full_page=True)
            checks.append(
                "Filled FVG/order-block/session/OTE primitives render and redraw under zoom and pan"
            )
            for symbol in ["ETHUSDT", "EURUSD", "BTCUSDT"]:
                page.get_by_label("Instrument", exact=True).select_option(symbol)
                page.wait_for_timeout(650)
            checks.append("Crypto and explicitly labeled demo forex symbol switching")
            for tf in ["1m", "15m", "30m", "1h", "4h", "1d", "1w", "1M", "5m"]:
                with page.expect_response(
                    lambda r: f"/api/candles/BTCUSDT?timeframe={tf}&" in r.url
                    and "before=" not in r.url,
                    timeout=30000,
                ) as response:
                    page.get_by_label("Timeframe", exact=True).select_option(tf)
                assert response.value.status == 200
                page.wait_for_timeout(150)
            checks.append("All nine chart timeframes load successfully")
            nav("Economic Calendar")
            page.get_by_text("BLOCKED", exact=True).wait_for()
            page.get_by_label("Impact filter").select_option("high")
            page.get_by_label("Currency filter").select_option("USD")
            page.get_by_text(
                "No provider events available for these filters."
            ).wait_for()
            checks.append(
                "Calendar missing-key state, impact and currency filters are honest"
            )
            nav("News")
            page.get_by_text("BLOCKED", exact=True).wait_for()
            checks.append("News missing-key state is independent of calendar")
            nav("Correlations")
            page.locator(".correlation-table tbody tr").first.wait_for()
            assert page.locator(".correlation-table tbody td").count() == 9
            page.get_by_label("Correlation symbols").fill("BTCUSDT,ETHUSDT")
            page.get_by_role("button", name="Measure relationships", exact=True).click()
            page.wait_for_function(
                "document.querySelectorAll('.correlation-table tbody td').length===4"
            )
            checks.append(
                "Correlation matrix, aligned return statistics and instrument changes"
            )
            nav("Paper Trading")
            page.get_by_role(
                "button", name="Set 2% stop / 4% target", exact=True
            ).wait_for()
            page.wait_for_timeout(500)
            page.get_by_label("Starting balance", exact=True).fill("15000")
            page.get_by_role("button", name="Set starting balance", exact=True).click()
            page.get_by_text("Starting virtual balance updated.", exact=True).wait_for()
            page.get_by_role(
                "button", name="Set 2% stop / 4% target", exact=True
            ).click()
            page.get_by_label("Paper units", exact=True).fill(".01")
            page.get_by_role("button", name="Preview paper order", exact=True).click()
            page.get_by_role(
                "button", name="Confirm paper order", exact=True
            ).wait_for()
            a = client.get(
                "http://127.0.0.1:8000/api/paper/account?symbol=BTCUSDT"
            ).json()
            assert not a["positions"]
            checks.append("Paper order preview persists without placing a position")
            page.get_by_role("button", name="Confirm paper order", exact=True).click()
            page.get_by_role("button", name="Close position", exact=True).wait_for()
            a = client.get(
                "http://127.0.0.1:8000/api/paper/account?symbol=BTCUSDT"
            ).json()
            assert len(a["positions"]) == 1 and a["balance"] < 15000
            checks.append(
                "Confirmed virtual fill reserves collateral and charges entry fees"
            )
            page.get_by_role("button", name="Close position", exact=True).click()
            page.get_by_role("dialog", name="Confirm paper close").wait_for()
            page.get_by_role("button", name="Confirm close", exact=True).click()
            page.get_by_text(
                "Paper position closed. Realized performance updated.", exact=True
            ).wait_for()
            a = client.get(
                "http://127.0.0.1:8000/api/paper/account?symbol=BTCUSDT"
            ).json()
            assert not a["positions"] and a["trade_count"] == 1
            assert abs(a["balance"] - (15000 + a["trades"][0]["net_pnl"])) < 1e-7
            page.screenshot(path=str(ROOT / "docs/paper-trading.png"), full_page=True)
            checks.append(
                "Manual close, net P&L, persistent trade history and equity curve reconcile"
            )
            page.reload()
            page.locator("nav").wait_for()
            nav("Paper Trading")
            page.get_by_text("manual", exact=True).wait_for()
            checks.append("Paper account and authentication survive page reload")
            nav("Alerts")
            page.get_by_label("Price", exact=True).fill("1")
            page.get_by_role(
                "button", name="Create alert for BTCUSDT", exact=True
            ).click()
            page.locator(".alert-row").first.wait_for()
            page.get_by_role("button", name="Enable notifications", exact=True).click()
            page.get_by_role("button", name="Notifications on", exact=True).wait_for()
            page.get_by_role("button", name="Sound off", exact=True).click()
            page.get_by_role("button", name="Sound on", exact=True).wait_for()
            checks.append(
                "Alert creation, browser permission and sound opt-in controls"
            )
            for _ in range(75):
                notes = client.get("http://127.0.0.1:8000/api/notifications").json()
                if notes:
                    break
                page.wait_for_timeout(1000)
            assert notes, "Background alert did not fire"
            checks.append(
                "Background collector triggers and persists a source-scoped price alert"
            )
            nav("Backtesting")
            page.get_by_role("button", name="Run backtest", exact=True).click()
            page.get_by_text("Measured backtest results", exact=True).wait_for(
                timeout=30000
            )
            page.get_by_text("Chronological evaluation windows", exact=True).click()
            page.get_by_text("Forward window 3", exact=True).wait_for()
            checks.append(
                "Backtest chronological research, holdout and three forward windows render"
            )
            nav("Paper Trading")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(500)
            assert page.evaluate(
                "document.documentElement.scrollWidth<=window.innerWidth"
            )
            page.screenshot(path=str(ROOT / "docs/paper-mobile.png"), full_page=True)
            checks.append("Paper workspace mobile layout without page overflow")
            assert not errors, errors
            checks.append("No browser runtime errors across new modules")
            browser.close()
    summary = {
        "status": "passed",
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": checks,
        "runtime_errors": errors,
        "mode": "demo with authentication",
        "note": "Calendar/news credential absence verified; no claim of live provider verification.",
    }
    (ROOT / "docs/completion-browser-validation.json").write_text(
        json.dumps(summary, indent=2)
    )
    print(json.dumps(summary, indent=2), flush=True)
finally:
    for proc in reversed(processes):
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    log.close()
