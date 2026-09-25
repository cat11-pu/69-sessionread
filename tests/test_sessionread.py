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

    def test_first_read_binds_freshest(self):
        reader = Reader()
        reader.report("n1", 10)
        reader.report("n2", 11)
        reader.report("n3", 11)
        self.assertEqual(reader.read("c1")["node"], "n2")
        self.assertEqual(reader.stats()["sticky"]["c1"], "n2")

    def test_sticky_until_required_unmet(self):
        reader = Reader()
        reader.report("n1", 10)
        reader.report("n2", 4)
        reader.report("n3", 11)
        reader.bind("c1", "n2")
        self.assertEqual(reader.read("c1")["node"], "n2")
        result = reader.read("c1", 11)
        self.assertEqual(result["node"], "n3")
        self.assertEqual(reader.stats()["switches"], 1)
        self.assertEqual(reader.read("c1", 11)["node"], "n3")
        self.assertEqual(reader.stats()["switches"], 1)

    def test_stale_counted_but_returned(self):
        reader = Reader(max_lag=3)
        reader.report("n1", 11)
        reader.report("n2", 4)
        reader.bind("c1", "n2")
        result = reader.read("c1")
        self.assertEqual(result, {"node": "n2", "applied": 4})
        self.assertEqual(reader.stats()["stale"], 1)

    def test_monotonic_per_client(self):
        reader = Reader()
        reader.report("n1", 10)
        reader.report("n2", 4)
        reader.report("n3", 11)
        reader.bind("c1", "n2")
        seen = [reader.read("c1", required)["applied"] for required in (0, 11, 11)]
        self.assertEqual(seen, [4, 11, 11])
        self.assertEqual(all(b >= a for a, b in zip(seen, seen[1:])), True)

    def test_switch_target_ordering(self):
        reader = Reader(max_lag=3)
        reader.report("n1", 10)
        reader.report("n2", 4)
        reader.report("n3", 11)
        reader.report("n4", 11)
        reader.bind("c1", "n2")
        self.assertEqual(reader.read("c1", 11)["node"], "n3")

    def test_persist_restore_roundtrip(self):
        reader = Reader(max_lag=3)
        reader.report("n1", 10)
        reader.report("n2", 4)
        reader.report("n3", 11)
        reader.bind("c1", "n2")
        reader.read("c1")
        reader.read("c1", 11)
        blob = reader.persist()
        rebooted = Reader()
        rebooted.restore(blob)
        self.assertEqual(rebooted.stats(), reader.stats())

    def test_recover_via_http(self):
        server = serve(0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
        urllib.request.urlopen(base + "/report", data=b'{"node": "n1", "applied": 10}', timeout=5).read()
        urllib.request.urlopen(base + "/bind", data=b'{"client": "c1", "node": "n1"}', timeout=5).read()
        with urllib.request.urlopen(base + "/recover", data=b"{}", timeout=5) as response:
            recovered = json.loads(response.read())
        self.assertEqual(recovered["sticky"], {"c1": "n1"})
        server.shutdown()
