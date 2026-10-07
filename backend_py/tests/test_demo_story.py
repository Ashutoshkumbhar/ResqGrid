import unittest

from fastapi.testclient import TestClient

from main import app


class DemoStoryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_demo_start_endpoint_exists_and_returns_user_facing_payload(self):
        response = self.client.post("/api/demo/start")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIn("demo", payload)
        self.assertIn("narration", payload["demo"])
        self.assertIn("updatedState", payload)
        self.client.post("/api/demo/stop")

    def test_demo_story_is_deterministic_and_has_narration_steps(self):
        start = self.client.post("/api/demo/start")
        self.assertEqual(start.status_code, 200, start.text)
        demo = start.json()["demo"]
        self.assertTrue(demo["steps"], "demo should include at least one scheduled step")
        self.assertTrue(all(isinstance(step["narration"], str) for step in demo["steps"]))
        self.assertEqual(demo["steps"][0]["step"], 0)
        stop = self.client.post("/api/demo/stop")
        self.assertEqual(stop.status_code, 200, stop.text)

    def test_impact_compare_returns_metrics_for_both_strategies(self):
        response = self.client.get("/api/impact/compare")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("withResQGrid", payload)
        self.assertIn("withoutResQGrid", payload)
        for key in ["villagesReached", "totalPopulationReached", "averageResponseTimeMinutes", "villagesMissed", "wastedDispatches"]:
            self.assertIn(key, payload["withResQGrid"])
            self.assertIn(key, payload["withoutResQGrid"])
        self.assertTrue(payload["withResQGrid"]["villagesReached"] >= payload["withoutResQGrid"]["villagesReached"])

    def test_forecast_endpoint_returns_risk_profile_for_each_settlement(self):
        response = self.client.get("/api/forecast")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("settlements", payload)
        self.assertIn("hours", payload)
        self.assertTrue(payload["settlements"])
        first_settlement = next(iter(payload["settlements"].values()))
        self.assertIn("riskByHour", first_settlement)
        self.assertIn("firstHighHour", first_settlement)
        self.assertIn("firstCriticalHour", first_settlement)

    def test_data_sources_are_exposed_for_roads_elevation_and_weather(self):
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("dataSources", payload)
        self.assertIn("roads", payload["dataSources"])
        self.assertIn("elevation", payload["dataSources"])
        self.assertIn("weather", payload["dataSources"])
        self.assertIn("Live", str(payload["dataSources"]["weather"]))

    def test_alert_message_builds_multilingual_templates_and_manual_send_endpoint(self):
        response = self.client.post("/api/alerts/send", json={"settlementId": "S2", "language": "hi", "recipient": "+919999999999"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("message", payload)
        self.assertIn("language", payload)
        self.assertIn("settlementId", payload)
        self.assertIn("S2", payload["message"])
        history = self.client.get("/api/alerts")
        self.assertEqual(history.status_code, 200, history.text)
        self.assertTrue(history.json())

    def test_photo_report_endpoint_accepts_image_and_returns_manual_review_payload(self):
        response = self.client.post(
            "/api/reports/photo",
            data={
                "text": "Road is flooded and water is ankle deep near the bridge",
                "latitude": "18.57",
                "longitude": "73.78",
            },
            files={"image": ("report.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("report", payload)
        self.assertIn("parsed", payload)
        self.assertIn("manualReview", payload["parsed"])

    def test_priority_engine_counts_vulnerable_population_and_evacuation_endpoint_exists(self):
        settlement = next(s for s in self.client.get("/api/settlements").json() if s["id"] == "S2")
        self.assertIn("vulnerablePopulation", settlement)
        self.assertGreater(settlement["vulnerablePopulation"], 0)
        response = self.client.get("/api/evacuation/S2")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("settlementId", payload)
        self.assertIn("shelter", payload)
        self.assertIn("route", payload)

    def test_audit_and_accuracy_endpoints_expose_trust_metrics(self):
        audit_response = self.client.get("/api/audit")
        self.assertEqual(audit_response.status_code, 200, audit_response.text)
        self.assertIsInstance(audit_response.json(), list)

        accuracy_response = self.client.get("/api/accuracy")
        self.assertEqual(accuracy_response.status_code, 200, accuracy_response.text)
        payload = accuracy_response.json()
        self.assertIn("precisionPercent", payload)
        self.assertIn("recallPercent", payload)
        self.assertIn("averageLeadTimeMinutes", payload)
        self.assertIn("confusionMatrix", payload)


if __name__ == "__main__":
    unittest.main()
