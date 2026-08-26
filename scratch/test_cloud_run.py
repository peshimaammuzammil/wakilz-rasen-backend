import httpx

LIVE_URL = "https://wakilz-voice-635406175951.asia-south1.run.app"

try:
    print(f"Testing {LIVE_URL}/health ...")
    r = httpx.get(f"{LIVE_URL}/health", timeout=10.0)
    print("Status:", r.status_code)
    print("Response:", r.text)
except Exception as e:
    print("Health check failed:", e)

try:
    print(f"\nTesting {LIVE_URL}/api/client/verify?key=wakilz_demo ...")
    r = httpx.get(f"{LIVE_URL}/api/client/verify?key=wakilz_demo", timeout=10.0)
    print("Status:", r.status_code)
    print("Response:", r.text)
except Exception as e:
    print("Client verify failed:", e)

try:
    print(f"\nTesting {LIVE_URL}/api/rasen/calls ...")
    r = httpx.get(f"{LIVE_URL}/api/rasen/calls", timeout=10.0)
    print("Status:", r.status_code)
    print("Response:", r.text[:200])
except Exception as e:
    print("Rasen calls failed:", e)
