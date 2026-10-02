import time
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.auth.manager import account_manager
from config import SUPPORTED_MODELS, IMAGE_MODELS

router = APIRouter(prefix="/api", tags=["management"])

@router.get("/accounts")
async def list_accounts():
    now = time.time()
    accounts_info = []
    for acc in account_manager.accounts:
        cooldown_active = account_manager.is_cooling_down(acc)
        accounts_info.append({
            "email": acc.email,
            "project_id": acc.project_id,
            "health_score": acc.health_score,
            "cooldown_active": cooldown_active,
            "consecutive_failures": acc.consecutive_failures,
            "token_usage": acc.token_usage,
            "last_used": acc.last_used,
            "cooldowns": acc.cooldowns
        })
    return {"accounts": accounts_info}

@router.delete("/accounts/{email}")
async def delete_account(email: str):
    success = await account_manager.remove_account(email)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "ok", "message": f"Account {email} removed"}

@router.post("/accounts/reset")
async def reset_accounts():
    account_manager.reset_all_accounts()
    return {"status": "ok", "message": "All accounts reset"}

@router.get("/status")
async def get_status():
    return {
        "status": "healthy",
        "accounts_count": len(account_manager.accounts),
        "supported_models_count": len(SUPPORTED_MODELS),
        "image_models": IMAGE_MODELS,
        "strategy": account_manager.strategy
    }
