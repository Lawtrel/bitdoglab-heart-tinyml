from email.message import Message
import io
import json
import unittest
from unittest.mock import Mock
from heart_tinyml.web.server import make_handler

class HttpBoundaryTests(unittest.TestCase):
    def request(self, path, *, method="GET", token="session", host="127.0.0.1:8766", origin=None, body=b"{}", length=None):
        controller = Mock()
        controller.post.return_value = {"ok": True}
        handler_type = make_handler(controller, "session", 8766, 100)
        handler = object.__new__(handler_type)
        handler.path = path
        handler.headers = Message()
        handler.headers["Host"] = host
        handler.headers["X-Demo-Token"] = token
        handler.headers["Content-Length"] = str(len(body) if length is None else length)
        if origin:
            handler.headers["Origin"] = origin
        handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
        response = {"headers": {}}
        handler.send_response = lambda code: response.update(code=code)
        handler.send_header = lambda name, value: response["headers"].update({name: value})
        handler.end_headers = lambda: None
        getattr(handler, "do_" + method)()
        response["body"] = handler.wfile.getvalue()
        return response, controller

    def test_root_injects_csrf_nonce_without_a_secret_url(self):
        response, _ = self.request("/")
        self.assertEqual(response["code"], 200)
        self.assertIn(b'content="session"', response["body"])
        self.assertNotIn(b"__DEMO_NONCE__", response["body"])
        self.assertIn("frame-ancestors 'none'", response["headers"]["Content-Security-Policy"])

    def test_wrong_host_token_and_cross_origin_are_rejected(self):
        for patch in ({"host": "attacker.test:8766"}, {"token": "wrong"}, {"origin": "https://attacker.test"}):
            response, controller = self.request("/api/analyze", method="POST", **patch)
            self.assertEqual(response["code"], 403)
            controller.post.assert_not_called()

    def test_oversized_and_invalid_json_are_rejected(self):
        for patch in ({"length": 101}, {"body": b"bad JSON"}):
            response, controller = self.request("/api/analyze", method="POST", **patch)
            self.assertEqual(response["code"], 400)
            controller.post.assert_not_called()

    def test_valid_post_is_dispatched(self):
        response, controller = self.request("/api/connect", method="POST")
        self.assertEqual(response["code"], 200)
        controller.post.assert_called_once_with("/api/connect", {})

    def test_non_allowlisted_paths_cannot_read_arbitrary_files(self):
        for path in ("/../pyproject.toml", "/model/model_int8.tflite", "/.env"):
            response, _ = self.request(path)
            self.assertEqual(response["code"], 404)
