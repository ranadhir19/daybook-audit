"""Unit tests for dayshift — toy cases with known right answers.

Includes the near-miss battery: commitments exactly at the legal
boundary must pass the gate untouched (a checker that clamps legal
values is over-blocking, and the audit would be measuring the gate,
not the fleet).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dayshift import checkers, engine  # noqa: E402
from dayshift.company import AgentProfiles, Company, Facts  # noqa: E402

FACTS = Facts(
    prices={"mug": 24.0, "boots": 118.0},
    max_discount_pct=15.0,
    refund_window_days=30,
    sla_days={"mug": 3, "boots": 5},
    approved_claims=("two-year warranty included",),
)


def quiet_company(**overrides) -> Company:
    """A company whose agents never err — isolates mechanism from noise."""
    base = dict(edge_field_loss=0.0, intake_miss=0.0, over_discount=0.0,
                short_promise=0.0, unapproved_claim=0.0, lax_refund=0.0,
                invoice_slip=0.0, misroute=0.0, drop=0.0)
    base.update(overrides)
    return Company(name="toy", facts=FACTS, profiles=AgentProfiles(**base),
                   unapproved_claims=("guaranteed to arrive tomorrow",))


class TestGateNearMisses(unittest.TestCase):
    def setUp(self):
        self.gate = checkers.GateLog()

    def test_discount_exactly_at_cap_passes(self):
        self.assertEqual(checkers.check_discount(FACTS, 15.0, self.gate), 15.0)
        self.assertEqual(self.gate.total_corrected, 0)

    def test_discount_above_cap_clamped(self):
        self.assertEqual(checkers.check_discount(FACTS, 22.0, self.gate), 15.0)
        self.assertEqual(self.gate.corrected["discount"], 1)

    def test_promise_exactly_at_sla_passes(self):
        self.assertEqual(checkers.check_promise(FACTS, "boots", 5, self.gate), 5)
        self.assertEqual(self.gate.total_corrected, 0)

    def test_promise_below_sla_raised(self):
        self.assertEqual(checkers.check_promise(FACTS, "boots", 2, self.gate), 5)

    def test_refund_on_last_window_day_passes(self):
        self.assertTrue(checkers.check_refund(FACTS, 30, True, self.gate))
        self.assertEqual(self.gate.total_corrected, 0)

    def test_refund_one_day_past_window_blocked(self):
        self.assertFalse(checkers.check_refund(FACTS, 31, True, self.gate))

    def test_approved_claim_passes(self):
        claim = "two-year warranty included"
        self.assertEqual(checkers.check_claim(FACTS, claim, self.gate), claim)

    def test_invoice_exact_total_passes(self):
        expected = FACTS.expected_invoice("mug", 2, 10.0)
        self.assertEqual(
            checkers.check_invoice(FACTS, "mug", 2, 10.0, expected, self.gate),
            expected)
        self.assertEqual(self.gate.total_corrected, 0)


class TestReceipts(unittest.TestCase):
    def test_receipt_restores_transit_loss(self):
        gate = checkers.GateLog()
        fields = {"qty": 2}
        checkers.apply_receipt(fields, {"qty": 2, "product": "mug"},
                               ("product", "qty"), gate)
        self.assertEqual(fields["product"], "mug")
        self.assertEqual(gate.recoveries, 1)

    def test_receipt_cannot_restore_never_captured(self):
        gate = checkers.GateLog()
        fields = {}
        checkers.apply_receipt(fields, {}, ("product",), gate)
        self.assertNotIn("product", fields)
        self.assertEqual(gate.recoveries, 0)


class TestEngine(unittest.TestCase):
    def test_quiet_fleet_has_no_violations_in_either_mode(self):
        company = quiet_company()
        items = engine.generate_day(company, 99, n_orders=10, n_refunds=5,
                                    n_campaigns=3, n_tickets=5)
        for mode in (engine.NAIVE, engine.GOVERNED):
            result = engine.simulate_day(company, items, mode, 99)
            bad = [c for it in result.items for c in it.commitments if c.violating]
            self.assertEqual(bad, [], f"{mode} produced violations with zero error rates")
            self.assertTrue(all(it.status == "completed" for it in result.items))

    def test_reproducible_same_seed(self):
        company = Company.from_json(ROOT / "examples" / "company.json")
        items = engine.generate_day(company, 7)
        a = engine.simulate_day(company, items, engine.NAIVE, 7)
        b = engine.simulate_day(company, items, engine.NAIVE, 7)
        self.assertEqual(
            [(it.status, len(it.commitments)) for it in a.items],
            [(it.status, len(it.commitments)) for it in b.items])

    def test_governed_never_orphans(self):
        company = quiet_company(drop=0.5, edge_field_loss=0.0)
        items = engine.generate_day(company, 5, n_orders=20, n_refunds=0,
                                    n_campaigns=0, n_tickets=0)
        result = engine.simulate_day(company, items, engine.GOVERNED, 5)
        self.assertEqual(
            sum(1 for it in result.items if it.status == "orphaned"), 0)
        self.assertGreater(result.counters.interventions, 0)

    def test_residual_refund_escapes_even_governed(self):
        # Age never captured -> support defaults to 10 days -> a truly
        # 45-day-old order is refunded, and the checker sees age 10 too.
        company = quiet_company(intake_miss=1.0)
        item = engine.Item(item_id=0, kind="refund",
                           true_fields={"product": "mug", "order_age_days": 45,
                                        "amount": 24.0},
                           fields={}, captured=frozenset())
        result_items = engine.simulate_day(
            company, [item], engine.GOVERNED, 1).items
        refunds = [c for c in result_items[0].commitments if c.kind == "refund"]
        self.assertEqual(len(refunds), 1)
        self.assertTrue(refunds[0].violating)
        self.assertTrue(refunds[0].residual)


if __name__ == "__main__":
    unittest.main()
