"""Run from project root: python scripts/train.py --symbol BTCUSDT --horizon 1h"""

import argparse, asyncio, json, sys, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database import store
from app.main import training_job, TrainRequest

parser = argparse.ArgumentParser()
parser.add_argument("--symbol", default="BTCUSDT")
parser.add_argument("--horizon", default="1h")
parser.add_argument("--bars", type=int, default=3000)
parser.add_argument("--boosters", action="store_true")
args = parser.parse_args()
store.init_db()
job = str(uuid.uuid4())
asyncio.run(
    training_job(
        job,
        TrainRequest(
            symbol=args.symbol,
            horizon=args.horizon,
            history_bars=args.bars,
            boosters=args.boosters,
        ),
    )
)
result = store.get("jobs", job)
print(json.dumps(result, indent=2))
sys.exit(0 if result["status"] == "completed" else 1)
