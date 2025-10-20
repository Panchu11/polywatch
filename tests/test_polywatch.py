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
        # Format: 0xABC...XYZ (3 chars after 0x, then ..., then last 3 chars)
        self.assertEqual(short_wallet("0x1234567890abcdef"), "0x123...def")


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
        self.assertIn("0x123...678", text)  # shortened wallet (0xABC...XYZ format)
        self.assertIn("Yes", text)
        self.assertIn("polymarket.com/profile", text)  # Polymarket link
        self.assertIn("Built by @ForgeLabs__", text)  # footer

    def test_enforce_280_and_no_sentence_cut(self):
        wallet = "0x1234567890abcdef1234567890abcdef12345678"
        row = {
            "title": "Will Kim Moon-soo be the People's Power Party candidate for president?",
            "outcome": "Yes",
            "realizedPnl": 6977733.43,
            "proxyWallet": wallet,
        }

        class FakeAI:
            def generate_tweet(self, display_name, pnl, title, outcome):
                # Multiple sentences, intentionally long, with a handle variant
                return (
                    "This trader just nuked the market like a degen god. "
                    "Absolute chaos, rockets everywhere 🚀🔥! "
                    "Numbers so stupid they make reality bend. @Polymarket668"
                )

        text = format_tweet(FakeAI(), wallet, row)
        self.assertLessEqual(len(text), 280)
        self.assertNotIn("...", text)
        self.assertIn("Built by @ForgeLabs__", text)
        self.assertIn("@Polymarket", text)
        self.assertNotIn("@Polymarket668", text)


if __name__ == "__main__":
    unittest.main()

