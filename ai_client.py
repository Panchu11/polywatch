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

        # Create prompt for Dobby - EXTREMELY UNHINGED with diverse styles (SHORTER, PUNCHIER)
        if is_win:
            # Multiple diverse winning prompts to avoid repetition
            win_prompts = [
                f"""Generate a SHORT, UNHINGED, PROFANE WINNER tweet about {wallet} making {pnl_str} profit.
Market: {market} - {outcome}

KEEP IT SHORT (3-4 lines max). Use line breaks. Be funny, profane, chaotic. Use emojis. MUST include @Polymarket tag ONCE in the middle/body, NOT at the start. Never start with @mention!""",
                f"""Generate a SHORT, CHAOTIC, PROFANE tweet celebrating {wallet} CRUSHING IT with {pnl_str}.
Market: {market} - {outcome}

KEEP IT SHORT (3-4 lines). Use line breaks. Be insane, profane, celebratory. Lots of emojis. MUST tag @Polymarket ONCE in the body, NOT at start. Never start with @!""",
                f"""Generate a SHORT, BONKERS, PROFANE tweet about {wallet} PRINTING {pnl_str}.
Market: {market} - {outcome}

KEEP IT SHORT (3-4 lines max). Line breaks. Be unhinged, profane, wild. Emojis. MUST mention @Polymarket ONCE in middle/body, NEVER at the start!""",
                f"""Generate a SHORT, DERANGED, PROFANE tweet about {wallet} MOONING with {pnl_str}.
Market: {market} - {outcome}

KEEP IT SHORT (3-4 lines). Line breaks. Be unhinged, profane, chaotic. Emojis. MUST tag @Polymarket ONCE in the body, NOT at beginning!""",
            ]
            prompt = win_prompts[hash(wallet) % len(win_prompts)]
        else:
            # Multiple diverse losing prompts to avoid repetition
            loss_prompts = [
                f"""Generate a SHORT, UNHINGED, PROFANE LOSER tweet about {wallet} LOSING {pnl_str}.
Market: {market} - {outcome}

KEEP IT SHORT (3-4 lines max). Line breaks. Be funny, profane, roast them. Emojis. MUST include @Polymarket tag ONCE in the body, NOT at start!""",
                f"""Generate a SHORT, UNHINGED, PROFANE tweet about {wallet} GETTING REKT for {pnl_str}.
Market: {market} - {outcome}

KEEP IT SHORT (3-4 lines). Line breaks. Be insane, profane, roast hard. Emojis. MUST tag @Polymarket ONCE in middle, NEVER at the start!""",
                f"""Generate a SHORT, BONKERS, PROFANE tweet about {wallet} BLOWING {pnl_str}.
Market: {market} - {outcome}

KEEP IT SHORT (3-4 lines max). Line breaks. Be unhinged, profane, roast. Emojis. MUST mention @Polymarket ONCE in body, NOT at beginning!""",
                f"""Generate a SHORT, DERANGED, PROFANE tweet about {wallet} DUMPING {pnl_str}.
Market: {market} - {outcome}

KEEP IT SHORT (3-4 lines). Line breaks. Be unhinged, profane, chaotic. Emojis. MUST tag @Polymarket ONCE in the body, NOT at start!""",
            ]
            prompt = loss_prompts[hash(wallet) % len(loss_prompts)]

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
                    "max_tokens": 100,
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

