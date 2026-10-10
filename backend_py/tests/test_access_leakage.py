"""
Tests for P2 (road accessibility at arrival).

Run from backend_py:   python -m unittest tests.test_access_leakage -v
"""
import copy
import random
import unittest

import numpy as np

from services.access_eval import node_elevations, toy_network
from services.access_model import (AccessPredictor, FEATURES, build_dataset, forecast_feature, observed_features,
                                   split_by_group, train_and_evaluate)
from services.disruption_sim import make_events, road_profile, simulate_event, synthetic_monsoon_rain
from services.routing_engine import plan_route_predictive


def _setup(hours=24 * 40):
    net = toy_network()
    elev = node_elevations(net["settlements"])
    profiles = {r["id"]: road_profile(r, elev) for r in net["roads"]}
    prof_list = [profiles[r["id"]] for r in net["roads"]]
    events = make_events(synthetic_monsoon_rain(hours))
    sims = {e.event_id: simulate_event(e, prof_list) for e in events}
    return net, profiles, prof_list, events, sims


class LeakageTests(unittest.TestCase):
    def test_observed_features_ignore_the_future(self):
        net, profiles, prof_list, events, sims = _setup(24 * 20)
        ev = events[0]
        sim = sims[ev.event_id]
        t = 40
        for i, prof in enumerate(prof_list):
            before = observed_features(ev.rain, sim["closed"][i], sim["rep_hours"][i], sim["rep_signs"][i], prof, t)
            # Change EVERYTHING that happens at or after the decision time.
            rain2 = ev.rain.copy()
            rain2[t:] = rain2[t:] * 7 + 3.0
            closed2 = sim["closed"][i].copy()
            closed2[t:] = ~closed2[t:]
            rh2 = np.concatenate([sim["rep_hours"][i], [t, t + 1, t + 5]])
            rs2 = np.concatenate([sim["rep_signs"][i], [1, 1, -1]])
            after = observed_features(rain2, closed2, rh2, rs2, prof, t)
            self.assertEqual(before, after, f"observed features leaked future data for {prof['road_id']}")

    def test_forecast_is_the_only_look_ahead(self):
        rain = np.zeros(48)
        a = forecast_feature(rain, 10, 3, 1.0)
        rain[10:13] = 5.0
        b = forecast_feature(rain, 10, 3, 1.0)
        self.assertEqual(a, 0.0)
        self.assertGreater(b, 0.0)
        self.assertEqual(FEATURES.count("fc_rain_h"), 1)

    def test_train_and_test_share_no_rain_window(self):
        net, profiles, prof_list, events, sims = _setup()
        df = build_dataset(events, sims, prof_list, max_rows=8000)
        train, test = split_by_group(df, 0.3, seed=7)
        self.assertTrue(len(train) and len(test))
        self.assertFalse(set(train["group_id"]) & set(test["group_id"]))


class BehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.net, cls.profiles, cls.prof_list, cls.events, cls.sims = _setup()
        df = build_dataset(cls.events, cls.sims, cls.prof_list, max_rows=12000)
        res = train_and_evaluate(df, n_bootstrap=2, save_path=None)
        cls.predictor = AccessPredictor(bundle={"model": res["model"], "ensemble": res["ensemble"], "features": FEATURES})

    def _predict(self, roads):
        rain = {"rain_1h": 8, "rain_3h": 20, "rain_6h": 35, "rain_24h": 60, "fc_rain_h": 15}
        return self.predictor.predict(roads, self.profiles, rain, horizon_h=3)

    def test_confirmed_closure_is_binding(self):
        roads = copy.deepcopy(self.net["roads"])
        roads[0]["status"] = "BLOCKED"
        out = self._predict(roads)
        self.assertEqual(out["p"][roads[0]["id"]], 0.0)
        self.assertIn(roads[0]["id"], out["confirmedClosed"])

    def test_probabilities_are_valid(self):
        out = self._predict(copy.deepcopy(self.net["roads"]))
        for v in out["p"].values():
            self.assertTrue(0.0 <= v <= 1.0)

    def test_predictive_route_never_uses_a_blocked_road(self):
        rng = random.Random(3)
        net = self.net
        for trial in range(200):
            roads = copy.deepcopy(net["roads"])
            blocked = set(rng.sample([r["id"] for r in roads], k=rng.randint(1, 4)))
            for r in roads:
                r["status"] = "BLOCKED" if r["id"] in blocked else "OPEN"
            out = self._predict(roads)
            for res in net["resources"]:
                for s in net["settlements"]:
                    route = plan_route_predictive(res, {"id": s["id"], "name": s["name"]}, net["nodes"], roads,
                                                  out["p"], out["p_low"])
                    if route.get("escalationRequired"):
                        self.assertEqual(route["reliability"], 0.0)   # unreachable is flagged, never a fake route
                    else:
                        self.assertFalse(set(route["roadIds"]) & blocked, f"trial {trial}: used a blocked road")


if __name__ == "__main__":
    unittest.main()