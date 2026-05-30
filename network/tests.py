import json

from django.test import Client, TestCase

from .models import RouteHistory


class NetworkApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def post_json(self, path, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def create_node(self, name):
        return self.post_json("/nodes", {"name": name})

    def create_edge(self, source, destination, latency):
        return self.post_json(
            "/edges",
            {"source": source, "destination": destination, "latency": latency},
        )

    def test_shortest_route_and_history(self):
        for name in ["ServerA", "ServerB", "ServerC", "ServerD"]:
            response = self.create_node(name)
            self.assertEqual(response.status_code, 201)

        self.create_edge("ServerA", "ServerB", 10)
        self.create_edge("ServerB", "ServerD", 13.4)
        self.create_edge("ServerA", "ServerC", 50)
        self.create_edge("ServerC", "ServerD", 1)

        response = self.post_json(
            "/routes/shortest",
            {"source": "ServerA", "destination": "ServerD"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"total_latency": 23.4, "path": ["ServerA", "ServerB", "ServerD"]},
        )
        self.assertEqual(RouteHistory.objects.count(), 1)

        history_response = self.client.get("/routes/history?source=ServerA&limit=1")
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response.json()[0]["path"], ["ServerA", "ServerB", "ServerD"])

    def test_validation_and_no_path(self):
        self.assertEqual(self.post_json("/nodes", {}).status_code, 400)
        self.assertEqual(self.create_node("ServerA").status_code, 201)
        self.assertEqual(self.create_node("ServerA").status_code, 400)
        self.assertEqual(self.create_node("ServerB").status_code, 201)
        self.assertEqual(self.create_node("ServerC").status_code, 201)

        self.assertEqual(self.create_edge("ServerA", "ServerB", 0).status_code, 400)
        self.assertEqual(self.create_edge("ServerA", "ServerB", 12.5).status_code, 201)
        self.assertEqual(self.create_edge("ServerB", "ServerA", 12.5).status_code, 400)

        response = self.post_json(
            "/routes/shortest",
            {"source": "ServerA", "destination": "ServerC"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(RouteHistory.objects.count(), 0)
