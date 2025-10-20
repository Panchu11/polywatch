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

        # Create prompt for Dobby - EXTREMELY UNHINGED with diverse styles (NO CHARACTER LIMIT - X Premium)
        if is_win:
            # Multiple diverse winning prompts to avoid repetition
            win_prompts = [
                f"""Generate an EXTREMELY UNHINGED, PROFANE, CHAOTIC WINNER tweet about {wallet} making {pnl_str} profit on @Polymarket. MUST mention @Polymarket explicitly.
Market: {market} - {outcome}

Be INSANELY funny, use profanity, be chaotic and celebratory. Use LOTS of emojis. MAXIMUM UNHINGED. MUST include @Polymarket. Write a COMPLETE SENTENCE that doesn't get cut off. Go wild!""",
                f"""Generate a COMPLETELY UNHINGED, CHAOTIC, PROFANE tweet celebrating {wallet} CRUSHING IT with {pnl_str} on @Polymarket. MUST mention @Polymarket.
Market: {market} - {outcome}

Be absolutely INSANE, use extreme profanity, be celebratory and chaotic. Use TONS of emojis. MAXIMUM CHAOS. MUST include @Polymarket. Write COMPLETE SENTENCES. No limits, go crazy!""",
                f"""Generate an ABSOLUTELY BONKERS, PROFANE, UNHINGED tweet about {wallet} PRINTING {pnl_str} on @Polymarket. MUST mention @Polymarket explicitly.
Market: {market} - {outcome}

Be MAXIMALLY UNHINGED, use profanity, be chaotic and wild. Use LOTS of emojis. EXTREME CHAOS. MUST include @Polymarket. Write COMPLETE SENTENCES that flow naturally. Be insane!""",
                f"""Generate a COMPLETELY DERANGED, PROFANE, CHAOTIC tweet about {wallet} MOONING with {pnl_str} on @Polymarket. MUST mention @Polymarket.
Market: {market} - {outcome}

Be INSANELY UNHINGED, use extreme profanity, be absolutely chaotic. Use TONS of emojis. MAXIMUM UNHINGED. MUST include @Polymarket. Write COMPLETE SENTENCES. Go absolutely wild!""",
            ]
            prompt = win_prompts[hash(wallet) % len(win_prompts)]
        else:
            # Multiple diverse losing prompts to avoid repetition
            loss_prompts = [
                f"""Generate an EXTREMELY UNHINGED, PROFANE, CHAOTIC LOSER tweet about {wallet} LOSING {pnl_str} on @Polymarket. MUST mention @Polymarket explicitly.
Market: {market} - {outcome}

Be INSANELY funny, use profanity, roast them hard, be chaotic. Use LOTS of emojis. MAXIMUM UNHINGED. MUST include @Polymarket. Write COMPLETE SENTENCES. Go wild!""",
                f"""Generate a COMPLETELY UNHINGED, PROFANE, CHAOTIC tweet about {wallet} GETTING REKT for {pnl_str} on @Polymarket. MUST mention @Polymarket.
Market: {market} - {outcome}

Be absolutely INSANE, use extreme profanity, roast them mercilessly, be chaotic. Use TONS of emojis. MAXIMUM CHAOS. MUST include @Polymarket. Write COMPLETE SENTENCES. No limits!""",
                f"""Generate an ABSOLUTELY BONKERS, PROFANE, UNHINGED tweet about {wallet} BLOWING {pnl_str} on @Polymarket. MUST mention @Polymarket explicitly.
Market: {market} - {outcome}

Be MAXIMALLY UNHINGED, use profanity, roast them hard, be chaotic and wild. Use LOTS of emojis. EXTREME CHAOS. MUST include @Polymarket. Write COMPLETE SENTENCES. Go insane!""",
                f"""Generate a COMPLETELY DERANGED, PROFANE, CHAOTIC tweet about {wallet} DUMPING {pnl_str} on @Polymarket. MUST mention @Polymarket.
Market: {market} - {outcome}

Be INSANELY UNHINGED, use extreme profanity, roast them, be absolutely chaotic. Use TONS of emojis. MAXIMUM UNHINGED. MUST include @Polymarket. Write COMPLETE SENTENCES. Go wild!""",
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
                    "max_tokens": 300,
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

