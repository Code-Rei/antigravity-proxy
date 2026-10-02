# 🍌 Antigravity Proxy (Python)

A high-performance, asynchronous proxy server written in Python (FastAPI + HTTPX) that connects to Google Antigravity & Gemini Cloud Code Assist APIs.

It provides full OpenAI-compatible API endpoints for:
1. **🎨 Image Generation (`/v1/images/generations`)**: Uses Google's native **Nano Banana 2** (`gemini-3-pro-image`) engine with configurable aspect ratios, disk saving, and base64 output.
2. **💬 Chat & Thinking Completions (`/v1/chat/completions`)**: Full SSE streaming & non-streaming support for Gemini 3 Pro/Flash (`thinkingLevel`), Claude 3.5/3.7/Opus/Sonnet, tool function calling, and inline image markdown.
3. **📋 Models Listing (`/v1/models`)**: Lists all supported Gemini, Claude, and Nano Banana models.
4. **👥 Multi-Account Pool & Automatic Rotation**: Handles multiple Google accounts with automatic token refresh, health scoring, quota cooldowns, and seamless failovers across sandbox (`daily` / `autopush` / `prod`) endpoints.
5. **✨ Modern Web Dashboard**: Includes a live interactive playground for Nano Banana 2 image generation, chat testing, and account management at `http://localhost:8000/`.

---

## ⚡ Quick Start

### 1. Requirements
- Python 3.10+
- A Google Account

### 2. Setup Virtual Environment & Install Dependencies
```bash
python -m venv .venv
.\.venv\Scripts\activate  # On Windows
# source .venv/bin/activate # On Linux/macOS

pip install -r requirements.txt
```

### 3. Start the Proxy Server
```bash
python run.py
```
The server will start at **`http://localhost:8000`**.

### 4. Connect Your Google Account
1. Open your browser and go to `http://localhost:8000`.
2. Click **"Connect Google Account"** (or open `http://localhost:8000/oauth/start`).
3. Complete the Google OAuth sign-in. Your credentials and refresh tokens will be stored locally in `config/accounts.json`.

---

## 🎨 Nano Banana 2 Image Generation (`/v1/images/generations`)

Antigravity Proxy routes requests to Google Cloud Code Assist's `gemini-3-pro-image` model (Google's native Nano Banana 2 engine).

### Endpoint Specification
- **URL**: `http://localhost:8000/v1/images/generations`
- **Method**: `POST`
- **Headers**: `Content-Type: application/json`

### Supported Parameters
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `prompt` | `string` | **Required** | Text prompt describing the image to generate |
| `model` | `string` | `"nano-banana-2"` | `nano-banana-2`, `gemini-3-pro-image`, `imagen-3`, `dall-e-3` |
| `size` | `string` | `"1024x1024"` | `1024x1024` (1:1), `1792x1024` (16:9), `1024x1792` (9:16), `4:3`, `3:4`, `21:9` |
| `response_format`| `string` | `"b64_json"` | `"url"` (saved locally and served as a link) or `"b64_json"` |
| `n` | `integer`| `1` | Number of image candidates (1-4) |

### cURL Example
```bash
curl -X POST http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A futuristic floating cyberpunk city at sunset with volumetric lighting, 8k",
    "model": "nano-banana-2",
    "size": "16:9",
    "response_format": "url"
  }'
```

### Python (OpenAI SDK) Example
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-antigravity"  # Any non-empty string
)

response = client.images.generate(
    model="nano-banana-2",
    prompt="Cinematic shot of an astronaut looking at an alien monolith",
    size="1792x1024",
    response_format="url"
)

print("Generated Image URL:", response.data[0].url)
```

---

## 💬 Chat Completions (`/v1/chat/completions`)

Full OpenAI-compatible chat endpoint supporting reasoning / thinking tokens and streaming.

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-antigravity"
)

stream = client.chat.completions.create(
    model="gemini-3-pro-high",
    messages=[{"role": "user", "content": "Explain quantum computing in simple terms"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

> **Tip:** You can also pass `model="nano-banana-2"` directly into `/v1/chat/completions`! The proxy will synthesize the image and return a markdown image preview `![Generated Image](...)`.

---

## 🛠️ Editor Integrations

### Cursor / VS Code / OpenCode
Configure your editor with:
- **OpenAI Base URL**: `http://localhost:8000/v1`
- **API Key**: `sk-antigravity`
- **Models**:
  - `gemini-3-pro-high`
  - `gemini-3-flash`
  - `claude-sonnet-4-6-thinking`
  - `nano-banana-2`

---

## 📂 Project Architecture

```
antigravity-proxy/
├── config.py                 # Core constants, model mappings, and OAuth settings
├── run.py                    # Server startup script
├── requirements.txt          # Python dependencies
├── app/
│   ├── main.py               # FastAPI application entry & CORS middleware
│   ├── auth/
│   │   ├── models.py         # Account data models
│   │   ├── oauth.py          # Google OAuth grant, refresh & project discovery
│   │   └── manager.py        # Multi-account rotation & cooldown manager
│   ├── core/
│   │   ├── headers.py        # Antigravity device impersonation headers
│   │   └── errors.py         # Google API error and quota parser
│   ├── routes/
│   │   ├── chat.py           # /v1/chat/completions (SSE streaming & thinking)
│   │   ├── images.py         # /v1/images/generations (Nano Banana 2 engine)
│   │   ├── models.py         # /v1/models
│   │   ├── oauth.py          # /oauth/start & /oauth-callback
│   │   └── api.py            # /api management endpoints
│   └── services/
│       ├── image_service.py  # Image generation executor & storage
│       └── transform.py      # OpenAI to Google format transformer
└── static/
    ├── index.html            # Premium web dashboard
    ├── style.css             # Dark-mode styling & animations
    ├── app.js                # Frontend client logic
    └── generated_images/     # Output directory for locally saved images
```

---

## 📄 License
MIT License.
