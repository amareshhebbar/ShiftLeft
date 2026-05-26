#!/usr/bin/env python3
"""
scripts/benchmark.py — ShiftLeft Benchmark Runner

Runs the full ShiftLeft pipeline against one or more GitLab repositories
and measures every meaningful metric: triage accuracy, first-attempt pass
rate, time to MR, token usage, and USD cost.

Results are saved to:
  .benchmarks/<timestamp>.json   (raw — never overwritten)
  BENCHMARKS.md                  (formatted — always updated to latest)

Usage
-----
  # Run against the default test repo  (creates a real MR)
  python scripts/benchmark.py

  # Dry run — no branch or MR created
  python scripts/benchmark.py --dry-run

  # Single repo
  python scripts/benchmark.py --repo youruser/yourrepo

  # Multiple repos from a YAML config
  python scripts/benchmark.py --config scripts/benchmark_repos.yaml

  # Write results without running anything (uses last .benchmarks/*.json)
  python scripts/benchmark.py --from-last

  # Write sample BENCHMARKS.md using the known python-gitlab result only
  python scripts/benchmark.py --sample

Environment
-----------
  GITLAB_TOKEN, GCP_PROJECT_ID, GITLAB_TARGET_PROJECT  (see .env.example)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env before any ShiftLeft import
_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))

# ── Pricing (Gemini 2.0 Flash, Vertex AI — May 2026) ─────────────────────────
# https://cloud.google.com/vertex-ai/generative-ai/pricing
INPUT_COST_PER_1K  = 0.000075   # $0.075 / 1M input tokens
OUTPUT_COST_PER_1K = 0.000300   # $0.300 / 1M output tokens

# ── Default repos ─────────────────────────────────────────────────────────────
DEFAULT_REPOS = [
    {
        "project":        "amareshhebbar/python-gitlab-forktesting",
        "description":    "python-gitlab — HTTP 429 retry logic",
        "expected_file":  "gitlab/_backends/requests_backend.py",
        "expected_topic": "retry",
    },
]

# ── Known result for --sample mode ───────────────────────────────────────────
SAMPLE_RESULTS = [
    {
        "project":        "amareshhebbar/python-gitlab-forktesting",
        "description":    "python-gitlab — HTTP 429 retry logic",
        "run_id":         "2026-05-17_032851",
        "elapsed_s":      58.3,
        "files_mapped":   32,
        "issues_found":   3,
        "target_file":    "gitlab/_backends/requests_backend.py",
        "severity":       "high",
        "issue_summary":  "Missing retry logic for HTTP 429 rate limit responses in RequestsBackend",
        "triage_correct": True,
        "iterations":     1,
        "first_attempt":  True,
        "tests_passed":   True,
        "mr_url":         "https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2",
        "input_tokens":   12441,
        "output_tokens":  1043,
        "cost_usd":       0.0012,
        "success":        True,
        "error":          None,
        "diff_lines_added":    12,
        "diff_lines_removed":  0,
        "model":          "gemini-3.1-pro-preview",
        "backend":        "Vertex AI",
    },
]


# ── Result class ──────────────────────────────────────────────────────────────

class BenchmarkResult:
    def __init__(self, project: str, description: str):
        self.project        = project
        self.description    = description
        self.run_id         = ""
        self.started_at     = 0.0
        self.finished_at    = 0.0
        self.files_mapped   = 0
        self.issues_found   = 0
        self.target_file    = ""
        self.severity       = ""
        self.issue_summary  = ""
        self.triage_correct: Optional[bool] = None
        self.iterations     = 0
        self.tests_passed   = False
        self.mr_url         = ""
        self.error: Optional[str] = None
        self.input_tokens   = 0
        self.output_tokens  = 0
        self.diff_added     = 0
        self.diff_removed   = 0
        self.model          = ""
        self.backend        = ""

    @property
    def elapsed(self) -> float:
        return self.finished_at - self.started_at

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens  / 1000 * INPUT_COST_PER_1K
            + self.output_tokens / 1000 * OUTPUT_COST_PER_1K
        )

    @property
    def success(self) -> bool:
        return bool(self.mr_url) and not self.error

    def to_dict(self) -> dict:
        return {
            "project":          self.project,
            "description":      self.description,
            "run_id":           self.run_id,
            "elapsed_s":        round(self.elapsed, 1),
            "files_mapped":     self.files_mapped,
            "issues_found":     self.issues_found,
            "target_file":      self.target_file,
            "severity":         self.severity,
            "issue_summary":    self.issue_summary,
            "triage_correct":   self.triage_correct,
            "iterations":       self.iterations,
            "first_attempt":    self.iterations <= 1,
            "tests_passed":     self.tests_passed,
            "mr_url":           self.mr_url,
            "input_tokens":     self.input_tokens,
            "output_tokens":    self.output_tokens,
            "diff_lines_added": self.diff_added,
            "diff_lines_removed": self.diff_removed,
            "cost_usd":         round(self.cost_usd, 4),
            "success":          self.success,
            "error":            self.error,
            "model":            self.model,
            "backend":          self.backend,
        }


# ── Token counter (monkey-patches utils.llm.generate) ────────────────────────

class _TokenCounter:
    def __init__(self):
        self.input_tokens  = 0
        self.output_tokens = 0
        self._orig         = None
        self._model        = ""
        self._backend      = ""

    def __enter__(self):
        import utils.llm as llm_module
        self._orig = llm_module.generate
        info = llm_module.backend_info()
        self._model   = info.get("model", "")
        self._backend = info.get("backend", "")
        counter = self

        def _patched(prompt, temperature=0.1, max_tokens=16384, model_override=None):
            result = counter._orig(prompt, temperature, max_tokens, model_override)
            counter.input_tokens  += max(1, len(prompt) // 4)
            counter.output_tokens += max(1, len(result) // 4)
            return result

        llm_module.generate = _patched
        return self

    def __exit__(self, *_):
        import utils.llm as llm_module
        if self._orig:
            llm_module.generate = self._orig


# ── Single benchmark run ──────────────────────────────────────────────────────

def run_one(
    project: str,
    description: str,
    expected_file: Optional[str] = None,
    expected_topic: Optional[str] = None,
    dry_run: bool = False,
    index: int = 1,
    total: int = 1,
) -> BenchmarkResult:

    result = BenchmarkResult(project=project, description=description)
    result.started_at = time.monotonic()

    _hr = "─" * 64
    print(f"\n{_hr}")
    print(f"  [{index}/{total}] {project}")
    print(f"  {description}")
    if dry_run:
        print("  MODE: dry run (no branch/MR)")
    print(_hr)

    try:
        from core.graph import shiftleft_app
        from core.state import ShiftLeftState

        run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        result.run_id = run_id

        initial: ShiftLeftState = {
            "run_id":            run_id,
            "repo_url":          f"https://gitlab.com/{project}",
            "trigger_source":    "benchmark",
            "gitlab_project_id": project,
            "open_issues":       [],
            "branch_name":       f"shiftleft/bench-{run_id}",
            "file_map":          {},
            "yaml_map":          {},
            "repo_local_path":   "",
            "issue_summary":     "",
            "target_files":      [],
            "severity":          "medium",
            "patches":           [],
            "iteration":         0,
            "test_results":      "",
            "tests_passed":      False,
            "pr_url":            "",
            "pr_number":         0,
            "diff_hunks":        [],
            "changed_files":     [],
        }

        # Dry-run: skip branch/MR
        if dry_run:
            import agents.hitl as hitl_mod
            _orig_hitl = hitl_mod.hitl
            def _dry_hitl(state):
                print("  [dry-run] skipping branch/commit/MR")
                patches = state.get("patches") or []
                return {
                    **state,
                    "pr_url":        f"DRY_RUN//{run_id}",
                    "pr_number":     0,
                    "changed_files": [p["file_path"] for p in patches],
                    "diff_hunks":    [],
                }
            hitl_mod.hitl = _dry_hitl

        with _TokenCounter() as tc:
            final = shiftleft_app.invoke(initial)

        if dry_run:
            hitl_mod.hitl = _orig_hitl

        result.finished_at   = time.monotonic()
        result.files_mapped  = len(final.get("file_map") or {})
        result.issues_found  = len(final.get("open_issues") or [])
        result.target_file   = ((final.get("target_files") or ["?"])[0])
        result.severity      = final.get("severity", "")
        result.issue_summary = final.get("issue_summary", "")
        result.iterations    = final.get("iteration", 1)
        result.tests_passed  = bool(final.get("tests_passed"))
        result.mr_url        = final.get("pr_url", "")
        result.input_tokens  = tc.input_tokens
        result.output_tokens = tc.output_tokens
        result.model         = tc._model
        result.backend       = tc._backend

        # Count diff lines
        for patch in (final.get("patches") or []):
            diff = patch.get("diff", "")
            result.diff_added   += sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
            result.diff_removed += sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))

        # Triage accuracy
        if expected_file:
            result.triage_correct = (
                result.target_file == expected_file
                or result.target_file.endswith(expected_file.split("/")[-1])
            )
        elif expected_topic:
            result.triage_correct = expected_topic.lower() in result.issue_summary.lower()

        t = "✅" if result.triage_correct else ("❓" if result.triage_correct is None else "❌")
        a = "✅" if result.iterations <= 1 else f"⚠️ attempt {result.iterations}"
        s = "✅" if result.tests_passed else "⚠️"

        print(f"  {'✅' if result.success else '❌'}  {'SUCCESS' if result.success else 'FAILED'}  {result.elapsed:.1f}s")
        print(f"  {t}  Triage: {result.target_file}")
        print(f"  {a}  Auditor: {'PASS' if result.tests_passed else 'FAIL'}")
        print(f"  💰  ${result.cost_usd:.4f}  ({result.input_tokens:,} in / {result.output_tokens:,} out tokens)")
        if result.mr_url and not dry_run:
            print(f"  🔗  {result.mr_url}")

    except Exception as exc:
        result.finished_at = time.monotonic()
        result.error = str(exc)
        print(f"  ❌  ERROR: {exc}")
        import traceback; traceback.print_exc()

    return result


# ── Markdown generator ────────────────────────────────────────────────────────

def _row(r: dict) -> str:
    """Format one result dict as a markdown table row."""
    triage  = "✅" if r.get("triage_correct") else ("❓" if r.get("triage_correct") is None else "❌")
    attempt = "✅ 1st" if r.get("first_attempt") else f"⚠️ {r.get('iterations','?')}nd"
    tests   = "✅ PASS" if r.get("tests_passed") else "⚠️ SKIP"
    mr      = f"[MR]({r['mr_url']})" if r.get("mr_url") and not str(r.get("mr_url","")).startswith("DRY") else "dry-run"
    added   = r.get("diff_lines_added", "?")
    removed = r.get("diff_lines_removed", "?")
    err     = f" ❌ `{str(r.get('error',''))[:35]}`" if r.get("error") else ""
    target  = r.get("target_file","?").split("/")[-1]

    return (
        f"| `{r['project'].split('/')[-1]}` "
        f"| {r.get('files_mapped','?')} "
        f"| {r.get('issues_found','?')} "
        f"| {triage} `{target}`{err} "
        f"| {attempt} "
        f"| {tests} "
        f"| +{added} / -{removed} "
        f"| {r.get('elapsed_s','?')}s "
        f"| ${r.get('cost_usd', 0):.4f} "
        f"| {mr} |"
    )


def generate_markdown(results: list[dict], meta: dict) -> str:
    ts      = meta.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    backend = meta.get("backend", "Vertex AI")
    model   = meta.get("model", "gemini-3.1-pro-preview")
    n       = len(results)

    succeeded   = sum(1 for r in results if r.get("success"))
    triage_ok   = sum(1 for r in results if r.get("triage_correct"))
    triage_n    = sum(1 for r in results if r.get("triage_correct") is not None)
    first_pass  = sum(1 for r in results if r.get("first_attempt") and r.get("success"))
    avg_time    = round(sum(r.get("elapsed_s", 0) for r in results) / n, 1) if n else 0
    total_cost  = sum(r.get("cost_usd", 0) for r in results)
    total_in    = sum(r.get("input_tokens", 0) for r in results)
    total_out   = sum(r.get("output_tokens", 0) for r in results)

    lines = [
        "# ShiftLeft — Benchmark Results",
        "",
        "> Auto-generated by `python scripts/benchmark.py`.  ",
        f"> Last updated: **{ts}**  ",
        f"> LLM: **{backend}** · `{model}`  ",
        f"> Pricing: $0.075/1M input · $0.30/1M output (Gemini 2.0 Flash, Vertex AI)",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Runs | {n} |",
        f"| MR success rate | **{succeeded}/{n}** ({100*succeeded//n if n else 0}%) |",
        f"| Triage accuracy | **{triage_ok}/{triage_n}** ({100*triage_ok//triage_n if triage_n else 0}%) — correct file targeted |",
        f"| 1st-attempt syntax pass | **{first_pass}/{succeeded}** ({100*first_pass//succeeded if succeeded else 0}%) |",
        f"| Average time to MR | **{avg_time}s** |",
        f"| Total tokens used | {total_in:,} input + {total_out:,} output |",
        f"| Total cost | **${total_cost:.4f}** — avg **${total_cost/n:.4f}** per run |",
        "",
        "---",
        "",
        "## Per-Repository Results",
        "",
        "| Repo | Files | Issues | Triage | 1st attempt | Tests | Diff | Time | Cost | MR |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for r in results:
        lines.append(_row(r))

    lines += [
        "",
        "---",
        "",
        "## How to Regenerate",
        "",
        "```bash",
        "# Dry run (no MRs created)",
        "python scripts/benchmark.py --dry-run",
        "",
        "# Full run against default repo (creates a real MR)",
        "python scripts/benchmark.py",
        "",
        "# Multiple repos",
        "python scripts/benchmark.py --config scripts/benchmark_repos.yaml",
        "",
        "# Regenerate from last saved JSON (no pipeline run)",
        "python scripts/benchmark.py --from-last",
        "```",
        "",
        "Raw JSON results are saved to `.benchmarks/<timestamp>.json` and never overwritten.",
        "",
        "---",
        "",
        "## Detailed Results",
        "",
    ]

    for r in results:
        lines += [
            f"### `{r['project']}`",
            "",
            f"**{r.get('description', '')}**  ",
            f"Run ID: `{r.get('run_id', '?')}`",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Target file | `{r.get('target_file','?')}` |",
            f"| Severity | `{r.get('severity','?')}` |",
            f"| Issue summary | {r.get('issue_summary','?')} |",
            f"| Triage correct | {'✅ Yes' if r.get('triage_correct') else '❓ Unknown' if r.get('triage_correct') is None else '❌ No'} |",
            f"| Auditor iterations | {r.get('iterations', '?')} |",
            f"| Tests passed | {'✅ Yes' if r.get('tests_passed') else '❌ No'} |",
            f"| Diff | +{r.get('diff_lines_added','?')} / -{r.get('diff_lines_removed','?')} lines |",
            f"| Time | {r.get('elapsed_s','?')}s |",
            f"| Input tokens | {r.get('input_tokens',0):,} |",
            f"| Output tokens | {r.get('output_tokens',0):,} |",
            f"| Cost | ${r.get('cost_usd',0):.4f} |",
            f"| LLM backend | {r.get('backend','?')} · `{r.get('model','?')}` |",
        ]
        if r.get("mr_url") and not str(r.get("mr_url","")).startswith("DRY"):
            lines.append(f"| MR | [{r['mr_url']}]({r['mr_url']}) |")
        if r.get("error"):
            lines.append(f"| Error | `{r['error']}` |")
        lines.append("")

    return "\n".join(lines)


# ── Save helpers ──────────────────────────────────────────────────────────────

def _save_json(results: list[dict]) -> Path:
    out_dir = ROOT / ".benchmarks"
    out_dir.mkdir(exist_ok=True)
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    path = out_dir / f"{ts}.json"
    path.write_text(json.dumps(results, indent=2))
    return path


def _last_json() -> list[dict]:
    bdir = ROOT / ".benchmarks"
    if not bdir.exists():
        return []
    files = sorted(bdir.glob("*.json"), reverse=True)
    if not files:
        return []
    print(f"  Loading: {files[0]}")
    return json.loads(files[0].read_text())


def _write_markdown(results: list[dict], meta: dict) -> Path:
    md   = generate_markdown(results, meta)
    path = ROOT / "BENCHMARKS.md"
    path.write_text(md)
    return path


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ShiftLeft Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/benchmark.py                    # run default repo
  python scripts/benchmark.py --dry-run          # no MRs created
  python scripts/benchmark.py --repo user/repo   # single repo
  python scripts/benchmark.py --from-last        # regenerate from last JSON
  python scripts/benchmark.py --sample           # write sample BENCHMARKS.md
        """,
    )
    parser.add_argument("--repo",      help="Single GitLab project (user/repo)")
    parser.add_argument("--config",    help="YAML file with list of repos")
    parser.add_argument("--dry-run",   action="store_true", help="No branch/MR created")
    parser.add_argument("--from-last", action="store_true", help="Regenerate BENCHMARKS.md from last JSON")
    parser.add_argument("--sample",    action="store_true", help="Write BENCHMARKS.md from built-in sample data")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  ShiftLeft Benchmark Runner")
    print("=" * 64)

    # ── Sample mode ───────────────────────────────────────────────
    if args.sample:
        print("  MODE: sample — writing BENCHMARKS.md from built-in data")
        meta = {
            "timestamp": "2026-05-17 03:29 UTC (sample)",
            "backend":   "Vertex AI",
            "model":     "gemini-3.1-pro-preview",
        }
        path = _write_markdown(SAMPLE_RESULTS, meta)
        print(f"\n📄  BENCHMARKS.md written ({path})")
        return

    # ── From-last mode ────────────────────────────────────────────
    if args.from_last:
        print("  MODE: from-last — regenerating BENCHMARKS.md from last JSON")
        results = _last_json()
        if not results:
            print("  No .benchmarks/*.json found. Run a benchmark first.")
            sys.exit(1)
        meta = {"timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
        path = _write_markdown(results, meta)
        print(f"\n📄  BENCHMARKS.md updated ({path})")
        return

    # ── Live run ──────────────────────────────────────────────────
    from utils.llm import backend_info
    info = backend_info()
    print(f"  LLM: {info['backend']} · {info['model']} · {info.get('project','N/A')}")
    if args.dry_run:
        print("  MODE: dry run — no branches or MRs will be created")

    if args.repo:
        repos = [{"project": args.repo, "description": f"ad-hoc: {args.repo}"}]
    elif args.config:
        repos = yaml.safe_load(Path(args.config).read_text())
        print(f"  Config: {args.config} ({len(repos)} repo(s))")
    else:
        repos = DEFAULT_REPOS
        print(f"  Using default suite ({len(repos)} repo(s))")

    results_objs = []
    total_start  = time.monotonic()

    for i, cfg in enumerate(repos, 1):
        r = run_one(
            project       = cfg["project"],
            description   = cfg.get("description", cfg["project"]),
            expected_file = cfg.get("expected_file"),
            expected_topic= cfg.get("expected_topic"),
            dry_run       = args.dry_run,
            index         = i,
            total         = len(repos),
        )
        results_objs.append(r)

    total_elapsed = time.monotonic() - total_start
    results_dicts = [r.to_dict() for r in results_objs]

    # Save raw JSON
    json_path = _save_json(results_dicts)
    print(f"\n📁  JSON: {json_path}")

    # Summary
    n           = len(results_objs)
    succeeded   = sum(1 for r in results_objs if r.success)
    triage_ok   = sum(1 for r in results_objs if r.triage_correct)
    triage_n    = sum(1 for r in results_objs if r.triage_correct is not None)
    first_pass  = sum(1 for r in results_objs if r.iterations <= 1 and r.success)
    avg_time    = sum(r.elapsed for r in results_objs) / n if n else 0
    total_cost  = sum(r.cost_usd for r in results_objs)

    print(f"\n{'='*64}")
    print(f"  RESULTS")
    print(f"{'='*64}")
    print(f"  Total wall time : {total_elapsed:.0f}s")
    print(f"  MR success rate : {succeeded}/{n}")
    if triage_n:
        print(f"  Triage accuracy : {triage_ok}/{triage_n} ({100*triage_ok//triage_n}%)")
    print(f"  1st-attempt pass: {first_pass}/{succeeded}")
    print(f"  Avg time / MR   : {avg_time:.0f}s")
    print(f"  Total cost      : ${total_cost:.4f}  (avg ${total_cost/n:.4f}/run)")
    print(f"{'='*64}")

    # Write BENCHMARKS.md
    meta = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "backend":   info.get("backend", "?"),
        "model":     info.get("model", "?"),
    }
    md_path = _write_markdown(results_dicts, meta)
    print(f"\n📄  BENCHMARKS.md updated ({md_path})")

    if succeeded < n:
        print(f"\n⚠️  {n - succeeded} run(s) failed.")
        sys.exit(1)
    print("✅  All runs succeeded.")


if __name__ == "__main__":
    main()