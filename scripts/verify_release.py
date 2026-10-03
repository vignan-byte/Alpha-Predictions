"""Verify ZIP hashes, exclusions and an extracted backend/paper startup without altering user data."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
archive = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else ROOT.parent / "AlphaPredictorsAI-FINAL.zip"
)
with tempfile.TemporaryDirectory(prefix="alpha-release-") as directory:
    target = Path(directory)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None, "ZIP CRC failed"
        names = z.namelist()
        assert all(
            not Path(n).is_absolute() and ".." not in Path(n).parts for n in names
        )
        assert all(
            not any(
                p in ("node_modules", ".venv", "__pycache__", ".pytest_cache")
                for p in Path(n).parts
            )
            for n in names
        )
        assert all(
            Path(n).name != ".env" and Path(n).suffix not in (".db", ".joblib", ".pyc")
            for n in names
        )
        manifest = z.read("AlphaPredictorsAI/MANIFEST.sha256").decode().splitlines()
        for line in manifest:
            digest, name = line.split("  ", 1)
            assert (
                hashlib.sha256(z.read("AlphaPredictorsAI/" + name)).hexdigest()
                == digest
            ), name
        z.extractall(target)
    project = target / "AlphaPredictorsAI"
    required = [
        "setup.bat",
        "setup.ps1",
        "run.bat",
        "run.ps1",
        "README.md",
        "backend/requirements.txt",
        "backend/.env.example",
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/src/App.tsx",
        "backend/tests/test_completion.py",
        "tests/completion_browser.py",
    ]
    assert all((project / p).is_file() for p in required)
    env = dict(
        os.environ,
        PYTHONPATH=str(project / "backend"),
        MOCK_MODE="true",
        API_TOKEN="",
        DATABASE_URL="sqlite:///" + str(target / "isolated.db"),
    )
    code = """
import json
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    assert c.get('/health').json()['database']=='connected'
    q=c.get('/api/paper/quote/BTCUSDT').json()['price']
    p=c.post('/api/paper/preview',json=dict(symbol='BTCUSDT',side=1,units=.001,stop=q*.9,target=q*1.1))
    assert p.status_code==200,p.text
    ident=p.json()['id']
    assert c.post('/api/paper/confirm',json=dict(symbol='BTCUSDT',preview_id=ident,confirm=True)).status_code==200
    assert c.post('/api/paper/positions/'+ident+'/close',json=dict(symbol='BTCUSDT',confirm=True)).status_code==200
    a=c.get('/api/paper/account?symbol=BTCUSDT').json()
    assert a['trade_count']==1 and not a['positions']
    assert c.get('/api/predictions/BTCUSDT').json()['probability'] is None
print(json.dumps({'health':'PASS','migrations':'PASS','extracted_paper_lifecycle':'PASS','unvalidated_model_gate':'PASS'}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project / "backend",
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    smoke = json.loads(result.stdout.strip().splitlines()[-1])
report = dict(
    status="passed",
    archive=archive.name,
    files=len(names),
    verified_hashes=len(manifest),
    required_files=len(required),
    exclusions="PASS",
    extracted_smoke=smoke,
    note="Extracted source uses the installed Python dependency environment. Native Windows execution is not available on this Linux runner.",
)
(ROOT / "docs/zip-verification.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
