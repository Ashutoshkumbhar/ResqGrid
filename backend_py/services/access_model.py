"""
Road-accessibility-at-arrival model (P2, Addition 2).

Question answered for every road segment:
    "Will this road still be usable when the team ARRIVES (decision time + h hours)?"
The model outputs a probability, not a yes/no.

No-leakage rule
---------------
Every OBSERVED feature is computed only from data with index < t (the decision
time). The only look-ahead is `fc_rain_h`, the rain FORECAST for the next h
hours (a noisy copy of the future rain, because real forecasts are imperfect).
A forecast is legitimately available at decision time. The label (road usable at
t + h) is the only thing that uses the future. tests/test_access_leakage.py
proves this by changing the future and checking the observed features stay equal.

Splitting rule: train and test sets are split by rain-window group (whole events),
never by random rows.
"""
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from services.disruption_sim import Event, _seed

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "cache"))
MODEL_PATH = os.path.join(CACHE_DIR, "access_model.joblib")

HORIZONS = (1, 2, 3, 6)
REPORT_HALF_LIFE_H = 3.0     # a report loses half its weight every 3 hours (stale reports fade)
FORECAST_NOISE_SIGMA = 0.35  # forecast error: log-normal noise on the true future rain

FEATURES = [
    "rain_1h", "rain_3h", "rain_6h", "rain_24h",      # observed rain up to decision time
    "fc_rain_h", "horizon_h",                          # forecast rain until arrival, hours ahead
    "is_bridge", "is_causeway", "flood_prone", "rel_elev_m", "distance_km",   # terrain / road type
    "closed_now", "hours_in_state",                    # last known status and how long it has lasted
    "report_signal", "reports_3h",                     # decayed citizen reports, recent report count
]


# ---------------------------------------------------------------- features
def observed_features(rain, closed, rep_hours, rep_signs, prof: Dict[str, Any], t: int) -> Dict[str, float]:
    """Everything known at decision time t. Uses ONLY indices < t."""
    past = np.asarray(rain, dtype=float)[:t]
    hist = np.asarray(closed, dtype=bool)[:t]
    last = bool(hist[-1]) if len(hist) else False
    tail = hist[-24:][::-1]
    if len(tail):
        diff = np.nonzero(tail != tail[0])[0]
        in_state = int(diff[0]) if diff.size else len(tail)
    else:
        in_state = 24
    rh = np.asarray(rep_hours, dtype=float)
    rs = np.asarray(rep_signs, dtype=float)
    seen = rh < t
    age = (t - 1) - rh[seen]
    weight = 0.5 ** (age / REPORT_HALF_LIFE_H)
    return {
        "rain_1h": float(past[-1:].sum()), "rain_3h": float(past[-3:].sum()),
        "rain_6h": float(past[-6:].sum()), "rain_24h": float(past[-24:].sum()),
        "is_bridge": prof["is_bridge"], "is_causeway": prof["is_causeway"], "flood_prone": prof["flood_prone"],
        "rel_elev_m": prof["rel_elev_m"], "distance_km": prof["distance_km"],
        "closed_now": float(last), "hours_in_state": float(in_state),
        "report_signal": float((rs[seen] * weight).sum()),
        "reports_3h": float((age <= 3).sum()),
    }


def forecast_feature(rain, t: int, h: int, noise: float) -> float:
    """Rain FORECAST for the next h hours: true future rain times a noisy error factor."""
    return float(np.asarray(rain, dtype=float)[t:t + h].sum() * noise)


def _forecast_noise(event_id: str, t: int, h: int) -> float:
    rng = np.random.default_rng(_seed("fc", event_id, t, h))
    return float(rng.lognormal(0.0, FORECAST_NOISE_SIGMA))


# ---------------------------------------------------------------- dataset
def build_dataset(events: List[Event], sims: Dict[str, Dict[str, Any]], profiles: List[Dict[str, Any]],
                  decision_step: int = 3, min_t: int = 24, horizons=HORIZONS,
                  max_rows: Optional[int] = None, seed: int = 0) -> pd.DataFrame:
    """One row per (event, road, decision hour, horizon). Label: usable_at_arrival (1 = usable)."""
    rows: List[Dict[str, Any]] = []
    for ev in events:
        sim = sims[ev.event_id]
        closed = sim["closed"]
        T = closed.shape[1]
        t0 = datetime.fromisoformat(ev.start_time)
        for t in range(min_t, T - 1, decision_step):
            for i, prof in enumerate(profiles):
                obs = observed_features(ev.rain, closed[i], sim["rep_hours"][i], sim["rep_signs"][i], prof, t)
                for h in horizons:
                    if t + h >= T:
                        continue
                    row = {
                        "event_id": ev.event_id, "group_id": ev.group_id, "scale": ev.scale,
                        "road_id": prof["road_id"], "t": t,
                        "decision_time": (t0 + timedelta(hours=t)).isoformat(timespec="minutes"),
                        "arrival_time": (t0 + timedelta(hours=t + h)).isoformat(timespec="minutes"),
                        **obs,
                        "fc_rain_h": forecast_feature(ev.rain, t, h, _forecast_noise(ev.event_id, t, h)),
                        "horizon_h": float(h),
                        "usable_at_arrival": int(not closed[i, t + h]),
                        "rain_source_note": "real hourly rain x scale; closures simulated",
                    }
                    rows.append(row)
    df = pd.DataFrame(rows)
    if max_rows and len(df) > max_rows:
        df = df.sample(max_rows, random_state=seed).sort_values(["event_id", "t"]).reset_index(drop=True)
    return df


def split_by_group(df: pd.DataFrame, test_frac: float = 0.3, seed: int = 7) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Whole rain-window groups go to train OR test, never both."""
    groups = sorted(df["group_id"].unique())
    rng = np.random.default_rng(seed)
    rng.shuffle(groups)
    n_test = max(1, int(round(len(groups) * test_frac)))
    test_groups = set(groups[:n_test])
    mask = df["group_id"].isin(test_groups)
    return df[~mask].copy(), df[mask].copy()


# ---------------------------------------------------------------- model
def make_model(model_type: str = "logistic"):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if model_type == "gbm":
        return GradientBoostingClassifier(n_estimators=150, max_depth=3, random_state=7)
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))


def calibration_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> Dict[str, Any]:
    """When we say 70% usable, are about 70% of those roads really usable?"""
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, n_bins - 1)
    rows, ece = [], 0.0
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        mp, obs = float(p[m].mean()), float(y[m].mean())
        ece += m.mean() * abs(mp - obs)
        rows.append({"bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}", "n": int(m.sum()),
                     "meanPredictedUsable": round(mp, 3), "observedUsable": round(obs, 3)})
    return {"expectedCalibrationError": round(float(ece), 4), "bins": rows}


def train_and_evaluate(df: pd.DataFrame, model_type: str = "logistic", test_frac: float = 0.3,
                       seed: int = 7, n_bootstrap: int = 8, save_path: Optional[str] = MODEL_PATH) -> Dict[str, Any]:
    from sklearn.base import clone
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import brier_score_loss, roc_auc_score
    import joblib

    train, test = split_by_group(df, test_frac, seed)
    assert not (set(train["group_id"]) & set(test["group_id"])), "group leakage between train and test"
    X_tr, y_tr = train[FEATURES].values, train["usable_at_arrival"].values
    X_te, y_te = test[FEATURES].values, test["usable_at_arrival"].values

    model = make_model(model_type)
    model.fit(X_tr, y_tr)
    p = model.predict_proba(X_te)[:, 1]
    p_persist = 1.0 - test["closed_now"].values   # "current status only" baseline

    metrics = {
        "modelType": model_type,
        "trainRows": int(len(train)), "testRows": int(len(test)),
        "trainGroups": int(train["group_id"].nunique()), "testGroups": int(test["group_id"].nunique()),
        "closedRateTest": round(float(1 - y_te.mean()), 4),
        "auc": round(float(roc_auc_score(y_te, p)), 4),
        "brier": round(float(brier_score_loss(y_te, p)), 4),
        "baselineCurrentStatusAuc": round(float(roc_auc_score(y_te, p_persist)), 4),
        "baselineCurrentStatusBrier": round(float(brier_score_loss(y_te, p_persist)), 4),
    }
    metrics["calibration"] = calibration_table(y_te, p)

    sample = np.random.default_rng(seed).choice(len(X_te), size=min(20000, len(X_te)), replace=False)
    imp = permutation_importance(model, X_te[sample], y_te[sample], scoring="roc_auc", n_repeats=5, random_state=seed)
    order = np.argsort(-imp.importances_mean)
    metrics["featureImportance"] = [{"feature": FEATURES[i], "aucDrop": round(float(imp.importances_mean[i]), 4)} for i in order]

    # Small bootstrap ensemble -> a rough uncertainty (std of p) for each road. Resamples whole groups.
    ensemble = []
    groups = np.array(sorted(train["group_id"].unique()))
    rng = np.random.default_rng(seed)
    for _ in range(n_bootstrap):
        pick = rng.choice(groups, size=len(groups), replace=True)
        boot = pd.concat([train[train["group_id"] == g] for g in pick], ignore_index=True)
        m = clone(model)
        m.fit(boot[FEATURES].values, boot["usable_at_arrival"].values)
        ensemble.append(m)

    bundle = {"model": model, "ensemble": ensemble, "features": FEATURES,
              "meta": {"modelType": model_type, "metrics": {k: v for k, v in metrics.items() if k not in ("calibration", "featureImportance")}}}
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        joblib.dump(bundle, save_path)
    metrics["heldOutGroups"] = sorted(test["group_id"].unique())
    return {"metrics": metrics, "model": model, "ensemble": ensemble, "train": train, "test": test}


# ---------------------------------------------------------------- inference (used by the live platform)
def approx_rain_features(rain_24h_mm: float, intensity_mm_h: float, forecast_next_h_mm: Optional[float] = None,
                         horizon_h: int = 3) -> Dict[str, float]:
    """
    BRIDGE until hourly rain is wired in: build rain aggregates from the numbers the platform already has
    (24 h accumulation and peak mm/h). It is an approximation and should be labelled as one in the UI.
    """
    r24 = float(rain_24h_mm)
    r1 = min(r24, float(intensity_mm_h))
    r3 = min(r24, float(intensity_mm_h) * 2.2)
    r6 = min(r24, float(intensity_mm_h) * 3.5)
    fc = float(forecast_next_h_mm) if forecast_next_h_mm is not None else float(intensity_mm_h) * horizon_h * 0.6
    return {"rain_1h": r1, "rain_3h": r3, "rain_6h": r6, "rain_24h": r24, "fc_rain_h": fc}


class AccessPredictor:
    """Loads the saved model and gives P(road usable at arrival) for every road."""

    def __init__(self, path: str = MODEL_PATH, bundle: Optional[Dict[str, Any]] = None):
        if bundle is None:
            import joblib
            bundle = joblib.load(path)
        self.model = bundle["model"]
        self.ensemble = bundle.get("ensemble") or []
        self.features = bundle["features"]
        self.meta = bundle.get("meta", {})

    def predict(self, roads: List[Dict[str, Any]], profiles: Dict[str, Dict[str, Any]], rain: Dict[str, float],
                horizon_h: int, road_state: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, Dict[str, float]]:
        """
        roads        : platform road dicts (status OPEN / AT_RISK / BLOCKED)
        profiles     : road_id -> disruption_sim.road_profile(...)
        rain         : rain_1h, rain_3h, rain_6h, rain_24h, fc_rain_h (see approx_rain_features)
        road_state   : optional road_id -> {"hours_in_state", "report_signal", "reports_3h"}
        Returns {"p": {road: P(usable)}, "p_low": {road: mean - 1 std}, "confirmedClosed": [...]}.
        A CONFIRMED closure (status BLOCKED) is binding: probability 0 until the platform
        reopens it with newer verified evidence.
        """
        road_state = road_state or {}
        rows, ids = [], []
        for r in roads:
            prof = profiles[r["id"]]
            st = road_state.get(r["id"], {})
            row = {**rain, **{k: prof[k] for k in ("is_bridge", "is_causeway", "flood_prone", "rel_elev_m", "distance_km")},
                   "horizon_h": float(horizon_h), "closed_now": float(r["status"] == "BLOCKED"),
                   "hours_in_state": float(st.get("hours_in_state", 24.0)),
                   "report_signal": float(st.get("report_signal", 0.0)), "reports_3h": float(st.get("reports_3h", 0.0))}
            rows.append([row[f] for f in self.features])
            ids.append(r["id"])
        X = np.asarray(rows, dtype=float)
        p = self.model.predict_proba(X)[:, 1]
        if self.ensemble:
            stack = np.vstack([m.predict_proba(X)[:, 1] for m in self.ensemble])
            std = stack.std(axis=0)
        else:
            std = np.zeros_like(p)
        p_low = np.clip(p - std, 0.0, 1.0)
        confirmed = [r["id"] for r in roads if r["status"] == "BLOCKED"]
        out_p = {rid: float(v) for rid, v in zip(ids, p)}
        out_low = {rid: float(v) for rid, v in zip(ids, p_low)}
        for rid in confirmed:       # binding closure
            out_p[rid] = 0.0
            out_low[rid] = 0.0
        return {"p": out_p, "p_low": out_low, "confirmedClosed": confirmed}