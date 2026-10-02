import time
from fastapi import APIRouter
from config import SUPPORTED_MODELS

router = APIRouter(prefix="/v1", tags=["models"])

@router.get("/models")
async def list_models():
    now = int(time.time())
    models_data = [
        {
            "id": model_id,
            "object": "model",
            "created": now,
            "owned_by": "google-antigravity",
            "permission": [],
            "root": model_id,
            "parent": None
        }
        for model_id in sorted(SUPPORTED_MODELS)
    ]
    return {
        "object": "list",
        "data": models_data
    }
