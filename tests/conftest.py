"""Shared test fixtures."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")

CONFIG_DIR = Path(__file__).parent.parent / "config"


@pytest.fixture
def config_dir():
    return CONFIG_DIR
