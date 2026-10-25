---
name: suggest-model
description: Recommend GPT, Claude, or Gemini using task fit, the user's intelligence scores, and live subscription headroom; treat benchmark cost as secondary. Use when asked which model to use, to compare model value, or to conserve weekly or 5-hour usage.
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

These examples guide judgment, not guarantees. A task may need a particular score within a tier; state the reason for that stronger requirement. The tier is an adequacy floor, not an instruction to choose its cheapest model. A higher tier is eligible for a lower-tier task, but an upgrade needs a task-fit or availability reason. Never silently lower the capability requirement to fit available quota.

Record task fit separately from the general intelligence score. Use explicit user preferences, concrete task constraints, and relevant user-reported outcomes or task-specific evaluations. If no comparative evidence exists, say **task fit unmeasured** and treat eligible families equally on fit. Do not invent vendor strengths, latency, context limits, tool support, or task-success rates from a model name or a general intelligence score. Do not raise the score floor just to force a preferred family.

**Complete when:** the required tier (and any stronger score floor), task-specific constraints and fit evidence, and explicit user preferences are recorded.

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

Apply that conservative envelope **before** tier filtering and ranking. In particular, an indistinguishable Sonnet High configuration is not a confirmed Tier 1 choice merely because one observation scored 52.

Antigravity can also report **“Claude & GPT (shared)”** limits. Those are a different third-party pool, not Gemini headroom and not native Claude Code or ChatGPT headroom. Exclude them under the default routes above. If the user explicitly identifies a different actual route, bind the model to that route's matching account and model/shared-group limits, and disclose the route change; never silently borrow another pool.

Apply **all** binding limits, including shared account limits and model/family-specific sublimits. Switching Claude effort or model does not escape a shared Claude limit; likewise for the GPT models. Keep any extra reported window as a constraint rather than discarding it because it is not 5-hour or weekly.

Normalize remaining amounts from `amount.remainingFraction` first; otherwise use an explicitly percent-valued remaining amount, or `remaining / limit` for compatible units and a positive limit. Validate fractions are within 0–1. For each window, use the most restrictive applicable remaining fraction and preserve its reset time; also retain any other exhausted limit's reset. A reported exhausted/blocked status or account-level denial overrides a positive amount. A reset time passing is a reason to refresh, not proof that quota is full.

Evaluate accounts separately. Do not add account percentages, deduplicate independent accounts, or double-count rows belonging to the same shared group. If the selected account or model scope cannot be determined, mark that binding unknown. A genuinely unreported window is **unreported**, not 100% free, 0% left, or an invented weekly/5-hour limit; flag the uncertainty.

**Complete when:** each candidate has its subscription/account, all binding limits, 5-hour and weekly remaining values or explicit unknown/unreported states, reset times, and evidence timestamp.

## 4. Compare all families; choose for task fit and subscription balance

1. Evaluate **GPT, Claude, and Gemini**, not just the cheapest catalog rows or the family running this conversation. Filter to configurations meeting the capability requirement and explicit user constraints, using conservative envelopes where needed. Use only the catalog below unless the user updates it. Record why a family has no adequate candidate; do not silently drop it because its benchmark USD/task is higher. If no configuration meets the constraints even before quota, report the constraint conflict; another usage reading cannot fix it.
2. Exclude exhausted or explicitly blocked candidates. Prefer confirmed bindings and current evidence over unknown ones. If none are confirmed to meet the requirement, give only a clearly conditional suggestion and request the missing readings, or offer waiting for a reported reset. An exhausted model is never the current recommendation. A lower-tier option must be labeled a capability compromise, not an adequate substitute.
3. Assess **both** windows and every shared/model-specific limit. Treat positive headroom of **10% or less as critical**, **over 10% through 25% as conserve**, and **over 25% as normal**. These are planning thresholds, not provider-imposed blocks. The tightest binding limit determines the quota condition.
4. Check weekly pacing when a weekly limit has a known duration and future reset: compare its remaining fraction with `(resetsAt - now) / durationMs`, capped at 1. Less remaining than the fraction of the week still left is a **weekly pace risk** under an even-use assumption. This is a conservation signal, not a prediction of task capacity; label the assumption. Without a usable reset/duration, pacing is unknown. Do not turn dollars per task into quota consumption or estimate tasks remaining without measured task-level quota burn.
5. Default to **task fit + subscription balance** for the subscription routes above. The catalog's USD/task is a benchmark measurement, **not marginal cash spend on these subscriptions**. Rank confirmed adequate choices in this order:
   - **Quota condition:** normal before conserve before critical.
   - **Weekly pacing:** known on-pace before at-risk or unknown pacing.
   - **Supported task fit:** prefer relevant comparative evidence or an explicit soft preference; if unmeasured, keep candidates tied on fit. Hard capability constraints were already applied.
   - **Subscription balance:** for each remaining pool, take the minimum remaining fraction across its binding limits. Keep pools within **10 percentage points** of the highest such value; prefer these over materially tighter pools even within the same headroom band. This is a conservation heuristic, not an assertion that equal provider percentages buy equal work. Do not use incomplete/unknown limits to claim a pool has more headroom. Differences of 10 points or less are a tie, not a reason to chase tiny fluctuations.
   - **Right-sized capability, then benchmark cost:** within the retained pools, prefer the required tier over an unnecessary higher tier. For judgment-heavy work within that tier, prefer higher conservative intelligence, explaining that this is a general capability proxy, not a task-specific result. For bounded mechanical work without evidence that extra intelligence helps, skip that upgrade. Use lower benchmark USD/task as the final tie-break; an exact tie is a tie, not an automatic preference for GPT or the current provider.
6. Honor an explicit request to minimize benchmark cost, favor a family, or use a different verified route; state how it changes the default ordering. Never override exhaustion, a hard capability requirement, or unknown quota. If all adequate choices are under pressure but available, apply the ordering and warn; planning thresholds are not blocks. A larger benchmark cost alone is not a reason to reject Claude or Gemini on a subscription. Equally, do not rotate providers or force a non-GPT winner merely for variety: a GPT recommendation is valid when it wins under the stated policy.

**Complete when:** every family was assessed, and one recommendation plus at most two useful alternatives is justified by capability, fit evidence, both quota windows, weekly pacing, and the applicable cost priority. If there is no confirmed adequate choice, that limitation is the result, not an invitation to invent availability.

## 5. Respond compactly

- State the required tier, the recommended model/effort (or that none is confirmed adequate), and the selection mode: **task fit + subscription balance** unless explicitly overridden.
- Use one comparison table, at most three candidates: exact model/effort and benchmark observation, intelligence, **benchmark USD/task**, subscription, 5-hour left and reset, weekly left and reset, quota condition, and decisive fit/balance evidence. Distinguish observations from a conservative envelope.
- Include the best eligible alternative from each other family, within that three-row limit. For a family with no adequate available candidate, give its concrete exclusion or uncertainty instead of fabricating an alternative. This comparison is required even when GPT wins; diversity in the comparison does not require diversity in the winner.
- Give one short reason covering the decisive fit/capability/quota tradeoff and the benchmark-cost tie-break, if used. Report weekly pace risk when it affected the decision. Do not describe a higher benchmark cost as extra subscription cash spend.
- Include the usage observation time and source; show resets in the user's known timezone, otherwise UTC. Mark unknown, unreported, stale, user-reported, and simulated data explicitly. Never describe a recommendation as usage-verified when a binding window is unknown.

## Decision examples — simulated, not current usage

These illustrate the default policy, not usage evidence for a real recommendation. Assume all binding limits are known, all pools are normal and weekly on-pace, and task fit is unmeasured unless stated. Percentages below are each pool's tightest binding limit.

- **Mechanical task; GPT 40%, Claude 85%, Gemini 55%:** choose Haiku High using its conservative envelope (38, $0.12). Claude has materially more headroom; Luna's $0.07 benchmark does not override subscription balance.
- **Mechanical task; GPT 40%, Claude 50%, Gemini 90%:** choose Gemini Flash High. Its higher benchmark cost is not an extra subscription charge.
- **Judgment-heavy Tier 1 task with floor 50; all pools 80%:** choose Opus High (54) over Sol High (50), using general capability as the stated proxy—not a claim of measured task-specific superiority. Gemini is below the floor; ambiguous Sonnet High is conservatively 47.
- **Mechanical task; GPT 80%, Claude 90%, Gemini 88%:** all pools are within 10 points of the best. With no comparative fit evidence or need for more intelligence, Luna Max wins the final benchmark-cost tie-break. Do not force a different provider.

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
