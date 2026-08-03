from __future__ import annotations

from pathlib import Path

import pytest

from drexel_schedule_generator.webtms.auth import AuthenticationRequired, WEBTMS_URL
from drexel_schedule_generator.webtms.browser_client import PageSnapshot, WebTMSBrowserClient
from drexel_schedule_generator.webtms.checkpoint import CrawlCheckpoint
from drexel_schedule_generator.webtms.crawler import crawl_term


class FakeClient:
    def __init__(self, pages: dict[str, str], *, expire_on: str | None = None) -> None:
        self.pages = pages
        self.expire_on = expire_on
        self.requested: list[str] = []
        self.retry_count = 0

    def navigate(self, url: str) -> PageSnapshot:
        if url == self.expire_on:
            raise AuthenticationRequired("expired")
        self.requested.append(url)
        return PageSnapshot(url=url.split("?", 1)[0], html=self.pages[url], status_code=200)


def pages(detail: str) -> dict[str, str]:
    return {
        WEBTMS_URL: "<a href='/webtms_du/collegesSubjects/202615'>Fall Quarter 26-27</a>",
        "/webtms_du/collegesSubjects/202615": "<a href='/webtms_du/collegesSubjects/202615?collCode=CI'>Computing</a>",
        "/webtms_du/collegesSubjects/202615?collCode=CI": "<a href='/webtms_du/courseList/CS'>Computer Science (CS)</a>",
        "/webtms_du/courseList/CS": """<table id='sortableTable'><tbody>
          <tr><td>CS</td><td>172</td><td>Lecture</td><td>Face</td><td>A</td><td><span title='Max enroll=30'><a href='/webtms_du/courseDetails/40081'>40081</a></span></td><td>Programming</td></tr>
          <tr><td>CS</td><td>600</td><td>Lecture</td><td>Face</td><td>1</td><td><a href='/webtms_du/courseDetails/49999'>49999</a></td><td>Graduate</td></tr>
          <tr><td>CS</td><td>ABC</td><td>Lecture</td><td>Face</td><td>1</td><td><a href='/webtms_du/courseDetails/48888'>48888</a></td><td>Ambiguous</td></tr>
        </tbody></table>""",
        "/webtms_du/courseDetails/40081?crseNumb=172": detail,
    }


def fall_detail() -> str:
    fixture = Path(__file__).parent / "fixtures" / "webtms" / "cs_172_lecture_with_final_exam.html"
    return fixture.read_text(encoding="utf-8").replace("Summer Quarter 25-26 (202545)", "Fall Quarter 26-27 (202615)")


def test_complete_crawl_filters_levels_deduplicates_and_checkpoints(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "crawl.json"
    client = FakeClient(pages(fall_detail()))
    result = crawl_term(client, delay_checkpoint=checkpoint_path)

    assert result.complete
    assert result.term.source_id == "202615"
    assert len(result.dataset.courses) == 1
    assert result.stats.graduate_skipped == 1
    assert result.stats.ambiguous_skipped == 1
    assert result.stats.recurring_meetings == 1
    assert result.stats.invalid_meetings == 1
    assert result.dataset.courses[0].section.maximum_enrollment == 30
    assert "crseNumb=172" in client.requested[-1]
    stored = CrawlCheckpoint(checkpoint_path, "202615", resume=True)
    assert stored.completed_crns == {"40081", "49999", "48888"}

    resumed = FakeClient(pages(fall_detail()))
    resumed_result = crawl_term(resumed, delay_checkpoint=checkpoint_path, resume=True)
    assert len(resumed_result.dataset.courses) == 1
    assert all("courseDetails" not in url for url in resumed.requested)


def test_wrong_term_checkpoint_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "crawl.json"
    CrawlCheckpoint(path, "202615").save()
    with pytest.raises(ValueError, match="different term"):
        CrawlCheckpoint(path, "202625", resume=True)


def test_authentication_expiration_stops_crawl(tmp_path: Path) -> None:
    client = FakeClient(pages(fall_detail()), expire_on="/webtms_du/courseList/CS")
    with pytest.raises(AuthenticationRequired):
        crawl_term(client, delay_checkpoint=tmp_path / "crawl.json")


def test_browser_navigation_retries_429(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __init__(self, status: int) -> None: self.status = status
    class Page:
        url = WEBTMS_URL
        attempts = 0
        def goto(self, *_args: object, **_kwargs: object) -> Response:
            self.attempts += 1
            return Response(429 if self.attempts == 1 else 200)
        def content(self) -> str: return "rate limited" if self.attempts == 1 else "<title>WebTMS</title>"

    client = WebTMSBrowserClient.__new__(WebTMSBrowserClient)
    client.delay_seconds = 0
    client.max_retries = 1
    client.retry_count = 0
    client.requested_urls = []
    client._page = Page()
    client._last_navigation = 0.0
    monkeypatch.setattr("drexel_schedule_generator.webtms.browser_client.time.sleep", lambda _: None)
    snapshot = client.navigate(WEBTMS_URL)
    assert snapshot.status_code == 200
    assert client.retry_count == 1
