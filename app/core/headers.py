import uuid
import sys
from typing import Dict
from config import ANTIGRAVITY_VERSION

def generate_fingerprint() -> str:
    return str(uuid.uuid4())

def get_platform_name() -> str:
    if sys.platform == "win32":
        return "WINDOWS"
    elif sys.platform == "darwin":
        return "MACOS"
    return "LINUX"

def get_antigravity_headers(access_token: str, fingerprint: str = None, model: str = "") -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Antigravity/{ANTIGRAVITY_VERSION} Chrome/138.0.7204.235 Electron/37.3.1 Safari/537.36",
        "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
        "Client-Metadata": f'{{"ideType":"ANTIGRAVITY","platform":"{get_platform_name()}","pluginType":"GEMINI"}}',
    }
    if fingerprint:
        headers["X-Client-Session-Id"] = fingerprint
    return headers
