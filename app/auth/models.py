from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class AntigravityAccount(BaseModel):
    email: str
    refresh_token: str
    access_token: Optional[str] = None
    expires_at: Optional[int] = 0
    project_id: Optional[str] = "rising-fact-p41fc"
    health_score: int = 100
    consecutive_failures: int = 0
    cooldowns: Dict[str, float] = Field(default_factory=dict)
    last_used: float = 0
    token_usage: int = 0
    fingerprint: Optional[str] = None

class AccountPublicInfo(BaseModel):
    email: str
    project_id: Optional[str]
    health_score: int
    is_active: bool
    cooldown_active: bool
    last_used: float
    token_usage: int

class SelectionStrategy(str):
    ROUND_ROBIN = "round_robin"
    HEALTH_PRIORITY = "health_priority"
    LEAST_USED = "least_used"
