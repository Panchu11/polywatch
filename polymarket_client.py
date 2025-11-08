from __future__ import annotations
import requests
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional
from utils import parse_iso, now_utc

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"


class PolymarketClient:
    def __init__(self, timeout: int = 15):
        self.session = requests.Session()
        self.timeout = timeout

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        r = self.session.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_closed_positions(self, wallet: str, limit: int = 100) -> List[Dict[str, Any]]:
        url = f"{DATA_API}/closed-positions"
        params = {
            "user": wallet,
            "limit": limit,
            "sortBy": "REALIZEDPNL",
            "sortDirection": "DESC",
        }
        return self._get(url, params=params)

    def get_recent_pnl_from_trades(self, since_minutes: int = 90, min_pnl: float = 1000) -> List[Dict[str, Any]]:
        """
        Calculate realized PnL from recent trades (last `since_minutes`).

        Returns a list of dicts with:
        - wallet: trader address
        - conditionId: market condition ID
        - title: market title
        - outcome: outcome name
        - realizedPnl: calculated PnL from trades
        - endDate: market end date
        - trade_count: number of trades in this position
        - latest_trade_time: timestamp of most recent trade

        Only includes positions with abs(realizedPnl) >= min_pnl.
        """
        # Fetch all recent trades
        url = f"{DATA_API}/trades"
        params = {
            "limit": 10000,  # Get as many recent trades as possible
        }

        try:
            all_trades = self._get(url, params=params)
        except Exception as e:
            print(f"[PolymarketClient] Error fetching trades: {e}")
            return []

        if not isinstance(all_trades, list):
            return []

        # Filter to only trades within time window
        cutoff_timestamp = int((now_utc() - timedelta(minutes=since_minutes)).timestamp())
        recent_trades = []
        for trade in all_trades:
            if not isinstance(trade, dict):
                continue
            ts = trade.get("timestamp")
            if ts and int(ts) >= cutoff_timestamp:
                recent_trades.append(trade)

        if not recent_trades:
            return []

        # Group trades by (wallet, conditionId)
        from collections import defaultdict
        positions = defaultdict(lambda: {
            "trades": [],
            "wallet": None,
            "conditionId": None,
            "title": None,
            "outcome": None,
            "endDate": None,
        })

        for trade in recent_trades:
            wallet = trade.get("proxyWallet")
            condition_id = trade.get("conditionId")
            if not wallet or not condition_id:
                continue

            key = (wallet, condition_id)
            positions[key]["trades"].append(trade)
            positions[key]["wallet"] = wallet
            positions[key]["conditionId"] = condition_id
            positions[key]["title"] = trade.get("title") or positions[key]["title"]
            positions[key]["outcome"] = trade.get("outcome") or positions[key]["outcome"]
            positions[key]["endDate"] = trade.get("endDate") or positions[key]["endDate"]

        # Calculate PnL for each position
        results = []
        for (wallet, condition_id), pos_data in positions.items():
            trades = pos_data["trades"]

            # Simple PnL calculation: sum of (side * price * size)
            # Buy = negative cash flow, Sell = positive cash flow
            total_pnl = 0.0
            for trade in trades:
                side = trade.get("side", "").upper()
                price = float(trade.get("price", 0) or 0)
                size = float(trade.get("size", 0) or 0)

                if side == "BUY":
                    total_pnl -= price * size
                elif side == "SELL":
                    total_pnl += price * size

            if abs(total_pnl) < min_pnl:
                continue

            # Get latest trade timestamp
            latest_ts = max(int(t.get("timestamp", 0)) for t in trades)

            results.append({
                "wallet": wallet,
                "conditionId": condition_id,
                "title": pos_data["title"] or "Unknown Market",
                "outcome": pos_data["outcome"] or "Unknown",
                "realizedPnl": total_pnl,
                "endDate": pos_data["endDate"],
                "trade_count": len(trades),
                "latest_trade_time": latest_ts,
                "proxyWallet": wallet,  # For compatibility with existing code
            })

        return results

    def get_trades_for_market(self, condition_id: str, limit: int = 1000, min_cash: Optional[float] = None) -> List[Dict[str, Any]]:
        url = f"{DATA_API}/trades"
        params: Dict[str, Any] = {
            "limit": limit,
            "takerOnly": True,
            "market": [condition_id],
        }
        if min_cash is not None:
            params.update({"filterType": "CASH", "filterAmount": min_cash})
        return self._get(url, params=params)

    def get_recently_closed_markets(self, since_minutes: int = 30, limit: int = 200) -> List[Dict[str, Any]]:
        # Fallback: return empty list. The Gamma API doesn't reliably expose recently closed markets.
        # Use get_recent_big_trades() instead to find recent large trades.
        return []

    def get_recent_big_trades(self, min_cash: float = 500, since_minutes: int = 30, limit: int = 1000) -> List[Dict[str, Any]]:
        """Fetch recent large trades from the Data API."""
        url = f"{DATA_API}/trades"
        params = {
            "limit": limit,
            "filterType": "CASH",
            "filterAmount": min_cash,
        }
        try:
            data = self._get(url, params=params)
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        cutoff_timestamp = int((now_utc() - timedelta(minutes=since_minutes)).timestamp())
        out: List[Dict[str, Any]] = []
        for trade in data:
            if not isinstance(trade, dict):
                continue
            # Check if trade is recent (trades use Unix timestamp)
            ts = trade.get("timestamp")
            if ts and int(ts) >= cutoff_timestamp:
                out.append(trade)
        return out

    def lookup_profile_name(self, wallet: str) -> Optional[str]:
        # Try gamma search for a profile matching proxyWallet
        url = f"{GAMMA_API}/public-search"
        params = {"q": wallet, "limit": 5}
        try:
            data = self._get(url, params=params)
        except Exception:
            return None
        if isinstance(data, dict):
            profiles = data.get("profiles") or data.get("data") or []
        elif isinstance(data, list):
            profiles = data
        else:
            profiles = []
        for p in profiles:
            if str(p.get("proxyWallet", "")).lower() == wallet.lower():
                # Prefer pseudonym then name
                return p.get("pseudonym") or p.get("name")
        # Fallback: if any profile returned, take pseudonym
        if profiles:
            return profiles[0].get("pseudonym") or profiles[0].get("name")
        return None

    def get_twitter_handle(self, wallet: str) -> Optional[str]:
        """
        Fetch X/Twitter handle from Polymarket profile page.

        Returns the handle without @ prefix, or None if not found.
        Uses a simple regex-based approach to extract from embedded JSON data.
        """
        try:
            # Fetch the profile page HTML
            profile_url = f"https://polymarket.com/profile/{wallet}"
            response = self.session.get(profile_url, timeout=self.timeout)
            response.raise_for_status()
            html = response.text

            # Look for social links in the embedded JSON data
            # Pattern: "socialLinks":[{"type":"twitter","url":"https://x.com/username"}]
            # or "twitter":"username" or similar

            # Try to find Twitter/X link in socialLinks array
            social_links_match = re.search(
                r'"socialLinks"\s*:\s*\[([^\]]+)\]',
                html
            )
            if social_links_match:
                social_links_json = social_links_match.group(1)
                # Look for twitter type with URL
                twitter_url_match = re.search(
                    r'"type"\s*:\s*"twitter"[^}]*"url"\s*:\s*"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)"',
                    social_links_json
                )
                if twitter_url_match:
                    handle = twitter_url_match.group(1)
                    # Filter out common non-user paths and Polymarket itself
                    if handle.lower() not in ['intent', 'share', 'i', 'home', 'explore', 'notifications', 'messages', 'polymarket']:
                        return handle

            # Fallback: look for any X/Twitter link in the page (but filter more strictly)
            # This is less reliable but might catch some cases
            all_twitter_links = re.findall(
                r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)',
                html
            )
            for handle in all_twitter_links:
                # Filter out common non-user paths and Polymarket
                if handle.lower() not in ['intent', 'share', 'i', 'home', 'explore', 'notifications', 'messages', 'polymarket', 'forgelabs__']:
                    return handle

            return None

        except Exception as e:
            # Silently fail - X handle is optional
            print(f"Warning: Could not fetch X handle for {wallet}: {e}")
            return None

