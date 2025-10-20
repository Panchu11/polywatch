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
                f"""Generate a SHORT, UNHINGED, PROFANE WINNER tweet about {wallet} making {pnl_str} profit on {market} - {outcome}.

RULES:
- KEEP IT SHORT (1-2 sentences max, under 100 chars)
- Be funny, profane, chaotic
- Use emojis
- When mentioning the market, format it as: "on [market name] on @Polymarket"
- Example: "just crushed the Trump election on @Polymarket"
- DO NOT put @Polymarket in weird places like "Trump vs @Polymarket Biden"
- Never start with @mention!""",
                f"""Generate a SHORT, CHAOTIC, PROFANE tweet celebrating {wallet} CRUSHING IT with {pnl_str} on {market} - {outcome}.

RULES:
- KEEP IT SHORT (1-2 sentences, under 100 chars)
- Be insane, profane, celebratory
- Lots of emojis
- When mentioning the market, say: "on [market name] on @Polymarket"
- Example: "ate the Steelers game on @Polymarket"
- NEVER insert @Polymarket in the middle of the market name
- Never start with @!""",
                f"""Generate a SHORT, BONKERS, PROFANE tweet about {wallet} PRINTING {pnl_str} on {market} - {outcome}.

RULES:
- KEEP IT SHORT (1-2 sentences max, under 100 chars)
- Be unhinged, profane, wild
- Emojis
- Format: "on [market name] on @Polymarket"
- Example: "demolished the Lions vs Buccaneers on @Polymarket"
- DO NOT write "Lions vs @Polymarket Buccaneers"
- NEVER at the start!""",
                f"""Generate a SHORT, DERANGED, PROFANE tweet about {wallet} MOONING with {pnl_str} on {market} - {outcome}.

RULES:
- KEEP IT SHORT (1-2 sentences, under 100 chars)
- Be unhinged, profane, chaotic
- Emojis
- Say: "on [market name] on @Polymarket"
- Example: "nuked the election market on @Polymarket"
- NEVER put @Polymarket inside the market name
- NOT at beginning!""",
            ]
            prompt = win_prompts[hash(wallet) % len(win_prompts)]
        else:
            # Multiple diverse losing prompts to avoid repetition
            loss_prompts = [
                f"""Generate a SHORT, UNHINGED, PROFANE LOSER tweet about {wallet} LOSING {pnl_str} on {market} - {outcome}.

RULES:
- KEEP IT SHORT (1-2 sentences max, under 100 chars)
- Be funny, profane, roast them
- Emojis
- Format: "on [market name] on @Polymarket"
- Example: "ate shit on the Buccaneers game on @Polymarket"
- DO NOT write "Buccaneers vs @Polymarket Lions"
- NOT at start!""",
                f"""Generate a SHORT, UNHINGED, PROFANE tweet about {wallet} GETTING REKT for {pnl_str} on {market} - {outcome}.

RULES:
- KEEP IT SHORT (1-2 sentences, under 100 chars)
- Be insane, profane, roast hard
- Emojis
- Say: "on [market name] on @Polymarket"
- Example: "got destroyed on the Trump market on @Polymarket"
- NEVER insert @Polymarket in the middle of market name
- NEVER at the start!""",
                f"""Generate a SHORT, BONKERS, PROFANE tweet about {wallet} BLOWING {pnl_str} on {market} - {outcome}.

RULES:
- KEEP IT SHORT (1-2 sentences max, under 100 chars)
- Be unhinged, profane, roast
- Emojis
- Format: "on [market name] on @Polymarket"
- Example: "blew it on the election on @Polymarket"
- DO NOT put @Polymarket inside the market name
- NOT at beginning!""",
                f"""Generate a SHORT, DERANGED, PROFANE tweet about {wallet} DUMPING {pnl_str} on {market} - {outcome}.

RULES:
- KEEP IT SHORT (1-2 sentences, under 100 chars)
- Be unhinged, profane, chaotic
- Emojis
- Say: "on [market name] on @Polymarket"
- Example: "dumped hard on the Steelers on @Polymarket"
- NEVER write "Steelers vs @Polymarket Ravens"
- NOT at start!""",
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

