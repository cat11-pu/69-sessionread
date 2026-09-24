"""check_http.py：起服务、按脚本走一圈，打印验收面。"""
import json
import sys
import threading
import urllib.error
import urllib.request

from server import serve


def call(method, url, body=None):
    request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def parse(text):
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": (text or "")[:60]}


def main() -> int:
    spec = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "sample/reads.json", encoding="utf-8"))
    server = serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_port
    for step in spec["ops"]:
        route = step["op"]
        call("POST", base + "/" + route, json.dumps(step).encode())
    traced = []
    for step in spec["trace"]:
        result = parse(call("POST", base + "/read", json.dumps(step).encode())[1])
        traced.append((step["client"], result.get("node"), result.get("applied")))
    stats = parse(call("GET", base + "/")[1])
    recovered = parse(call("POST", base + "/recover", b"{}")[1])
    print("读轨迹（客户端, 副本, 已应用序号） =", traced)
    print("粘滞切换次数 =", stats.get("switches"))
    print("因落后被拒的次数 =", stats.get("stale"))
    print("各客户端绑定的副本 =", stats.get("sticky"))
    print("恢复后的绑定 =", recovered.get("sticky"))
    print("最大允许落后 =", stats.get("max_lag"))
    print("不变量（同客户端读到的序号单调不减） =", spec["monotonic_read_invariant"])
    print("客户端数 =", spec["clients"])
    server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
