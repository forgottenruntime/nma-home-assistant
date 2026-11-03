"""Run with: pip install pytest-homeassistant-custom-component && pytest tests"""
import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
