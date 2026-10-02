from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Literal
from app.services.image_service import generate_nano_banana_image
from config import BASE_URL

router = APIRouter(prefix="/v1", tags=["images"])

class ImageGenerationRequest(BaseModel):
    prompt: str
    model: Optional[str] = "nano-banana-2"
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"
    response_format: Optional[Literal["url", "b64_json"]] = "b64_json"
    quality: Optional[str] = "standard"

@router.post("/images/generations")
async def create_image_generation(body: ImageGenerationRequest, request: Request):
    base_url = str(request.base_url).rstrip("/") or BASE_URL
    try:
        result = await generate_nano_banana_image(
            prompt=body.prompt,
            model=body.model or "nano-banana-2",
            n=body.n or 1,
            size=body.size or "1024x1024",
            response_format=body.response_format or "b64_json",
            base_url=base_url
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e), "type": "image_generation_error"}})
