"""Verify the package installs and can be imported."""

import pytest


def test_import_package() -> None:
    import yantrabodha_mcp
    assert yantrabodha_mcp.__version__ == "0.1.0"


def test_import_mcp() -> None:
    from yantrabodha_mcp import mcp
    assert mcp is not None
