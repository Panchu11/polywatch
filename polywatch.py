from __future__ import annotations
import json
import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

from polymarket_client import PolymarketClient
from twitter_client import TwitterClient
from ai_client import AIClient
from state_store import PostedCache, save_json, load_json
from utils import env_bool, env_int, format_usd, describe_pnl, now_utc, now_utc_iso, short_wallet

WALLETS_PATH = "wallets.json"
POSTED_PATH = "posted.json"

DEFAULT_THRESHOLD = 1000
DEFAULT_SINCE_MINUTES = 90

FOOTER = "\nBuilt by @ForgeLabs__"
MAX_TWEET_LEN = 280  # Enforce classic 280-char limit


def load_wallets() -> List[str]:
    """Load wallets from env WALLETS (comma or whitespace-separated) or wallets.json."""
    env_val = os.getenv("WALLETS", "").strip()
    addrs: List[str] = []
    if env_val:
        sep = "," if "," in env_val else None
        addrs = [w.strip() for w in env_val.split(sep) if w.strip()]
    if not addrs:
        wallets = load_json(WALLETS_PATH, default=[])
        if isinstance(wallets, list):
            addrs = [w.strip() for w in wallets if isinstance(w, str) and w.strip()]
    return addrs


def unique_id(wallet: str, row: Dict[str, Any]) -> str:
    # Use conditionId + endDate per user to identify a unique claim per wallet/market
    return f"{wallet}:{row.get('conditionId')}:{row.get('endDate')}"


def apply_footer_and_trim(text: str, wallet: str = "", pnl: float = 0, market: str = "", outcome: str = "") -> str:
    """Compose tweet with footer and metadata and keep total <= MAX_TWEET_LEN without cutting sentences."""
    pnl_str = format_usd(abs(pnl))

    # Explicit Unicode escapes to avoid any source-encoding ambiguity
    money_bag = "\U0001F4B0"
    chart_up = "\U0001F4CA"
    link_emoji = "\U0001F517"

    # Collapse AI multi-line into a single first-line paragraph
    ai_line = " ".join((text or "").strip().splitlines())

    # Ensure @Polymarket mention is present in the FIRST sentence so it survives trimming
    _sent = re.split(r"(?<=[.!?])\s+", ai_line) if ai_line else []
    if _sent:
        if "@Polymarket" not in _sent[0]:
            # Insert before terminal punctuation so it stays in sentence 0
            m = re.match(r"^(.*?)([.!?]+)$", _sent[0])
            if m:
                _sent[0] = (m.group(1).rstrip() + " @Polymarket" + m.group(2))
            else:
                _sent[0] = (_sent[0].rstrip() + " @Polymarket")
        ai_line = " ".join(_sent)
    else:
        ai_line = "@Polymarket"


    def build_lines(ai: str) -> list[str]:
        lines = [
            ai.strip(),
            "",
            f"{money_bag} {pnl_str} on {outcome}",
            f"{chart_up} Market: {market}",
        ]
        if wallet:
            profile_link = f"https://polymarket.com/profile/{wallet}"
            lines.append("")
            lines.append(link_emoji)
            lines.append(profile_link)
        lines.append("")
        lines.append(FOOTER)
        return lines

    def build_lines_compact(ai: str) -> list[str]:
        # Remove cosmetic blank lines to save characters
        lines = [
            ai.strip(),
            f"{money_bag} {pnl_str} on {outcome}",
            f"{chart_up} Market: {market}",
        ]
        if wallet:
            profile_link = f"https://polymarket.com/profile/{wallet}"
            lines.append(link_emoji)
            lines.append(profile_link)
        lines.append(FOOTER)
        return lines

    # Initial attempt with full formatting
    lines = build_lines(ai_line)
    crafted = "\n".join(lines)
    if len(crafted) <= MAX_TWEET_LEN:
        return crafted

    # Sentence-aware fitting: include as many full sentences as fit
    sentences = re.split(r"(?<=[.!?])\s+", ai_line) if ai_line else []
    best = None
    for i in range(1, len(sentences) + 1):
        candidate_ai = " ".join(sentences[:i]).strip()
        attempt = "\n".join(build_lines(candidate_ai))
        if len(attempt) <= MAX_TWEET_LEN:
            best = attempt
        else:
            break
    if best:
        return best

    # Try compact formatting with only the first sentence
    first_sentence = (sentences[0].strip() if sentences else ai_line.split(".")[0].strip()) or ""
    if first_sentence:
        attempt = "\n".join(build_lines_compact(first_sentence))
        if len(attempt) <= MAX_TWEET_LEN:
            return attempt

    # Minimal safe AI line fallback (complete sentence, very short)
    minimal_ai = "Massive move. @Polymarket"
    attempt = "\n".join(build_lines_compact(minimal_ai))
    if len(attempt) <= MAX_TWEET_LEN:
        return attempt

    # If still too long (e.g., extremely long market title), iteratively shorten market by words
    words = market.split()
    while words:
        shorter_market = " ".join(words)
        # Rebuild compact variant with shortened market
        lines_c = build_lines_compact(minimal_ai)
        # Replace market line (index 2 in compact format)
        lines_c[2] = f"{chart_up} Market: {shorter_market}"
        crafted_c = "\n".join(lines_c)
        if len(crafted_c) <= MAX_TWEET_LEN:
            return crafted_c
        words.pop()  # drop last word and retry

    # As a last resort, return the compact minimal variant (AI sentence intact) with a hard-cropped market at word boundary
    mk = market
    lines_c = build_lines_compact(minimal_ai)
    # Reduce market until it fits; do not cut the AI sentence
    while True:
        lines_c[2] = f"{chart_up} Market: {mk}".rstrip()
        crafted_c = "\n".join(lines_c)
        if len(crafted_c) <= MAX_TWEET_LEN or not mk:
            return crafted_c
        # remove last word or last char
        if " " in mk:
            mk = mk.rsplit(" ", 1)[0]
        else:
            mk = mk[:-1]


def _sanitize_ai_text(text: str) -> str:
    """Ensure @Polymarket is mentioned correctly in the format 'on @Polymarket'."""
    # Normalize CRLF to LF and trim trailing spaces on lines
    text = text.replace("\r", "")
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Normalize any @Polymarket variants to canonical form
    text = re.sub(r"@Polymarket\w+", "@Polymarket", text)

    # Check if AI already used the correct format "on @Polymarket"
    if "on @Polymarket" in text:
        # Good! AI followed instructions. Just clean up spacing.
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # AI didn't use correct format. Remove all @Polymarket and add it properly.
    # Remove ALL @Polymarket mentions
    text = re.sub(r"@Polymarket\s*", "", text)

    # Clean up any leftover artifacts from removal
    text = re.sub(r"\s+\.\s+", ". ", text)  # " . " -> ". "
    text = re.sub(r"\s+\.", ".", text)       # " ." -> "."
    text = re.sub(r"\s+", " ", text).strip()

    # Add "on @Polymarket" at the end of the FIRST sentence
    sentences = re.split(r"(?<=[.!?])\s+", text) if text else []
    if sentences:
        # Add "on @Polymarket" before the terminal punctuation of the first sentence
        m = re.match(r"^(.*?)([.!?]+)$", sentences[0])
        if m:
            sentences[0] = (m.group(1).rstrip() + " on @Polymarket" + m.group(2))
        else:
            sentences[0] = (sentences[0].rstrip() + " on @Polymarket")
        text = " ".join(sentences)
    else:
        text = "on @Polymarket"
    return text


def format_tweet(ai_client: AIClient, wallet: str, row: Dict[str, Any], client: PolymarketClient = None) -> str:
    """Generate tweet using AI model with multi-line format."""
    title = row.get("title") or row.get("slug") or "a market"
    outcome = row.get("outcome") or row.get("oppositeOutcome") or "?"
    pnl = float(row.get("realizedPnl", 0) or 0)
    full_wallet = wallet or row.get("proxyWallet", "")

    # Try to get profile name, fallback to shortened wallet
    display_name = None
    if client:
        display_name = client.lookup_profile_name(full_wallet)

    if not display_name:
        display_name = short_wallet(full_wallet)

    # Try to generate AI tweet
    ai_tweet = ai_client.generate_tweet(display_name, pnl, title, outcome)

    if ai_tweet:
        # Use AI-generated tweet with sanitization
        base = _sanitize_ai_text(ai_tweet)
    else:
        # Fallback to simple format if AI fails - still include @Polymarket
        base = f"{display_name} just made a big move on '{title}' with {describe_pnl(pnl)} via @Polymarket! \U0001F3AF"

    return apply_footer_and_trim(base, full_wallet, pnl, title, outcome)


def within_daily_cap(cache: PostedCache, max_per_day: int) -> bool:
    # Count from last 24 hours
    since = (now_utc() - timedelta(hours=24)).isoformat()
    return cache.count_since(since) < max_per_day


def main():
    print("[PolyWatch] Starting run @", now_utc_iso())
    dry_run = env_bool("DRY_RUN", True)
    threshold = env_int("MIN_PROFIT_USD", DEFAULT_THRESHOLD)
    since_minutes = env_int("SINCE_MINUTES", DEFAULT_SINCE_MINUTES)
    max_per_day = env_int("MAX_TWEETS_PER_DAY", 17)

    wallets = load_wallets()

    client = PolymarketClient()
    tw = TwitterClient()
    ai = AIClient()
    posted = PostedCache(POSTED_PATH)

    # Optional: single test tweet path
    test_text = os.getenv("TEST_TWEET_TEXT", "").strip()
    if test_text:
        try:
            tweet_text = apply_footer_and_trim(test_text)
            if dry_run:
                print("[PolyWatch] DRY_RUN: would tweet (TEST_TWEET_TEXT):", tweet_text)
            else:
                tweet_id = tw.post_tweet(tweet_text)
                print("[PolyWatch] Test tweet posted:", tweet_id, tweet_text)
            return
        except Exception as e:
            print("[PolyWatch] Error posting test tweet:", e)
            return

    # Check daily cap
    cap_ok = within_daily_cap(posted, max_per_day)
    if not cap_ok:
        print("[PolyWatch] Daily cap reached — not posting.")
        return

    global_mode = env_bool("GLOBAL_MODE", True) or not wallets

    if global_mode:
        print("[PolyWatch] Running in GLOBAL mode (calculating PnL from recent trades)")

        try:
            positions = client.get_recent_pnl_from_trades(since_minutes=since_minutes, min_pnl=threshold)
        except Exception as e:
            print("[PolyWatch] Error calculating PnL from trades:", e)
            import traceback
            traceback.print_exc()
            return

        if not positions:
            print("[PolyWatch] No qualifying positions found in the last {since_minutes} minutes.")
            return

        print(f"[PolyWatch] Found {len(positions)} positions with PnL >= ${threshold:,.0f} from recent trades.")

        # Collect all claims and sort by absolute PnL (biggest first)
        all_claims = []
        for row in positions:
            wallet = row.get("wallet") or row.get("proxyWallet")
            if not wallet:
                continue

            uid = unique_id(wallet, row)
            if posted.contains(uid):
                print(f"[PolyWatch] Skipping {uid} — already posted")
                continue

            display = client.lookup_profile_name(wallet) or short_wallet(wallet)
            pnl = float(row.get("realizedPnl", 0) or 0)

            all_claims.append({
                "id": uid,
                "wallet": wallet,
                "display": display,
                "row": row,
                "pnl": pnl,
                "abs_pnl": abs(pnl),
            })

        if not all_claims:
            print("[PolyWatch] No new qualifying claims found.")
            return

        # Sort by absolute PnL (biggest first) and take top 1
        all_claims.sort(key=lambda x: x["abs_pnl"], reverse=True)
        top_claim = all_claims[0]

        print(f"[PolyWatch] Found {len(all_claims)} qualifying claims, posting top 1")

        # Generate and post tweet immediately
        text = format_tweet(ai, top_claim["wallet"], top_claim["row"], client)

        try:
            if dry_run:
                print("[PolyWatch] DRY_RUN: would tweet (trade_id: {})".format(top_claim["id"]))
                # Save tweet content for inspection
                with open("last_tweet.txt", "w", encoding="utf-8") as f:
                    f.write(text)
                tweet_id = None
            else:
                tweet_id = tw.post_tweet(text)
                print("[PolyWatch] Tweet posted:", tweet_id)
        except Exception as e:
            print("[PolyWatch] Error posting tweet:", e)
            return

        # Always add to cache, even in dry-run
        try:
            posted.add(top_claim["id"], tweet_id)
            print("[PolyWatch] Posted 1 tweet this run (dry_run={}).".format(dry_run))
        except Exception as e:
            print("[PolyWatch] Error saving to cache:", e)
    else:
        print("[PolyWatch] GLOBAL_MODE disabled and no wallets configured — nothing to do.")
        return


if __name__ == "__main__":
    main()

