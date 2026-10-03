import hashlib
import json
import time
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import (
    RandomForestClassifier,
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    log_loss,
    mean_absolute_error,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from threadpoolctl import threadpool_limits
from app.features.engine import build, targets, FEATURES, FEATURE_VERSION, TARGET_VERSION
from app.core.config import ROOT
from app.core.utils import clean
from app.database import store

DIR = ROOT / "models" / "trained"
DIR.mkdir(parents=True, exist_ok=True)
LABELS = ["Bearish", "Neutral", "Bullish"]



def decision_labels(p, rule=None):
    """Apply a validation-learned abstention rule without changing probabilities."""
    p = np.asarray(p)
    top = np.argmax(p, axis=1)
    if not rule:
        return top
    min_conf = float(rule.get("min_confidence", 0.34))
    min_margin = float(rule.get("min_margin", 0.0))
    order = np.sort(p, axis=1)
    margin = order[:, -1] - order[:, -2]
    return np.where(
        (p.max(axis=1) < min_conf) | (margin < min_margin),
        1,  # Neutral / no strong edge
        top,
    ).astype(int)


def learn_decision_rule(y, p):
    """Learn a conservative Neutral/abstain rule on validation data only."""
    best = {"score": -1.0, "min_confidence": 0.34, "min_margin": 0.0}
    # Keep a meaningful amount of directional coverage; otherwise a rule can
    # game accuracy by abstaining almost everywhere.
    for conf in np.arange(0.34, 0.71, 0.02):
        for margin in np.arange(0.00, 0.31, 0.02):
            pred = decision_labels(p, {"min_confidence": conf, "min_margin": margin})
            coverage = float(np.mean(pred != 1))
            if coverage < 0.20:
                continue
            score = float(f1_score(y, pred, labels=[0, 1, 2], average="macro", zero_division=0))
            if score > best["score"]:
                best = {
                    "score": score,
                    "min_confidence": float(conf),
                    "min_margin": float(margin),
                    "directional_coverage": coverage,
                }
    best.pop("score", None)
    return best


def metrics(y, p, rule=None):
    pred = decision_labels(p, rule)
    confidence = p.max(axis=1)
    correct = pred == y
    ece = 0.0
    for a in np.linspace(0, 0.9, 10):
        mask = (confidence >= a) & (
            confidence < (a + 0.1) if a < 0.9 else confidence <= 1
        )
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - confidence[mask].mean())
    return dict(
        samples=len(y),
        balanced_accuracy=float(balanced_accuracy_score(y, pred)),
        accuracy=float(accuracy_score(y, pred)),
        log_loss=float(log_loss(y, p, labels=[0, 1, 2])),
        brier=float(np.mean(np.sum((p - np.eye(3)[y]) ** 2, axis=1))),
        calibration_error=float(ece),
        precision=float(
            precision_score(y, pred, labels=[0, 1, 2], average="macro", zero_division=0)
        ),
        recall=float(
            recall_score(y, pred, labels=[0, 1, 2], average="macro", zero_division=0)
        ),
        f1=float(f1_score(y, pred, labels=[0, 1, 2], average="macro", zero_division=0)),
        roc_auc=(
            float(roc_auc_score(y, p, labels=[0, 1, 2], multi_class="ovr"))
            if len(np.unique(y)) == 3
            else None
        ),
        confusion_matrix=confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
        class_order=LABELS,
    )


def candidates(boosters=False):
    estimators = {
        "logistic": make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            StandardScaler(),
            LogisticRegression(max_iter=1200, C=0.05, class_weight="balanced"),
        ),
        "random_forest": make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            RandomForestClassifier(
                n_estimators=600,
                max_depth=10,
                min_samples_leaf=6,
                max_features="sqrt",
                class_weight="balanced_subsample",
                random_state=42,
                n_jobs=1,
            ),
        ),
        "extra_trees": make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            ExtraTreesClassifier(
                n_estimators=600,
                max_depth=12,
                min_samples_leaf=5,
                max_features="sqrt",
                class_weight="balanced",
                random_state=44,
                n_jobs=1,
            ),
        ),
        "hist_gradient_boosting": make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            HistGradientBoostingClassifier(
                max_iter=250,
                learning_rate=0.04,
                max_leaf_nodes=15,
                l2_regularization=2.0,
                random_state=45,
            ),
        ),
    }
    if boosters:
        from xgboost import XGBClassifier
        from lightgbm import LGBMClassifier
        from catboost import CatBoostClassifier

        for name, model in [
            (
                "xgboost",
                XGBClassifier(
                    n_estimators=300,
                    max_depth=4,
                    learning_rate=0.03,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    objective="multi:softprob",
                    eval_metric="mlogloss",
                    n_jobs=1,
                    random_state=42,
                ),
            ),
            (
                "lightgbm",
                LGBMClassifier(
                    n_estimators=300,
                    max_depth=5,
                    learning_rate=0.03,
                    num_leaves=24,
                    verbosity=-1,
                    n_jobs=1,
                    random_state=42,
                ),
            ),
            (
                "catboost",
                CatBoostClassifier(
                    iterations=300,
                    depth=5,
                    learning_rate=0.03,
                    loss_function="MultiClass",
                    verbose=False,
                    thread_count=1,
                    random_seed=42,
                ),
            ),
        ]:
            estimators[name] = make_pipeline(
                SimpleImputer(strategy="median", keep_empty_features=True), model
            )
    return estimators


def probabilities(model, x):
    raw = model.predict_proba(x)
    result = np.full((len(x), 3), 1e-8)
    for i, k in enumerate(model.classes_):
        result[:, int(k)] = raw[:, i]
    return result / result.sum(axis=1, keepdims=True)


def calibrated(model, cal, x):
    return probabilities(cal, np.log(np.clip(probabilities(model, x), 1e-8, 1)))


@threadpool_limits.wrap(limits=1)
def train(df, symbol, tf, horizon, source, boosters=False):
    d, _, _ = build(df)
    identity_horizon = horizon
    if horizon == "session":
        from app.features.session_targets import session_targets

        target = session_targets(d)
        horizon = 96  # Four-day embargo covers weekend next-session labels.
    else:
        target = targets(d, horizon)
    valid = target.notna().all(axis=1) & d.atr.notna() & (d.index >= 60)
    d = d.loc[valid].reset_index(drop=True)
    target = target.loc[valid].reset_index(drop=True)
    n = len(d)
    if n < max(500, horizon * 12):
        raise ValueError(
            f"Insufficient history: {n} usable candles; need {max(500,horizon*12)}"
        )
    x = d[FEATURES].to_numpy()
    y = target["class"].astype(int).to_numpy()
    a = int(n * 0.5)
    b = int(n * 0.65)
    c = int(n * 0.8)
    train_idx = np.arange(0, a - horizon)
    cal_idx = np.arange(a, b - horizon)
    val_idx = np.arange(b, c - horizon)
    test_idx = np.arange(c, n, horizon)
    if min(len(train_idx), len(cal_idx), len(val_idx), len(test_idx)) < 20:
        raise ValueError("Insufficient purged partitions")
    for idx in (train_idx, cal_idx):
        if len(np.unique(y[idx])) < 3:
            raise ValueError(
                "Training/calibration requires all three classes; collect more history"
            )
    compare = []
    models = {}
    # Candidate comparison is validation-only. Test is evaluated exactly once for the selected model.
    for name, model in candidates(boosters).items():
        model.fit(x[train_idx], y[train_idx])
        cal = LogisticRegression(C=0.5, max_iter=600).fit(
            np.log(np.clip(probabilities(model, x[cal_idx]), 1e-8, 1)), y[cal_idx]
        )
        p = calibrated(model, cal, x[val_idx])
        score = metrics(y[val_idx], p)
        compare.append(dict(name=name, **score))
        models[name] = (model, cal)
    winner = min(compare, key=lambda r: (r["log_loss"], -r["f1"]))
    model, cal = models[winner["name"]]
    validation_p = calibrated(model, cal, x[val_idx])
    decision_rule = learn_decision_rule(y[val_idx], validation_p)
    folds = []
    for tr, te in TimeSeriesSplit(n_splits=3, gap=horizon).split(x[:a]):
        if len(np.unique(y[tr])) < 2:
            continue
        baseline = candidates()["logistic"]
        baseline.fit(x[tr], y[tr])
        folds.append(
            dict(
                train_end=int(tr[-1]),
                test_start=int(te[0]),
                **metrics(y[te], probabilities(baseline, x[te])),
            )
        )
    regressors = {}
    reg_metrics = {}
    for name in ["return", "high", "low", "volatility"]:
        reg = make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            HistGradientBoostingRegressor(
                max_iter=80, max_leaf_nodes=12, l2_regularization=5, random_state=42
            ),
        )
        reg.fit(x[train_idx], target[name].to_numpy()[train_idx])
        regressors[name] = reg
        reg_metrics[name] = float(
            mean_absolute_error(
                target[name].to_numpy()[test_idx], reg.predict(x[test_idx])
            )
        )
    test_p = calibrated(model, cal, x[test_idx])
    test_metrics = metrics(y[test_idx], test_p, decision_rule)
    rng = np.random.default_rng(42)
    importance = {}
    for j, name in enumerate(FEATURES):
        shuffled = x[val_idx].copy()
        rng.shuffle(shuffled[:, j])
        importance[name] = float(
            metrics(y[val_idx], calibrated(model, cal, shuffled))["log_loss"]
            - winner["log_loss"]
        )
    prior = (np.bincount(y[train_idx], minlength=3) + 1) / (len(train_idx) + 3)
    baseline_loss = float(
        log_loss(y[val_idx], np.tile(prior, (len(val_idx), 1)), labels=[0, 1, 2])
    )
    fingerprint = hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()
    version = (
        time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        + "-"
        + fingerprint[:8]
        + "-"
        + str(time.time_ns())[-5:]
    )
    metadata = dict(
        version=version,
        symbol=symbol,
        timeframe=tf,
        horizon_bars=horizon,
        target_horizon=identity_horizon,
        source=source,
        feature_version=FEATURE_VERSION,
        target_version=TARGET_VERSION,
        features=FEATURES,
        training_date=time.time(),
        data_hash=fingerprint,
        history_start=int(df.time.iloc[0]),
        history_end=int(df.end_time.iloc[-1]),
        model=winner["name"],
        validation=dict(winner, decision_rule=decision_rule),
        test=test_metrics,
        decision_rule=decision_rule,
        regression_mae=reg_metrics,
        comparison=compare,
        walk_forward=folds,
        baseline_log_loss=baseline_loss,
        partitions=dict(
            train=len(train_idx),
            calibration=len(cal_idx),
            validation=len(val_idx),
            test=len(test_idx),
            purge=horizon,
        ),
        test_by_regime={},
        feature_importance=importance,
        parameters=model.get_params(deep=False).__repr__(),
    )
    for regime in np.unique(d.regime.iloc[test_idx]):
        mask = d.regime.iloc[test_idx].to_numpy() == regime
        metadata["test_by_regime"][regime] = metrics(y[test_idx][mask], test_p[mask], decision_rule)
    # Validation-only promotion; test never determines which model is deployed.
    key = f"{source}:{symbol}:{tf}:{identity_horizon}"
    old = store.get("active_models", key)
    incumbent_loss = None
    eligible_incumbent = True
    if old:
        artifact = load(old["version"])
        compatible_incumbent = (
            artifact["metadata"].get("feature_version") == FEATURE_VERSION
            and artifact["metadata"].get("target_version") == TARGET_VERSION
            and artifact["metadata"].get("features") == FEATURES
        )
        eligible_incumbent = (
            compatible_incumbent
            and artifact["metadata"]["history_end"] < int(
                d.time.iloc[val_idx[0]]
            )
        )
        if eligible_incumbent:
            incumbent_loss = metrics(
                y[val_idx],
                calibrated(artifact["model"], artifact["calibrator"], x[val_idx]),
            )["log_loss"]
    promote = (
        winner["log_loss"] < baseline_loss
        and (
            not eligible_incumbent
            or incumbent_loss is None
            or winner["log_loss"] < incumbent_loss * 0.99
        )
    )
    metadata["promoted"] = promote
    metadata["validation_status"] = "VALIDATED" if promote else "REJECTED"
    metadata["incumbent_validation_log_loss"] = incumbent_loss
    metadata["incumbent_eligible"] = eligible_incumbent
    metadata["promotion_reason"] = (
        "Validation beats class-prior baseline and incumbent by required margin"
        if promote
        else "Did not pass validation promotion gate; retained as research artifact (incumbent comparison requires a wholly later validation period)"
    )
    bundle = dict(model=model, calibrator=cal, regressors=regressors, metadata=metadata)
    joblib.dump(bundle, DIR / (version + ".joblib"))
    (ROOT / "models" / "metadata").mkdir(exist_ok=True)
    (ROOT / "models" / "metadata" / (version + ".json")).write_text(
        json.dumps(clean(metadata), indent=2), encoding="utf-8"
    )
    store.put("model_versions", version, metadata)
    if promote:
        store.put("active_models", key, {"version": version})
    return clean(metadata)


_CACHE = {}


def load(version):
    if version not in _CACHE:
        if len(_CACHE) > 20:
            _CACHE.clear()
        _CACHE[version] = joblib.load(DIR / (version + ".joblib"))
    return _CACHE[version]


def infer(df, symbol, tf, horizon, source):
    key = f"{source}:{symbol}:{tf}:{horizon}"
    active = store.get("active_models", key)

    def compatible(version):
        try:
            bundle = load(version)
        except Exception:
            return None
        meta = bundle.get("metadata", {})
        if (
            meta.get("feature_version") == FEATURE_VERSION
            and meta.get("target_version") == TARGET_VERSION
            and meta.get("features") == FEATURES
            and meta.get("promoted") is True
            and meta.get("source") == source
            and meta.get("symbol") == symbol
            and meta.get("timeframe") == tf
            and str(meta.get("horizon_bars")) == str(horizon)
        ):
            return bundle
        return None

    bundle = compatible(active["version"]) if active else None

    # Recover automatically when an old active pointer references a retired
    # feature schema. This keeps prediction safe after feature migrations.
    if bundle is None:
        candidates = [
            m for m in store.records("model_versions")
            if m.get("promoted") is True
            and m.get("feature_version") == FEATURE_VERSION
            and m.get("target_version") == TARGET_VERSION
            and m.get("features") == FEATURES
            and m.get("source") == source
            and m.get("symbol") == symbol
            and m.get("timeframe") == tf
            and str(m.get("horizon_bars")) == str(horizon)
        ]
        candidates.sort(key=lambda m: float(m.get("training_date", 0)), reverse=True)
        for meta in candidates:
            bundle = compatible(meta["version"])
            if bundle is not None:
                store.put("active_models", key, {"version": meta["version"]})
                active = {"version": meta["version"]}
                break

    if bundle is None:
        return None


    d, _, _ = build(df)
    if int(d.end_time.iloc[-1]) < bundle["metadata"]["history_end"]:
        raise ValueError(
            "Model cannot predict before its training/selection history ends"
        )
    x = d[FEATURES].iloc[[-1]].to_numpy()
    p = calibrated(bundle["model"], bundle["calibrator"], x)[0]
    rule = bundle["metadata"].get("decision_rule")
    pred = decision_labels(p.reshape(1, -1), rule)[0]
    r = {k: float(m.predict(x)[0]) for k, m in bundle["regressors"].items()}
    return dict(
        direction=LABELS[int(pred)],
        probability=float(p[int(pred)]),
        probabilities=dict(zip(LABELS, p.tolist())),
        estimates=r,
        model_version=active["version"],
        metrics=bundle["metadata"]["test"],
        decision_rule=rule,
        signal_confidence=(
            "HIGH" if p.max() >= 0.65 and (np.sort(p)[-1] - np.sort(p)[-2]) >= 0.15
            else "MEDIUM" if p.max() >= 0.55
            else "LOW"
        ),
        validation_status="VALIDATED",
        used_features=bundle["metadata"]["features"],
        trained_through=bundle["metadata"]["history_end"],
    )




