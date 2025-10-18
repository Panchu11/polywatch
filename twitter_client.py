from __future__ import annotations
import os
from typing import Optional


class TwitterClient:
    def __init__(self):
        # Lazy import tweepy to avoid hard dependency during tests
        global tweepy
        try:
            import tweepy  # type: ignore
        except Exception as e:  # pragma: no cover
            tweepy = None  # type: ignore
        self._tweepy = tweepy
        self._client = None

    def _require_env(self, name: str) -> str:
        v = os.getenv(name)
        if not v:
            raise RuntimeError(f"Missing required env var: {name}")
        return v

    def get_client(self):
        if self._client is not None:
            return self._client
        if self._tweepy is None:
            raise RuntimeError("tweepy is not installed. Please install tweepy to post tweets.")
        api_key = self._require_env("TWITTER_API_KEY")
        api_secret = self._require_env("TWITTER_API_SECRET")
        access_token = self._require_env("TWITTER_ACCESS_TOKEN")
        access_secret = self._require_env("TWITTER_ACCESS_TOKEN_SECRET")
        bearer = os.getenv("TWITTER_BEARER_TOKEN")
        # v2 client supports posting tweets with OAuth1 user context
        self._client = self._tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
            bearer_token=bearer,
            wait_on_rate_limit=True,
        )
        return self._client

    def post_tweet(self, text: str) -> Optional[str]:
        client = self.get_client()
        resp = client.create_tweet(text=text)
        # Tweepy v4 returns dict-like with data.id
        tweet_id = None
        try:
            tweet_id = str(resp.data.get("id"))  # type: ignore
        except Exception:
            pass
        return tweet_id

