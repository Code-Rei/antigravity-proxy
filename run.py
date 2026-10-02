import uvicorn
from config import PROXY_HOST, PROXY_PORT

if __name__ == "__main__":
    print(f"🚀 Starting Antigravity Proxy on http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"🎨 Nano Banana 2 Image Generation enabled at http://localhost:{PROXY_PORT}/v1/images/generations")
    print(f"💬 Chat Completions enabled at http://localhost:{PROXY_PORT}/v1/chat/completions")
    print(f"📊 Dashboard available at http://localhost:{PROXY_PORT}/")
    uvicorn.run("app.main:app", host=PROXY_HOST, port=PROXY_PORT, reload=True)
