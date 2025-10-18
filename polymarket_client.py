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
            end_date = row.get("endDate") or ""
            ended = parse_iso(end_date)
            if abs(pnl) >= min_profit and ended >= cutoff:
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
        # Best-effort: fetch recently updated/closed markets and filter locally
        url = f"{GAMMA_API}/markets"
        params_list = [
            {"limit": limit, "closed": True, "sortBy": "closedTime", "sortDirection": "desc"},
            {"limit": limit, "sortBy": "updatedAt", "sortDirection": "desc"},
        ]
        data: Any = None
        for params in params_list:
            try:
                data = self._get(url, params=params)
                break
            except Exception:
                data = None
        if not data:
            return []
        items = data.get("markets") or data.get("data") or data
        if not isinstance(items, list):
            return []
        cutoff = now_utc() - timedelta(minutes=since_minutes)
        out: List[Dict[str, Any]] = []
        for m in items:
            # Heuristic fields
            closed = bool(m.get("closed") or m.get("resolved") or False)
            closed_time = m.get("closedTime") or m.get("endDate") or m.get("resolveTime") or m.get("lastTradedAt")
            try:
                ct = parse_iso(str(closed_time)) if closed_time else None
            except Exception:
                ct = None
            if closed and ct and ct >= cutoff:
                out.append(m)
        return out

    def lookup_profile_name(self, wallet: str) -> Optional[str]:
        # Try gamma search for a profile matching proxyWallet
        url = f"{GAMMA_API}/public-search"
        params = {"q": wallet, "limit": 5}
        try:
            data = self._get(url, params=params)
        except Exception:
            return None
        profiles = data.get("profiles") or []
        for p in profiles:
            if str(p.get("proxyWallet", "")).lower() == wallet.lower():
                # Prefer pseudonym then name
                return p.get("pseudonym") or p.get("name")
        # Fallback: if any profile returned, take pseudonym
        if profiles:
            return profiles[0].get("pseudonym") or profiles[0].get("name")
        return None

