<!--
Fill every section. Write "None" where a section does not apply; keep the heading.
Delete this comment block before filing. Mark anything not verified as Unknown.
-->

Blocked by: <#n Title | owner/repo#n Title | https://github.com/owner/repo/issues/n Title | None>

## Outcome

<One or two sentences: the behaviour that exists when this issue is done, as a caller or user sees it. Use the terms from the repo's domain docs.>

## Problem and motivation

<Why this matters now. Link the originating request, issue, or PR.>

## Current behaviour and evidence

Classification: <complete | partial | implemented but disabled/unreleased | absent>

- <Claim>. Evidence: `path/to/file` `symbolName`; <doc path>; <#issue or #PR>.
- Cite only paths and symbols you checked exist. Anything new is labelled `(proposed)`.

## Scope

- In: <...>

## Non-goals

- <...>

## Approach and tradeoffs

<The chosen approach in 3 to 6 sentences. Name the material alternatives and why each was rejected.>

## Implementation plan

Ordered steps. Each step names the file or symbol it touches (or `(proposed)`) and ends with a checkable "Done when".

1. <Step>. Done when: <observable check>.
2. <Step>. Done when: <observable check>.

Include each line below that applies; delete the rest:

- Callers and contracts affected: <callers, API shapes, events, schemas>.
- Migrations and data: <migration name, backfill, rollback order>.
- Auth and authorisation: <which gate applies and how it is preserved>.
- Release gate: <how the change reaches production under the repo's release rules>.

## Acceptance criteria

- [ ] <Measurable, observable criterion.>
- [ ] <Measurable, observable criterion.>

## Tests and smoke plan

- Focused tests: <test file(s) and cases; new test files labelled `(proposed)`>.
- Behavioural smoke: <exact request or command, and the expected result>.

## Docs and API catalog

- <Doc or README section to update, and what changes there, or None>.

## Dependencies

- Blockers: <#n Title: why it must finish first, or None>.
- Unblocks: <#n Title, or None>.

## Risks and rollback

- <Material risk and its mitigation, or None.>
- Rollback: <how to revert safely, or None.>

## Unknowns

- <Unverified fact.> Verify by: <command, file, or owner decision>.
