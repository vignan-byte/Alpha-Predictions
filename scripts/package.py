"""Create a source distribution without secrets, installed dependencies or runtime data."""

from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT.parent / "AlphaPredictorsAI-FINAL.zip"
SKIP_DIRS = {"node_modules", ".venv", "__pycache__", ".pytest_cache", ".git"}
required = [
    "README.md",
    "setup.bat",
    "setup.ps1",
    "run.bat",
    "run.ps1",
    "backend/requirements.txt",
    "backend/.env.example",
    "backend/app/main.py",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/src/App.tsx",
    "scripts/launch.py",
    "backend/tests/test_completion.py",
    "tests/completion_browser.py",
]
for name in required:
    if not (ROOT / name).is_file():
        raise RuntimeError(f"Required release file missing: {name}")
files = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        continue
    if path.name == ".env" or path.suffix in {
        ".pyc",
        ".db",
        ".log",
        ".joblib",
        ".tsbuildinfo",
    }:
        continue
    if path.name.endswith((".db-shm", ".db-wal")):
        continue
    if (
        rel.parts[:2]
        in [
            ("models", "trained"),
            ("models", "metadata"),
            ("models", "versions"),
            ("models", "artifacts"),
        ]
        and path.name != ".gitkeep"
    ):
        continue
    if path.name == "MANIFEST.sha256":
        continue
    files.append(path)
manifest = (
    "\n".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}"
        for p in sorted(files)
    )
    + "\n"
)
with zipfile.ZipFile(
    DEST, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
) as archive:
    for p in sorted(files):
        archive.write(p, arcname="AlphaPredictorsAI/" + p.relative_to(ROOT).as_posix())
    archive.writestr("AlphaPredictorsAI/MANIFEST.sha256", manifest)
with zipfile.ZipFile(DEST) as archive:
    assert archive.testzip() is None
    for row in archive.read("AlphaPredictorsAI/MANIFEST.sha256").decode().splitlines():
        digest, name = row.split("  ", 1)
        assert (
            hashlib.sha256(archive.read("AlphaPredictorsAI/" + name)).hexdigest()
            == digest
        )
    assert all("AlphaPredictorsAI/" + name in archive.namelist() for name in required)
print(
    json.dumps(
        {
            "zip": str(DEST),
            "files": len(files) + 1,
            "bytes": DEST.stat().st_size,
            "sha256": hashlib.sha256(DEST.read_bytes()).hexdigest(),
        },
        indent=2,
    )
)
