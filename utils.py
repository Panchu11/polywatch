from __future__ import annotations
import os
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_utc_iso() -> str:
    return now_utc().isoformat()


def parse_iso(dt: str) -> datetime:
    # Handles both with/without timezone Z
    try:
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except Exception:
        # Best-effort: if not parseable, return epoch
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def format_usd(amount: float | int) -> str:
    # Format with commas; keep 0 decimals if integer, else 2 decimals
    neg = amount < 0
    val = -amount if neg else amount
    if val == int(val):
        s = f"${int(val):,}"
    else:
        s = f"${val:,.2f}"
    return f"-{s}" if neg else s

def describe_pnl(pnl: float | int) -> str:
    kind = "profit" if pnl >= 0 else "loss"
    return f"{format_usd(pnl if pnl >= 0 else -pnl)} {kind}"


def short_wallet(addr: str) -> str:
    if not addr or len(addr) < 10:
        return addr
    return f"{addr[:6]}…{addr[-4:]}"


def env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "t", "yes", "y"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

