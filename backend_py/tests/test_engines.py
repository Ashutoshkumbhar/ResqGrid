import unittest

from fastapi.testclient import TestClient

from main import app
from services.priority_engine import calculate_priority
from services.risk_engine import calculate_flood_risk
from services.routing_engine import plan_route


class EngineRegressionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_risk_engine_calculates_explainable_score(self):
        settlement = {
            "id": "S2",
            "name": "Village B (Sangvi Riverside)",
            "population": 4200,
            "rainfall": 125,
            "rainfallIntensity": 22,
            "relativeElevation": 12,
            "elevation": 535,
            "terrainClass": "lowland",
            "waterLevelMeters": 1.4,
            "waterLevel": "ALERT",
            "accessibility": "AT_RISK",
        }
        reports = [{"severity": "HIGH", "text": "Water entered homes and the bridge is blocked."}]

        risk = calculate_flood_risk(settlement, reports)

        self.assertIn("riskStatus", risk)
        self.assertGreater(risk["riskScore"], 0)
        self.assertTrue(risk["riskFactors"])
        self.assertTrue(risk["evidence"])

    def test_priority_engine_scores_urgent_settlements(self):
        settlement = {
            "population": 3000,
            "riskScore": 82,
            "riskStatus": "HIGH",
        }

        priority = calculate_priority(settlement, [{"severity": "HIGH"}], "ALTERNATIVE", [])

        self.assertGreater(priority["responsePriority"], 50)
        self.assertIn("routeFeasibility", priority)
        self.assertIn("priorityFactors", priority)

    def test_routing_engine_plans_valid_route(self):
        nodes = {
            "N1": {"id": "N1", "name": "Base Depot"},
            "N2": {"id": "N2", "name": "Village B"},
            "N3": {"id": "N3", "name": "Alternate Route"},
        }
        roads = [
            {"id": "R1", "name": "Main access", "source": "N1", "destination": "N2", "distanceKm": 5.0, "status": "OPEN", "coordinates": [[0, 0], [1, 1]]},
            {"id": "R2", "name": "Loop road", "source": "N1", "destination": "N3", "distanceKm": 7.0, "status": "OPEN", "coordinates": [[0, 0], [2, 1]]},
            {"id": "R3", "name": "Final connector", "source": "N3", "destination": "N2", "distanceKm": 3.0, "status": "OPEN", "coordinates": [[2, 1], [1, 1]]},
        ]
        resource = {"id": "RES-1", "name": "Rescue Team", "locationName": "Base Depot", "nodeId": "N1", "speedKmh": 25}
        target = {"id": "N2", "name": "Village B"}

        result = plan_route(resource, target, nodes, roads, use_osrm=False)

        self.assertEqual(result["originalRouteStatus"], "VALID")
        self.assertGreater(result["distanceKm"], 0)
        self.assertIsNotNone(result["etaMinutes"])

    def test_demo_start_endpoint_returns_payload(self):
        response = self.client.post("/api/demo/start")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIn("demo", payload)
        self.assertIn("narration", payload["demo"])
        self.assertTrue(payload["demo"]["steps"])
        self.client.post("/api/demo/stop")


if __name__ == "__main__":
    unittest.main()
