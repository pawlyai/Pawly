"""
Checklist loader — reads YAML files from src/checklists/data/ and validates.

Loaded checklists live in module-level cache. Reload requires process restart
(or call reload() explicitly during dev).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from src.checklists.schema import ChecklistSpec
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DATA_DIR = Path(__file__).parent / "data"
_CACHE: dict[str, ChecklistSpec] = {}


def load_all() -> dict[str, ChecklistSpec]:
    """Load every *.yaml in data/ that isn't a TODO placeholder."""
    if _CACHE:
        return _CACHE

    if not _DATA_DIR.exists():
        logger.warning("checklist data dir missing", path=str(_DATA_DIR))
        return {}

    for path in sorted(_DATA_DIR.glob("CL-*.yaml")):
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            spec = ChecklistSpec.model_validate(raw)
            _CACHE[spec.checklist_id] = spec
            logger.info(
                "checklist loaded",
                id=spec.checklist_id,
                status=spec.approval.status,
            )
        except Exception as exc:
            logger.error("checklist load failed", path=str(path), error=str(exc))

    return _CACHE


def get(checklist_id: str) -> Optional[ChecklistSpec]:
    """Look up a checklist by ID. Returns None if missing or not loaded."""
    if not _CACHE:
        load_all()
    return _CACHE.get(checklist_id)


def all_approved() -> list[ChecklistSpec]:
    """All checklists with status=approved (i.e. vet has signed off)."""
    if not _CACHE:
        load_all()
    return [
        spec for spec in _CACHE.values()
        if spec.approval.status == "approved"
    ]


def all_loaded() -> list[ChecklistSpec]:
    """All loaded checklists regardless of approval status."""
    if not _CACHE:
        load_all()
    return list(_CACHE.values())


def reload() -> dict[str, ChecklistSpec]:
    """Force-reload from disk (dev only)."""
    _CACHE.clear()
    return load_all()
