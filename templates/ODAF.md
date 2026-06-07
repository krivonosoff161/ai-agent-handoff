# ODAF — a task-framing format for agents

Vague tasks ("fix the scanner", "improve X") cause clarification loops and drift.
ODAF forces the contract to be explicit *before* any code is written:

| Field | Question it answers |
|---|---|
| **Outcome** | What is the deliverable? What does "done" look like? |
| **Data** | Where do the inputs live? Which files / sources to read? |
| **Action** | What are the concrete steps? |
| **Format** | What's the output shape / file names / location? |

### Before (vague)
> Make the news filter cheaper.

### After (ODAF)
> **Outcome:** filter drops >50% of items before the LLM, same recall.
> **Data:** `feeds/*.jsonl`; current rules in `prefilter.py`.
> **Action:** add dedup + min-length gates; measure drop rate on the sample.
> **Format:** edit `prefilter.py` + one before/after metric line in `SESSION.md`.

Use ODAF as the body of every `TASK.md`.
