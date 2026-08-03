from pathlib import Path

import pytest

from drexel_schedule_generator.webtms.auth import SessionStateError, default_state_path, delete_storage_state, ensure_safe_state_path, is_authentication_url


def test_drexel_connect_is_recognized_as_authentication() -> None:
    assert is_authentication_url("https://connect.drexel.edu/idp/profile/SAML2/Redirect/SSO")
    assert not is_authentication_url("https://termmasterschedule.drexel.edu/webtms_du/")


def test_default_state_path_is_git_ignored() -> None:
    assert ensure_safe_state_path(default_state_path()) == default_state_path()


def test_unignored_repository_path_is_rejected() -> None:
    with pytest.raises(SessionStateError):
        ensure_safe_state_path(Path(__file__).resolve().parents[2] / "unsafe-state.json")


def test_delete_storage_state_outside_repository(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    state.write_text("{}", encoding="utf-8")
    assert delete_storage_state(state)
    assert not state.exists()
