"""Authenticated, rate-conscious WebTMS browser navigation."""

from __future__ import annotations

import time
import random
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .auth import AuthenticationRequired, WEBTMS_URL, default_state_path, ensure_safe_state_path, is_authentication_url

ALLOWED_HOST = "termmasterschedule.drexel.edu"
USER_AGENT = "DrexelScheduleGenerator-Portfolio/0.2 (authorized maintainer course-data refresh)"


class RateLimited(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    url: str
    html: str
    status_code: int


def safe_public_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


class WebTMSBrowserClient:
    def __init__(self, state_path: Path | None = None, *, delay_seconds: float = 2.0, max_retries: int = 2) -> None:
        self.state_path = ensure_safe_state_path(state_path or default_state_path())
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.retry_count = 0
        self.requested_urls: list[str] = []
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._last_navigation = 0.0

    def __enter__(self) -> WebTMSBrowserClient:
        if not self.state_path.is_file():
            raise AuthenticationRequired("No local WebTMS session is available. Authenticate first.")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(storage_state=self.state_path, user_agent=USER_AGENT)
        self._page = self._context.new_page()
        return self

    def __exit__(self, *_: object) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def navigate(self, url: str = WEBTMS_URL) -> PageSnapshot:
        absolute = urljoin(WEBTMS_URL, url)
        parts = urlsplit(absolute)
        if parts.scheme != "https" or (parts.hostname or "").lower() != ALLOWED_HOST:
            raise ValueError("Navigation is limited to the HTTPS WebTMS host.")
        if self._page is None:
            raise RuntimeError("Use WebTMSBrowserClient as a context manager.")
        for attempt in range(self.max_retries + 1):
            elapsed = time.monotonic() - self._last_navigation
            if self._last_navigation and elapsed < self.delay_seconds:
                time.sleep(self.delay_seconds - elapsed)
            try:
                response = self._page.goto(absolute, wait_until="domcontentloaded")
                self._last_navigation = time.monotonic()
                final_url = self._page.url
                if is_authentication_url(final_url):
                    raise AuthenticationRequired("The WebTMS session expired. Authenticate again.")
                if (urlsplit(final_url).hostname or "").lower() != ALLOWED_HOST:
                    raise RuntimeError("WebTMS redirected to an unexpected host.")
                status = response.status if response is not None else 200
                html = self._page.content()
                if status == 429 or "too many requests" in html.casefold():
                    raise RateLimited("WebTMS asked the crawler to slow down.")
                if status >= 500:
                    raise RuntimeError("WebTMS returned a transient server error.")
                public_url = safe_public_url(final_url)
                self.requested_urls.append(public_url)
                return PageSnapshot(url=public_url, html=html, status_code=status)
            except AuthenticationRequired:
                raise
            except (RateLimited, RuntimeError):
                if attempt >= self.max_retries:
                    raise
                self.retry_count += 1
                time.sleep(self.delay_seconds * (2 ** (attempt + 1)) + random.uniform(0, 0.25))
            except Exception:
                if attempt >= self.max_retries:
                    raise RuntimeError("WebTMS navigation failed after bounded retries.") from None
                self.retry_count += 1
                time.sleep(self.delay_seconds * (2 ** (attempt + 1)))
        raise RuntimeError("WebTMS navigation failed.")

    def follow_link_text(self, text: str) -> PageSnapshot:
        """Follow a visible WebTMS link when server flow depends on page context."""
        if self._page is None:
            raise RuntimeError("Use WebTMSBrowserClient as a context manager.")
        elapsed = time.monotonic() - self._last_navigation
        if self._last_navigation and elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        try:
            self._page.locator("a", has_text=text).first.click()
            self._page.wait_for_load_state("domcontentloaded")
        except Exception:
            raise RuntimeError("WebTMS link navigation failed.") from None
        self._last_navigation = time.monotonic()
        final_url = self._page.url
        if is_authentication_url(final_url):
            raise AuthenticationRequired("The WebTMS session expired. Authenticate again.")
        if (urlsplit(final_url).hostname or "").lower() != ALLOWED_HOST:
            raise RuntimeError("WebTMS redirected to an unexpected host.")
        public_url = safe_public_url(final_url)
        self.requested_urls.append(public_url)
        return PageSnapshot(url=public_url, html=self._page.content(), status_code=200)
