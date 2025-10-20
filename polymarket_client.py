from __future__ import annotations
import requests
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

    def get_recent_big_claims(self, wallet: str, min_profit: float, since_minutes: int = 30) -> List[Dict[str, Any]]:
        rows = self.get_closed_positions(wallet)
        cutoff = now_utc() - timedelta(minutes=since_minutes)
        out: List[Dict[str, Any]] = []
        for row in rows:
            pnl = float(row.get("realizedPnl", 0) or 0)

            # The /closed-positions endpoint only returns positions that have been closed
            # We should filter by when the position was actually closed, not market endDate
            # However, the API may not expose the exact close timestamp
            # For now, we'll accept all closed positions with sufficient PnL
            # and rely on the deduplication cache to prevent re-posting

            if abs(pnl) >= min_profit:
                out.append(row)
        return out

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

