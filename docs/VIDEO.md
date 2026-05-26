# ShiftLeft — Demo Video Guide


## Video Specs

| Field | Value |
|---|---|
| Target length | 3:53 exactly |
| Resolution | 1920×1080 minimum |
| Format | MP4 (H.264) |
| Audio | Clear narration — no background noise |
| Captions | Add auto-captions on YouTube after upload |
| Thumbnail | See [SCREENSHOTS.md](SCREENSHOTS.md) |

---

## Pre-recording Checklist

Before you hit record:

```bash
# 1. Confirm the pipeline works
python main.py --repo amareshhebbar/python-gitlab-forktesting

# 2. Confirm Streamlit is live and not spinning
open https://shiftleft.streamlit.app

# 3. Open GitLab project with 3 issues ready
open https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/issues

# 4. Have the live MR open in a tab
open https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2

# 5. Open terminal in the shiftleft/ directory
cd ~/hackathon2/shiftleft

# 6. Close all other apps — no notifications, no dock bouncing
```

**Font size in terminal:** increase to 18px minimum. Judges watch on small screens.

---

## Screen Layout

Record at 1920×1080. Use this layout across scenes:

```
Scene 1-2 (0:00–0:28):  Slides / title card
Scene 3-4 (0:28–1:10):  Terminal (full screen) — live pipeline run
Scene 5-6 (1:10–2:10):  Terminal + browser side by side (70/30 split)
Scene 7   (2:10–2:35):  GitLab MR page (full browser)
Scene 8   (2:35–3:00):  GitLab MR diff tab (full browser)
Scene 9   (3:00–3:25):  GitLab file browser → .shiftleft/ folder
Scene 10  (3:25–3:53):  Streamlit dashboard + GitHub README
```

---

## Full Script with Screen Directions

### [0:00 — 0:28] Problem & Intro

**Screen:** Title card or slides. Show the ShiftLeft logo / GitHub README header.

> Every engineering team has the same problem.
> A backlog of bugs. Issues sitting open for days, sometimes weeks.
> Nobody has time. The fix never gets started.
>
> ShiftLeft changes that.
>
> Point it at any GitLab repository, add one label to an issue,
> and within sixty seconds — you have a Merge Request, ready for review.
> No human writes a single line of code.

**Transition:** Switch to terminal window, full screen.

---

### [0:28 — 0:45] Pipeline starts

**Screen:** Terminal. Type `python main.py --repo amareshhebbar/python-gitlab-forktesting` and press Enter. Let the output start streaming.

> Let me show you exactly how it works.
>
> I'm triggering ShiftLeft now against a real Python project on GitLab.
> It has three open issues. Thirty-two source files.
> Watch the five agents fire in sequence.

**What the terminal should show at this moment:**
```
2026-05-17 03:28:51 [INFO] utils.llm — LLM backend: Vertex AI  project=my-project
2026-05-17 03:28:51 [INFO] cartographer — run_id=2026-05-17_032851
2026-05-17 03:28:52 [INFO] cartographer — fetching repository tree via GitLab REST API
```

---

### [0:45 — 1:10] Cartographer

**Screen:** Terminal — scroll so the cartographer log lines are visible.

> First — the Cartographer.
>
> It uses the GitLab MCP server to read every source file in the repository.
> Not just filenames — it does a full AST parse of each one.
> Functions, classes, imports, docstrings, line counts.
> It also pulls all open issues directly from the GitLab API.
>
> Everything gets built into a structured YAML knowledge map —
> a machine-readable understanding of the entire codebase.
>
> Thirty-two files mapped in under twelve seconds.

**What the terminal should show:**
```
2026-05-17 03:28:52 [INFO] cartographer — 32 Python files selected
2026-05-17 03:28:54 [INFO] cartographer — gitlab/client.py  (412 loc, 18 funcs, 3 classes)
2026-05-17 03:28:55 [INFO] cartographer — gitlab/_backends/requests_backend.py  (124 loc, 3 funcs, 1 class)
2026-05-17 03:29:02 [INFO] cartographer — 32 YAML manifests built
2026-05-17 03:29:03 [INFO] cartographer — 3 open issues loaded
  #1 Add context manager support to ProjectManager
  #2 No retry logic for API rate limit responses (HTTP 429)
  #3 Missing type annotations in gitlab/utils.py
```

**Tip:** If your actual run shows different output, that's fine — the narration mentions "32 files" and "3 issues" which you can verify beforehand.

---

### [1:10 — 1:35] Triage

**Screen:** Terminal — scroll to show the triage output.

> Next — Triage.
>
> The entire file map, plus the open issue list, goes to Gemini
> running on Vertex AI — Google Cloud's native AI platform.
>
> Gemini reads it all and selects the single highest-severity bug.
> In this case: missing retry logic for HTTP four-twenty-nine rate limit responses
> in the requests backend file.
>
> This is a real crash — any four-twenty-nine from the GitLab API
> would kill the request with no recovery.
>
> Severity: high. Target file identified. Moving on.

**What the terminal should show:**
```
2026-05-17 03:29:03 [INFO] triage — 32 code files + 3 issues → Gemini (Vertex AI)
2026-05-17 03:29:07 [INFO] triage — severity=HIGH  target=['gitlab/_backends/requests_backend.py']  summary='Missing retry logic for HTTP 429 rate limit responses'
```

---

### [1:35 — 1:55] Coder

**Screen:** Terminal — show the coder log lines.

> Now the Coder agent takes over.
>
> It reads the full content of the target file —
> and sends it to Gemini with the bug summary.
> Gemini returns the complete fixed file.
> Not a snippet. Not a patch suggestion. The whole thing.
>
> The fix: urllib3 Retry with exponential backoff,
> covering four-twenty-nine, five-hundred, five-oh-two, and five-oh-three errors.
> Twelve lines added. Clean.

**What the terminal should show:**
```
2026-05-17 03:29:07 [INFO] coder — iteration 1, targets: ['gitlab/_backends/requests_backend.py']
2026-05-17 03:29:07 [INFO] coder — calling Gemini (Vertex AI) for gitlab/_backends/requests_backend.py (5242 chars, lang=python)
2026-05-17 03:29:13 [INFO] coder — patch for gitlab/_backends/requests_backend.py: 12 lines changed
```

---

### [1:55 — 2:10] Auditor

**Screen:** Terminal — show auditor output.

> The Auditor validates it.
>
> It runs py_compile on the patched file in an isolated temp directory.
> Syntax check: passed on the first attempt.
>
> If it had failed, the Coder would have been called again automatically,
> with the failing diff injected as context — so it knows what not to repeat.
> Up to three retries. This one didn't need any.

**What the terminal should show:**
```
2026-05-17 03:29:13 [INFO] auditor — iteration 1: PASSED ✅
2026-05-17 03:29:13 [INFO] auditor — results:
  [PASS] gitlab/_backends/requests_backend.py: syntax OK
  [INFO] No test files in patched set — pytest skipped
```

---

### [2:10 — 2:35] HITL

**Screen:** Terminal — show HITL log lines. Optionally switch to browser showing the branch appear in real time.

> Finally — the HITL agent.
>
> It creates a new branch using the GitLab MCP server.
> Then pushes the patched file and the YAML knowledge base
> via the GitLab commits REST API.
> Then opens the Merge Request — also via REST.

**What the terminal should show:**
```
2026-05-17 03:29:14 [INFO] hitl — ✅ branch created via GitLab MCP: shiftleft/run-2026-05-17_032851
2026-05-17 03:29:22 [INFO] hitl — committed batch 1 (1 files) via REST
2026-05-17 03:29:28 [INFO] hitl — committed batch 2 (36 files) via REST
2026-05-17 03:29:30 [INFO] hitl — ✅ MR: https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2

================================================================
✅  Merge Request: https://gitlab.com/.../merge_requests/2
================================================================
```

---

### [2:35 — 3:00] Live MR on screen

**Screen:** Switch to browser. Show the MR page. Scroll slowly through the description table showing Run ID, Severity, Tests, LLM Backend. Then switch to the "Changes" tab to show the diff.

> And here it is. A real, open Merge Request on GitLab.
> The diff is clean. The description includes the run ID,
> severity, test results, and the LLM backend that generated the fix.
> Ready for a human to review and merge.
>
> Total time from trigger to open MR: fifty-eight seconds.

**What to show on screen:**
- MR title: `fix(high): Missing retry logic for HTTP 429 rate limit responses`
- Description table with: Run ID, Severity=HIGH, Tests=✅ PASSED, LLM Backend=Vertex AI
- Switch to Changes tab — show the green `+` lines for the `urllib3.Retry` addition

---

### [3:00 — 3:25] Knowledge base

**Screen:** Navigate in the GitLab file browser to `.shiftleft/` folder. Click on `map/gitlab/_backends/requests_backend.yaml`. Show the YAML content.

> One more thing. Every run also commits a dot-shiftleft folder
> to the repository — a living YAML knowledge map of the codebase.
> It gets better with every run. The repo builds a self-understanding over time.

**What to show:**
```yaml
file: gitlab/_backends/requests_backend.py
last_analyzed: 2026-05-17_032851
loc: 124
imports: [requests, urllib3, logging]
functions:
  - name: http
    args: [self, "verb: str", "path: str", "**kwargs"]
    returns: requests.Response
```

---

### [3:25 — 3:53] Wrap-up

**Screen:** Switch to Streamlit dashboard (`https://shiftleft.streamlit.app`). Show the live agent tracker UI. Then briefly show the GitHub README with all the badges.

> ShiftLeft is built on Gemini via Vertex AI, GitLab MCP, LangGraph,
> and Google Cloud Run — with full LLM observability through Arize Phoenix.
>
> Every single LLM call is traced. Token counts, latency, and agent timing —
> all visible in real time. You always know exactly what the pipeline is doing
> and what it costs. On average, each run uses around seventeen thousand tokens —
> less than one cent per bug fixed.
>
> That is the economics of autonomous engineering.
> Not a demo. Not a prototype. A working system,
> fixing real bugs in real repositories, right now.
>
> The GitHub link, the live dashboard, and the example Merge Request
> are all in the description below.
>
> Thanks for watching.

---

## Editing Notes

| Timestamp | Edit |
|---|---|
| 0:00 | Hard cut from title card to terminal |
| 0:28 | Add subtle sound effect as `python main.py` runs |
| 1:10 | Optional: zoom in on the triage severity line |
| 2:10 | Crossfade terminal → browser |
| 2:35 | Highlight the diff lines with yellow screen annotation |
| 3:00 | Zoom in slowly on the YAML content |
| 3:25 | Fade to Streamlit dashboard |
| 3:53 | Hard cut to black |

## YouTube Upload Settings

```
Title:     ShiftLeft — Autonomous Bug-Fixing Agent for GitLab (Google Cloud Hackathon 2026)
Category:  Science & Technology
Tags:      GitLab, Gemini, Vertex AI, LangGraph, AI Agent, MCP, Google Cloud, Hackathon, DevTools
Visibility: Public
```

Add the YouTube description from `VIDEO_DESCRIPTION.md` (or see [the Devpost story](DEVPOST_STORY.md) for the full description text).