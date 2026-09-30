---
name: lab
description: Take a college lab from handout to zipped submission — Python on the Colab runtime via colab-mcp, everything else locally — in the user's house style.
disable-model-invocation: true
---

Run the college lab whose handout arrives with this message (pasted text, or a PDF / `.md` in the lab directory) through to a zipped submission. Courses: DL, CV, AML, DS (distributed systems), DCCN. The house style below is the set of corrections the user otherwise sends after every lab, so it binds every step.

## House style

- **Place** — `~/Code/College/<Course>_College/<lab_dir>` (DCCN: `~/Code/College/DCCN_Lab`). A new `<lab_dir>` copies its siblings' naming (`DL_lab_6` beside `DL_lab_5`). Every file the lab produces stays inside it; file names follow the handout when it dictates them.
- **Notebook** — one `lab_N.ipynb`: a setup cell, then one decoupled code cell per task that runs on its own after setup. Code cells only; `## Task N` header cells when the user asks for them.
- **Code** — reads like a strong student's hand-in: direct, idiomatic, compact, no comments or docstrings. The single comment that belongs is a short note where the code deliberately departs from the handout. Anything the handout explicitly requires overrides this list.
- **Output** — cells print metrics and draw plots; interpretation lives only in `results.md`.
- **Follow-ups** — "improve X" / "add Y" becomes new cells appended at the bottom; existing cells stay exactly as they are. The architecture stays fixed when the user says so.
- **Existing results** — when the user already trained and downloaded outputs, every deliverable is built from those files.
- **Deadline** — when the user names a submission time, size epochs and data handling to fit it and state the ETA before any long run.
- **Shell** — prefix commands with `export _ZO_DOCTOR=0;`. There is no sudo: hand the user the exact command for anything that needs it.

## 1. Read the handout

Read the whole handout and extract the lab number, every task (numbered as the handout numbers them), the language, the dataset and its source, and any deliverables it names. Pick the path:

- **Colab** (step 2a) — Python whose work is computation: model training, CV, data analysis, numerical experiments.
- **Local** (step 2b) — C/C++, shell tools (`dig`, `nslookup`), and Python that must run as local processes or services (RabbitMQ producer/consumer, gRPC, Flask/OAuth on `localhost`, socket client/server).

The dataset comes from a Kaggle link in the handout, Google Drive at `/content/drive/MyDrive/DATASETS/<name>`, or a zip the user uploaded to `/content/<file>.zip`. Ask once when the handout leaves the source open.

Done when the lab dir exists and you have posted a short task list with the chosen path and dataset source.

## 2a. Colab path

1. **Connect** — run `ToolSearch` with query `select:mcp__colab-mcp__open_colab_browser_connection`, then call that tool; it opens a Colab tab. Tell the user: for a training lab, first set Runtime → Change runtime type → T4 GPU (the change restarts the session), then click **Connect** in the tab. Wait for their message that it is connected.
2. **Load notebook tools** — `ToolSearch` keyword search `colab`. Done when a first cell returns output: `!nvidia-smi` showing the T4 for GPU labs, `import sys; sys.version` otherwise.
3. **Data** — Drive datasets: `drive.mount('/content/drive')` (the user approves the popup) and read the files in place. Uploaded zips: unzip into `/content`. Kaggle links: `kagglehub.dataset_download`. Done when a cell prints the dataset's sample counts or shapes.
4. **Build** — add and run the notebook cell by cell in house style, fixing a failing cell in place before adding the next. Every figure is also saved with `plt.savefig` under `/content/results/`. Done when every task cell has run cleanly with its metrics and plots in the output.
5. **Bring it home** — write the same cells to `<lab_dir>/lab_N.ipynb`. Pull the executed notebook and `/content/results/` into the lab dir with a Colab tool when one can; otherwise zip `/content/results` and run `files.download` on it from `google.colab`, ask the user to download the notebook via File → Download → .ipynb, and move both from `~/Downloads`. Done when the executed notebook and every result image sit in the lab dir.

## 2b. Local path

1. **Toolchain** — `gcc`/`g++` for C/C++; for Python `uv venv` and `uv pip install -r requirements.txt` with `requirements.txt` in the lab dir; the handout's tools otherwise. Done when a trivial compile, import, or connection to each required service (e.g. the RabbitMQ broker) succeeds.
2. **Write** — one plainly named source file per program the handout defines (server/client, producer/consumer, one per technique), in house style.
3. **Run** — run every task on the handout's test inputs and save each run's terminal output under `results/`. Done when every task has a saved output showing it working.

## 3. Deliverables

1. `results.md` — the metrics table (or per-task outputs) plus a conclusion of three to five sentences.
2. `README.md` with run instructions only when the user or handout asks for one.
3. `lab_N.zip` in the lab dir holding the notebook or sources, result images and outputs, `results.md`, and `README.md` / `requirements.txt` when present; `.venv` and datasets stay out.

Done when `unzip -l lab_N.zip` lists every deliverable. Finish with a few lines for the user: each task's headline metric or result, and the zip path.
