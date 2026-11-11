#!/usr/bin/env python3
"""Print a narrated trace of one seeded day in each mode.

Used to author examples/sample_day.md from real incidents — every
line below comes out of the simulation, nothing is staged.

Usage: python3 examples/trace_day.py [--seed 7]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dayshift import engine  # noqa: E402
from dayshift.company import Company  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    company = Company.from_json(ROOT / "examples" / "company.json")
    items = engine.generate_day(company, args.seed)
    for mode in (engine.NAIVE, engine.GOVERNED):
        r = engine.simulate_day(company, items, mode, args.seed)
        print(f"===== {mode} (seed {args.seed}) =====")
        for it in r.items:
            marks = []
            for c in it.commitments:
                if c.violating:
                    marks.append(f"VIOLATION:{c.kind}"
                                 + ("(residual)" if c.residual else ""))
            print(f"#{it.item_id:<3} {it.kind:<9} {it.status:<11} "
                  f"commitments={len(it.commitments)} {' '.join(marks)}")
        print(f"gate corrected: {r.gate.corrected}  "
              f"recoveries: {r.gate.recoveries}  "
              f"interventions: {r.counters.interventions}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
