import json
import re
from typing import Dict, Any, Optional

class GoogleApiError:
    def __init__(self, status: int, message: str, reason: str, retry_delay: float = 0.0, is_quota: bool = False):
        self.status = status
        self.message = message
        self.reason = reason
        self.retry_delay = retry_delay
        self.is_quota = is_quota

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "message": self.message,
                "type": "api_error" if not self.is_quota else "insufficient_quota",
                "code": self.status,
                "reason": self.reason,
                "retry_delay": self.retry_delay
            }
        }

def parse_google_error(status: int, text: str) -> GoogleApiError:
    message = text
    reason = "UNKNOWN_ERROR"
    retry_delay = 0.0
    is_quota = status == 429

    try:
        data = json.loads(text)
        err = data.get("error", {})
        message = err.get("message", text)
        status_str = err.get("status", "")
        if status_str:
            reason = status_str

        details = err.get("details", [])
        for d in details:
            if isinstance(d, dict):
                if "quotaResetDelay" in d.get("metadata", {}):
                    try:
                        retry_delay = float(d["metadata"]["quotaResetDelay"])
                    except (ValueError, TypeError):
                        pass
                if "retryDelay" in d:
                    try:
                        retry_delay = float(d["retryDelay"])
                    except (ValueError, TypeError):
                        pass

        if retry_delay == 0.0 and "reset after" in message:
            match = re.search(r"reset after\s+([0-9\.]+)s", message)
            if match:
                retry_delay = float(match.group(1))

    except Exception:
        pass

    if status == 429:
        is_quota = True
        if reason == "UNKNOWN_ERROR":
            reason = "RESOURCE_EXHAUSTED"

    return GoogleApiError(status, message, reason, retry_delay, is_quota)
