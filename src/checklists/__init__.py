"""
Vet-Reviewed Clarification Checklists.

Each checklist encodes one clinical scenario as structured data:
    Section 1: scope + trigger keywords
    Section 2: mandatory slots (must collect before advice)
    Section 3: conditional slots (collect when trigger conditions met)
    Section 5: urgency triggers (deterministic skip-clarification rules)
    Section 7: ask order (turn-by-turn slot priority)
    Section 9: hard limits (constraints injected into LLM prompt)
    Section 10: advice template (filled with collected slot values)

The schema mirrors the vet-review checklist template — every YAML file is
designed to be reviewed and signed off section-by-section by a DVM before
its `status` field flips from `draft` to `approved`.
"""
