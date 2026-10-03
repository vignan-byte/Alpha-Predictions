import json
import math
import numpy as np
import pandas as pd


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return float(obj) if math.isfinite(obj) else None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


def dumps(obj):
    return json.dumps(clean(obj), allow_nan=False)
