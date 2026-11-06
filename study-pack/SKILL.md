---
name: study-pack
description: Build a study pack from supplied lecture notes, past-year or past-exam papers, or assignments - topic coverage, worked derivations, similar-question practice, and explained solutions. Use when the user wants exam revision, derivations resembling past questions, or explanations of past-paper or assignment solutions from their course material.
---

# Study Pack

A **study pack** is one self-contained revision artifact (HTML by default) built only from the user's supplied course material, with every claim traceable to a source and every practice item labelled by provenance.

## Procedure

Each step ends on its completion criterion. Do not start the next step until the current one is met.

### 1. Inventory the sources

List every supplied file: type (notes, slides, PYQ, past paper, assignment, solution set), course/year/paper identifier, page or slide count, and question count.

Done when: every supplied file appears in the inventory with those fields filled, or is marked "unreadable" with the reason.

Ask the user only when the material needed to proceed is absent (no notes and no papers at all) or the deliverable is unidentifiable and no default applies. Otherwise proceed with HTML as the default format unless the user requests another (e.g., Markdown).

### 2. Fix scope and deliverable

Record the exam scope (topics, chapters, or syllabus lines the user named or the notes/papers imply), the requested format (HTML, Markdown, or other), and the requested depth.

Done when: each topic in scope is listed, and the deliverable format is written down.

### 3. Build the traceability ledger

Assign stable IDs before writing any content:

- `S<n>`: a supplied notes location, e.g. `S3 lecture-4.pdf p.12`.
- `P<year>-<paper>-Q<n>`: a question from a past paper, e.g. `P2024-Paper1-Q3(b)`.
- `A<n>`: an assignment item.
- `G<n>`: a generated practice item (provenance `generated`). `H<n>`: a predicted practice item (provenance `predicted`). Numbering is separate from `S`, `P`, and `A`, so a generated or predicted ID never looks like an original source. Each `G` or `H` item still cites the actual source IDs it was built from, e.g., `G1 (from S3)`.

Every question, derivation, and claim in the artifact cites at least one ID.

Done when: every topic from step 2 maps to one or more IDs, or is explicitly marked `GAP` (not covered by supplied material).

### 4. Label provenance

Every practice item carries exactly one label:

| Label | Meaning |
|---|---|
| `official` | Verbatim text of a supplied past-paper question. |
| `paraphrase` | Restatement of an official question, citing its ID. |
| `generated` | New practice question written from supplied notes, not attributed to any paper. |
| `predicted` | Practice hypothesis that a topic may appear in a future exam. Never presented as fact. |

Done when: each item in the artifact shows its label, its own ID (`G<n>`/`H<n>`, or the original `P`/`A` ID), and the source IDs it cites.

### 5. Report topic frequency transparently

Count each topic's appearances across the supplied papers and, where marks are shown, their marks.

- Report the sample: number of papers, years covered, and which papers are missing.
- Report actual counts per topic (e.g., "Topic X: 4 of 6 supplied papers, 38 of 120 marks"), with marks where shown.
- Rank topics only from these counts. Label any ranking from a small sample as weak.
- Never state a likelihood or forecast of what will appear in a future exam.

Done when: the sample size, the per-topic counts (and marks where shown), and any small-sample caveat appear in the artifact.

### 6. Write derivations

For each derivation:

- State assumptions, domain of validity, and units on the first line that uses them.
- Show one logical step per line. Justify each step with the rule or definition it uses.
- Cite the source ID of the notes that contain the result.

For derived or new numerical examples (not values copied from supplied papers or notes), run the arithmetic with a real computation (a short Python or shell call) and record the output. Put the computed value in the artifact. If the computation cannot run, mark the value `unverified`.

Done when: every derived or new numerical value traces to a recorded computation or is marked `unverified`, and copied values cite their source ID.

### 7. Write practice and solutions

Each practice question includes: the question, the solution, and a one-line check (dimensional check, limiting case, or recomputation).

- Solutions explain the method first, then the calculation.
- When an official question has no supplied answer, label its solution `generated, unverified against official marking scheme`.
- When a question is ambiguous, write the ambiguity and the interpretation you chose. Do not resolve it silently.
- Never invent a marking scheme, a mark allocation, or an "official" answer.

Done when: every practice question has a solution, a check, and a provenance label, and each ambiguity is flagged.

### 8. Explain assignment solutions

For assignment items, explain the concept, the method, and the reasoning path, and give worked solutions as requested. Check each worked answer against any supplied solution set. Where they differ, or no solution set is supplied, say so; never invent an official answer. Flag ambiguous wording instead of resolving it silently. Keep academic-honesty statements factual: name the supplied sources used, and state that worked solutions are explanations written here, not official answers.

Done when: each assignment item in scope has a worked explanation, a check against supplied solutions (or a note that none was supplied), and any ambiguity flagged.

### 9. Present the material

Present in the requested format. HTML is the default.

Apply teach-me's conventions inside the artifact (do not create a teach-me workspace unless the user asks for one):

- Short sections, one idea each.
- Practice answers: HTML hides them behind `<details>`; Markdown gives each answer its own labelled line below the question.
- One recommended primary source per topic.
- Navigation: HTML uses anchored links between topics, practice, and the traceability table; Markdown uses a plain contents list.

For supplemental facts that the supplied material lacks, read `skill://research` and use high-trust primary sources. Mark each supplemental fact with its source URL and a `supplemental` tag. Never let supplemental material replace or contradict supplied material without flagging the conflict.

Done when: each supplemental fact has a source and tag, and each conflict is flagged.

### 10. Write the artifact

Format: the requested format; HTML if none is requested.

- HTML: one self-contained file. Inline all CSS. At most one inline script, only for navigation or `<details>` behaviour. No `eval` and no network fetches. Use inline SVG for diagrams. No required external images or scripts.
- Math: use offline rendering only when tooling is present (e.g., a local KaTeX or pandoc); rendered output is then typeset. Otherwise keep raw LaTeX in `\( … \)` or `\[ … \]`. Raw LaTeX is NOT typeset: never report it as typeset, and state the visual limitation in the report. An optional online renderer may be added, but it is never the only route to content, and no integrity hash is invented.
- Markdown: use `$…$` and `$$…$$` only when the confirmed target renderer supports them; otherwise preserve readable plain-text or LaTeX source and state the rendering limitation. No HTML tags, anchors, or `<details>`.
- Anchors (HTML only): use `#id` links; every target must exist.
- Never overwrite an existing file. If the chosen output name exists, pick the next free name and report it. If the user named a path that exists, ask before overwriting.

Done when: the file is at a path that did not previously exist (or the user confirmed the overwrite) and is in the requested format.

### 11. Check the artifact

Run the checks for the format written:

- HTML: balanced tags and valid structure; every internal anchor resolves to an id; every math delimiter closed; render in a browser or headless renderer if one is available, and report it.
- Markdown: headings and tables well-formed; every math delimiter closed; every internal link resolves to a heading or is removed; no HTML-only constructs.
- All formats: every practice item has a provenance label and a source ID; every derived or new numerical value traces to a recorded computation or is marked `unverified`. Values copied from supplied papers are cited, not recomputed.

Done when: every check for the format passes, or each failure is reported with its location.

## Completion report

Keep the final message short. It contains:

1. Output path(s).
2. Coverage table: topic → source IDs, or `GAP`.
3. Verification run: which computations and checks ran, and their results.
4. Source limitations: missing years or papers, unreadable files, unverified values, open ambiguities, and math status (typeset, or raw source only).
5. Decisions made: format, ranking method, and assignment flags (what was explained, and what was checked against supplied solutions).

Honest limits beat confident gaps. A pack that states "insufficient sample" and marks `GAP` is complete. A pack that fills gaps with plausible content is not.
