import json
import uuid
import re
from typing import Dict, Any, List, Tuple, Optional

ANTIGRAVITY_SYSTEM_INSTRUCTION = (
    "You are Antigravity, a powerful agentic AI coding assistant designed by the Google DeepMind team "
    "working on Advanced Agentic Coding. You are pair programming with a USER to solve their coding task. "
    "The task may require creating a new codebase, modifying or debugging an existing codebase, or simply answering a question."
)

CLAUDE_MODELS = {
    "claude-opus-4-6-thinking",
    "claude-sonnet-4-6-thinking",
    "claude-sonnet-4-5-thinking",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
}

def resolve_target_model(model: str) -> str:
    m = model.lower().strip()
    m = re.sub(r"^(openai|antigravity|custom_openai|litellm|google)/", "", m)
    m = re.sub(r"^antigravity-", "", m)
    m = re.sub(r"^gemini-claude-", "claude-", m)

    # Image models
    if any(k in m for k in ["banana", "gemini-3-pro-image", "imagen", "dall-e"]):
        return "gemini-3-pro-image"

    # Claude models
    if "claude" in m:
        if "opus" in m:
            return "claude-opus-4-6-thinking"
        if "sonnet" in m:
            if "4-5" in m:
                return "claude-sonnet-4-5-thinking"
            return "claude-sonnet-4-6-thinking"
        if "haiku" in m:
            return "claude-3-5-haiku-20241022"
        return "claude-sonnet-4-6-thinking"

    # Gemini 3
    if "gemini-3" in m:
        if "3.1" in m:
            if "low" in m:
                return "gemini-3.1-pro-low"
            return "gemini-3.1-pro-high"
        if "flash" in m:
            return "gemini-3-flash"
        if "low" in m:
            return "gemini-3-pro-low"
        return "gemini-3-pro-high"

    # Gemini 2.5
    if "gemini-2.5" in m:
        if "pro" in m:
            return "gemini-2.5-pro"
        return "gemini-2.5-flash"

    return m

def clean_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Cleans standard JSON Schema for Antigravity function declarations."""
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    cleaned = {}
    for key, value in schema.items():
        if key in ["$schema", "$id", "title", "additionalProperties", "definitions", "$defs"]:
            continue
        if key == "properties" and isinstance(value, dict):
            cleaned["properties"] = {
                prop: clean_json_schema(prop_val)
                for prop, prop_val in value.items()
            }
        elif key == "items" and isinstance(value, dict):
            cleaned["items"] = clean_json_schema(value)
        else:
            cleaned[key] = value

    if "type" not in cleaned:
        cleaned["type"] = "object"
    return cleaned

def transform_to_google_body(
    openai_body: Dict[str, Any],
    project_id: str,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    raw_model = openai_body.get("model", "gemini-3-pro-high")
    target_model = resolve_target_model(raw_model)
    messages = openai_body.get("messages", [])

    system_message = ""
    other_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            system_message += (msg.get("content", "") + "\n")
        else:
            other_messages.append(msg)

    # Process contents
    contents = []
    for msg in other_messages:
        role = "model" if msg.get("role") in ["assistant", "model"] else "user"
        parts = []

        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            parts.append({"text": content})
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        parts.append({"text": part.get("text", "")})
                    elif part.get("type") == "image_url":
                        # Support multimodal input if provided
                        url = part.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            mime = url.split(";")[0].replace("data:", "")
                            data = url.split(",")[-1]
                            parts.append({"inlineData": {"mimeType": mime, "data": data}})

        # Handle tool results
        if msg.get("role") == "tool":
            role = "user"
            resp = msg.get("content", "{}")
            try:
                resp_obj = json.loads(resp) if isinstance(resp, str) else resp
            except Exception:
                resp_obj = {"result": resp}
            if not isinstance(resp_obj, dict):
                resp_obj = {"result": resp_obj}

            func_resp = {
                "name": msg.get("name", "tool_result"),
                "response": resp_obj
            }
            if msg.get("tool_call_id"):
                func_resp["id"] = msg.get("tool_call_id")
            parts.append({"functionResponse": func_resp})

        # Handle assistant tool calls
        if msg.get("tool_calls"):
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                args = fn.get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                func_call = {
                    "name": fn.get("name", "function"),
                    "args": args
                }
                if tc.get("id"):
                    func_call["id"] = tc.get("id")
                parts.append({"functionCall": func_call})

        if not parts:
            parts.append({"text": " "})

        contents.append({"role": role, "parts": parts})

    # System instruction
    full_system_text = (ANTIGRAVITY_SYSTEM_INSTRUCTION + "\n\n" + system_message).strip()
    system_instruction = {
        "role": "user",
        "parts": [{"text": full_system_text}]
    }

    # Generation config
    is_thinking = "thinking" in target_model or "gemini-3" in target_model
    tier = "high"
    if "low" in target_model or "low" in raw_model:
        tier = "low"
    elif "medium" in target_model or "medium" in raw_model:
        tier = "medium"

    generation_config: Dict[str, Any] = {
        "temperature": openai_body.get("temperature", 0.7),
        "topP": openai_body.get("top_p", 0.95),
        "maxOutputTokens": openai_body.get("max_tokens", 8192 if not is_thinking else 32768),
        "candidateCount": 1
    }

    if is_thinking:
        generation_config["thinkingConfig"] = {
            "includeThoughts": True,
            "thinkingLevel": tier if "gemini-3" in target_model else undefined_thinking_level(tier),
        }
        if "gemini-3" not in target_model:
            generation_config["thinkingConfig"]["thinkingBudget"] = 32768 if tier == "high" else 16000

    google_body: Dict[str, Any] = {
        "project": project_id,
        "model": target_model,
        "contents": contents,
        "systemInstruction": system_instruction,
        "generationConfig": generation_config,
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ],
        "sessionId": session_id or str(uuid.uuid4())
    }

    # Tools
    tools = openai_body.get("tools")
    if tools and isinstance(tools, list):
        func_declarations = []
        for t in tools:
            fn = t.get("function", {})
            func_declarations.append({
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "parameters": clean_json_schema(fn.get("parameters", {}))
            })
        if func_declarations:
            google_body["tools"] = [{"functionDeclarations": func_declarations}]
            if "claude" in target_model:
                google_body["toolConfig"] = {"functionCallingConfig": {"mode": "VALIDATED"}}

    return google_body

def undefined_thinking_level(tier: str):
    # Helper for budget calculation
    return None

def format_openai_chunk(
    request_id: str,
    model: str,
    content: Optional[str] = None,
    reasoning: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    finish_reason: Optional[str] = None
) -> str:
    delta: Dict[str, Any] = {}
    if content is not None:
        delta["content"] = content
    if reasoning is not None:
        delta["reasoning_content"] = reasoning
    if tool_calls:
        delta["tool_calls"] = tool_calls

    chunk = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": int(uuid.uuid1().time / 1e7),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason
            }
        ]
    }
    return f"data: {json.dumps(chunk)}\n\n"
