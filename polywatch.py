from __future__ import annotations
import json
import os
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
PENDING_PATH = "tweets.json"

DEFAULT_THRESHOLD = 10000
DEFAULT_SINCE_MINUTES = 30

FOOTER = "\nBuilt by @Panchu2605"
MAX_TWEET_LEN = 280


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
    """Apply footer and trim to fit Twitter character limit with multi-line format."""
    # Format: AI tweet + wallet/pnl info + market + link + footer
    pnl_str = format_usd(abs(pnl))

    # Build multi-line tweet
    lines = [
        text.strip(),  # AI-generated content
        "",
        f"💰 {pnl_str} on {outcome}",
        f"📊 Market: {market}",
    ]

    if wallet:
        # Add Polymarket profile link on separate line with 🔗 indicator
        profile_link = f"https://polymarket.com/profile/{wallet}?ref=caneleo"
        lines.append("")
        lines.append("🔗")
        lines.append(profile_link)

    lines.append("")
    lines.append(FOOTER)

    crafted = "\n".join(lines)

    # If too long, trim the AI-generated content
    if len(crafted) > MAX_TWEET_LEN:
        available = MAX_TWEET_LEN - len("\n".join(lines[1:])) - 10
        trimmed_text = text[:available].rstrip() + "..."
        lines[0] = trimmed_text
        crafted = "\n".join(lines)

    return crafted


def format_tweet(ai_client: AIClient, wallet: str, row: Dict[str, Any]) -> str:
    """Generate tweet using AI model with multi-line format."""
    title = row.get("title") or row.get("slug") or "a market"
    outcome = row.get("outcome") or row.get("oppositeOutcome") or "?"
    pnl = float(row.get("realizedPnl", 0) or 0)
    full_wallet = wallet or row.get("proxyWallet", "")

    # Use shortened wallet for display
    short_addr = short_wallet(full_wallet)

    # Try to generate AI tweet
    ai_tweet = ai_client.generate_tweet(short_addr, pnl, title, outcome)

    if ai_tweet:
        # Use AI-generated tweet
        base = ai_tweet
    else:
        # Fallback to simple format if AI fails
        base = f"{short_addr} just made a big move on '{title}' with {describe_pnl(pnl)}! 🎯"

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
    pending: List[Dict[str, Any]] = load_json(PENDING_PATH, default=[])

    new_tweets: List[Dict[str, Any]] = []

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

    # Enforce daily cap before attempting network posts; we still collect pending
    cap_ok = within_daily_cap(posted, max_per_day)

    global_mode = env_bool("GLOBAL_MODE", True) or not wallets

    if global_mode:
        print("[PolyWatch] Running in GLOBAL mode (scanning recent big trades)")
        min_trade_cash = env_int("MIN_TRADE_CASH", 500)
        top_n = env_int("TOP_N_TRADES", 3)

        try:
            big_trades = client.get_recent_big_trades(min_cash=min_trade_cash, since_minutes=since_minutes, limit=1000)
        except Exception as e:
            print("[PolyWatch] Error fetching recent big trades:", e)
            big_trades = []

        if not big_trades:
            print("[PolyWatch] No recent big trades found in window.")
        else:
            print(f"[PolyWatch] Found {len(big_trades)} recent big trades.")

        # Collect unique wallets from trades
        wallets_set = set()
        for trade in big_trades:
            w = trade.get("proxyWallet")
            if w:
                wallets_set.add(w)

        print(f"[PolyWatch] Checking {len(wallets_set)} unique traders for big PnL...")

        # Collect all claims and sort by absolute PnL (biggest first)
        all_claims = []
        for wallet in wallets_set:
            try:
                claims = client.get_recent_big_claims(wallet, min_profit=threshold, since_minutes=since_minutes)
            except Exception as e:
                continue

            if not claims:
                continue

            display = client.lookup_profile_name(wallet) or short_wallet(wallet)
            for row in claims:
                uid = unique_id(wallet, row)
                if posted.contains(uid):
                    continue
                pnl = float(row.get("realizedPnl", 0) or 0)
                all_claims.append({
                    "id": uid,
                    "wallet": wallet,
                    "display": display,
                    "row": row,
                    "pnl": pnl,
                    "abs_pnl": abs(pnl),
                })

        # Sort by absolute PnL (biggest first) and take top N
        all_claims.sort(key=lambda x: x["abs_pnl"], reverse=True)
        top_claims = all_claims[:top_n]

        print(f"[PolyWatch] Found {len(all_claims)} qualifying claims, posting top {len(top_claims)}")

        for claim in top_claims:
            text = format_tweet(ai, claim["wallet"], claim["row"])
            entry = {
                "id": claim["id"],
                "wallet": claim["wallet"],
                "display": claim["display"],
                "tweet": text,
                "row": claim["row"],
                "created_at": now_utc_iso(),
            }
            new_tweets.append(entry)
    else:
        if not wallets:
            print("[PolyWatch] No wallets configured — nothing to do.")
            return
        for wallet in wallets:
            try:
                claims = client.get_recent_big_claims(wallet, min_profit=threshold, since_minutes=since_minutes)
            except Exception as e:
                print(f"[PolyWatch] Error fetching claims for {wallet}: {e}")
                continue
            if not claims:
                continue
            # Lookup display name once per wallet
            display = client.lookup_profile_name(wallet) or short_wallet(wallet)

            for row in claims:
                uid = unique_id(wallet, row)
                if posted.contains(uid):
                    continue
                text = format_tweet(ai, wallet, row)
                entry = {
                    "id": uid,
                    "wallet": wallet,
                    "display": display,
                    "tweet": text,
                    "row": row,
                    "created_at": now_utc_iso(),
                }
                new_tweets.append(entry)

    if not new_tweets:
        print("[PolyWatch] No new qualifying claims found.")
        return

    # Save to pending queue for review (append)
    pending.extend(new_tweets)
    save_json(PENDING_PATH, pending)
    print(f"[PolyWatch] Queued {len(new_tweets)} tweets to {PENDING_PATH}")

    # Post if allowed
    if not cap_ok:
        print("[PolyWatch] Daily cap reached — not posting.")
        return

    posted_now = 0
    for entry in new_tweets:
        if not within_daily_cap(posted, max_per_day):
            print("[PolyWatch] Reached daily cap mid-run — stopping posts.")
            break
        try:
            if dry_run:
                print("[PolyWatch] DRY_RUN: would tweet:", entry["tweet"])
                tweet_id = None
            else:
                tweet_id = tw.post_tweet(entry["tweet"])  # may raise if creds missing
                print("[PolyWatch] Tweet posted:", tweet_id, entry["tweet"])
            posted.add(entry["id"], tweet_id)
            posted_now += 1
        except Exception as e:
            print("[PolyWatch] Error posting tweet:", e)

    print(f"[PolyWatch] Posted {posted_now} tweets this run (dry_run={dry_run}).")


if __name__ == "__main__":
    main()

