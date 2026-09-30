---
name: design-help
description: Run an iterative UI/UX design workflow for an app, website, screen, or flow. Grills the user for a real design brief before touching pixels, then produces quick low-fidelity prototypes to react to, and refines over multiple rounds instead of one-shotting a finished design. Use whenever the user wants to design or redesign a UI, explore what a screen/app/website/flow should look like, asks for mockups, wireframes, or UI concepts, wants a second opinion on a layout, or wants to think through product UX before writing production code. Composes the grilling, prototype, impeccable, and beautify-flutter skills rather than duplicating them.
---

# Design Help

The failure mode this skill exists to prevent: jumping straight from "design me X" to a single finished-looking mockup the user has to react to cold. Instead, run a loop — **brief → prototype → feedback → refine** — and only add polish once a direction is actually validated. Each phase below leans on an existing skill instead of reinventing it; this skill's job is sequencing them and injecting design-specific judgment.

## Phase 1 — Grill for the brief

Before any pixels, invoke `mattpocock-skills:grilling` to interview the user. Grilling's mechanic (design-tree, frontier rounds) is generic — seed it with the design-specific branches that actually matter here so the first round isn't wasted on questions grilling wouldn't know to ask on its own:

- **Who's it for** — target user(s), their context of use, what they're trying to get done
- **Platform & stack** — web, mobile, Flutter, existing codebase or greenfield; any existing design system/component library already in play (check the repo before asking — don't make the user state what you can find)
- **Tone & references** — brand adjectives, competitor or inspiration links, "make it feel like X but not Y"
- **Must-have flows/screens** — the 2-3 things that have to work, vs. nice-to-haves
- **Constraints** — timeline, fidelity needed (throwaway concept vs. near-final), accessibility requirements, dark mode
- **Success criteria** — how they'll know a direction is right when they see it

Match the grill's depth to the ask. A "redesign this settings page" needs a short, targeted round or two, not a full interrogation — over-grilling a small request is its own failure mode. A "help me design this whole app" earns the full treatment. Stop grilling once you have enough to produce a meaningfully different first prototype than you would have without asking — not when every conceivable question is answered.

## Phase 2 — Prototype low-fidelity, fast

Never build prototypes yourself in the main session — delegate the actual building to `Agent` subagents with `model: "sonnet"` (Sonnet 5). Two reasons: it keeps the main session free to keep interviewing/coordinating instead of burning its own context on markup, and — more importantly for divergent directions — a fresh subagent per direction produces a genuinely different take, whereas one agent (or one continued session) building direction B right after direction A tends to anchor on A instead of exploring a real alternative.

Pick the branch based on what exists:

- **Greenfield, or a concept that doesn't need to live in real code yet** → build the prototype as an Artifact. **Dispatch one Sonnet 5 subagent per direction, in parallel, in a single message with multiple `Agent` calls.** Each gets a self-contained prompt: the full brief from phase 1, plus one explicit, distinct creative angle you assign it (e.g. "dense, data-forward dashboard layout" vs. "card-based, minimal, generous whitespace" vs. "narrative single-column flow") — decide the 2-3 angles yourself from the brief before spawning, don't let the subagents each guess their own angle. Each subagent should load `artifact-design` (and `artifact-capabilities` if the prototype needs to demonstrate interaction/state) and publish its own Artifact, then report back the URL and a one-line description of what it built. Show all resulting Artifacts to the user together — divergence at low fidelity is the entire point of this phase. Tell each subagent explicitly to keep it to layout, hierarchy, and flow; skip final colors, copy, and pixel-level detail on this pass.
- **An existing app/codebase where the prototype needs to sit near real code or real data** → dispatch a Sonnet 5 subagent per prompt in `mattpocock-skills:prototype` (its UI branch), with the codebase path, the brief, and the assigned angle(s) in its prompt (a fresh agent has no memory of this conversation, so state everything it needs — file paths, stack, brief). If you want multiple divergent directions here too, either spawn one subagent per direction in isolated worktrees (`Agent` with `isolation: "worktree"`), or one subagent building all variants behind the single switcher that skill already specifies — pick worktrees when the directions are different enough that they'd conflict in one file.
- **Flutter specifically** → after a subagent's prototype lands, `dart-flutter:flutter-add-widget-preview` is the fast way to let the user see it live without a full run cycle.

Never let a "first pass" prototype reach for final polish — tell subagents this explicitly, since a fresh agent left to its own judgment will often over-invest. Rough is the point — it's cheaper to throw away three rough directions than to over-invest in one polished one that misses.

## Phase 3 — Show it, get specific feedback, iterate

Present the prototype(s) and ask pointed reaction questions, not "thoughts?" — e.g. "of these three, which hierarchy reads right at a glance?", "does the empty state make sense without the tooltip?", "is this too busy for the target user from phase 1?". Vague prompts get vague feedback; specific prompts get decisions.

Feed the answers back into another round of phase 2, narrowing each time:
- **Round 1**: divergent directions, rough fidelity
- **Round 2+**: one chosen direction, refined — real copy, tighter spacing, edge cases (empty/error/loading states)
- Only stop iterating when the user says a direction is right, not when you run out of ideas to add

## Phase 4 — Polish, once (and only once) a direction is locked

Don't run a polish pass before the user has committed to a direction — polishing something that gets thrown away next round is wasted work. Once locked in:

- Web / general frontend → invoke `impeccable` for the visual/UX critique and polish pass (hierarchy, spacing, color, motion, accessibility, anti-patterns).
- Flutter → invoke the `beautify-flutter` skill (`~/development/flutter/.agents/skills/beautify-flutter/SKILL.md`) for Material 3 theming, dark-mode parity, and Flutter-idiomatic polish; it's more Flutter-specific than `impeccable` for that project.

## The loop, stated plainly

This is not brief → prototype → polish → done. It's brief → prototype → feedback → **back to prototype** as many times as it takes, with polish deferred to the very end. If you notice yourself about to hand the user a "final" version without having shown them at least one earlier rough pass first, stop and produce the rough pass instead — the whole value of this skill is catching direction problems while they're still cheap to fix.
