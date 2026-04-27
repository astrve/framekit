from framekit.core.models.metadata import MetadataCandidate
from framekit.modules.metadata.selector import MetadataCandidateSelector, choose_metadata_candidate


def _candidate(
    index: int, *, reasons: list[str] | None = None, external_url: str | None = None
) -> MetadataCandidate:
    return MetadataCandidate(
        provider_name="tmdb",
        provider_id=str(index),
        kind="movie",
        title=f"Title {index}",
        year="2019",
        confidence=1.0 - (index * 0.1),
        reasons=reasons or [],
        external_url=external_url,
    )


def test_selector_returns_none_when_empty():
    selector = MetadataCandidateSelector([])
    assert selector.run() is None


def test_choose_metadata_candidate_returns_selected(monkeypatch):
    expected = _candidate(2)

    def fake_select_one(*, title, entries, page_size, on_open_current=None):
        assert title == "TMDb Match Selector"
        assert page_size == 8
        assert len(entries) == 2
        return expected

    monkeypatch.setattr("framekit.modules.metadata.selector.select_one", fake_select_one)

    result = choose_metadata_candidate([_candidate(1), expected])

    assert result is expected


def test_selector_marks_stored_choice_as_selected(monkeypatch):
    saved = _candidate(1, reasons=["stored choice"])
    normal = _candidate(2, reasons=["partial title"])

    captured = {}

    def fake_select_one(*, title, entries, page_size, on_open_current=None):
        captured["entries"] = entries
        return saved

    monkeypatch.setattr("framekit.modules.metadata.selector.select_one", fake_select_one)

    result = MetadataCandidateSelector([saved, normal], page_size=2).run()

    assert result is saved
    assert captured["entries"][0].selected is True
    assert captured["entries"][1].selected is False
    assert "saved" in (captured["entries"][0].hint or "")


def test_selector_returns_none_on_keyboard_interrupt(monkeypatch):
    def fake_select_one(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("framekit.modules.metadata.selector.select_one", fake_select_one)

    result = MetadataCandidateSelector([_candidate(1)]).run()

    assert result is None


def test_selector_open_current_callback_opens_browser(monkeypatch):
    opened: list[str] = []

    def fake_open(url: str) -> None:
        opened.append(url)

    monkeypatch.setattr("framekit.modules.metadata.selector.webbrowser.open", fake_open)

    candidate = _candidate(1, external_url="https://example.test/item")

    def fake_select_one(*, title, entries, page_size, on_open_current=None):
        assert on_open_current is not None
        on_open_current(candidate)
        return candidate

    monkeypatch.setattr("framekit.modules.metadata.selector.select_one", fake_select_one)

    result = MetadataCandidateSelector([candidate]).run()

    assert result is candidate
    assert opened == ["https://example.test/item"]
