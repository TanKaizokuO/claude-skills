---
name: suggest-model
description: Recommend an orchestrator → worker pair from the user's fixed routing table, choosing Main or Backup from live quota. GPT and Claude are paid subscriptions; Gemini is unavailable. Use when choosing a model or worker, comparing models, or planning work around usage limits.
---

# Suggest a model

Recommend; do not switch models, edit routing, enable paid overages, redeem resets, or start the proposed task. Use the conversation and invocation arguments as the task brief.

**Explicit decision gate — check first.** If the user has already named the model, worker, or effort for this work in the conversation (e.g. "use haiku xhigh workers", "do it on Opus"), there is nothing to recommend. Stop: do not fetch usage or offer alternatives, and do not run this skill as a subagent to second-guess the choice. If invoked anyway, reply in one line that the user's choice stands. Proceed only when the user explicitly asks for advice, a comparison, or a second opinion, or leaves the model open. A preference phrased as a question ("should I use Haiku?") is a request for advice.

**Billing and availability.** GPT (ChatGPT / Codex) and Claude (Claude Code) are **paid subscriptions**; benchmark USD/task is not marginal cash on a subscription. Gemini / Antigravity is unavailable: never recommend it, dispatch it, check its quota for routing, or restore it after a reset. Historical records may retain it.

**The routing table is the policy.** Pick the row, then pick Main or Backup from quota. Do not re-rank models by benchmark score, benchmark cost, utilization, or rotation. Change the table only when the user asks; keep it identical to the **Model routing** section of `~/.omp/agent/AGENTS.md`.

**Preferred roles.** Claude orchestrates; GPT workers handle normal execution, including read-only work. Claude workers are quota/harness fallbacks, not the default. Keep the existing session as orchestrator; do not dispatch a GPT orchestrator. Terra Medium handles bounded routine work; Sol High handles difficult reasoning, reviews, and security (intelligence 50 versus Terra High 42 in the supplied chart).

## 1. Classify the task

Map the work to exactly one row below. A request that spans several rows (e.g. plan, then build, then review) gets one pair per phase. If the work is unclear enough that the row would change, ask what the work is before recommending.

## 2. Routing table (orchestrator → worker)

| Task | Main | Backup |
|---|---|---|
| Read-only work: exploring code, searching, summarizing, web research | Claude Haiku 5.5 High → GPT-6.1 Terra Medium (Codex) | Claude Haiku 5.5 High → Claude Haiku 5.5 High |
| Simple mechanical edits, small scripts, docs, commit messages | Claude Sonnet 5.5 Medium → GPT-6.1 Terra Medium (Codex) | Claude Sonnet 5.5 Medium → Claude Haiku 5.5 Max |
| Building features, multi-step coding | Claude Opus 5.5 Medium → GPT-6.1 Terra Medium (Codex) | Claude Opus 5.5 Medium → Claude Sonnet 5.5 High |
| Hard coding, large refactors | Claude Opus 5.5 High → GPT-6.1 Sol High (Codex) | Claude Opus 5.5 High → Claude Opus 5.5 Medium |
| Code review | Claude Sonnet 5.5 High → GPT-6.1 Sol High (Codex) | Claude Sonnet 5.5 High → Claude Sonnet 5.5 High |
| Planning, architecture, hard debugging | Claude Opus 5.5 High → GPT-6.1 Sol High (Codex) | Claude Opus 5.5 High → Claude Opus 5.5 Medium |
| Security review | Claude Opus 5.5 High → GPT-6.1 Sol High (Codex) | Claude Opus 5.5 High → Claude Opus 5.5 Medium |

### Dispatch mapping

| Model | omp worker (`task` agent) | Claude Code (`Agent` tool) |
|---|---|---|
| Claude Haiku 5.5 High | `haiku-5-5-high-worker` | `model: "haiku"`, `effort: "high"` |
| Claude Haiku 5.5 Max | `haiku-5-5-max-worker` | `model: "haiku"`, `effort: "max"` |
| Claude Sonnet 5.5 High | `sonnet-5-5-high-worker` | `model: "sonnet"`, `effort: "high"` |
| Claude Opus 5.5 Medium | `opus-5-5-medium-worker` | `model: "opus"`, `effort: "medium"` |
| GPT-6.1 Terra Medium | `gpt-6-1-terra-medium-worker` | not dispatchable: use the Backup column |
| GPT-6.1 Sol High | `gpt-6-1-sol-high-worker` | not dispatchable: use the Backup column |

Orchestrators are the main session model; an orchestrator is never dispatched as a worker. When the session model differs from the row's orchestrator, say so in one line and name the recommended `/model`; do not stop the work for it.

## 3. Fetch current usage

For an actual recommendation, run on **every invocation**:

```sh
omp usage --json --redact
```

Use the per-account `reports`, not aggregated `capacity`. Keep each report's `fetchedAt`, limits, status, and `window.resetsAt` (Unix ms). If a relevant report is more than five minutes old, refresh only that provider once:

```sh
omp usage invalidate --provider <provider-id>
omp usage --json --redact --provider <provider-id>
```

| Models | Subscription | Provider ID | Binding limits |
|---|---|---|---|
| GPT-6.1 Sol, GPT-6.1 Terra, GPT-6 Luna | ChatGPT / Codex (paid) | `openai-codex` | Shared 5-hour and 7-day, plus model-specific limits |
| Claude Opus, Sonnet, Haiku | Claude Code (paid) | `anthropic` | Shared 5-hour and 7-day, plus model-specific limits |

Ignore unavailable providers, including Antigravity; their capacity is not Claude Code or Codex capacity. Remaining fraction comes from `amount.remainingFraction`, else a percent value, else `remaining / limit`. An exhausted/blocked status overrides a positive amount. Errors, missing reports, or stale data after one refresh mean **unknown**, never free. Never infer quota from token logs, `omp stats`, or the cost audit. Never read or print credentials. Hypothetical comparisons may use a supplied snapshot labelled **simulated**.

## 4. Main or Backup

Start from **Main** and switch per pool:

- **GPT in the Main pair**: use the **Backup** pair if any GPT window is exhausted, blocked, or unknown, or the GPT weekly window is **behind pace**: remaining fraction < `(resetsAt − now) / 7 days`.
- **Claude**: every pair uses a Claude orchestrator, so a Claude window that is exhausted, blocked, or unknown has no substitute in the table. Report **no confirmed choice** with the blocking window and its reset time; do not switch to a GPT orchestrator unless the user asks.
- **Claude Code harness**: the native `Agent` tool cannot dispatch GPT workers. Unless an available GPT dispatch integration is explicitly configured, use Backup for every row; do not invent a bridge or silently route to Gemini.

These are switches, not rankings: a pool with plenty of headroom never displaces the table's choice. A reset time passing is a reason to refetch, not proof of headroom.

## 5. Respond compactly

- **Task row**, chosen **Main / Backup**, and the pair as `Orchestrator → Worker` with its dispatch ID.
- One reason line naming the deciding quota fact (e.g. "GPT weekly behind pace; using Backup").
- One quota table: provider, 5-hour left and reset, weekly left and reset, pace status. Resets in **IST (`Asia/Kolkata`)**.
- Observation time and source. Mark unknown, stale, user-reported, and simulated evidence explicitly.
- No raw JSON, no catalog dump, at most ~12 lines.

## Intelligence reference — user-supplied Artificial Analysis chart, 10 Nov 2026

Use this chart to judge general intelligence. It supersedes the intelligence column of the older catalog below; it does not replace task-specific coding measurements or automatically re-rank the routing table. The image does not state its publication date or index version.

| Model | Effort | Intelligence |
|---|---|---:|
| Claude Opus 5.5 | High | 52 |
| GPT-6.1 Sol | High | 50 |
| Claude Opus 5.5 | Medium | 48 |
| GPT-6.1 Sol | Medium | 46 |
| GPT-6.1 Terra | Xhigh | 45 |
| GPT-6.1 Terra | High | 42 |
| Claude Sonnet 5.5 | High | 42 |
| GPT-6.1 Terra | Medium | 38 |
| Claude Haiku 5.5 | Max | 36 |
| Claude Haiku 5.5 | Xhigh | 35 |
| Claude Sonnet 5.5 | Medium | 31 |
| Claude Haiku 5.5 | High | 30 |
| GPT-6 Luna | Max | 28 |

For intelligence-only comparisons, follow this ordering and preserve ties. Do not infer scores for absent models or efforts. Unavailable models are never candidates, regardless of historical benchmarks.

## Reference catalog — Artificial Analysis, 29 Oct 2026

User-supplied measurements for explaining choices, not for re-ranking the table. Source: `~/Downloads/artificial_analysis_coding_benchmarks_14_models_2026-10-29.md`. Replace only when the user supplies newer data.

| Model | Effort | Intel. v5 | Intel. $/task | FrontierCode 2.0 | Terminal-Bench 4.0 | Coding Agent Index v2.0 (harness) | Agent $/task | Agent min/task |
|---|---|---:|---:|---:|---:|---|---:|---:|
| Claude Opus 5.5 | High | 52 | $3.46 | 36% | 57% | N/V | N/V | N/V |
| Claude Opus 5.5 | Medium | 48 | $2.45 | 33% | 53% | N/V | N/V | N/V |
| Claude Opus 5.5 | Low | 35 | $0.98 | 16% | 31% | N/V | N/V | N/V |
| Claude Sonnet 5.5 | High | 41 | $1.64 | 26% | 44% | N/V | N/V | N/V |
| Claude Sonnet 5.5 | Medium | 30 | $0.78 | 11% | 30% | N/V | N/V | N/V |
| Claude Haiku 5.5 | Max | 36 | $0.41 | 35% | 33% | 37 (Claude Code) | $2.67 | 72.0 |
| Claude Haiku 5.5 | Xhigh | 34 | $0.25 | 30% | 29% | N/V | N/V | N/V |
| Claude Haiku 5.5 | High | 30 | $0.16 | 23% | 22% | N/V | N/V | N/V |
| GPT-6.1 Sol | High | 50 | $0.59 | 37% | 52% | N/V | N/V | N/V |
| GPT-6.1 Sol | Medium | 46 | $0.36 | 33% | 48% | N/V | N/V | N/V |
| GPT-6.1 Terra | High | 42 | $0.26 | 37% | 42% | 46 (Codex) | $0.54 | 12.7 |
| GPT-6.1 Terra | Medium | 38 | $0.17 | 35% | 32% | 42 (Codex) | $0.39 | 10.2 |
| GPT-6 Luna | Max | 28 | $0.15 | 25% | 13% | 31 (Codex) | $0.16 | 21.3 |
| Gemini 3.8 Flash | High | 31 | $7.77 (free to the user) | 19% | 20% | 33 (Antigravity SDK) | $2.51 (free to the user) | 13.1 |

Caveats from the source: **N/V means not verified, not zero**. Agent scores depend on the harness and cannot be credited to the model alone. Intelligence Index v5 is a broad composite, so treat it only as a tie-breaker for coding. Don't mix scores across benchmark versions (Gemini's launch-era 59 is not comparable to its v5 score of 31). Gemini's high $/task comes from ~99k output tokens per task; that drains its quota faster, but costs the user nothing.
