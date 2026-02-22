import os
from functools import lru_cache
from typing import Any

from posthog import Posthog

from .logger import logger


class AnalyticsService:
    def __init__(self, api_key: str | None, host: str):
        if not api_key:
            logger.error(
                "[AnalyticsService] POSTHOG_API_KEY not set, analytics disabled"
            )
            return

        self.posthog = Posthog(api_key, host)
        logger.info("[AnalyticsService] PostHog analytics enabled")

    def capture(
        self, distinct_id: str, event: str, properties: dict[str, Any] | None = None
    ) -> None:
        try:
            self.posthog.capture(event, distinct_id=distinct_id, properties=properties)
        except Exception as e:
            logger.error(f"[AnalyticsService] Failed to capture '{event}': {e}")


@lru_cache()
def get_analytics_service() -> AnalyticsService:
    api_key = os.getenv("POSTHOG_API_KEY")
    if not api_key:
        logger.error("POSTHOG_API_KEY not set")
        raise KeyError("POSTHOG_API_KEY not set")
    return AnalyticsService(
        api_key=os.getenv("POSTHOG_API_KEY"),
        host=os.getenv("POSTHOG_HOST", "https://us.i.posthog.com"),
    )
