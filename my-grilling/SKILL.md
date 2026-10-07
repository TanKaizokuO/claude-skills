---
name: my-grilling
description: Grill the user relentlessly about a plan, decision, or idea, using the interactive AskUserQuestion tool. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

Interview me relentlessly about every aspect of this until we reach a shared understanding. Walk down each branch of the decision tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

**Every question MUST be asked through the `AskUserQuestion` tool** (the interactive selection UI with selectable options and "Other" for custom input). NEVER write questions as plain chat text.

- Each question: short `header` chip, a clear `question`, 2–4 distinct `options` with short labels and tradeoffs in `description`.
- Put your recommended option first and append "(Recommended)" to its label. Do not add an "Other" option; the UI supplies it.
- Ask one decision at a time, waiting for the answer before continuing. Only batch several questions in one call when they are truly independent and tightly related.
- Use `multiSelect: true` only when several options can legitimately be chosen together.
- If the user picks "Other" and types custom input, acknowledge it first, then re-ask anything still unresolved.

If a *fact* can be found by exploring the environment (filesystem, tools, etc.), look it up rather than asking me. The *decisions*, though, are mine — put each one to me via `AskUserQuestion` and wait for my answer.

Do not act on it until I confirm we have reached a shared understanding (confirm via `AskUserQuestion` too).
