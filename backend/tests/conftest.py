"""Pytest configuration for the backend test suite."""

import pytest

pytest_plugins: list[str] = []


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers used by the auth (and future) test modules."""

    config.addinivalue_line("markers", "asyncio: mark test as an asyncio coroutine")
