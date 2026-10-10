"""
P2 pipeline: rain -> simulated closures -> features/labels -> model -> baseline vs predictive.

Run from the backend_py folder:

    python run_p2.py                      # real Open-Meteo archive rain + platform road network
    python run_p2.py --synthetic-rain     # offline rain (labelled SYNTHETIC)
    python run_p2.py --toy-network        # built-in toy road network (no platform data needed)
    python run_p2.py --model gbm          # gradient boosting instead of logistic regression

Outputs go to data/p2_outputs/:
    features_labels.csv          every feature row with its label and timestamps
    baseline_vs_predictive.csv   every simulated trip, both methods
    access_model_report.json     metrics, calibration, feature importance, comparison summary
and the trained model is saved to data/cache/access_model.joblib
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.access_eval import node_elevations, run_comparison, toy_network
from services.access_model import FEATURES, AccessPredictor, build_dataset, train_and_evaluate
from services.disruption_sim import fetch_archive_rain, make_events, road_profile, simulate_event, synthetic_monsoon_rain

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "p2_outputs")


def load_network(use_toy: bool):
    if use_toy:
        net = toy_network()
        return net["nodes"], net["roads"], net["settlements"], net["resources"], net["center"], "TOY_NETWORK"
    from services.data_processing import load_and_process
    ds = load_and_process(fetch_terrain=False)
    # If OpenStreetMap roads were loaded there can be thousands; cap at 60 roads so the run stays fast.
    roads = ds["roads"][:60]
    keep_nodes = {r["source"] for r in roads} | {r["destination"] for r in roads}
    nodes = {k: v for k, v in ds["nodes"].items() if k in keep_nodes}
    center = tuple(ds["district"]["center"])
    return nodes, roads, ds["settlements"], ds["resources"], center, "PLATFORM_DATASET"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic-rain", action="store_true")
    ap.add_argument("--toy-network", action="store_true")
    ap.add_argument("--model", default="logistic", choices=["logistic", "gbm"])
    ap.add_argument("--start", default="2025-06-01")
    ap.add_argument("--end", default="2025-09-30")
    ap.add_argument("--max-rows", type=int, default=150000)
    ap.add_argument("--risk-aversion", type=float, default=25.0,
                    help="km of extra driving worth one unit of -ln(P usable); higher = avoids risky roads more")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    nodes, roads, settlements, resources, (lat, lon), net_source = load_network(args.toy_network)
    print(f"[1/6] Road network: {net_source} ({len(roads)} roads, {len(settlements)} settlements)")

    series = None if args.synthetic_rain else fetch_archive_rain(lat, lon, args.start, args.end)
    if series is None:
        print("      Using SYNTHETIC rain (labelled as such in the report).")
        series = synthetic_monsoon_rain()
    print(f"[2/6] Rain source: {series['source']} ({len(series['rain'])} hours)")

    elev = node_elevations(settlements)
    profiles = {r["id"]: road_profile(r, elev) for r in roads}
    prof_list = [profiles[r["id"]] for r in roads]

    events = make_events(series)
    sims = {ev.event_id: simulate_event(ev, prof_list) for ev in events}
    closed_rate = sum(float(s["closed"].mean()) for s in sims.values()) / max(1, len(sims))
    print(f"[3/6] Simulated {len(events)} events; roads closed {closed_rate:.1%} of the time on average")

    df = build_dataset(events, sims, prof_list, max_rows=args.max_rows)
    df.to_csv(os.path.join(OUT_DIR, "features_labels.csv"), index=False)
    print(f"[4/6] Features/labels table: {len(df):,} rows -> features_labels.csv")

    result = train_and_evaluate(df, model_type=args.model)
    m = result["metrics"]
    print(f"[5/6] Model {args.model}: AUC {m['auc']} (current-status baseline {m['baselineCurrentStatusAuc']}), "
          f"Brier {m['brier']} (baseline {m['baselineCurrentStatusBrier']}), calibration error {m['calibration']['expectedCalibrationError']}")

    held = set(m["heldOutGroups"])
    test_events = [e for e in events if e.group_id in held]
    predictor = AccessPredictor(bundle={"model": result["model"], "ensemble": result["ensemble"],
                                        "features": FEATURES})
    comp = run_comparison(test_events, sims, roads, nodes, resources, settlements, predictor, profiles,
                          risk_aversion_km=args.risk_aversion)
    comp["trips"].to_csv(os.path.join(OUT_DIR, "baseline_vs_predictive.csv"), index=False)
    print("[6/6] Baseline vs predictive on held-out events:")
    print(json.dumps(comp["summary"], indent=2))

    report = {"rainSource": series["source"], "network": net_source,
              "labelNote": "Road closures are SIMULATED by a documented rule driven by rain; results are not real-world accuracy.",
              "metrics": m, "comparison": comp["summary"],
              "skippedUnreachableAtDecision": comp["skippedUnreachableAtDecision"]}
    with open(os.path.join(OUT_DIR, "access_model_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Done. Files in {OUT_DIR}")


if __name__ == "__main__":
    main()