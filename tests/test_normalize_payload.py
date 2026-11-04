from custom_components.awtrix_ng.awtrix_ng_api import _normalize_icon


def test_numeric_text_cast_to_str():
    assert _normalize_icon({"text": 1230})["text"] == "1230"
    assert _normalize_icon({"text": 12.5})["text"] == "12.5"


def test_text_untouched_otherwise():
    fragments = [{"t": "a", "c": "FFFFFF"}]
    assert _normalize_icon({"text": fragments})["text"] is fragments
    assert _normalize_icon({"text": "hi"})["text"] == "hi"
    assert _normalize_icon({"text": True})["text"] is True
    assert "text" not in _normalize_icon({"icon": 5})


def test_icon_cast_still_works():
    assert _normalize_icon({"icon": 1234})["icon"] == "1234"
