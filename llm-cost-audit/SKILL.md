---
name: llm-cost-audit
description: Weekly read-only audit of LLM spend (omp and Claude Code) in INR, plus triage of expensive sessions that made no edits. Use for /llm-cost-audit, "weekly cost review", or "where did my tokens go".
---

Read-only weekly review of LLM spend. Never edit configs, databases or jobs from this skill; changes are proposed to the user, not applied.

1. Sync omp's stats: `omp stats -s` (the db is lazily synced, so it is stale otherwise).
2. Run `python3 ~/.claude/skills/llm-cost-audit/scripts/audit.py [--days 7] [--min-cost 100] [--json]`. It works on a temp copy of `~/.omp/stats.db`, reads `~/.claude/projects/**/*.jsonl` (deduped on message id + requestId), and recomputes cost from raw tokens with `prices.json` (stored costs are unreliable). Models missing from `prices.json` are listed as unpriced, not guessed; add them to the file.
3. Summarise for the user, conclusions first: totals per tool, model, project and day; top sessions; spikes; then each waste detector (repeated sleep-call loops at high context, cache reads above 100k context, premium models on read-only subagents, old-model use after the newer one shipped).
4. Walk the TRIAGE table with the user (sessions at or above the threshold with zero edit/write calls). They decide research vs waste; do not label them yourself. Prompt snippets are redacted when they look secret-like. Never print more of a user prompt than the table shows; if a plaintext secret turns up, tell the user to rotate it without repeating it.
5. Agree actions with the user (model routing, compaction, stopping loops). Update `prices.json` and its `supersessions` list when new models or prices appear.

Rules: money is INR at 95.56/USD (in `prices.json`) and is API-equivalent value, not necessarily cash on a subscription. "Avoidable" old-model spend counts only requests made after the newer model was available. `--days 9999` covers everything.
