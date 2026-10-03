"""Optional full-browser test. pip install playwright; python -m playwright install chromium.
Run from project root with frontend dependencies installed.
Starts isolated demo servers and cleans them up. No credentials needed.
"""

import json, os, subprocess, sys, tempfile, time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
env = dict(
    os.environ,
    MOCK_MODE="true",
    DATABASE_URL="sqlite:///" + str(Path(tempfile.mkdtemp()) / "e2e.db"),
    OMP_NUM_THREADS="1",
    OPENBLAS_NUM_THREADS="1",
)
logs = open(ROOT / "docs" / "browser-test.log", "w")
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
    stdout=logs,
    stderr=logs,
)
npm = "npm.cmd" if os.name == "nt" else "npm"
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
    stdout=logs,
    stderr=logs,
)
checks = []
try:
    with httpx.Client(trust_env=False) as client:
        for _ in range(60):
            if backend.poll() is not None or frontend.poll() is not None:
                raise RuntimeError("A test server exited before readiness")
            try:
                if (
                    client.get("http://127.0.0.1:5173").status_code == 200
                    and client.get("http://127.0.0.1:8000/health").status_code == 200
                ):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Servers did not start")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": 1512, "height": 1080}, device_scale_factor=1
        )
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:5173", wait_until="networkidle")
        page.get_by_text("DEMO MODE · SYNTHETIC DATA", exact=True).wait_for()
        page.locator(".chart-host canvas").first.wait_for()
        page.wait_for_function(
            "document.querySelector('.live-price')?.textContent !== '—' && document.querySelector('.state-regime')?.textContent !== 'Awaiting data'"
        )
        first = page.locator(".live-price").inner_text()
        page.wait_for_timeout(2500)
        second = page.locator(".live-price").inner_text()
        assert first != second, "Price did not update via WebSocket"
        checks.append("Dashboard, candles and WebSocket price updates")
        page.screenshot(path=str(ROOT / "docs" / "dashboard.png"), full_page=True)
        page.get_by_label("Timeframe", exact=True).select_option("15m")
        page.wait_for_timeout(1600)
        page.get_by_role("button", name="FVG", exact=True).click()
        page.get_by_role("button", name="Structure", exact=True).click()
        page.get_by_role("button", name="← Load earlier candles", exact=True).click()
        page.wait_for_timeout(1000)
        checks.append("Timeframe switching, chart layers and historical loading")
        for title in [
            "Live Markets",
            "Chart",
            "Predictions",
            "Market Scanner",
            "ICT / SMC Analysis",
            "Model Performance",
            "Prediction History",
            "Watchlist",
            "Settings",
        ]:
            page.locator("nav").get_by_role("button", name=title, exact=True).click()
            page.wait_for_timeout(350)
            assert page.locator("h1").inner_text() == title
            checks.append("Page: " + title)
        page.locator("nav").get_by_role("button", name="Alerts", exact=True).click()
        page.get_by_label("Price", exact=True).fill("1")
        page.get_by_role("button", name="Create alert for BTCUSDT").click()
        page.locator(".alert-row").first.wait_for()
        checks.append("Alert creation persisted")
        page.locator("nav").get_by_role(
            "button", name="Model Performance", exact=True
        ).click()
        page.get_by_role("button", name="Train & validate model", exact=True).click()
        page.get_by_text("Job: completed", exact=False).wait_for(timeout=90000)
        checks.append("Model training job completed through the UI")
        page.locator("nav").get_by_role(
            "button", name="Predictions", exact=True
        ).click()
        page.get_by_text("MODEL DIRECTION", exact=True).wait_for(timeout=15000)
        checks.append("Promoted demo model forecast displayed")
        page.locator("nav").get_by_role("button", name="Chart", exact=True).click()
        page.get_by_role("button", name="Forecast range", exact=True).click()
        page.wait_for_timeout(700)
        page.screenshot(path=str(ROOT / "docs/forecast-zone.png"), full_page=True)
        checks.append("Validated demo prediction range overlays the chart")
        page.locator("nav").get_by_role(
            "button", name="Prediction History", exact=True
        ).click()
        page.locator("tbody tr").first.wait_for()
        checks.append("Generated prediction persisted in history")

        page.locator("nav").get_by_role(
            "button", name="Backtesting", exact=True
        ).click()
        page.get_by_role("button", name="Run backtest", exact=True).click()
        page.get_by_text("Measured backtest results", exact=True).wait_for(
            timeout=30000
        )
        assert page.locator(".table-wrap tbody tr").count() > 0
        page.get_by_role("button", name="Drawdown", exact=True).click()
        checks.append("Backtest form, trade table, equity and drawdown charts")
        page.locator("nav").get_by_role("button", name="Dashboard", exact=True).click()
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(1000)
        page.screenshot(
            path=str(ROOT / "docs" / "dashboard-mobile.png"), full_page=True
        )
        assert page.evaluate(
            "document.documentElement.scrollWidth<=window.innerWidth"
        ), "Mobile layout overflows"
        checks.append("Mobile layout without horizontal overflow")
        assert not errors, errors
        checks.append("No browser runtime errors")
        browser.close()
    print(json.dumps({"status": "passed", "checks": checks}, indent=2))
    (ROOT / "docs" / "browser-validation.json").write_text(
        json.dumps({"status": "passed", "checks": checks}, indent=2)
    )
finally:
    for process in (frontend, backend):
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    logs.close()
