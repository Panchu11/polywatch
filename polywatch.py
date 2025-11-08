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

DEFAULT_THRESHOLD = 10000
DEFAULT_SINCE_MINUTES = 90

FOOTER = "\nBuilt by @ForgeLabs__"
CTA = "Copy trade via TG alerts: https://tinyurl.com/3fe62ksz"

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

    # Ensure first sentence ends with "on @Polymarket" so it survives trimming
    _sent = re.split(r"(?<=[.!?])\s+", ai_line) if ai_line else []
    if _sent:
        if "@Polymarket" not in _sent[0]:
            # Insert before terminal punctuation; avoid double "on"
            m = re.match(r"^(.*?)([.!?]+)$", _sent[0])
            if m:
                base, punct = m.group(1).rstrip(), m.group(2)
                base = re.sub(r"\s+on\s*$", "", base, flags=re.IGNORECASE)
                _sent[0] = (base + " on @Polymarket" + punct)
            else:
                s0 = re.sub(r"\s+on\s*$", "", _sent[0].rstrip(), flags=re.IGNORECASE)
                _sent[0] = (s0 + " on @Polymarket")
        ai_line = " ".join(_sent)
    else:
        ai_line = "on @Polymarket"

    # Heuristic fix: if the AI left a dangling "vs" before the tag, replace with the full market name
    if market:
        ai_line = re.sub(r"\bon\s+[^.!?]*?\bvs\.?\s+on @Polymarket\b", f"on {market} on @Polymarket", ai_line, flags=re.IGNORECASE)
        ai_line = re.sub(r"\bvs\.?\s+on @Polymarket\b", f"{market} on @Polymarket", ai_line, flags=re.IGNORECASE)


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
        lines.append(CTA)
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
        lines.append(CTA)
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

    # If first sentence still too long, try shortening the MARKET TITLE first (not the AI text)
    # This preserves the AI personality while fitting in 280 chars
    if first_sentence:
        words = market.split()
        while len(words) > 3:  # Keep at least 3 words of market title
            shorter_market = " ".join(words)
            lines_c = build_lines_compact(first_sentence)
            lines_c[2] = f"{chart_up} Market: {shorter_market}"
            crafted_c = "\n".join(lines_c)
            if len(crafted_c) <= MAX_TWEET_LEN:
                return crafted_c
            words.pop()  # drop last word and retry

    # If still too long, try with even shorter market (down to 1 word)
    if first_sentence:
        words = market.split()
        while words:
            shorter_market = " ".join(words)
            lines_c = build_lines_compact(first_sentence)
            lines_c[2] = f"{chart_up} Market: {shorter_market}"
            crafted_c = "\n".join(lines_c)
            if len(crafted_c) <= MAX_TWEET_LEN:
                return crafted_c
            words.pop()

    # Before falling back to minimal AI, progressively drop non-essential lines while keeping the first sentence (to preserve display_name)
    if first_sentence:
        lines_keep = build_lines_compact(first_sentence)
        # Drop chart line first
        lines_no_chart = [ln for ln in lines_keep if not ln.startswith(f"{chart_up} ")]
        crafted_nc = "\n".join(lines_no_chart)
        if len(crafted_nc) <= MAX_TWEET_LEN:
            return crafted_nc
        # Drop link emoji glyph next (keep URL)
        lines_no_emoji = [ln for ln in lines_no_chart if ln != link_emoji]
        crafted_ne = "\n".join(lines_no_emoji)
        if len(crafted_ne) <= MAX_TWEET_LEN:
            return crafted_ne
        # Try shrinking the AI line to identity-only while keeping money line
        if wallet and short_wallet(wallet) in first_sentence:
            identity_only = f"{short_wallet(wallet)} on @Polymarket"
        else:
            identity_only = "Trader on @Polymarket"
        lines_shrink = [identity_only] + [ln for ln in lines_no_emoji[1:]]
        crafted_shrink = "\n".join(lines_shrink)
        if len(crafted_shrink) <= MAX_TWEET_LEN:
            return crafted_shrink

        # Drop money line only if still too long
        lines_no_money = [ln for ln in lines_no_emoji if not ln.startswith(f"{money_bag} ")]
        crafted_nm = "\n".join(lines_no_money)
        if len(crafted_nm) <= MAX_TWEET_LEN:
            return crafted_nm

    # ONLY NOW fall back to minimal AI (as absolute last resort)
    minimal_ai = "Massive move. @Polymarket"
    attempt = "\n".join(build_lines_compact(minimal_ai))
    if len(attempt) <= MAX_TWEET_LEN:
        return attempt

    # If even minimal AI + metadata is too long, shorten market with minimal AI
    words = market.split()
    while words:
        shorter_market = " ".join(words)
        lines_c = build_lines_compact(minimal_ai)
        lines_c[2] = f"{chart_up} Market: {shorter_market}"
        crafted_c = "\n".join(lines_c)
        if len(crafted_c) <= MAX_TWEET_LEN:
            return crafted_c
        words.pop()

    # As a last resort, try compact minimal variant and progressively drop non-essential lines until it fits
    mk = market
    lines_c = build_lines_compact(minimal_ai)
    while True:
        lines_c[2] = f"{chart_up} Market: {mk}".rstrip()
        crafted_c = "\n".join(lines_c)
        if len(crafted_c) <= MAX_TWEET_LEN:
            return crafted_c
        if not mk:
            break
        if " " in mk:
            mk = mk.rsplit(" ", 1)[0]
        else:
            mk = mk[:-1]

    # If still too long after emptying market title, drop chart line
    lines_no_chart = [ln for ln in lines_c if not ln.startswith(f"{chart_up} ")]
    crafted_nc = "\n".join(lines_no_chart)
    if len(crafted_nc) <= MAX_TWEET_LEN:
        return crafted_nc

    # Drop money line next
    lines_no_money = [ln for ln in lines_no_chart if not ln.startswith(f"{money_bag} ")]
    crafted_nm = "\n".join(lines_no_money)
    if len(crafted_nm) <= MAX_TWEET_LEN:
        return crafted_nm

    # Drop link emoji glyph (keep the URL line)
    lines_no_emoji = [ln for ln in lines_no_money if ln != link_emoji]
    crafted_ne = "\n".join(lines_no_emoji)
    if len(crafted_ne) <= MAX_TWEET_LEN:
        return crafted_ne

    # Absolute fallback: shrink AI line to a tiny identity (avoid '...' from short wallets)
    tail = [ln for ln in lines_no_emoji if ln != lines_no_emoji[0]]
    tiny_ai = "Trader on @Polymarket"
    assembled = "\n".join([tiny_ai] + tail)
    return assembled[:MAX_TWEET_LEN]


def _sanitize_ai_text(text: str) -> str:
    """Place @Polymarket naturally: ensure first sentence ends with "on @Polymarket" and remove stray mentions elsewhere."""
    # Normalize CRLF to LF and trim trailing spaces on lines
    text = (text or "").replace("\r", "")
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Normalize any @Polymarket variants to the canonical handle, then remove all occurrences
    text = re.sub(r"@Polymarket\w+", "@Polymarket", text)
    text = re.sub(r"@Polymarket\s*", "", text)

    # Clean up artifacts from removal
    text = re.sub(r"\s+\.\s+", ". ", text)  # " . " -> ". "
    text = re.sub(r"\s+\.", ".", text)       # " ." -> "."
    # If removal left a trailing "on" before punctuation (e.g., "game on."), drop it
    text = re.sub(r"\s+on(\s*[.!?])", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()

    # Add "on @Polymarket" at the end of the FIRST sentence (before its terminal punctuation if present)
    sentences = re.split(r"(?<=[.!?])\s+", text) if text else []
    if sentences:
        m = re.match(r"^(.*?)([.!?]+)$", sentences[0])
        if m:
            base, punct = m.group(1).rstrip(), m.group(2)
            # Avoid double "on" when appending
            base = re.sub(r"\s+on\s*$", "", base, flags=re.IGNORECASE)
            sentences[0] = f"{base} on @Polymarket{punct}"
        else:
            s0 = re.sub(r"\s+on\s*$", "", sentences[0].rstrip(), flags=re.IGNORECASE)
            sentences[0] = s0 + " on @Polymarket"
        text = " ".join(sentences)
    else:
        text = "on @Polymarket"
    # Final cleanups to avoid artifacts like "on on @Polymarket" or a stray trailing "on"
    text = re.sub(r"\bon\s+on\s+@Polymarket\b", "on @Polymarket", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)(?<!@Polymarket)\s+on\s*$", "", text)
    return text


def format_tweet(ai_client: AIClient, wallet: str, row: Dict[str, Any], client: PolymarketClient = None) -> str:
    """Generate tweet using AI model with multi-line format."""
    title = row.get("title") or row.get("slug") or "a market"
    outcome = row.get("outcome") or row.get("oppositeOutcome") or "?"
    pnl = float(row.get("realizedPnl", 0) or 0)
    full_wallet = wallet or row.get("proxyWallet", "")

    # Try to get X/Twitter handle first, then profile name, fallback to shortened wallet
    display_name = None
    if client:
        # Try to get X handle
        twitter_handle = client.get_twitter_handle(full_wallet)
        if twitter_handle:
            display_name = f"@{twitter_handle}"
        else:
            # Fallback to profile name
            display_name = client.lookup_profile_name(full_wallet)

    if not display_name:
        display_name = short_wallet(full_wallet)

    # Generate tweet - our new generator already includes proper @Polymarket placement
    ai_tweet = ai_client.generate_tweet(display_name, pnl, title, outcome)

    if ai_tweet:
        # Use AI-generated tweet directly (already properly formatted)
        base = ai_tweet
    else:
        # Fallback to simple format if AI fails
        base = f"{display_name} just made a big move on {title} on @Polymarket! \U0001F3AF"

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
        require_x_handle = env_bool("REQUIRE_X_HANDLE", False)
        print("[PolyWatch] Running in GLOBAL mode (calculating PnL from recent trades)")
        if require_x_handle:
            print("[PolyWatch] X Handle Filter: ENABLED (only posting trades from users with linked X handles)")
        else:
            print("[PolyWatch] X Handle Filter: DISABLED (posting all qualifying trades)")

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

        # Check if we should filter by X handle
        require_x_handle = env_bool("REQUIRE_X_HANDLE", False)

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

            # If filtering by X handle, check if user has one
            if require_x_handle:
                twitter_handle = client.get_twitter_handle(wallet)
                if not twitter_handle:
                    print(f"[PolyWatch] Skipping {short_wallet(wallet)} — no X handle linked")
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
            if require_x_handle:
                print("[PolyWatch] No new qualifying claims found with X handles linked.")
            else:
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

