# dayshift

**Your agent fleet runs the business all day. What did it promise your customers while you weren't looking?**

The current genre demo is a dashboard: a dozen agents staffed into
departments — sales, finance, marketing, support — a store of company
context underneath, and one conductor agent the founder talks to.
What the genre never ships is the audit. When work crosses
departments all day, three things quietly go wrong: commitments drift
away from the company's own facts (a discount past the cap, a delivery
promise faster than the SLA, a refund outside the window, a claim the
company never approved), handoffs lose the fields the next department
needed, and some work simply falls on the floor — silently.

dayshift is that audit, as a runnable simulation bench:

- A **fact store** holds the ground truth: prices, discount cap,
  refund window, delivery SLAs, approved claims.
- A **seeded business day** generates real work — orders, refunds,
  campaigns, tickets — that flows through the department fleet, with
  declared agent error profiles (over-discounting, short promises,
  invented claims, invoice slips, lost fields, misroutes).
- The same day runs under **two operating modes**: a *naive* fleet
  (agents act on whatever they're handed; commitments land as made)
  and a *governed* fleet (commitments checked against the fact store
  before they land, handoffs carry receipts that restore in-transit
  losses, lost items escalate to the conductor instead of vanishing).
- The **audit** reports, per mode: violations that reached a customer
  per 100 commitments, split into *checkable* and *residual* classes;
  required-field survival across handoffs; orphans vs visible
  failures; and conductor load.

Pure Python, standard library only, no API keys, no network. Every
number below reproduces byte-identically.

```bash
python3 run_day.py            # 20 seeded days x 2 modes -> results.json, RESULTS.md
python3 examples/trace_day.py --seed 7   # one narrated day, both modes
python3 validate.py           # harness: tests + reproduction + scans
```

## Measured results (20 days, 1,080 work items per mode)

| Metric | Naive fleet | Governed fleet |
|---|---|---|
| **Violations that reached a customer** | **289** | **22** |
| Escape rate per 100 commitments | 17.40 | 1.23 |
| Checkable escapes (discount / promise / claim / invoice-slip / lax refund) | 269 | **0** |
| Residual escapes (built on a never-captured field) | 20 | 22 |
| Commitments corrected at the gate before landing | — | 265 |
| Items orphaned (vanished silently) | 42 | 0 |
| Conductor interventions | 0 | 39 |
| Items failed visibly (incomplete) | 126 | 39 |
| Required-field survival at handoffs | 91.6% | 97.5% |
| Completion rate | 84.4% | 96.4% |

Full tables: [RESULTS.md](RESULTS.md). One narrated day:
[examples/sample_day.md](examples/sample_day.md).

## The finding that matters

Governance, as modelled here, is **complete against the checkable
classes and useless against the residual one** — and the audit can
prove both halves:

- Every escaped discount, promise, claim, invoice-slip and lax refund
  in the naive run (269) is gone in the governed run. A fact store
  plus a pre-commitment check is enough for the whole class.
- The residual escape rate **does not move**: 20 escapes in 1,661
  naive commitments (1.20 per 100) vs 22 in 1,794 governed commitments
  (1.23 per 100). These are commitments built on a field that was
  never captured at intake — support refunds a 45-day-old order
  because the age was never recorded and the default (10 days) looks
  fine to the checker too; finance invoices for quantity 1 because
  the real quantity never made it into the record. No gate catches
  them, because the gate reads the same record the agent did. The
  only fix is intake quality, and any fleet audit that doesn't split
  this class out will credit governance with more than it did.

Two honest asymmetries in the comparison: the governed fleet attempts
*more* commitments (1,794 vs 1,661) because more of its work survives
to make them — which is why the headline metric is a rate per 100
commitments, not a raw count; and the naive fleet's zero conductor
interventions is not efficiency, it is silence — its 42 lost items
were never surfaced to anyone.

## What this does not claim

- The agents are **scripted** with declared, seeded error rates, in
  the open (examples/company.json). The bench measures how much of a
  *declared* error load each operating mode lets reach a customer —
  an architectural property of the modes. It does not measure any
  real LLM's error rates, and the specific percentages would change
  with the profiles; the class split (checkable vs residual) is the
  result that is meant to survive re-profiling.
- The checker is deterministic code with perfect knowledge of the
  fact store. A learned or LLM-based checker would have its own error
  rate, which this bench does not model.
- One fictional company, four work-item types, five commitment
  classes. Real fleets have more of everything; the taxonomy is the
  contribution, not the census.

## Layout

```
dayshift/     fact store + profiles (company.py), the day engine
              (engine.py), governance (checkers.py), the audit (audit.py)
run_day.py    the experiment: N seeded days x 2 modes -> results.json + RESULTS.md
examples/     company.json (Fernbrook Supply Co., fictional), trace_day.py,
              sample_day.md (a real seed-7 day, narrated)
tests/        unit tests incl. the gate near-miss battery (at-cap discount,
              at-SLA promise, last-day refund must all pass untouched)
validate.py   compile + tests + byte-identical reproduction + scans
```

## License

MIT — see [LICENSE](LICENSE).
