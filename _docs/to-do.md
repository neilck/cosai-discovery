# To-Do

Engineering follow-ups that aren't blocking but should be addressed before they become problems.

Each item: title, why it matters, what to do, references.

---

## LangGraph custom-dataclass deserialization warnings

**Status:** open
**Surfaced:** 2026-05-19 during the first multi-project Stage 1 run.

### Symptom

Re-running Stage 1 from a cached checkpoint prints a stack of warnings:

```
Deserializing unregistered type cdx_indexer.scan.ParsedPyProject from checkpoint.
This will be blocked in a future version. Set LANGGRAPH_STRICT_MSGPACK=true to
block now, or add to allowed_msgpack_modules to allow explicitly:
  [('cdx_indexer.scan', 'ParsedPyProject')]
Deserializing unregistered type cdx_indexer.scan.ProjectScan from checkpoint...
Deserializing unregistered type cdx_indexer.planner.EntryPlanPackage from checkpoint...
Deserializing unregistered type cdx_indexer.planner.EntryPlanSnippet from checkpoint...
Deserializing unregistered type cdx_indexer.planner.EntryPlanReference from checkpoint...
Deserializing unregistered type cdx_indexer.planner.PlannerOutput from checkpoint...
```

### Why it matters

The DB stores LangGraph state (including our custom dataclasses) via msgpack. LangGraph is moving toward requiring explicit type registration; in a future release, unregistered custom types will be **blocked**, not just warned. When that lands, our checkpoint reuse will break silently — the LLM will be called on every run.

### Why it isn't urgent today

Caching still works. The warnings are nags, not errors. The codebase isn't shipping yet, so we have time to fix this cleanly.

### Two fix options

**Option 1 — Register our dataclasses with LangGraph's msgpack serializer.**
The minimum-change fix. Tell LangGraph it's OK to (de)serialise these types. Likely a small `langgraph.serde.register(...)` call at module import time, plus a list of `(module, classname)` pairs.

Pros: smallest diff. Cons: still tied to msgpack-of-custom-types; future LangGraph versions may change the API again.

**Option 2 — Keep complex objects out of LangGraph state entirely.**
Refactor so state holds only JSON-friendly dicts. Nodes pickle/unpickle nothing; conversion to/from dataclasses happens at the boundaries (input via `scan.to_dict()`, output via `PlannerOutput.from_dict()`).

Pros: future-proof; aligned with how LangGraph wants you to model state. Cons: more code surface; constructors need defensive `.get()` on every field; loses Python type-safety inside the graph.

### Recommendation when picking up

Lean Option 2 once Stage 2 work begins. State will get more complex (per-entry processing fan-out); keeping it JSON-friendly from the start is cheaper than retrofitting. The model would be:

```python
class _PlannerState(TypedDict, total=False):
    scan: dict                       # scan.to_dict()
    raw_llm_response: str
    parsed: dict
    output: dict                     # PlannerOutput.to_dict()
```

Then `run_planner()` does the in-out conversion once.

### References

- `src/cdx_indexer/planner.py` — `_PlannerState`, `_build_graph`, the three node functions.
- `src/cdx_indexer/scan.py` — `ProjectScan` and the parsed-manifest dataclasses, all of which need their `to_dict` round-trips audited.
- LangGraph serialization docs: https://langchain-ai.github.io/langgraph/concepts/persistence/ (msgpack section).
