"""Interactive Drexel authentication and private Playwright state handling."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Browser, Playwright, sync_playwright

WEBTMS_URL = "https://termmasterschedule.drexel.edu/webtms_du/"
CONNECT_HOST = "connect.drexel.edu"
DEFAULT_TIMEOUT_SECONDS = 600


class AuthenticationRequired(RuntimeError):
    """Raised without sensitive detail when a WebTMS session is absent or expired."""


class SessionStateError(RuntimeError):
    """Raised when storage state cannot be handled safely."""


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_state_path() -> Path:
    return repository_root() / ".private" / "webtms" / "storage-state.json"


def is_authentication_url(url: str) -> bool:
    try:
        return (urlsplit(url).hostname or "").lower() == CONNECT_HOST
    except ValueError:
        return False


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def ensure_safe_state_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    root = repository_root().resolve()
    if _is_within(resolved, root):
        relative = resolved.relative_to(root)
        check = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", "--", str(relative)],
            cwd=root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if check.returncode != 0:
            raise SessionStateError(
                "Refusing to store browser session state in a repository path that Git does not ignore."
            )
    return resolved


def _restrict_permissions(path: Path, *, directory: bool) -> None:
    try:
        path.chmod(0o700 if directory else 0o600)
    except OSError:
        pass


def save_storage_state(context: object, path: Path) -> Path:
    destination = ensure_safe_state_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _restrict_permissions(destination.parent, directory=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix="storage-state-", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        context.storage_state(path=temporary)  # type: ignore[attr-defined]
        _restrict_permissions(temporary, directory=False)
        os.replace(temporary, destination)
        _restrict_permissions(destination, directory=False)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def delete_storage_state(path: Path | None = None) -> bool:
    destination = ensure_safe_state_path(path or default_state_path())
    existed = destination.exists()
    destination.unlink(missing_ok=True)
    return existed


def _launch(playwright: Playwright, *, headless: bool) -> Browser:
    return playwright.chromium.launch(headless=headless)


def authenticate_interactively(
    path: Path | None = None, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> Path:
    """Open a visible browser; only Drexel's page receives credentials and MFA."""
    destination = ensure_safe_state_path(path or default_state_path())
    with sync_playwright() as playwright:
        browser = _launch(playwright, headless=False)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(WEBTMS_URL, wait_until="domcontentloaded")
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if not is_authentication_url(page.url) and "termmasterschedule.drexel.edu" in page.url:
                    page.wait_for_load_state("domcontentloaded")
                    return save_storage_state(context, destination)
                page.wait_for_timeout(500)
        except Exception:
            raise AuthenticationRequired(
                "Interactive authentication did not complete; no session details were saved."
            ) from None
        finally:
            browser.close()
    raise AuthenticationRequired(
        "Interactive authentication timed out; no session details were saved."
    )


def validate_stored_session(path: Path | None = None) -> bool:
    destination = ensure_safe_state_path(path or default_state_path())
    if not destination.is_file():
        return False
    try:
        with sync_playwright() as playwright:
            browser = _launch(playwright, headless=True)
            context = browser.new_context(storage_state=destination)
            page = context.new_page()
            page.goto(WEBTMS_URL, wait_until="domcontentloaded")
            valid = not is_authentication_url(page.url)
            browser.close()
            return valid
    except Exception:
        return False
