import json
import threading
import unittest
import urllib.error
import urllib.request

from sessionread import Reader
from server import serve

class TestReader(unittest.TestCase):
    def test_report_counts(self):
        reader = Reader()
        self.assertEqual(reader.report("n1", 5)["replicas"], 1)

    def test_read_without_replicas(self):
        self.assertIsNone(Reader().read("c1")["node"])

    def test_read_returns_node(self):
        reader = Reader()
        reader.report("n1", 5)
        self.assertEqual(reader.read("c1")["node"], "n1")

    def test_stats_shape(self):
        self.assertIn("max_lag", Reader().stats())

    def test_http_report_read(self):
        server = serve(0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
        urllib.request.urlopen(base + "/report", data=b'{"node": "n1", "applied": 3}', timeout=5).read()
        with urllib.request.urlopen(base + "/read", data=b'{"client": "c1"}', timeout=5) as response:
            self.assertEqual(json.loads(response.read())["node"], "n1")
        server.shutdown()
