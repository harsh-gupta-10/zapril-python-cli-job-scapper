"""
Camoufox-powered async scraper engine.

This module is intentionally fetch-only: it returns raw HTML so parsing
stays separate and can be handled by existing parser functions.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Sequence

from camoufox.async_api import AsyncCamoufox
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

DEFAULT_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
)

RETRYABLE_STATUS_CODES = {403, 429}


class ScraperEngineError(RuntimeError):
    """Raised when the scraper engine cannot fetch the page."""


@dataclass(slots=True)
class _FetchAttemptResult:
    html: str
    status_code: int


class ScraperEngine:
    """
    Camoufox + Playwright-stealth fetcher.

    Usage:
        engine = ScraperEngine()
        html = await engine.fetch(url)
        parsed = existing_parser(html)  # parsing remains external
    """

    def __init__(
        self,
        *,
        min_human_delay_seconds: float = 2.0,
        max_human_delay_seconds: float = 8.0,
        max_retries: int = 4,
        backoff_base_seconds: float = 1.5,
        navigation_timeout_ms: int = 45_000,
        headless: bool = True,
        user_agents: Sequence[str] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if min_human_delay_seconds <= 0 or max_human_delay_seconds <= 0:
            raise ValueError("Human-like delays must be positive.")
        if min_human_delay_seconds > max_human_delay_seconds:
            raise ValueError("min_human_delay_seconds must be <= max_human_delay_seconds.")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0.")
        if backoff_base_seconds <= 0:
            raise ValueError("backoff_base_seconds must be > 0.")
        if navigation_timeout_ms <= 0:
            raise ValueError("navigation_timeout_ms must be > 0.")

        self._min_delay = min_human_delay_seconds
        self._max_delay = max_human_delay_seconds
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._navigation_timeout_ms = navigation_timeout_ms
        self._headless = headless
        self._user_agents = list(user_agents or DEFAULT_USER_AGENTS)
        if not self._user_agents:
            raise ValueError("At least one user-agent must be configured.")

        self._rng = random.SystemRandom()
        self._last_user_agent: str | None = None
        self._logger = logger or logging.getLogger(__name__)
        self._stealth = Stealth(init_scripts_only=True)

    async def fetch(self, url: str) -> str:
        """
        Fetch a URL and return page HTML.

        Retries on 403/429 with exponential backoff and jitter.
        """
        if not url or not url.strip():
            raise ValueError("url cannot be empty.")

        last_error: Exception | None = None
        max_attempts = self._max_retries + 1

        for attempt in range(1, max_attempts + 1):
            user_agent = self._rotate_user_agent()
            await self._human_delay()

            self._logger.info(
                "Fetching URL with Camoufox (attempt %s/%s): %s",
                attempt,
                max_attempts,
                url,
            )

            try:
                result = await self._fetch_once(url=url, user_agent=user_agent)
                if result.status_code in RETRYABLE_STATUS_CODES:
                    raise ScraperEngineError(
                        f"Received retryable HTTP status {result.status_code} for {url}"
                    )

                self._logger.info(
                    "Fetched URL successfully with status %s: %s",
                    result.status_code,
                    url,
                )
                return result.html

            except ScraperEngineError as exc:
                last_error = exc

                if attempt >= max_attempts:
                    break

                backoff_seconds = self._get_backoff_delay(attempt)
                self._logger.warning(
                    "Retrying fetch after error (%s). Backoff: %.2fs. URL: %s",
                    exc,
                    backoff_seconds,
                    url,
                )
                await asyncio.sleep(backoff_seconds)

            except Exception as exc:
                last_error = exc

                if attempt >= max_attempts:
                    break

                backoff_seconds = self._get_backoff_delay(attempt)
                self._logger.warning(
                    "Fetch attempt failed (%s). Backoff: %.2fs. URL: %s",
                    exc,
                    backoff_seconds,
                    url,
                )
                await asyncio.sleep(backoff_seconds)

        raise ScraperEngineError(
            f"Failed to fetch URL after {max_attempts} attempts: {url}"
        ) from last_error

    async def _fetch_once(self, *, url: str, user_agent: str) -> _FetchAttemptResult:
        async with AsyncCamoufox(
            headless=self._headless,
            humanize=True,
            block_images=True,
            os=["windows", "macos", "linux"],
        ) as browser:
            page = await browser.new_page()
            await page.set_extra_http_headers(
                {
                    "User-Agent": user_agent,
                    "Accept-Language": "en-US,en;q=0.9",
                    "DNT": "1",
                }
            )
            await self._stealth.apply_stealth_async(page)

            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._navigation_timeout_ms,
            )

            status_code = response.status if response else 200

            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=min(self._navigation_timeout_ms, 8_000),
                )
            except PlaywrightTimeoutError:
                self._logger.debug("networkidle timeout reached for %s; using current DOM", url)

            html = await page.content()
            if not html:
                raise ScraperEngineError(f"Empty HTML returned for {url}")

            return _FetchAttemptResult(html=html, status_code=status_code)

    async def _human_delay(self) -> None:
        delay_seconds = self._rng.uniform(self._min_delay, self._max_delay)
        self._logger.debug("Applying human-like delay: %.2fs", delay_seconds)
        await asyncio.sleep(delay_seconds)

    def _rotate_user_agent(self) -> str:
        if len(self._user_agents) == 1:
            self._last_user_agent = self._user_agents[0]
            return self._last_user_agent

        choices = [ua for ua in self._user_agents if ua != self._last_user_agent]
        next_ua = self._rng.choice(choices)
        self._last_user_agent = next_ua
        self._logger.debug("Selected user-agent: %s", next_ua)
        return next_ua

    def _get_backoff_delay(self, attempt: int) -> float:
        exponential = self._backoff_base_seconds * (2 ** (attempt - 1))
        jitter = self._rng.uniform(0.2, 0.8)
        return exponential + jitter


logging.getLogger(__name__).addHandler(logging.NullHandler())
