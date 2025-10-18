PolyWatch — Polymarket Profit-Tracking Twitter Bot

Overview
- Tracks Polymarket wallets for realized PnL > $25,000 using the public Data API
- Posts formatted tweets via X (Twitter) API (free plan), with duplicate-prevention cache
- Saves pending tweets to tweets.json and all posted to posted.json
- Designed to run locally or via GitHub Actions/cron

Important
- Do NOT hardcode Twitter credentials. Use environment variables or a local .env file.
- Respect Twitter/X free-plan limits (17 tweets/day). This bot enforces a local cap.
- Provide your wallet list in wallets.json.

Quick start (local)
1) Create and fill wallets.json with addresses:
   [
     "0x56687bf447db6ffa42ffe2204a05edaa20f55839"
   ]
2) Set environment variables (or create .env) for X API keys:
   - TWITTER_API_KEY
   - TWITTER_API_SECRET
   - TWITTER_ACCESS_TOKEN
   - TWITTER_ACCESS_TOKEN_SECRET
   - Optional: TWITTER_BEARER_TOKEN
3) Install dependencies (requests, tweepy). Example:
   pip install -r requirements.txt
4) Dry-run first (default):
   python polywatch.py
5) Live mode: set DRY_RUN=false
   DRY_RUN=false python polywatch.py

Files
- polywatch.py            Main orchestrator; loads wallets, fetches claims, posts tweets, caches duplicates
- polymarket_client.py    Polymarket API client (closed-positions, public-search profile lookup)
- twitter_client.py       Minimal Tweepy client wrapper with safe lazy import
- state_store.py          JSON persistence and duplicate cache utilities
- utils.py                Formatting and helpers
- wallets.json            List of addresses to track (you fill this)
- posted.json             Cache of posted tweets by unique key
- tweets.json             Queue of pending tweets for review

Environment
- DRY_RUN=true            Default. Set to false to enable posting
- MIN_PROFIT_USD=25000    Threshold for highlighting claims
- MAX_TWEETS_PER_DAY=17   Local cap to stay under X free limits

GitHub Actions (optional)
- .github/workflows/polywatch.yml provided. Add repo secrets for all TWITTER_* variables.
- By default, the workflow runs in DRY_RUN mode. Flip to live by setting DRY_RUN to false in the workflow env or repo env.

Notes
- Realized PnL and claim context are derived from /closed-positions. Tweet includes title, outcome Yes/No, wallet name if available, and profit.
- Username lookup uses gamma public search; falls back to address if not found.
- This project includes standard-library unit tests (no extra deps).

Security
- Keep keys in env/Secrets. Do not commit them.
- Consider using a ".env" locally (python-dotenv optional but not required in this repo).

