import json
import time
import uuid
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, List, Optional
from config import SANDBOX_ENDPOINTS, BASE_URL
from app.auth.manager import account_manager
from app.core.headers import get_antigravity_headers
from app.core.errors import parse_google_error
from app.services.transform import (
    transform_to_google_body,
    format_openai_chunk,
    resolve_target_model
)
from app.services.image_service import generate_nano_banana_image

router = APIRouter(prefix="/v1", tags=["chat"])

@router.post("/chat/completions")
async def chat_completions(request: Request):
    openai_body = await request.json()
    raw_model = openai_body.get("model", "gemini-3-pro-high")
    is_streaming = openai_body.get("stream", False)
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    target_model = resolve_target_model(raw_model)

    # Check if this is an image model called via chat completions
    if target_model == "gemini-3-pro-image":
        messages = openai_body.get("messages", [])
        prompt = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, str):
                    prompt = content
                    break
                elif isinstance(content, list):
                    prompt = " ".join([p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"])
                    break

        if not prompt:
            prompt = "A high quality artistic image"

        base_url = str(request.base_url).rstrip("/") or BASE_URL
        try:
            img_result = await generate_nano_banana_image(
                prompt=prompt,
                model="nano-banana-2",
                n=1,
                size="1024x1024",
                response_format="url",
                base_url=base_url
            )
            img_url = img_result["data"][0].get("url") or f"data:image/png;base64,{img_result['data'][0].get('b64_json', '')}"
            markdown_content = f"![Generated Image]({img_url})\n\n**Prompt:** {prompt}"

            if is_streaming:
                async def stream_img():
                    yield format_openai_chunk(request_id, raw_model, content=markdown_content)
                    yield format_openai_chunk(request_id, raw_model, finish_reason="stop")
                    yield "data: [DONE]\n\n"
                return StreamingResponse(stream_img(), media_type="text/event-stream")

            return {
                "id": request_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": raw_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": markdown_content
                        },
                        "finish_reason": "stop"
                    }
                ]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail={"error": {"message": str(e), "type": "image_error"}})

    # Standard LLM Chat Completion
    max_attempts = 4
    tried_emails: List[str] = []
    last_error = "No available accounts"

    for attempt in range(max_attempts):
        account = await account_manager.get_best_account(
            model=target_model,
            excluded_emails=tried_emails,
            respect_cooldown=True
        )

        if not account:
            account = await account_manager.get_best_account(
                model=target_model,
                excluded_emails=[],
                respect_cooldown=False
            )
            if not account:
                break

        tried_emails.append(account.email)
        token = await account_manager.ensure_valid_token(account)
        headers = get_antigravity_headers(token, account.fingerprint, target_model)

        google_body = transform_to_google_body(
            openai_body,
            project_id=account.project_id or "rising-fact-p41fc"
        )

        for endpoint in SANDBOX_ENDPOINTS:
            endpoint_path = ":streamGenerateContent?alt=sse" if is_streaming else ":generateContent"
            target_url = f"{endpoint}/v1internal{endpoint_path}"

            try:
                if is_streaming:
                    client = httpx.AsyncClient(timeout=120.0)
                    req = client.build_request("POST", target_url, headers=headers, json=google_body)
                    resp = await client.send(req, stream=True)

                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        await client.aclose()
                        parsed = parse_google_error(resp.status_code, err_text.decode("utf-8", errors="ignore"))
                        print(f"[Chat] Error {resp.status_code} ({parsed.reason}) from {account.email}: {parsed.message}")
                        if resp.status_code == 429:
                            account_manager.mark_cooldown(account.email, parsed.retry_delay or 60.0, target_model)
                        continue

                    # Successful stream
                    account_manager.update_usage(account.email, success=True, tokens=100)

                    async def event_generator():
                        try:
                            buffer = ""
                            async for raw_line in resp.aiter_lines():
                                line = raw_line.strip()
                                if not line:
                                    continue
                                if line.startswith("data:"):
                                    data_str = line[5:].strip()
                                    if not data_str:
                                        continue
                                    try:
                                        chunk_json = json.loads(data_str)
                                        cands = chunk_json.get("response", {}).get("candidates") or chunk_json.get("candidates", [])
                                        for cand in cands:
                                            parts = cand.get("content", {}).get("parts", [])
                                            text_delta = ""
                                            reasoning_delta = ""
                                            tool_calls = []

                                            for p in parts:
                                                if "text" in p:
                                                    if p.get("thought", False):
                                                        reasoning_delta += p["text"]
                                                    else:
                                                        text_delta += p["text"]
                                                elif "functionCall" in p:
                                                    fc = p["functionCall"]
                                                    tool_calls.append({
                                                        "index": 0,
                                                        "id": fc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                                                        "type": "function",
                                                        "function": {
                                                            "name": fc.get("name"),
                                                            "arguments": json.dumps(fc.get("args", {}))
                                                        }
                                                    })

                                            finish_reason = "tool_calls" if tool_calls else cand.get("finishReason", "").lower()
                                            if finish_reason == "stop" or not finish_reason:
                                                finish_reason = None

                                            yield format_openai_chunk(
                                                request_id,
                                                raw_model,
                                                content=text_delta if text_delta else None,
                                                reasoning=reasoning_delta if reasoning_delta else None,
                                                tool_calls=tool_calls if tool_calls else None,
                                                finish_reason=finish_reason
                                            )
                                    except Exception as ex:
                                        pass
                            yield format_openai_chunk(request_id, raw_model, finish_reason="stop")
                            yield "data: [DONE]\n\n"
                        finally:
                            await resp.aclose()
                            await client.aclose()

                    return StreamingResponse(
                        event_generator(),
                        media_type="text/event-stream",
                        headers={"X-Antigravity-Account": account.email}
                    )

                else:
                    # Non-streaming
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        resp = await client.post(target_url, headers=headers, json=google_body)

                    if resp.status_code == 200:
                        account_manager.update_usage(account.email, success=True, tokens=100)
                        data = resp.json()
                        candidates = data.get("response", {}).get("candidates") or data.get("candidates", [])
                        full_content = ""
                        reasoning_content = ""
                        tool_calls = []
                        finish_reason = "stop"

                        if candidates:
                            cand = candidates[0]
                            parts = cand.get("content", {}).get("parts", [])
                            for p in parts:
                                if "text" in p:
                                    if p.get("thought", False):
                                        reasoning_content += p["text"]
                                    else:
                                        full_content += p["text"]
                                elif "functionCall" in p:
                                    fc = p["functionCall"]
                                    tool_calls.append({
                                        "id": fc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                                        "type": "function",
                                        "function": {
                                            "name": fc.get("name"),
                                            "arguments": json.dumps(fc.get("args", {}))
                                        }
                                    })
                            if tool_calls:
                                finish_reason = "tool_calls"

                        msg: Dict[str, Any] = {
                            "role": "assistant",
                            "content": full_content
                        }
                        if reasoning_content:
                            msg["reasoning_content"] = reasoning_content
                        if tool_calls:
                            msg["tool_calls"] = tool_calls

                        return {
                            "id": request_id,
                            "object": "chat.completion",
                            "created": int(time.time()),
                            "model": raw_model,
                            "choices": [
                                {
                                    "index": 0,
                                    "message": msg,
                                    "finish_reason": finish_reason
                                }
                            ]
                        }

                    else:
                        parsed = parse_google_error(resp.status_code, resp.text)
                        last_error = f"{parsed.reason}: {parsed.message}"
                        if resp.status_code == 429:
                            account_manager.mark_cooldown(account.email, parsed.retry_delay or 60.0, target_model)
                        else:
                            account_manager.update_usage(account.email, success=False)

            except Exception as e:
                print(f"[Chat] Exception requesting {endpoint}: {e}")
                last_error = str(e)

    raise HTTPException(
        status_code=429,
        detail={
            "error": {
                "message": f"All Antigravity accounts exhausted or error encountered: {last_error}",
                "type": "insufficient_quota",
                "code": "insufficient_quota"
            }
        }
    )
