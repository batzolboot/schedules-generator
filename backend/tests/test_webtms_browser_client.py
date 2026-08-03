from drexel_schedule_generator.webtms.browser_client import safe_public_url


def test_public_url_drops_query_and_fragment() -> None:
    assert safe_public_url("https://example.test/path?token=secret#part") == "https://example.test/path"
