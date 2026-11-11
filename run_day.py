#!/usr/bin/env python3
"""Run the dayshift audit experiment.

Simulates DAYS seeded business days for the sample company in both
modes (naive fleet / governed fleet) over identical generated work,
and writes results.json + RESULTS.md. Fully deterministic: the same
command always produces byte-identical outputs.

Usage: python3 run_day.py [--days 20] [--company examples/company.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dayshift import audit as audit_mod  # noqa: E402
from dayshift import engine  # noqa: E402
from dayshift.company import Company  # noqa: E402

BASE_SEED = 20261110


def run(company: Company, days: int) -> dict:
    per_mode = {}
    for mode in (engine.NAIVE, engine.GOVERNED):
        results = []
        for d in range(days):
            day_seed = BASE_SEED + d
            items = engine.generate_day(company, day_seed)
            results.append(engine.simulate_day(company, items, mode, day_seed))
        per_mode[mode] = audit_mod.audit(results)
    return {
        "company": company.name,
        "days": days,
        "base_seed": BASE_SEED,
        "profiles": {
            "edge_field_loss": company.profiles.edge_field_loss,
            "intake_miss": company.profiles.intake_miss,
            "over_discount": company.profiles.over_discount,
            "short_promise": company.profiles.short_promise,
            "unapproved_claim": company.profiles.unapproved_claim,
            "lax_refund": company.profiles.lax_refund,
            "invoice_slip": company.profiles.invoice_slip,
            "misroute": company.profiles.misroute,
            "drop": company.profiles.drop,
        },
        "naive": per_mode[engine.NAIVE],
        "governed": per_mode[engine.GOVERNED],
        "comparison": audit_mod.compare(per_mode[engine.NAIVE],
                                        per_mode[engine.GOVERNED]),
    }


def render_md(r: dict) -> str:
    n, g = r["naive"], r["governed"]
    lines = [
        "# dayshift — measured results",
        "",
        f"Company: {r['company']}  ",
        f"Days simulated per mode: {r['days']} (base seed {r['base_seed']}; "
        "identical generated work and per-item error draws in both modes)",
        "",
        "| Metric | Naive fleet | Governed fleet |",
        "|---|---|---|",
        f"| Work items | {n['items']} | {g['items']} |",
        f"| Completed | {n['status']['completed']} | {g['status']['completed']} |",
        f"| Incomplete (failed visibly) | {n['status']['incomplete']} | {g['status']['incomplete']} |",
        f"| Orphaned (vanished silently) | {n['status']['orphaned']} | {g['status']['orphaned']} |",
        f"| Commitments attempted | {n['commitments_attempted']} | {g['commitments_attempted']} |",
        f"| **Violations that reached a customer** | **{n['violations_escaped']}** | **{g['violations_escaped']}** |",
        f"| Escape rate per 100 commitments | {n['escape_rate_per_100']} | {g['escape_rate_per_100']} |",
        f"| Residual escapes (never-captured field) | {n['residual_violations']} | {g['residual_violations']} |",
        f"| Violations corrected at the gate | 0 (no gate) | {g['gate_corrected_total']} |",
        f"| Required-field survival at handoffs | {n['field_survival_final']:.2%} | {g['field_survival_final']:.2%} |",
        f"| Receipt recoveries | 0 | {g['receipt_recoveries']} |",
        f"| Handoffs | {n['handoffs']} | {g['handoffs']} |",
        f"| Misroute detours | {n['detours']} | {g['detours']} |",
        f"| Conductor interventions | {n['conductor_interventions']} | {g['conductor_interventions']} |",
        "",
        "Escaped violations by class (naive → governed):",
        "",
    ]
    classes = sorted(set(n["violations_by_class"]) | set(g["violations_by_class"]))
    for cls in classes:
        lines.append(f"- {cls}: {n['violations_by_class'].get(cls, 0)} → "
                     f"{g['violations_by_class'].get(cls, 0)}")
    lines += [
        "",
        "Gate corrections by class (governed): "
        + (", ".join(f"{k} {v}" for k, v in sorted(g["gate_corrected"].items()))
           or "none"),
        "",
        "Reading: governance removes the checkable escapes. What remains in the",
        "governed column is the residual class — commitments built on a field",
        "that was never captured at intake, validated against the same default",
        "the agent used. No fact check catches those; only better intake does.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=20)
    ap.add_argument("--company", default=str(ROOT / "examples" / "company.json"))
    ap.add_argument("--out-json", default=str(ROOT / "results.json"))
    ap.add_argument("--out-md", default=str(ROOT / "RESULTS.md"))
    args = ap.parse_args()

    company = Company.from_json(args.company)
    results = run(company, args.days)
    Path(args.out_json).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    Path(args.out_md).write_text(render_md(results))
    n, g = results["naive"], results["governed"]
    print(f"items={n['items']}  escapes naive={n['violations_escaped']} "
          f"governed={g['violations_escaped']}  "
          f"orphans naive={n['status']['orphaned']} governed={g['status']['orphaned']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
