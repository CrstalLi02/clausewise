"""Compare k6 JSON summaries for 1 replica vs. 20 replicas to validate scale-out throughput."""
import json
import sys

one = json.load(open(sys.argv[1], encoding="utf-8"))
twenty = json.load(open(sys.argv[2], encoding="utf-8"))

def metric(data, name, key):
    return float(data["metrics"][name]["values"][key])

one_rate = metric(one, "http_reqs", "rate")
twenty_rate = metric(twenty, "http_reqs", "rate")
one_p95 = metric(one, "http_req_duration", "p(95)")
twenty_p95 = metric(twenty, "http_req_duration", "p(95)")
gain = twenty_rate / max(one_rate, 0.0001)
print(json.dumps({"one_rps": one_rate, "twenty_rps": twenty_rate, "throughput_gain": gain,
                  "one_p95_ms": one_p95, "twenty_p95_ms": twenty_p95}, ensure_ascii=False, indent=2))
if gain < 2.0:
    raise SystemExit(1)
