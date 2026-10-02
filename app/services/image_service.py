import os
import time
import uuid
import base64
import httpx
from typing import Dict, Any, List, Optional
from config import (
    SANDBOX_ENDPOINTS,
    GENERATED_IMAGES_DIR,
    BASE_URL,
)
from app.auth.manager import account_manager
from app.core.headers import get_antigravity_headers
from app.core.errors import parse_google_error

# Size to aspect ratio mapping
SIZE_TO_ASPECT_RATIO = {
    "1024x1024": "1:1",
    "512x512": "1:1",
    "1:1": "1:1",
    "1792x1024": "16:9",
    "1920x1080": "16:9",
    "16:9": "16:9",
    "1024x1792": "9:16",
    "1080x1920": "9:16",
    "9:16": "9:16",
    "4:3": "4:3",
    "1024x768": "4:3",
    "3:4": "3:4",
    "768x1024": "3:4",
    "3:2": "3:2",
    "2:3": "2:3",
    "21:9": "21:9"
}

def resolve_aspect_ratio(size: Optional[str]) -> str:
    if not size:
        return "1:1"
    clean_size = size.lower().strip()
    return SIZE_TO_ASPECT_RATIO.get(clean_size, "1:1")

def save_image_to_disk(b64_data: str, mime_type: str = "image/png") -> str:
    ext = "png"
    if "jpeg" in mime_type or "jpg" in mime_type:
        ext = "jpg"
    elif "webp" in mime_type:
        ext = "webp"
    elif "gif" in mime_type:
        ext = "gif"

    filename = f"gen_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = GENERATED_IMAGES_DIR / filename

    raw_bytes = base64.b64decode(b64_data)
    with open(file_path, "wb") as f:
        f.write(raw_bytes)

    return filename

async def generate_nano_banana_image(
    prompt: str,
    model: str = "nano-banana-2",
    n: int = 1,
    size: str = "1024x1024",
    response_format: str = "b64_json",
    base_url: str = BASE_URL,
    max_attempts: int = 4
) -> Dict[str, Any]:
    aspect_ratio = resolve_aspect_ratio(size)
    n = max(1, min(n, 4))
    tried_emails: List[str] = []

    last_error = "No accounts available"

    for attempt in range(max_attempts):
        account = await account_manager.get_best_account(
            model="gemini-3-pro-image",
            excluded_emails=tried_emails,
            respect_cooldown=True
        )

        if not account:
            # Try without cooldown if accounts exhausted
            account = await account_manager.get_best_account(
                model="gemini-3-pro-image",
                excluded_emails=[],
                respect_cooldown=False
            )
            if not account:
                break

        tried_emails.append(account.email)
        token = await account_manager.ensure_valid_token(account)
        headers = get_antigravity_headers(token, account.fingerprint, "gemini-3.1-flash-image")

        payload = {
            "model": "gemini-3.1-flash-image",
            "project": account.project_id or "aicode-consumers",
            "request": {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                "systemInstruction": {
                    "parts": [{
                        "text": "You are an AI image generator. Generate images based on user descriptions. "
                                "Focus on creating high-quality, visually appealing images that match the user's request."
                    }]
                },
                "generationConfig": {
                    "imageConfig": {
                        "aspectRatio": aspect_ratio
                    },
                    "candidateCount": n
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_ONLY_HIGH"}
                ]
            }
        }

        # Try endpoints (daily -> autopush -> prod)
        for endpoint in SANDBOX_ENDPOINTS:
            for method_name in [":generateContent", ":streamGenerateContent"]:
                target_url = f"{endpoint}/v1internal{method_name}"
                try:
                    print(f"[NanoBanana2] Requesting image ({aspect_ratio}) from {account.email} on {endpoint}{method_name}...")
                    async with httpx.AsyncClient(timeout=90.0) as client:
                        resp = await client.post(target_url, headers=headers, json=payload)

                    if resp.status_code == 200:
                        extracted_images = []
                        resp_text = resp.text.strip()
                        
                        # Handle SSE stream format if streamGenerateContent was used
                        if "data:" in resp_text:
                            for line in resp_text.splitlines():
                                line = line.strip()
                                if line.startswith("data:"):
                                    data_chunk = line[5:].strip()
                                    if data_chunk and data_chunk != "[DONE]":
                                        try:
                                            chunk_json = json.loads(data_chunk)
                                            cands = chunk_json.get("response", {}).get("candidates") or chunk_json.get("candidates", [])
                                            for cand in cands:
                                                parts = cand.get("content", {}).get("parts", [])
                                                for part in parts:
                                                    if "inlineData" in part:
                                                        b64 = part["inlineData"].get("data")
                                                        mime = part["inlineData"].get("mimeType", "image/png")
                                                        if b64:
                                                            extracted_images.append((b64, mime))
                                        except Exception:
                                            pass
                        else:
                            # Standard JSON response
                            try:
                                data = resp.json()
                                candidates = data.get("response", {}).get("candidates") or data.get("candidates", [])
                                for cand in candidates:
                                    parts = cand.get("content", {}).get("parts", [])
                                    for part in parts:
                                        if "inlineData" in part:
                                            b64 = part["inlineData"].get("data")
                                            mime = part["inlineData"].get("mimeType", "image/png")
                                            if b64:
                                                extracted_images.append((b64, mime))
                            except Exception:
                                pass

                        if extracted_images:
                            account_manager.update_usage(account.email, success=True, tokens=1000)
                            results = []
                            for b64, mime in extracted_images:
                                item: Dict[str, Any] = {"revised_prompt": prompt}
                                if response_format == "url":
                                    filename = save_image_to_disk(b64, mime)
                                    item["url"] = f"{base_url}/static/generated_images/{filename}"
                                else:
                                    item["b64_json"] = b64
                                results.append(item)

                            return {
                                "created": int(time.time()),
                                "data": results
                            }
                        else:
                            print(f"[NanoBanana2] No inlineData in response from {endpoint}: {resp.text[:300]}")
                            last_error = "Model returned response without image data"

                    elif resp.status_code == 404 and method_name == ":generateContent":
                        # If generateContent not found, loop will try streamGenerateContent
                        continue
                    else:
                        err_text = resp.text
                        parsed = parse_google_error(resp.status_code, err_text)
                        print(f"[NanoBanana2] Error {resp.status_code} ({parsed.reason}) from {account.email}: {err_text[:300]}")
                        last_error = f"{parsed.reason}: {parsed.message}"
                        if resp.status_code == 429:
                            account_manager.mark_cooldown(account.email, parsed.retry_delay or 60.0, "gemini-3-pro-image")
                            break # Move to next account on rate limit
                        else:
                            account_manager.update_usage(account.email, success=False)

                except Exception as e:
                    print(f"[NanoBanana2] Connection exception with {endpoint}: {e}")
                    last_error = str(e)

    raise RuntimeError(f"Image generation failed after {max_attempts} attempts. Last error: {last_error}")
