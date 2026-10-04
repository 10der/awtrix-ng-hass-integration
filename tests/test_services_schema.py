"""Tests for service schemas."""

import pytest
import voluptuous as vol

from custom_components.awtrix_ng.const import APP_NAME_SCHEMA


@pytest.mark.parametrize("name", ["awtrix_app", "app-1", "A" * 32])
def test_app_name_valid(name: str) -> None:
    """Valid application names pass through unchanged."""
    assert APP_NAME_SCHEMA(name) == name


@pytest.mark.parametrize("name", ["", "my app", "app!", "a/b", "A" * 33])
def test_app_name_invalid(name: str) -> None:
    """Whitespace, special characters and over-long names are rejected."""
    with pytest.raises(vol.Invalid):
        APP_NAME_SCHEMA(name)
