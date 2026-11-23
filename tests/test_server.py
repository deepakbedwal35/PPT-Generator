import json
import threading
import unittest
import urllib.error
import urllib.request

from deck_maker.server import Handler, ThreadingHTTPServer


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_get_config(self):
        with urllib.request.urlopen(f"{self.url}/api/config") as response:
            self.assertEqual(response.status, 200)
            data = json.load(response)
            self.assertIn("generate", data)
            self.assertIn("compile", data)

    def test_get_api_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.url}/api/nonexistent")
        self.assertEqual(ctx.exception.code, 404)

    def test_static_sample_tex(self):
        with urllib.request.urlopen(f"{self.url}/sample.tex") as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"documentclass", response.read())

    def test_cross_origin_blocked(self):
        req = urllib.request.Request(
            f"{self.url}/api/compile",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": "http://malicious-site.com"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
