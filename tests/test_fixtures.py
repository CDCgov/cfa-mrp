"""Fixture round-trip tests — load TOML, compare to expected JSON."""

from __future__ import annotations

import json
from pathlib import Path

from mrp.config import load_toml

FIXTURES = Path(__file__).parent / "fixtures"


def _strip_computed_fields(data: dict) -> dict:
    """Remove fields that are computed at runtime (mrp section)."""
    result = dict(data)
    result.pop("mrp", None)
    return result


class TestSimpleFixture:
    def test_toml_matches_expected_json(self):
        config = load_toml(FIXTURES / "mrp.toml")
        with open(FIXTURES / "expected.json") as f:
            expected = json.load(f)

        expected_clean = _strip_computed_fields(expected)
        config_clean = _strip_computed_fields(config)

        assert config_clean == expected_clean


class TestProfiledFixture:
    def test_toml_matches_expected_json(self):
        config = load_toml(FIXTURES / "mrp.with_profiles.toml")
        with open(FIXTURES / "expected.simple.json") as f:
            expected = json.load(f)

        expected_clean = _strip_computed_fields(expected)
        config_clean = _strip_computed_fields(config)

        assert config_clean == expected_clean
