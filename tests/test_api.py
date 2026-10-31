
import os
import tempfile
import unittest

from app import create_app


class TaskFlowAPITests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

        db_path = os.path.join(
            self.temp.name,
            "test.db"
        )

        self.app = create_app(
            start_workers=False,
            database_path=db_path
        )

        self.client = self.app.test_client()

    def tearDown(self):
        self.client = None
        self.app = None
        self.temp.cleanup()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")

    def test_create_task(self):
        response = self.client.post(
            "/api/tasks",
            json={
                "task_type": "echo",
                "priority": "high",
                "payload": {"message": "hello"}
            }
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["status"], "pending")
        self.assertEqual(response.json["priority"], "high")

    def test_reject_invalid_priority(self):
        response = self.client.post(
            "/api/tasks",
            json={
                "task_type": "echo",
                "priority": "urgent",
                "payload": {}
            }
        )

        self.assertEqual(response.status_code, 400)

    def test_reject_unknown_task_type(self):
        response = self.client.post(
            "/api/tasks",
            json={
                "task_type": "run_shell",
                "priority": "low",
                "payload": {}
            }
        )

        self.assertEqual(response.status_code, 400)

    def test_list_and_get_task(self):
        created = self.client.post(
            "/api/tasks",
            json={
                "task_type": "echo",
                "priority": "medium",
                "payload": {"message": "test"}
            }
        ).json

        tasks = self.client.get("/api/tasks").json["tasks"]

        self.assertEqual(len(tasks), 1)

        fetched = self.client.get(
            "/api/tasks/" + created["id"]
        )

        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json["id"], created["id"])

    def test_missing_task(self):
        response = self.client.get("/api/tasks/not-real")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
