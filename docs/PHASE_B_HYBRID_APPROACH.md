# Phase B: Hybrid Mem0 + Validator Approach

## Goal
Compare two extraction pipelines:
- **Phase A**: Mem0 extraction → confidence filter (>= 0.5) → proposals
- **Phase B**: Mem0 extraction → validator → confidence-adjusted proposals

## Research Question
Does the validator improve Mem0 extraction? Or does it over-filter like with multi-agent?

## Implementation

### B1: Create _extract_mem0_with_validator()
```python
async def _extract_mem0_with_validator(
    raw_messages: list[dict],
    pet: Pet,
    existing_memories: list[PetMemory],
) -> list[MemoryProposal]:
    # Step 1: Extract with Mem0
    mem0_facts = extract_mem0_facts(...)
    
    # Step 2: Run validator on extracted facts
    validations = await validate_facts(messages, pet_name, mem0_facts)
    
    # Step 3: Filter by validator
    kept_facts = [f for f, v in ... if v.keep and v.confidence >= 0.5]
    
    # Step 4: Build proposals
    return [MemoryProposal(...) for f in kept_facts]
```

### B2: Add feature flag
```
EXTRACTION_BACKEND = "mem0" | "mem0_validator" | "multiagent"
```

### B3: Test on same cases as Phase A
- Run both Phase A and Phase B on the same test set
- Compare fact count and confidence adjustments

## Expected Results
- Phase A: 11 facts, high confidence (1.0)
- Phase B: ? facts after validator filtering

## Decision Criteria
If Phase B fact count <= Phase A:
  → Validator hurts Mem0
  → Recommend Phase A for production

If Phase B fact count > Phase A:
  → Validator helps by adding confidence
  → Recommend Phase B for production
