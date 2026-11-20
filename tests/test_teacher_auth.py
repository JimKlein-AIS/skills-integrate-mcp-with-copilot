import http.client
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import app
import teacher_auth


class TeacherAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.original_file = teacher_auth.TEACHERS_FILE
        teacher_auth.TEACHERS_FILE = Path(cls.tempdir.name) / "teachers.json"
        salt = "01" * 16
        teacher_auth.TEACHERS_FILE.write_text(json.dumps({
            "teacher": {"salt": salt, "hash": teacher_auth.password_hash("correct", salt)}
        }))
        cls.socket = socket.socket()
        cls.socket.bind(("127.0.0.1", 0))
        cls.socket.listen()
        cls.port = cls.socket.getsockname()[1]
        cls.server = uvicorn.Server(uvicorn.Config(app.app, log_level="error"))
        cls.thread = threading.Thread(target=cls.server.run, kwargs={"sockets": [cls.socket]}, daemon=True)
        cls.thread.start()
        deadline = time.monotonic() + 5
        while not cls.server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        if not cls.server.started:
            raise RuntimeError("Test server failed to start")

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(timeout=5)
        teacher_auth.TEACHERS_FILE = cls.original_file
        cls.tempdir.cleanup()

    def setUp(self):
        app.sessions.clear()
        self.participants = list(app.activities["Chess Club"]["participants"])

    def tearDown(self):
        app.activities["Chess Club"]["participants"] = self.participants

    def request(self, method, path, body=None, cookie=None, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if body is not None:
            body = json.dumps(body)
            headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
        if origin:
            headers["Origin"] = origin
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        data = json.loads(response.read())
        result = response.status, data, response.getheader("Set-Cookie")
        connection.close()
        return result

    def login(self):
        status, _, cookie = self.request("POST", "/auth/login", {
            "username": "teacher", "password": "correct"
        })
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        return cookie.split(";", 1)[0]

    def test_public_read_and_protected_mutations(self):
        status, activities, _ = self.request("GET", "/activities")
        self.assertEqual(status, 200)
        self.assertIn("michael@mergington.edu", activities["Chess Club"]["participants"])
        for method, action in [("POST", "signup"), ("DELETE", "unregister")]:
            status, _, _ = self.request(method, f"/activities/Chess%20Club/{action}?email=michael%40mergington.edu")
            self.assertEqual(status, 401)
        self.assertEqual(app.activities["Chess Club"]["participants"], self.participants)

    def test_login_registration_logout_and_session_revocation(self):
        status, _, _ = self.request("POST", "/auth/login", {"username": "teacher", "password": "wrong"})
        self.assertEqual(status, 401)
        cookie = self.login()
        status, session, _ = self.request("GET", "/auth/session", cookie=cookie)
        self.assertEqual((status, session["username"]), (200, "teacher"))
        path = "/activities/Chess%20Club/signup?email=new%40mergington.edu"
        self.assertEqual(self.request("POST", path, cookie=cookie)[0], 200)
        path = "/activities/Chess%20Club/unregister?email=new%40mergington.edu"
        self.assertEqual(self.request("DELETE", path, cookie=cookie)[0], 200)
        self.assertEqual(self.request("POST", "/auth/logout", cookie=cookie)[0], 200)
        self.assertEqual(self.request("DELETE", path, cookie=cookie)[0], 401)

    def test_expired_session_and_cross_origin_requests_are_rejected(self):
        cookie = self.login()
        path = "/activities/Chess%20Club/unregister?email=michael%40mergington.edu"
        self.assertEqual(self.request("DELETE", path, cookie=cookie, origin="https://other.example")[0], 403)
        self.assertEqual(self.request("POST", "/auth/login", {
            "username": "teacher", "password": "correct"
        }, origin="https://other.example")[0], 403)
        token = cookie.split("=", 1)[1]
        app.sessions[token] = ("teacher", time.time() - 1)
        self.assertEqual(self.request("DELETE", path, cookie=cookie)[0], 401)
        self.assertEqual(app.activities["Chess Club"]["participants"], self.participants)

    def test_missing_credentials_is_reported(self):
        original = teacher_auth.TEACHERS_FILE
        teacher_auth.TEACHERS_FILE = original.parent / "missing.json"
        try:
            status, data, _ = self.request("POST", "/auth/login", {
                "username": "teacher", "password": "correct"
            })
            self.assertEqual(status, 503)
            self.assertIn("not configured", data["detail"])
        finally:
            teacher_auth.TEACHERS_FILE = original

    def test_provisioned_credentials_are_hashed_and_private(self):
        original = teacher_auth.TEACHERS_FILE
        teacher_auth.TEACHERS_FILE = original.parent / "provisioned.json"
        try:
            with patch.object(sys, "argv", ["teacher_auth.py", "new-teacher"]), \
                 patch("getpass.getpass", side_effect=["new-password", "new-password"]):
                teacher_auth.main()
            contents = teacher_auth.TEACHERS_FILE.read_text()
            self.assertNotIn("new-password", contents)
            self.assertEqual(teacher_auth.TEACHERS_FILE.stat().st_mode & 0o777, 0o600)
            self.assertTrue(teacher_auth.authenticate("new-teacher", "new-password"))
            self.assertFalse(teacher_auth.authenticate("new-teacher", "wrong"))
        finally:
            teacher_auth.TEACHERS_FILE = original


if __name__ == "__main__":
    unittest.main()
