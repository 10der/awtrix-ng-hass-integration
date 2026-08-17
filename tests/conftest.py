"""Global fixtures for awtrix_ng tests."""

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant's test harness to load our custom_components tree.

    Core's test fixtures refuse to load anything outside homeassistant/components
    unless this fixture is pulled in - without it every test fails with
    "Integration 'awtrix_ng' not found".
    """
    yield
