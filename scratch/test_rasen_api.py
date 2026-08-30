"""Full diagnostic: checks /calls/{id} transcript + /analysis + /recording."""
import urllib.request
import json

KEY = "rkw_live_fy2774ye.-CVmtJZSYhOCOQasPD0PQpz0mEfeHtU2iqLpXlxqWIg"
BASE = "https://kalpa-api-454269687527.asia-south1.run.app/api/rasen/workspace"
HDR = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def get(path):
    req = urllib.request.Request(BASE + path, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)


# Get most recent completed call
status, data = get("/calls?limit=5")
calls = data.get("items", []) if isinstance(data, dict) else []
completed = [c for c in calls if c.get("detailed_status") == "completed"]
if not completed:
    print("No completed calls found")
    exit(1)

call_id = completed[0]["id"]
print(f"Testing call: {call_id}\n")

# 1. GET /calls/{id} — check transcript field
status, call = get(f"/calls/{call_id}")
print(f"=== GET /calls/{call_id}  HTTP {status} ===")
if isinstance(call, dict):
    tx = call.get("transcript")
    print(f"  transcript type: {type(tx).__name__}")
    if isinstance(tx, list):
        print(f"  transcript length: {len(tx)}")
        for t in tx[:3]:
            print(f"  turn: {json.dumps(t)[:120]}")
    else:
        print(f"  transcript value: {tx}")
    print(f"  recording_url: {str(call.get('recording_url',''))[:80]}")
print()

# 2. GET /calls/{id}/analysis
status, ana = get(f"/calls/{call_id}/analysis")
print(f"=== GET /calls/{call_id}/analysis  HTTP {status} ===")
if isinstance(ana, dict):
    print(f"  keys: {list(ana.keys())}")
    if "transcript" in ana:
        print(f"  transcript type: {type(ana['transcript']).__name__}, len={len(ana['transcript']) if isinstance(ana['transcript'], list) else 'N/A'}")
    if "extraction" in ana:
        print(f"  extraction: {json.dumps(ana['extraction'])[:200]}")
else:
    print(f"  ERROR: {ana}")
print()

# 3. GET /calls/{id}/recording
status, rec = get(f"/calls/{call_id}/recording")
print(f"=== GET /calls/{call_id}/recording  HTTP {status} ===")
if isinstance(rec, dict):
    url = rec.get("url")
    print(f"  url: {str(url)[:100] if url else 'null'}")
else:
    print(f"  ERROR: {rec}")
print()

# 4. GET /calls/{id}/transcript (live endpoint)
status, tx = get(f"/calls/{call_id}/transcript?after_id=0")
print(f"=== GET /calls/{call_id}/transcript  HTTP {status} ===")
print(f"  response: {str(tx)[:200]}")
