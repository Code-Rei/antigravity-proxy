import time
import httpx
import json

BASE_URL = "http://localhost:8000"

def test_models():
    print("\n--- 1. Testing /v1/models ---")
    r = httpx.get(f"{BASE_URL}/v1/models", timeout=10.0)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    model_ids = [m["id"] for m in data.get("data", [])]
    print(f"Total models available: {len(model_ids)}")
    assert "nano-banana-2" in model_ids, "nano-banana-2 missing from models"
    assert "gemini-3.1-pro-high" in model_ids, "gemini-3.1-pro-high missing"
    print("SUCCESS: /v1/models working correctly.")

def test_accounts():
    print("\n--- 2. Testing /api/accounts & /api/status ---")
    r = httpx.get(f"{BASE_URL}/api/status", timeout=10.0)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    status = r.json()
    print(f"Server status: {status['status']}, Accounts: {status['accounts_count']}")
    
    r_acc = httpx.get(f"{BASE_URL}/api/accounts", timeout=10.0)
    assert r_acc.status_code == 200
    accs = r_acc.json().get("accounts", [])
    print(f"Connected accounts: {[a['email'] for a in accs]}")
    print("SUCCESS: Management APIs working correctly.")

def test_chat_non_stream():
    print("\n--- 3. Testing /v1/chat/completions (non-stream) ---")
    payload = {
        "model": "gemini-3.1-pro-high",
        "messages": [
            {"role": "user", "content": "Reply with only 'ONLINE'"}
        ],
        "stream": False
    }
    r = httpx.post(f"{BASE_URL}/v1/chat/completions", json=payload, timeout=45.0)
    print("Status:", r.status_code)
    print("Body:", r.text[:300])
    return r.status_code == 200

def test_chat_stream():
    print("\n--- 4. Testing /v1/chat/completions (stream) ---")
    payload = {
        "model": "gemini-3.1-pro-high",
        "messages": [
            {"role": "user", "content": "Say hello in 3 words"}
        ],
        "stream": True
    }
    with httpx.stream("POST", f"{BASE_URL}/v1/chat/completions", json=payload, timeout=45.0) as resp:
        print("Status:", resp.status_code)
        chunks = []
        for line in resp.iter_lines():
            if line.startswith("data:"):
                chunks.append(line)
        print(f"Received {len(chunks)} stream chunks")
        if chunks:
            print("First chunk:", chunks[0][:150])
            print("Last chunk:", chunks[-1][:150])
    return resp.status_code == 200

def test_image_generation():
    print("\n--- 5. Testing /v1/images/generations (Nano Banana 2) ---")
    payload = {
        "prompt": "A majestic cyber horse galloping through a neon forest",
        "model": "nano-banana-2",
        "size": "1024x1024",
        "response_format": "url",
        "n": 1
    }
    r = httpx.post(f"{BASE_URL}/v1/images/generations", json=payload, timeout=60.0)
    print("Status:", r.status_code)
    print("Body:", r.text[:400])
    if r.status_code == 200:
        data = r.json()
        print("Image URL:", data["data"][0].get("url"))
    return r.status_code == 200

if __name__ == "__main__":
    test_models()
    test_accounts()
    print("\nLive model testing:")
    chat_ok = test_chat_non_stream()
    stream_ok = test_chat_stream()
    img_ok = test_image_generation()
    print("\n===============================")
    print(f"Summary: Chat: {chat_ok} | Stream: {stream_ok} | Image: {img_ok}")
    print("===============================")
