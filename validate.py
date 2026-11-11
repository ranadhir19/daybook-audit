#!/usr/bin/env python3
"""Validation harness for dayshift.

Stages (each reported PASS/FAIL; the run fails if any stage fails):
  1. compile check of every Python file in the repo;
  2. unit tests (gate near-miss battery, receipt semantics, engine
     invariants: quiet fleet violates nothing, governed never orphans,
     the residual refund escapes even governed — by design);
  3. reproduction: run_day.py is re-run into a temp directory and
     results.json + RESULTS.md must come back byte-identical — the
     numbers in the README are the numbers the code produces;
  4. data integrity: the sample company is coherent (every priced
     product has an SLA; claims lists non-empty; profiles in [0, 1]);
  5. reference-integrity scan of the exact repo content (the
     portfolio pre-push gate; the scanner lives outside this repo);
  6. banned-name check: the forbidden portfolio name appears nowhere.

Run: python3 validate.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
# The scanner path is assembled at runtime (portfolio convention)
# so this file never carries a self-matching literal for stage 5.
SCANNER = (Path.home() / "workspace" / "github-fis-watch"
           / ("fis" + "_scan.py"))


def stage(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    ok = True

    # 1. compile
    r = subprocess.run(
        [sys.executable, "-m", "compileall", "-q",
         str(ROOT / "dayshift"), str(ROOT / "run_day.py"),
         str(ROOT / "tests"), str(ROOT / "examples" / "trace_day.py")],
        capture_output=True, text=True)
    ok &= stage("compile", r.returncode == 0, r.stderr.strip()[:200])

    # 2. unit tests
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s",
         str(ROOT / "tests")],
        capture_output=True, text=True, cwd=ROOT)
    ok &= stage("unit tests", r.returncode == 0,
                r.stderr.strip().splitlines()[-1][:120]
                if r.stderr.strip() else "")

    # 3. reproduction (byte-identical)
    with tempfile.TemporaryDirectory() as td:
        out_json = Path(td) / "results.json"
        out_md = Path(td) / "RESULTS.md"
        r = subprocess.run(
            [sys.executable, str(ROOT / "run_day.py"),
             "--out-json", str(out_json), "--out-md", str(out_md)],
            capture_output=True, text=True, cwd=ROOT)
        same = (r.returncode == 0
                and out_json.read_bytes() == (ROOT / "results.json").read_bytes()
                and out_md.read_bytes() == (ROOT / "RESULTS.md").read_bytes())
    ok &= stage("reproduction", same,
                "results regenerate byte-identically" if same else "DRIFT")

    # 4. data integrity
    try:
        from dayshift.company import Company
        company = Company.from_json(ROOT / "examples" / "company.json")
        facts = company.facts
        coherent = (
            set(facts.prices) == set(facts.sla_days)
            and facts.approved_claims and company.unapproved_claims
            and all(0.0 <= v <= 1.0 for v in vars(company.profiles).values())
            and facts.max_discount_pct > 0 and facts.refund_window_days > 0)
        results = json.loads((ROOT / "results.json").read_text())
        coherent &= (results["naive"]["items"] == results["governed"]["items"]
                     and results["governed"]["violations_escaped"]
                     == results["governed"]["residual_violations"])
        detail = "company coherent; governed escapes are all residual"
    except Exception as exc:  # noqa: BLE001
        coherent, detail = False, str(exc)[:160]
    ok &= stage("data integrity", coherent, detail)

    # 5. reference-integrity scan (portfolio pre-push gate)
    if SCANNER.exists():
        r = subprocess.run(
            [sys.executable, str(SCANNER), str(ROOT)],
            capture_output=True, text=True)
        scan_ok = r.returncode == 0
        ok &= stage("reference-integrity scan", scan_ok,
                    r.stdout.strip().splitlines()[-1][:160]
                    if r.stdout.strip() else r.stderr.strip()[:160])
    else:
        ok &= stage("reference-integrity scan", False, "scanner not found")

    # 6. banned-name check (assembled at runtime; never a literal here)
    banned = "Dev" + "Pulse"
    hits = [str(p) for p in ROOT.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
            and p.suffix in {".py", ".md", ".toml", ".json"}
            and banned in p.read_text(errors="ignore")]
    ok &= stage("banned-name check", not hits,
                f"hits: {hits}" if hits else "absent everywhere")

    print("OVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
