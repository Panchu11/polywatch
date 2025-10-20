# PolyWatch Bot - 90-Minute Window Implementation

## Summary

The bot has been updated to **only fetch and post trades from the last 90 minutes**, based on actual trade timestamps rather than market end dates.

## What Changed

### Previous Behavior (BROKEN)
- Fetched closed positions per wallet
- Tried to filter by timestamps, but API didn't provide reliable close timestamps
- Fell back to using `endDate` (market resolution date), which is a **future date**
- Result: Old positions (even from 2022) could be posted if the market hadn't resolved yet

### New Behavior (FIXED)
- Fetches recent trades directly from the `/trades` API endpoint
- Filters trades to only those within the last `SINCE_MINUTES` (default: 90)
- Groups trades by (wallet, conditionId) to calculate realized PnL
- Only considers positions with trades in the specified time window
- Posts the single highest absolute PnL position

## Key Changes

### 1. New Method: `get_recent_pnl_from_trades()`
**File:** `polymarket_client.py`

```python
def get_recent_pnl_from_trades(self, since_minutes: int = 90, min_pnl: float = 10000):
    """
    Calculate realized PnL from recent trades (last `since_minutes`).
    Returns positions with abs(realizedPnl) >= min_pnl.
    """
```

This method:
- Fetches up to 10,000 recent trades from the API
- Filters to only trades within the time window (using Unix timestamps)
- Groups by (wallet, conditionId)
- Calculates PnL: BUY = negative cash flow, SELL = positive cash flow
- Returns only positions meeting the minimum PnL threshold

### 2. Updated Main Loop
**File:** `polywatch.py`

Changed from:
- Scanning wallets → fetching closed positions per wallet → filtering by PnL

To:
- Fetching all recent trades → calculating PnL from trades → filtering by PnL

## Configuration

### Environment Variables

```bash
# Time window for fetching trades (in minutes)
SINCE_MINUTES=90

# Minimum absolute PnL to post (in USD)
MIN_PROFIT_USD=10000

# Dry run mode (true = don't post to Twitter)
DRY_RUN=false
```

### Recommended Schedule

Run the bot **every 2 hours** to catch positions from the last 90 minutes:

**Windows Task Scheduler:**
```
Program: python
Arguments: polywatch.py
Start in: C:\Users\panchu\Desktop\polywatch
Trigger: Every 2 hours
```

**Cron (Linux/Mac):**
```cron
0 */2 * * * cd /path/to/polywatch && python polywatch.py
```

## Testing Results

### Dry Run Test (90-minute window)
```
[PolyWatch] Running in GLOBAL mode (calculating PnL from recent trades)
[PolyWatch] Found 1 positions with PnL >= $10,000 from recent trades.
[PolyWatch] Found 1 qualifying claims, posting top 1
```

### Timestamp Verification
```
Position 1:
  Wallet: 0x45b39e1f71e47fd4afe4b988ffad690b644735bc
  Market: Xi Jinping out in 2025?
  Realized PnL: $-170,891.78
  Latest trade: 2025-10-20T18:23:47+00:00 (0.2 minutes ago)
  ✓ WITHIN 90-minute window
```

### Time Window Tests
- **90 minutes:** Found 2 positions ✓
- **1 minute:** Found 1 position (correctly filtered out older one) ✓
- **0.1 minutes (6 seconds):** Found 0 positions ✓

### Unit Tests
All 6 tests pass:
- ✓ format_usd
- ✓ short_wallet
- ✓ cache_add_and_count
- ✓ enforce_280_and_no_sentence_cut
- ✓ format_tweet
- ✓ unique_id

## Tweet Format

Tweets remain under 280 characters with:
- Unhinged AI-generated text with @Polymarket mention
- 💰 PnL amount and outcome
- 📊 Market title
- 🔗 Polymarket profile link
- Footer: "Built by @ForgeLabs__"

Example:
```
0x9cb9…32f2 just ate shit for $22,981.00 on the Buccaneers vs @Polymarket. Lions game, you fucking donkey!

💰 $22,981 on Lions
📊 Market: Buccaneers vs. Lions

🔗
https://polymarket.com/profile/0x9cb990f1862568a63d8601efeebe0304225c32f2

Built by @ForgeLabs__
```

Length: 258 characters ✓

## How It Works

1. **Every 2 hours**, the bot runs
2. Fetches all trades from the last 90 minutes
3. Groups trades by (wallet, market) and calculates PnL
4. Filters to positions with absolute PnL >= $10,000
5. Sorts by absolute PnL (highest first)
6. Checks deduplication cache (wallet:conditionId:endDate)
7. Posts exactly **1 tweet** for the highest PnL position
8. Saves to cache to prevent re-posting

## Deduplication

Uses unique ID: `wallet:conditionId:endDate`

This ensures:
- Same wallet + market combination is only posted once
- Even if the position grows over multiple runs, we don't spam
- Cache persists in `posted.json`

## Next Steps

1. Set `DRY_RUN=false` in `.env` for live posting
2. Schedule the bot to run every 2 hours
3. Monitor `posted.json` to track posted tweets
4. Check Twitter for live posts

## Files Modified

- `polymarket_client.py` - Added `get_recent_pnl_from_trades()` method
- `polywatch.py` - Updated main loop to use trade-based PnL calculation
- `tools/verify_trade_timestamps.py` - Created verification script
- `tests/test_polywatch.py` - All tests still pass

