"""
Preflight schema validation for blackbox multiturn datasets.

Schema rules are derived from what test_message_handler_multiturn.py and the
fixtures in conftest.py actually access. The default mode is 'warn': errors
are listed and the run continues — paired with the .get(default) hardening
in conftest, malformed cases degrade rather than crashing the whole run.

Strict mode (--strict-validation) is for CI: any schema error fails the
session before a single LLM call is made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_CASE_FIELDS: tuple[str, ...] = (
    "name",
    "scenario",
    "chatbot_role",
    "criteria",
    "expected_outcome",
    "user_turns",
    "pet_profile",
)
REQUIRED_PET_FIELDS: tuple[str, ...] = (
    "name",
    "species",
)
REQUIRED_MEMORY_FIELDS: tuple[str, ...] = (
    "memory_type",
    "memory_term",
    "field",
    "value",
)


@dataclass
class ValidationReport:
    errors: dict[str, list[str]] = field(default_factory=dict)
    warnings: dict[str, list[str]] = field(default_factory=dict)

    def add_error(self, case_name: str, msg: str) -> None:
        self.errors.setdefault(case_name, []).append(msg)

    def add_warning(self, case_name: str, msg: str) -> None:
        self.warnings.setdefault(case_name, []).append(msg)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def error_count(self) -> int:
        return sum(len(v) for v in self.errors.values())

    @property
    def warning_count(self) -> int:
        return sum(len(v) for v in self.warnings.values())

    def format_summary(self, header: str) -> str:
        lines: list[str] = []
        lines.append("=" * 72)
        lines.append(header)
        lines.append("-" * 72)
        if self.has_errors:
            lines.append(
                f"ERRORS: {self.error_count} issue(s) across {len(self.errors)} case(s)"
            )
            for case_name in sorted(self.errors):
                lines.append(f"  [{case_name}]")
                for msg in self.errors[case_name]:
                    lines.append(f"    - {msg}")
        else:
            lines.append("ERRORS: none")
        if self.warnings:
            lines.append("")
            lines.append(
                f"WARNINGS: {self.warning_count} issue(s) across {len(self.warnings)} case(s)"
            )
            for case_name in sorted(self.warnings):
                lines.append(f"  [{case_name}]")
                for msg in self.warnings[case_name]:
                    lines.append(f"    - {msg}")
        lines.append("=" * 72)
        return "\n".join(lines)


def validate_dataset(cases: Any) -> ValidationReport:
    """Schema-check every case. Pure function — never raises, always returns a report."""
    report = ValidationReport()

    if not isinstance(cases, list):
        report.add_error(
            "<dataset>",
            f"top-level must be a list of cases, got {type(cases).__name__}",
        )
        return report

    seen_names: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            report.add_error(
                f"<case_{index}>",
                f"must be a dict, got {type(case).__name__}",
            )
            continue

        raw_name = case.get("name")
        name = raw_name if isinstance(raw_name, str) and raw_name else f"<case_{index}>"

        if not isinstance(raw_name, str) or not raw_name:
            report.add_error(name, "missing or empty 'name' field")
        elif raw_name in seen_names:
            report.add_error(name, f"duplicate name (also seen earlier; case index {index})")
        else:
            seen_names.add(raw_name)

        for required in REQUIRED_CASE_FIELDS:
            if required not in case:
                report.add_error(name, f"missing top-level field: {required}")

        user_turns = case.get("user_turns")
        if user_turns is not None:
            if not isinstance(user_turns, list) or not user_turns:
                report.add_error(name, "user_turns must be a non-empty list")
            else:
                for j, turn in enumerate(user_turns):
                    if not isinstance(turn, str) or not turn.strip():
                        report.add_error(
                            name, f"user_turns[{j}] must be a non-empty string"
                        )

        pet_profile = case.get("pet_profile")
        if pet_profile is not None:
            if not isinstance(pet_profile, dict):
                report.add_error(
                    name,
                    f"pet_profile must be a dict, got {type(pet_profile).__name__}",
                )
            else:
                for field_name in REQUIRED_PET_FIELDS:
                    if field_name not in pet_profile:
                        report.add_error(name, f"pet_profile missing field: {field_name}")

        memories = case.get("memories")
        if memories is not None:
            if not isinstance(memories, list):
                report.add_error(
                    name, f"memories must be a list, got {type(memories).__name__}"
                )
            else:
                for j, mem in enumerate(memories):
                    if not isinstance(mem, dict):
                        report.add_error(
                            name,
                            f"memories[{j}] must be a dict, got {type(mem).__name__}",
                        )
                        continue
                    for field_name in REQUIRED_MEMORY_FIELDS:
                        if field_name not in mem:
                            report.add_error(
                                name, f"memories[{j}] missing field: {field_name}"
                            )

        threshold = case.get("threshold")
        if threshold is not None:
            try:
                t = float(threshold)
                if not 0.0 <= t <= 1.0:
                    report.add_warning(name, f"threshold {t} outside [0.0, 1.0]")
            except (TypeError, ValueError):
                report.add_error(name, f"threshold must be numeric, got {threshold!r}")

    return report
