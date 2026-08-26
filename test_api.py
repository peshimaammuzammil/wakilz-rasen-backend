import httpx, json

BASE = "http://localhost:8080"

# Auth
r = httpx.get(f"{BASE}/api/client/verify", params={"key": "wakilz_demo"}, timeout=10)
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

# Full calls with analysis and date range (This Month)
print("=== GET /api/rasen/calls with analysis (Aug 2026) ===")
r2 = httpx.get(f"{BASE}/api/rasen/calls", headers=headers,
    params={"include_analysis": True, "max_calls": 200, "start_date": "2026-08-01", "end_date": "2026-08-26"},
    timeout=90
)
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    data = r2.json()
    print(f"Total fetched: {data['total_fetched']}")
    print(f"Has analysis: {data['has_analysis']}")
    
    # Show summary stats
    calls = data['calls']
    ended = [c for c in calls if c['status'] == 'ended']
    with_extraction = [c for c in ended if c.get('extraction') and c['extraction']]
    
    outcomes = {}
    for c in with_extraction:
        o = c['extraction'].get('call_outcome', 'null')
        outcomes[o] = outcomes.get(o, 0) + 1
    
    print(f"\nSummary:")
    print(f"  Total calls: {len(calls)}")
    print(f"  Ended: {len(ended)}")
    print(f"  With extraction: {len(with_extraction)}")
    print(f"  Outcomes: {outcomes}")
    
    # Sample enriched call
    if with_extraction:
        print(f"\nSample enriched call:")
        print(json.dumps(with_extraction[0], indent=2))
else:
    print(f"Error: {r2.text[:500]}")
