import unittest
from datetime import datetime, timedelta, timezone

from utils import format_usd, short_wallet
from state_store import PostedCache, save_json, load_json
from polywatch import unique_id, format_tweet
from ai_client import AIClient


class TestUtils(unittest.TestCase):
    def test_format_usd(self):
        self.assertEqual(format_usd(25200), "$25,200")
        self.assertEqual(format_usd(25200.5), "$25,200.50")

    def test_short_wallet(self):
        self.assertEqual(short_wallet("0x1234567890abcdef"), "0x1234…cdef")


class TestPostedCache(unittest.TestCase):
    def test_cache_add_and_count(self):
        cache = PostedCache(path="test_posted.json")
        # reset file
        save_json("test_posted.json", {"items": []})
        cache = PostedCache(path="test_posted.json")
        self.assertFalse(cache.contains("a"))
        cache.add("a", tweet_id=None)
        self.assertTrue(cache.contains("a"))
        # count since past
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.assertGreaterEqual(cache.count_since(past), 1)


class TestTweetFormatting(unittest.TestCase):
    def test_unique_id(self):
        row = {"conditionId": "cid", "endDate": "2025-01-01T00:00:00Z"}
        uid = unique_id("0xabc", row)
        self.assertEqual(uid, "0xabc:cid:2025-01-01T00:00:00Z")

    def test_format_tweet(self):
        wallet = "0x1234567890abcdef1234567890abcdef12345678"
        row = {"title": "Will BTC > $100k in 2025?", "outcome": "Yes", "realizedPnl": 25200, "proxyWallet": wallet}
        ai = AIClient()  # AI client without API key will use fallback
        text = format_tweet(ai, wallet, row)
        # Should contain shortened wallet, outcome, and link
        self.assertIn("0x1234…5678", text)  # shortened wallet
        self.assertIn("Yes", text)
        self.assertIn("polymarket.com/profile", text)  # Polymarket link
        self.assertIn("Tracked by @Panchu2605", text)  # footer


if __name__ == "__main__":
    unittest.main()

