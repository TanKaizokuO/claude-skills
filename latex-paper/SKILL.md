---
name: latex-paper
description: Use for LaTeX papers (.tex/.bib projects) when the user asks to edit or proofread sections, compile or fix build errors and PDF layout, audit citations and bibliography entries, or convert a manuscript to another venue template. Triggers on LaTeX, .tex, .bib, latexmk, BibTeX, Biber, camera-ready, and conference/journal template requests.
---

# LaTeX paper

Run only the branches the user requested: EDIT, BUILD, REFERENCES, VENUE. Each branch ends on its own completion criterion.

## 0. Scope (every branch)

1. **Entrypoint**: the root `.tex` the build uses. Source of truth, in order: documented build command (Makefile, README, CI workflow), `.latexmkrc`, then the only file with `\documentclass` and `\begin{document}`. If still ambiguous, pick the one the build config names and state the choice in the report.
2. **Locked files**: collect every path the user or repo marks as locked ("do not change main.tex"). Record `sha256sum` for each before editing; re-check after. Any change to a locked file is a failure to report, not a fix to apply.
3. **Template and engine**: read the `\documentclass` and any local `.cls`/`.sty`/`.bst`. Infer the engine from config, not habit: `fontspec`/`unicode-math` → XeLaTeX or LuaLaTeX; otherwise pdfLaTeX. Use the engine the project already builds with. Resolve the bibliography backend from `biblatex` options (`backend=`), the build config, or log output: `backend=bibtex` → BibTeX; biber backend or default `biblatex` → Biber; `\bibliographystyle` without `biblatex` → BibTeX; no `\cite` and no bibliography → no bibliography tool. Never change the configured backend.
4. **Toolchain check**: `command -v latexmk pdflatex lualatex xelatex biber bibtex pdftoppm`. Missing preferred tool (for example `latexmk`) → use the installed compatible route in BUILD step 1. Mark BUILD NOT RUN only when no compatible engine and bibliography tool pair exists, and name the exact missing binary or `.sty`. Finish all reachable source work. Never substitute `bibtex` for a required `biber`, or the reverse.

## Invariants (every branch)

- Equations, numerical results, table values, figure data, author names/affiliations/emails, funding, acknowledgements, and the meaning of claims stay unchanged unless the user requests that exact change.
- Never fabricate citations, DOIs, metric values, or results. If information is missing, leave the existing text and report the gap.
- Keep the template, class, and bibliography engine. Swap only when the requested branch or a verified build failure requires it, and explain why.
- Execution: no `-shell-escape`, `\write18`, or TeX-invoked external programs (minted, gnuplot, pythontex, epstopdf shell). Do not run them without explicit user approval for that run; otherwise stop that step and report the blocked feature.
- Artifacts: never delete or overwrite existing PDFs, `.aux`, or outputs the user keeps. Use the project's documented build command. Without one, build into a fresh scratch directory outside the source tree using BUILD step 1. Do not change `openout_any`, pass `-shell-escape`, or give bibtex/biber a directory-qualified output path to make a build pass.

## Branch EDIT (requested text changes or proofreading)

1. Locate target text with grep across the root file and everything it `\input`s, `\include`s, or `\subfile`s. Edit only files the request touches.
2. Keep labels, `\cite` keys, and macro names unchanged unless asked. Renaming breaks references in other files.
3. Math: change only requested notation. If a symbol is redefined, grep its `\newcommand`/`\DeclareMathOperator` and every use.
4. Completion: every requested edit is applied; every changed file and every changed equation or number is listed with before/after text.

## Branch BUILD (compile and fix errors)

1. Run the build command from step 0 when the project documents one. Otherwise choose the route the installed tools support:
   - **latexmk** (if installed): `latexmk -pdf -interaction=nonstopmode -file-line-error -outdir=<scratch> <src>/<main>.tex`. It runs the bibliography tool and reruns itself.
   - **Manual route** (no `latexmk`; `<src>` = source directory, `<main>` = root file basename, `<scratch>` = fresh directory outside the source tree):
     a. `cd <scratch>`, then run the engine on the absolute source path so aux, log, and PDF land in the working directory. Set search paths explicitly: `TEXINPUTS=<src>//: BIBINPUTS=<src>: BSTINPUTS=<src>: pdflatex -interaction=nonstopmode -file-line-error <src>/<main>.tex`. Use `//` only for subdirectory assets; the trailing `:` keeps the default path.
     b. In the same `<scratch>` cwd, run the resolved bibliography tool by basename only: `BIBINPUTS=<src>: BSTINPUTS=<src>: bibtex <main>` for the BibTeX backend, or `biber <main>` for the Biber backend. Skip this step when the sources have no bibliography. Never pass a directory path or `-output-directory` to bibtex or biber; TeX's `openout_any=p` rejects it and produces false undefined citations.
     c. Repeat the engine command twice more, until the log has no `Rerun` line.
   - The bibliography tool follows the backend resolved in step 0.3; a bibliography-free source needs none. Never swap a configured backend.
2. Read `<outdir>/<main>.log` and any `.blg`. Classify and act:
   - `! ` errors → fix the source line the `-file-line-error` output names; rebuild.
   - `Citation ... undefined` / `Reference ... undefined` after the final pass → REFERENCES branch.
   - `File ... not found` → missing asset, package, or bad path. Fix a wrong path; do not download or install packages silently; report the exact name.
   - `Overfull \hbox` / `Overfull \vbox` → fix only if the PDF shows clipping or overflow past the margin. Otherwise list as remaining.
   - `Font shape ... undefined`, `Missing character`, `Underfull` → report unless they are visibly wrong in the PDF.
3. Visual check (requires `pdftoppm`): `pdftoppm -r 110 -png <pdf> <scratch>/page`, then view each page image that contains changed text, figures, tables, or display equations. Check for: text or equations past the margin, table wider than the text block, figures far from their first reference, captions split from figures, and blank-page gaps. A visual pass is valid only for pages actually viewed; report the page numbers.
4. Completion: build exits 0; log has no `undefined` citation or reference lines; warnings are split into fixed and remaining with exact log text; PDF path reported.

## Branch REFERENCES (citation and bibliography audit)

1. **Keys**: collect `\cite*` keys from included files and `@type{key,` entries from every `.bib` in scope. Report: cited-but-missing keys, duplicate keys, and uncited entries (informational only; do not delete unless asked).
2. **Log**: confirm no `undefined` citation or reference lines in the final build.
3. **Metadata**: for each entry in scope (all if the user did not narrow it), check authors, title, venue, year, DOI, and pages against an authoritative record: publisher or DOI resolver, Crossref, DBLP, arXiv, ACL Anthology, or official proceedings. Use the `research` skill for primary-source lookup. Verdicts:
   - `VERIFIED`: matches the authoritative record.
   - `MISMATCH`: a field differs. Fix only that field, and only if the user asked for fixes; cite the source used.
   - `UNVERIFIED`: no authoritative record found. Leave the entry unchanged and list what was searched.
   - `WRONG`: the authoritative record shows a different work or a non-existent one. Report; do not substitute a replacement without direction.
   A failed search is `UNVERIFIED`, never `WRONG`.
4. **Claim support**: a matching bibliography record does not show that the cited work supports the sentence. Mark claim support `NOT CHECKED` unless the relevant passage was read, and then cite the passage location.
5. **Access**: a record found in a search is retrievable, not open access. Report access status separately and do not assume a full text was read.
6. **Keys**: do not rename keys while fixing. If a rename is unavoidable, update every `\cite` site in the same pass and rebuild.
7. **Format**: edit only the specific fields that change. Do not reformat or re-sort the `.bib` file.
8. Completion: every key in scope has a verdict with its source (DOI or URL); no undefined citation remains in the build (or BUILD is NOT RUN).

## Branch VENUE (template or format conversion)

1. Obtain the template from the venue's official source and record its name and version or date. If it is absent locally and cannot be fetched with approved tools, stop and report the missing template.
2. Write the converted paper to a new directory. Leave the original tree untouched.
3. Move body text, equations, tables, figures, and bibliography into the venue template. Keep the bibliography engine and style the template requires. Remove packages that conflict with the template (for example `geometry`, `fullpage`, or duplicate `natbib`) only when they break the build.
4. Anonymity and page limits are substantive changes. Apply anonymization only when the user requests it or the official call requires it; list every removed identifying element. Mark venue rules that could not be confirmed in the official source as `UNVERIFIED`.
5. Build with the template's engine. Count pages with the PDF and compare against the official limit (references and appendix rules as the call states).
6. Completion: converted directory builds (or BUILD NOT RUN); a content diff shows no changes to equations, results, or author details beyond the requested ones; page count compared to the stated limit.

## Report

- Modified files (exact paths); locked files with before/after hashes.
- Build route (latexmk or manual), working directory, command, exit status, output path, engine, and pass count.
- Warnings: fixed vs remaining, with exact log text.
- Citation evidence table: key | verdict | source (DOI or URL) | fields checked | claim support.
- Visual pages checked, and anything not run with its missing prerequisite.
