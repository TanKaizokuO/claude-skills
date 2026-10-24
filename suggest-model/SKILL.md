---
name: suggest-model
description: Recommend a model for a task using the user's intelligence scores, cost per task, and live subscription headroom. Use when asked which model to use, to compare model value, or to conserve weekly or 5-hour usage.
---

# Suggest a model

Recommend; do not switch models, edit routing, enable paid overages, redeem resets, or start the proposed task. Use the conversation and invocation arguments as the task brief.

## 1. Set the capability requirement

Identify the work, uncertainty, and consequence of a wrong answer. Use the existing conversation; ask only if the task or a decision-changing constraint is missing.

Choose the lowest adequate tier, stating the reason:

| Tier | Intelligence | Typical work |
|---|---|---|
| 3 — Low | Below 45 | Bounded mechanical edits, extraction, simple scripts, well-specified implementation. |
| 2 — Medium | 45–49 | Multi-step implementation, localized debugging, routine review with meaningful judgment. |
| 1 — High | 50+ | Ambiguous architecture, difficult debugging, cross-system reasoning, high-consequence decisions. |

These examples guide judgment, not guarantees. A task may need a particular score within a tier; state the reason for that stronger requirement. A higher tier is eligible for a lower-tier task, but extra intelligence alone does not justify extra cost. Never silently lower the capability requirement to fit available quota.

**Complete when:** the required tier (and any stronger score floor), task-specific capability constraints, and explicit user preferences are recorded.

## 2. Fetch current usage

For an actual recommendation, run this on **every invocation**, before choosing a model:

```sh
omp usage --json --redact
```

Use the per-account `reports`, not the aggregated `capacity` values. Retain each report's `fetchedAt`, applicable limits, status, and `window.resetsAt` (Unix milliseconds). `generatedAt` is not proof that each provider was freshly fetched.

If a relevant report is more than five minutes old, invalidate only that provider's usage cache, then refetch it once:

```sh
omp usage invalidate --provider <provider-id>
omp usage --json --redact --provider <provider-id>
```

Errors, missing reports, stale data after that refresh, and unparseable limits mean **unknown**, not unused or unlimited. If the CLI is unavailable or cannot obtain current limits, request only the missing providers' current usage-screen readings: remaining 5-hour and weekly amounts, reset times, and observation time. Do not infer subscription capacity from token logs, `omp stats`, API pricing, or the cost audit. Never read or print credentials to obtain quota.

For an explicitly hypothetical comparison or skill smoke check, use the supplied usage snapshot instead and label the result **simulated**. A user-supplied current snapshot must carry its observation time; identify it as user-reported rather than live. Do not use old conversation readings for a new actual recommendation.

**Complete when:** every relevant subscription has timestamped usage evidence or an explicit unknown state.

## 3. Bind each candidate to its real quota

The user's subscriptions and default routes are:

| Catalog models | Subscription | Provider ID | Applicable limits |
|---|---|---|---|
| GPT-6.1 Sol; GPT-6 Luna | ChatGPT / Codex | `openai-codex` | Native account's shared 5-hour and 7-day limits, plus any applicable model-specific limits. |
| All Claude Opus, Sonnet, and Haiku entries | Claude Code | `anthropic` | Native account's shared 5-hour and 7-day limits, plus any applicable model-specific limits. |
| Gemini 3.8 Flash | Gemini / Antigravity | `google-antigravity` | **Gemini** 5-hour and weekly limits, plus any applicable model-specific limits. |

The user explicitly said to **ignore the word “Fallback.”** It does not create another provider, subscription, or spare quota pool. The two Haiku High observations and the two Sonnet High observations remain separate benchmark entries, distinguished by intelligence and cost; they do not imply independently selectable routes. Do not invent a CLI model ID or promise a particular benchmark result from the same named configuration. When the observations would change the choice and no distinguishing configuration is known, explain the uncertainty and use the lower score and higher cost as a conservative decision envelope; retain the original observations in the catalog.

Antigravity can also report **“Claude & GPT (shared)”** limits. Those are a different third-party pool, not Gemini headroom and not native Claude Code or ChatGPT headroom. Exclude them under the default routes above. If the user explicitly identifies a different actual route, bind the model to that route's matching account and model/shared-group limits, and disclose the route change; never silently borrow another pool.

Apply **all** binding limits, including shared account limits and model/family-specific sublimits. Switching Claude effort or model does not escape a shared Claude limit; likewise for the GPT models. Keep any extra reported window as a constraint rather than discarding it because it is not 5-hour or weekly.

Normalize remaining amounts from `amount.remainingFraction` first; otherwise use an explicitly percent-valued remaining amount, or `remaining / limit` for compatible units and a positive limit. Validate fractions are within 0–1. For each window, use the most restrictive applicable remaining fraction and preserve its reset time; also retain any other exhausted limit's reset. A reported exhausted/blocked status or account-level denial overrides a positive amount. A reset time passing is a reason to refresh, not proof that quota is full.

Evaluate accounts separately. Do not add account percentages, deduplicate independent accounts, or double-count rows belonging to the same shared group. If the selected account or model scope cannot be determined, mark that binding unknown. A genuinely unreported window is **unreported**, not 100% free, 0% left, or an invented weekly/5-hour limit; flag the uncertainty.

**Complete when:** each candidate has its subscription/account, all binding limits, 5-hour and weekly remaining values or explicit unknown/unreported states, reset times, and evidence timestamp.

## 4. Choose by capability, availability, sustainability, then cost

1. Filter to models meeting the capability requirement and any explicit user budget or preferences. Use only the catalog below unless the user updates it. If no catalog configuration meets those constraints even before considering quota, report the constraint conflict; a reset or another usage reading cannot fix it.
2. Exclude exhausted or explicitly blocked candidates. Prefer candidates with confirmed bindings and current evidence over unknown ones. If none are confirmed to meet the requirement, report that fact: give only a clearly conditional suggestion and request the missing readings, or offer waiting for a reported reset. An exhausted model is never the current recommendation. A lower-tier option must be labeled a capability compromise, not a substitute meeting the requirement.
3. Assess **both** windows and shared/model-specific limits. Treat positive headroom of **10% or less as critical**, **over 10% through 25% as conserve**, and **over 25% as normal**. These are planning thresholds, not provider-imposed blocks. The tightest binding limit determines the quota condition.
4. Check weekly pacing when a weekly limit has a known duration and future reset: compare its remaining fraction with `(resetsAt - now) / durationMs`, capped at 1. Less remaining than the fraction of the week still left is a **weekly pace risk** under an even-use assumption. This is a conservation signal, not a prediction of task capacity; label the assumption. Without a usable reset/duration, pacing is unknown. Do not turn dollars per task into quota consumption or estimate tasks remaining without measured task-level quota burn.
5. Rank confirmed adequate choices by **headroom band first** (normal, then conserve, then critical), **weekly pacing second** (known on-pace before at-risk or unknown pacing), **lowest cost per task third**, and **higher intelligence for cost ties**. Raw percentage differences within the same band do not outrank cost. This preserves scarce pools while keeping cost decisive between similarly sustainable choices. If all choices are under pressure but available, keep this ordering and warn; planning thresholds are not hard blocks. If conserving quota substantially increases cost, show the cheaper adequate option and explain the tradeoff. A task-specific intelligence upgrade needs a stated reason. Honor an explicit user's priority, but never override actual exhaustion or hide unknown quota.

**Complete when:** one recommendation and at most two useful alternatives are justified against the capability requirement, both quota windows, weekly pacing, and supplied cost. If there is no confirmed adequate choice, that limitation is the result, not an invitation to invent availability.

## 5. Respond compactly

- State the task's required tier and the recommended model/effort, or state that no adequate model is confirmed available.
- Use one comparison table, at most three candidates: exact model/effort and benchmark observation, intelligence, USD/task, subscription, 5-hour left and reset, weekly left and reset, quota condition. Distinguish measured observations from a conservative envelope if one affected the decision.
- Give one short reason covering the decisive capability/cost/quota tradeoff. Explain an unexpectedly expensive choice or a rejected cheaper option. Report weekly pace risk when it affected the decision.
- Include the usage observation time and source; show resets in the user's known timezone, otherwise UTC. Mark unknown, unreported, stale, user-reported, and simulated data explicitly. Never describe a recommendation as usage-verified when a binding window is unknown.

## Model catalog — user-supplied measurements

The intelligence scores and USD cost per task below are the user's observations, not live prices, success probabilities, or subscription cash charges. Preserve all 13 entries, including dominated and duplicate-name observations. Update these measurements only when the user supplies replacements. Tier membership follows the numeric score.

| Tier | Model | Effort | Intelligence | USD/task |
|---|---|---|---:|---:|
| 1 | GPT-6.1 Sol | High | 50 | $0.32 |
| 1 | Claude Opus 5.5 | Medium | 51 | $1.34 |
| 1 | Claude Opus 5.5 | High | 54 | $1.82 |
| 1 | Claude Sonnet 5.5 | High | 52 | $2.01 |
| 2 | GPT-6.1 Sol | Medium | 48 | $0.21 |
| 2 | Claude Sonnet 5.5 | High | 47 | $0.88 |
| 3 | GPT-6 Luna | Max | 38 | $0.07 |
| 3 | Claude Haiku 5.5 | High | 38 | $0.08 |
| 3 | Claude Haiku 5.5 | High | 41 | $0.12 |
| 3 | Claude Haiku 5.5 | Max | 43 | $0.21 |
| 3 | Claude Sonnet 5.5 | Medium | 41 | $0.48 |
| 3 | Claude Opus 5.5 | Low | 42 | $0.55 |
| 3 | Gemini 3.8 Flash | High | 41 | $1.24 |
