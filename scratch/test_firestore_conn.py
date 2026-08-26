import asyncio
from google.cloud import firestore

async def test_firestore():
    try:
        print("Testing Firestore async client for project 'wakilz-dasboard'...")
        db = firestore.AsyncClient(project="wakilz-dasboard")
        # Read a collection or write a test doc
        ref = db.collection("client_keys").document("wakilz_demo")
        snap = await ref.get()
        print(f"Firestore connected! Doc 'client_keys/wakilz_demo' exists: {snap.exists}")
        if snap.exists:
            print("Doc data:", snap.to_dict())
    except Exception as e:
        print(f"Firestore connection result / error: {e}")

asyncio.run(test_firestore())
