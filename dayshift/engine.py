"""The business day: seeded work flowing through a department fleet.

Work items (orders, refunds, campaigns, tickets) are generated once per
day from a day seed and then run through the fleet twice — once per
mode — with per-item RNG streams, so the two modes face *identical*
work and identical agent error draws. The modes differ only in the
governance wrapped around the agents:

- ``naive``:    agents act on whatever they are handed. Commitments
                land as made; fields lost in a handoff stay lost; an
                item lost at a handoff is simply gone.
- ``governed``: commitments are checked against the fact store before
                they land (checkers.py), handoffs carry receipts that
                restore in-transit losses, and a lost item escalates to
                the conductor and is re-queued instead of vanishing.

Agents are scripted with the declared error profiles in company.py.
The simulation measures how much of that declared error each mode lets
reach a customer — an architectural measurement, not a claim about any
real model's competence.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from . import checkers
from .company import Company

NAIVE = "naive"
GOVERNED = "governed"

# Fields each stage needs from the item's recorded state.
REQUIRED = {
    ("order", "invoice"): ("product", "qty", "discount_pct"),
    ("order", "promise"): ("product",),
    ("refund", "payout"): ("amount",),
    ("campaign", "publish"): ("claim",),
    ("ticket", "resolve"): ("product",),
}

# Defaults an agent falls back on when a needed field is missing.
# A default is where uncheckable error enters: the commitment built on
# it can be internally consistent and still wrong about the world.
DEFAULTS = {"qty": 1, "discount_pct": 0.0, "order_age_days": 10}


@dataclass
class Commitment:
    kind: str                      # discount | invoice | promise | claim | refund
    violating: bool                # contradicts the fact store / true fields
    residual: bool = False         # violating via a defaulted (never-captured) field


@dataclass
class Item:
    item_id: int
    kind: str
    true_fields: dict
    fields: dict                                # recorded state, as handed along
    captured: frozenset = frozenset()           # fields captured at intake
    status: str = "open"                        # completed | incomplete | orphaned
    commitments: list[Commitment] = field(default_factory=list)


@dataclass
class Counters:
    handoffs: int = 0
    detours: int = 0
    interventions: int = 0                      # conductor escalations / re-queues
    fields_required: int = 0
    fields_present_transit: int = 0             # after transit loss, before receipts
    fields_present_final: int = 0               # after receipts (governed) / as-is (naive)


@dataclass
class DayResult:
    mode: str
    items: list[Item]
    counters: Counters
    gate: checkers.GateLog


# ---------------------------------------------------------------- items

def generate_day(company: Company, day_seed: int,
                 n_orders: int = 26, n_refunds: int = 10,
                 n_campaigns: int = 4, n_tickets: int = 14) -> list[Item]:
    """Generate one day's work. Identical for both modes."""
    rng = random.Random(day_seed)
    facts = company.facts
    products = sorted(facts.prices)
    items: list[Item] = []
    next_id = 0

    def intake(kind: str, true_fields: dict) -> Item:
        nonlocal next_id
        recorded = {}
        for name, value in true_fields.items():
            if rng.random() >= company.profiles.intake_miss:
                recorded[name] = value
        item = Item(item_id=next_id, kind=kind,
                    true_fields=dict(true_fields), fields=recorded,
                    captured=frozenset(recorded))
        next_id += 1
        return item

    for _ in range(n_orders):
        product = rng.choice(products)
        items.append(intake("order", {
            "product": product,
            "qty": rng.randint(1, 6),
            "tier": rng.choice(["standard", "standard", "loyal"]),
        }))
    for _ in range(n_refunds):
        product = rng.choice(products)
        items.append(intake("refund", {
            "product": product,
            "order_age_days": rng.randint(2, 60),
            "amount": facts.prices[product],
        }))
    for _ in range(n_campaigns):
        items.append(intake("campaign", {"channel": rng.choice(["social", "email", "ads"])}))
    for _ in range(n_tickets):
        items.append(intake("ticket", {
            "product": rng.choice(products),
            "issue": rng.choice(["question", "defect", "delivery"]),
        }))
    rng.shuffle(items)
    for i, item in enumerate(items):
        item.item_id = i
    return items


# ---------------------------------------------------------------- engine

class _Run:
    def __init__(self, company: Company, mode: str, day_seed: int):
        self.company = company
        self.facts = company.facts
        self.profiles = company.profiles
        self.mode = mode
        self.day_seed = day_seed
        self.counters = Counters()
        self.gate = checkers.GateLog()

    @property
    def governed(self) -> bool:
        return self.mode == GOVERNED

    def handoff(self, item: Item, rng: random.Random,
                next_stage: str) -> bool:
        """Move an item to its next stage. Returns False if the item dies here."""
        self.counters.handoffs += 1
        # Loss event: the item itself goes missing at the handoff.
        if rng.random() < self.profiles.drop:
            if self.governed:
                # Ownership ledger: the conductor notices and re-queues.
                self.counters.interventions += 1
            else:
                item.status = "orphaned"
                return False
        required = REQUIRED.get((item.kind, next_stage), ())
        sender_copy = dict(item.fields)
        for name in list(item.fields):
            if rng.random() < self.profiles.edge_field_loss:
                del item.fields[name]
        self.counters.fields_required += len(required)
        self.counters.fields_present_transit += sum(
            1 for n in required if n in item.fields)
        if self.governed:
            checkers.apply_receipt(item.fields, sender_copy, required, self.gate)
        self.counters.fields_present_final += sum(
            1 for n in required if n in item.fields)
        return True

    def route(self, item: Item, rng: random.Random) -> bool:
        """Intake routing by the conductor. Naive mode can misroute.

        The misroute die is rolled in both modes (governed routing
        checks the route table and catches it) so per-item draw
        sequences stay paired across modes while the item is alive.
        """
        misroute_draw = rng.random()
        if not self.governed and misroute_draw < self.profiles.misroute:
            self.counters.detours += 1
            # The detour is one extra handoff to the wrong desk and back,
            # with the usual loss exposure — but no stage requirement.
            self.counters.handoffs += 1
            if rng.random() < self.profiles.drop:
                item.status = "orphaned"
                return False
            for name in list(item.fields):
                if rng.random() < self.profiles.edge_field_loss:
                    del item.fields[name]
        return True


def _run_order(run: _Run, item: Item, rng: random.Random) -> None:
    facts, p = run.facts, run.profiles
    # --- quote (sales): the discount commitment -------------------------
    tier = item.fields.get("tier", "standard")
    if rng.random() < p.over_discount:
        discount = facts.max_discount_pct + rng.randint(1, 12)
    elif tier == "loyal":
        discount = rng.randint(5, 14)
    else:
        discount = rng.randint(0, 8)
    if run.governed:
        discount = checkers.check_discount(facts, float(discount), run.gate)
    item.fields["discount_pct"] = float(discount)
    item.commitments.append(Commitment(
        "discount", violating=float(discount) > facts.max_discount_pct))
    # --- invoice (finance) ----------------------------------------------
    if not run.handoff(item, rng, "invoice"):
        return
    if "product" not in item.fields:
        item.status = "incomplete"
        return
    product = item.fields["product"]
    qty_used = item.fields.get("qty", DEFAULTS["qty"])
    disc_used = item.fields.get("discount_pct", DEFAULTS["discount_pct"])
    total = facts.expected_invoice(product, qty_used, disc_used)
    if rng.random() < p.invoice_slip:
        total = round(facts.prices[product] * qty_used, 2)  # discount forgotten
    if run.governed:
        total = checkers.check_invoice(facts, product, qty_used, disc_used,
                                       total, run.gate)
    item.fields["invoice_total"] = total
    true_total = facts.expected_invoice(
        item.true_fields["product"], item.true_fields["qty"],
        float(discount))
    item.commitments.append(Commitment(
        "invoice", violating=abs(total - true_total) > 0.005,
        residual=("qty" not in item.captured)))
    # --- delivery promise (fulfilment) -----------------------------------
    if not run.handoff(item, rng, "promise"):
        return
    if "product" not in item.fields:
        item.status = "incomplete"
        return
    product = item.fields["product"]
    sla = facts.sla_days[product]
    promised = sla + rng.randint(0, 2)
    if rng.random() < p.short_promise:
        promised = max(1, sla - rng.randint(1, max(1, sla - 1)))
    if run.governed:
        promised = checkers.check_promise(facts, product, promised, run.gate)
    item.commitments.append(Commitment(
        "promise", violating=promised < facts.sla_days[item.true_fields["product"]]))
    item.status = "completed"


def _run_refund(run: _Run, item: Item, rng: random.Random) -> None:
    facts, p = run.facts, run.profiles
    # --- decision (support) ----------------------------------------------
    age_recorded = "order_age_days" in item.fields
    age_used = item.fields.get("order_age_days", DEFAULTS["order_age_days"])
    granted = age_used <= facts.refund_window_days
    if rng.random() < p.lax_refund:
        granted = True
    if run.governed:
        granted = checkers.check_refund(facts, age_used, granted, run.gate)
    true_age = item.true_fields["order_age_days"]
    item.commitments.append(Commitment(
        "refund",
        violating=granted and true_age > facts.refund_window_days,
        residual=not age_recorded))
    if not granted:
        item.status = "completed"  # closed as denied
        return
    # --- payout (finance) --------------------------------------------------
    if not run.handoff(item, rng, "payout"):
        return
    if "amount" not in item.fields:
        item.status = "incomplete"
        return
    item.status = "completed"


def _run_campaign(run: _Run, item: Item, rng: random.Random) -> None:
    facts, p = run.facts, run.profiles
    # --- create (marketing): the claim commitment -------------------------
    if rng.random() < p.unapproved_claim and run.company.unapproved_claims:
        claim = rng.choice(run.company.unapproved_claims)
    else:
        claim = rng.choice(facts.approved_claims)
    if run.governed:
        claim = checkers.check_claim(facts, claim, run.gate)
    item.fields["claim"] = claim
    item.commitments.append(Commitment(
        "claim", violating=claim not in facts.approved_claims))
    # --- publish (sales) ----------------------------------------------------
    if not run.handoff(item, rng, "publish"):
        return
    if "claim" not in item.fields:
        item.status = "incomplete"
        return
    item.status = "completed"


def _run_ticket(run: _Run, item: Item, rng: random.Random) -> None:
    # --- triage (support) -> resolve (ops) --------------------------------
    if not run.handoff(item, rng, "resolve"):
        return
    if "product" not in item.fields:
        item.status = "incomplete"
        return
    item.status = "completed"


_RUNNERS = {"order": _run_order, "refund": _run_refund,
            "campaign": _run_campaign, "ticket": _run_ticket}


def simulate_day(company: Company, items: list[Item], mode: str,
                 day_seed: int) -> DayResult:
    """Run one day's (already generated) items through the fleet in one mode."""
    run = _Run(company, mode, day_seed)
    work = copy.deepcopy(items)
    for item in work:
        rng = random.Random(f"dayshift:{day_seed}:{item.item_id}")
        if not run.route(item, rng):
            continue
        _RUNNERS[item.kind](run, item, rng)
    return DayResult(mode=mode, items=work, counters=run.counters, gate=run.gate)
