"""AI client for generating unhinged tweets using Dobby model via Fireworks API."""
from __future__ import annotations
import os
from typing import Optional


class AIClient:
    def __init__(self):
        self.api_key = os.getenv("FIREWORKS_API_KEY", "")
        self.model_id = "accounts/sentientfoundation/models/dobby-unhinged-llama-3-3-70b-new"
        self.base_url = "https://api.fireworks.ai/inference/v1"

    def generate_tweet(self, wallet: str, pnl: float, market: str, outcome: str) -> Optional[str]:
        """Generate an unhinged tweet about a PnL event using Dobby model."""
        if not self.api_key:
            return None

        try:
            import requests
        except ImportError:
            return None

        # Determine if it's a win or loss
        is_win = pnl > 0
        pnl_abs = abs(pnl)
        pnl_str = f"${pnl_abs:,.2f}"

        # Create prompt for Dobby
        if is_win:
            prompt = f"""Generate a SHORT, UNHINGED, CHAD WINNER tweet (max 200 chars) about someone making {pnl_str} profit on Polymarket.
Wallet: {wallet}
Market: {market}
Outcome: {outcome}

Be funny, unhinged, and celebratory. Use emojis. Keep it under 200 characters."""
        else:
            prompt = f"""Generate a SHORT, UNHINGED, SHAME tweet (max 200 chars) about someone losing {pnl_str} on Polymarket.
Wallet: {wallet}
Market: {market}
Outcome: {outcome}

Be funny, unhinged, and roast them. Use emojis. Keep it under 200 characters."""

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.9,  # High temperature for unhinged behavior
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("choices") and len(data["choices"]) > 0:
                tweet_text = data["choices"][0].get("message", {}).get("content", "").strip()
                return tweet_text if tweet_text else None
        except Exception as e:
            print(f"[AIClient] Error generating tweet: {e}")
            return None

        return None

