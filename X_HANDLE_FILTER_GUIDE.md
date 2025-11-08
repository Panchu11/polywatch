# X Handle Filter - Implementation Guide

## Current Situation

**Test Results (Last 24 hours, $1k+ PnL):**
- ✅ Found: 14 trades
- ❌ With X handles: **0 (0%)**
- ❌ Without X handles: **14 (100%)**

## What I Implemented

I've added an **optional X handle filter** that you can enable/disable with an environment variable:

### New Environment Variable: `REQUIRE_X_HANDLE`

- **`REQUIRE_X_HANDLE=false`** (default): Posts all qualifying trades
  - Tags users with `@handle` if they have X linked
  - Falls back to wallet address if no X handle
  - **This is the current recommended setting**

- **`REQUIRE_X_HANDLE=true`**: Only posts trades from users with X handles linked
  - Skips all trades from users without X handles
  - Always tags users with `@handle`
  - **Not recommended yet - would result in 0 tweets currently**

## How It Works

### Code Changes Made:

1. **`polywatch.py` lines 365-372**: Added filter status logging
2. **`polywatch.py` lines 382-421**: Added X handle checking logic
   - If `REQUIRE_X_HANDLE=true`, checks each wallet for X handle
   - Skips trades without X handles
   - Logs skipped trades

### Example Output:

```
[PolyWatch] Running in GLOBAL mode (calculating PnL from recent trades)
[PolyWatch] X Handle Filter: ENABLED (only posting trades from users with linked X handles)
[PolyWatch] Found 14 positions with PnL >= $10,000 from recent trades.
[PolyWatch] Skipping 0x6f2...8fb — no X handle linked
[PolyWatch] Skipping 0x740...8e6 — no X handle linked
...
[PolyWatch] No new qualifying claims found with X handles linked.
```

## Testing the Filter

I created a test script: `test_x_handle_filter.py`

### Usage:

```bash
# Test with $1k threshold, last 24 hours
python test_x_handle_filter.py 1000 1440

# Test with $5k threshold, last 48 hours
python test_x_handle_filter.py 5000 2880

# Test with $500 threshold, last 7 days
python test_x_handle_filter.py 500 10080
```

The script will:
- Fetch recent trades from Polymarket
- Check X handle availability for each
- Show detailed results
- Provide recommendations

## Recommendations

### Current Recommendation: **DO NOT ENABLE** the filter yet

**Reason:** 0% of recent traders have X handles linked

**Current Best Setup:**
```yaml
REQUIRE_X_HANDLE: false          # Disabled
MIN_PROFIT_USD: 10000            # $10k threshold
GLOBAL_MODE: true
MAX_TWEETS_PER_DAY: 1000
```

This setup will:
- ✅ Post all trades with PnL > $10k
- ✅ Tag users with `@handle` when available
- ✅ Use wallet address when X handle not available
- ✅ Maximize tweet volume

### Future: When to Enable the Filter

Enable `REQUIRE_X_HANDLE=true` when:
1. **At least 20-30% of traders have X handles linked**, OR
2. **You find at least 3-5 trades per day with X handles**

To check readiness, run:
```bash
python test_x_handle_filter.py 1000 1440
```

If the test shows good X handle adoption, you can enable it.

### If You Want to Enable It Anyway

If you want to enable the filter despite low adoption, you should:

1. **Lower the PnL threshold significantly** to increase volume:
   ```yaml
   REQUIRE_X_HANDLE: true
   MIN_PROFIT_USD: 500      # Much lower threshold
   ```

2. **Monitor for tweets** - you might get very few or none

3. **Be prepared to disable it** if no tweets are posted

## How to Enable/Disable

### In GitHub Actions (`.github/workflows/polywatch.yml`):

```yaml
env:
  REQUIRE_X_HANDLE: "false"    # Change to "true" to enable
  MIN_PROFIT_USD: "10000"
```

### For Local Testing:

**Windows PowerShell:**
```powershell
$env:REQUIRE_X_HANDLE="true"
python polywatch.py
```

**Linux/Mac:**
```bash
export REQUIRE_X_HANDLE=true
python polywatch.py
```

## Example Tweets

### With X Handle (when available):
```
@username crushed it on @Polymarket 🚀

💰 $15,000.50 on Yes
📊 Market: Will Trump win the 2024 election?

🔗 https://polymarket.com/profile/0xd189...

Built by @ForgeLabs__
Copy trade via TG alerts: https://tinyurl.com/3fe62ksz
```

### Without X Handle (current default):
```
0xd18...6f4 went all in on @Polymarket 🤑

💰 $15,000.50 on Yes
📊 Market: Will Trump win the 2024 election?

🔗 https://polymarket.com/profile/0xd189...

Built by @ForgeLabs__
Copy trade via TG alerts: https://tinyurl.com/3fe62ksz
```

## Summary

✅ **Implemented:** Optional X handle filter
✅ **Tested:** Works correctly
✅ **Recommendation:** Keep disabled for now (REQUIRE_X_HANDLE=false)
✅ **Reason:** 0% of traders have X handles linked currently
✅ **Future:** Enable when adoption increases

The bot is smart - it will automatically tag users with @handle when available, even with the filter disabled. This gives you the best of both worlds!

