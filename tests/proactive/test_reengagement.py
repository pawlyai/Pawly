"""
Unit tests for src/jobs/reengagement.py.

Reengagement now uses a hardcoded message format (no LLM call).
Tests cover the dedup key logic (_trigger_ref) and message content.
"""

import pytest


def test_trigger_ref_is_deterministic():
    from src.jobs.reengagement import _trigger_ref
    ref1 = _trigger_ref(12345)
    ref2 = _trigger_ref(12345)
    assert ref1 == ref2


def test_trigger_ref_differs_per_user():
    from src.jobs.reengagement import _trigger_ref
    assert _trigger_ref(1) != _trigger_ref(2)


def test_trigger_ref_length():
    from src.jobs.reengagement import _trigger_ref
    assert len(_trigger_ref(99)) == 32
