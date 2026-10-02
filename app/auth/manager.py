import json
import time
import asyncio
from typing import List, Optional, Dict
from config import ACCOUNTS_FILE
from app.auth.models import AntigravityAccount, SelectionStrategy
from app.auth.oauth import refresh_access_token
from app.core.headers import generate_fingerprint

class AccountManager:
    def __init__(self):
        self.accounts: List[AntigravityAccount] = []
        self.strategy: str = SelectionStrategy.ROUND_ROBIN
        self.current_index: int = 0
        self._lock = asyncio.Lock()
        self.load_accounts()

    def load_accounts(self):
        if ACCOUNTS_FILE.exists():
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.accounts = [AntigravityAccount(**acc) for acc in data]
                print(f"[Manager] Loaded {len(self.accounts)} accounts from {ACCOUNTS_FILE}")
            except Exception as e:
                print(f"[Manager] Error loading accounts: {e}")
                self.accounts = []
        else:
            self.accounts = []

    def save_accounts(self):
        try:
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump([acc.model_dump() for acc in self.accounts], f, indent=2)
        except Exception as e:
            print(f"[Manager] Error saving accounts: {e}")

    async def add_account(self, account: AntigravityAccount):
        async with self._lock:
            if not account.fingerprint:
                account.fingerprint = generate_fingerprint()
            # Replace existing or append
            for i, acc in enumerate(self.accounts):
                if acc.email == account.email:
                    self.accounts[i] = account
                    self.save_accounts()
                    return
            self.accounts.append(account)
            self.save_accounts()

    async def remove_account(self, email: str) -> bool:
        async with self._lock:
            initial_count = len(self.accounts)
            self.accounts = [acc for acc in self.accounts if acc.email != email]
            if len(self.accounts) < initial_count:
                self.save_accounts()
                return True
            return False

    async def ensure_valid_token(self, account: AntigravityAccount) -> str:
        now = int(time.time())
        # Refresh if token missing or expiring within 2 minutes
        if not account.access_token or (account.expires_at and account.expires_at - now < 120):
            print(f"[Manager] Refreshing access token for {account.email}...")
            try:
                token_data = await refresh_access_token(account.refresh_token)
                account.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                account.expires_at = now + expires_in
                self.save_accounts()
            except Exception as e:
                print(f"[Manager] Failed to refresh token for {account.email}: {e}")
                raise
        return account.access_token

    def is_cooling_down(self, account: AntigravityAccount, model: str = "") -> bool:
        now = time.time()
        # Clean expired cooldowns
        expired_keys = [k for k, expire_time in account.cooldowns.items() if expire_time <= now]
        for k in expired_keys:
            del account.cooldowns[k]

        if not account.cooldowns:
            return False

        if "global" in account.cooldowns:
            return True
        if model and model in account.cooldowns:
            return True
        return False

    async def get_best_account(
        self,
        model: str = "",
        excluded_emails: Optional[List[str]] = None,
        respect_cooldown: bool = True
    ) -> Optional[AntigravityAccount]:
        async with self._lock:
            if not self.accounts:
                return None

            excluded = set(excluded_emails or [])
            available = [acc for acc in self.accounts if acc.email not in excluded]

            if respect_cooldown:
                ready = [acc for acc in available if not self.is_cooling_down(acc, model)]
                if ready:
                    available = ready

            if not available:
                return None

            # Sort / select based on strategy
            if self.strategy == SelectionStrategy.HEALTH_PRIORITY:
                available.sort(key=lambda a: (a.health_score, -a.last_used), reverse=True)
                selected = available[0]
            elif self.strategy == SelectionStrategy.LEAST_USED:
                available.sort(key=lambda a: (a.last_used, a.token_usage))
                selected = available[0]
            else: # ROUND_ROBIN
                self.current_index = (self.current_index + 1) % len(available)
                selected = available[self.current_index]

            selected.last_used = time.time()
            if not selected.fingerprint:
                selected.fingerprint = generate_fingerprint()

            await self.ensure_valid_token(selected)
            return selected

    def mark_cooldown(self, email: str, duration_seconds: float = 60.0, model: str = ""):
        now = time.time()
        for acc in self.accounts:
            if acc.email == email:
                key = model if model else "global"
                acc.cooldowns[key] = now + duration_seconds
                acc.health_score = max(10, acc.health_score - 10)
                acc.consecutive_failures += 1
                self.save_accounts()
                print(f"[Cooldown] Marked {email} on cooldown for {duration_seconds}s (key: {key})")
                break

    def update_usage(self, email: str, success: bool, tokens: int = 0):
        for acc in self.accounts:
            if acc.email == email:
                if success:
                    acc.health_score = min(100, acc.health_score + 2)
                    acc.consecutive_failures = 0
                    acc.token_usage += tokens
                else:
                    acc.health_score = max(0, acc.health_score - 15)
                    acc.consecutive_failures += 1
                self.save_accounts()
                break

    def reset_all_accounts(self):
        for acc in self.accounts:
            acc.health_score = 100
            acc.consecutive_failures = 0
            acc.cooldowns.clear()
        self.save_accounts()

account_manager = AccountManager()
