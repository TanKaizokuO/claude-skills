---
name: ask-me
description: Surface every open decision up front as context-rich questions with a recommendation each, ask them by priority tier, then execute without further questions and log the decisions.
disable-model-invocation: true
---

Before doing the task, bring me every open decision with enough context to answer, plus your recommendation. Then stop asking and do the work.

## 1. Research first

- Read the relevant code, files, and prior context before asking anything. Delegate bulk reading to the `scout` subagent.
- Never ask what the repo, docs, or earlier answers already settle. Only ask real forks: choices where the right answer depends on my intent or preference.
- If nothing is genuinely open, say so in one line and proceed.

## 2. Collect and tier the decisions

List every open decision first, then sort into tiers:

- **P1, blockers:** nothing sensible can start until answered; or hard to reverse; or reshapes everything else.
- **P2, shapes the design:** changes the approach but not whether work can begin.
- **P3, details:** has a sensible default; I may just want to veto it.

If question B only makes sense after question A, put B in a later tier.

## 3. Ask one tier at a time

For the current tier, make one `AskUserQuestion` call with all of that tier's questions together (max 4 per call; if the tier has more, issue consecutive calls for the same tier before moving on).

**Put the context inside the question text. Do not print a chat preface before the call.** The question text is the only place I read, so it must carry everything needed to answer, in plain language (no unexplained jargon or internal names). Write each `question` as a short multi-line block, in this order:

- **Context:** what this is and what you found, with `file:line` references where relevant (1-3 lines).
- **Why it matters:** what the answer changes downstream (1 line).
- **Recommendation:** which option, and why, naming the main trade-off against the alternative (1-2 lines).
- **The question itself**, last, ending with a question mark.

Then the options:

- Short `header`, 2-4 distinct `options`; each option's `description` states the consequence of picking it.
- Recommended option first, label ends with "(Recommended)". Do not add an "Other" option; the UI supplies it.
- Each question must stand alone: I should be able to answer from the question text and option descriptions without scrolling up.

## 4. Move down the tiers

- Ask the next tier only after the current one is answered. Re-tier first, since answers may remove, add, or reorder questions.
- Never re-ask an answered question.
- If I answer with free text asking for clarification, re-ask that question with more context. Do not guess.

## 5. Log, then execute

After the last tier:

1. Append the decisions to `DECISIONS.md` in the working directory (create if missing), one entry per decision: date, question, my answer, why. Include any decisions you made on my behalf under a "defaulted" label.
2. Give a 3-6 line summary of what was decided and what you will now do.
3. Execute the task with no further questions. Re-ask only when something both blocks the work and could not have been foreseen; otherwise pick the recommended default and record it in `DECISIONS.md`.
