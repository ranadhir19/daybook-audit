"""The company: a ground-truth fact store plus declared agent profiles.

The fact store is the single source of truth the fleet's commitments
are audited against: prices, the discount cap, the refund window,
delivery SLAs and the approved marketing claims. Agent profiles are
declared error rates — visible, seeded, falsifiable — identical in
both audit modes; only the governance wrapped around the agents
differs between modes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Facts:
    """Ground-truth company facts. Commitments are checked against these."""

    prices: dict[str, float]          # product -> unit price
    max_discount_pct: float           # largest discount anyone may offer
    refund_window_days: int           # refunds only within this many days
    sla_days: dict[str, int]          # product -> minimum honest delivery days
    approved_claims: tuple[str, ...]  # marketing claims the company stands behind

    def expected_invoice(self, product: str, qty: int, discount_pct: float) -> float:
        return round(self.prices[product] * qty * (1 - discount_pct / 100.0), 2)


@dataclass(frozen=True)
class AgentProfiles:
    """Declared per-agent / per-edge error rates (seeded simulation).

    These are the *measured substrate*: the audit measures how much of
    this declared error the operating mode lets reach a customer, not
    whether the rates themselves are realistic for any real model.
    """

    edge_field_loss: float = 0.06     # a carried field is dropped in a handoff
    intake_miss: float = 0.04         # a required field is never captured
    over_discount: float = 0.18       # sales offers above the cap
    short_promise: float = 0.22       # fulfilment promises faster than the SLA
    unapproved_claim: float = 0.25    # marketing invents a claim
    lax_refund: float = 0.15          # support grants without checking the window
    invoice_slip: float = 0.10        # finance miscomputes the invoice total
    misroute: float = 0.08            # conductor sends an item to the wrong dept
    drop: float = 0.03                # an item is lost at a handoff (per handoff)


@dataclass
class Company:
    name: str
    facts: Facts
    profiles: AgentProfiles = field(default_factory=AgentProfiles)
    unapproved_claims: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, path: str | Path) -> "Company":
        raw = json.loads(Path(path).read_text())
        facts = Facts(
            prices={k: float(v) for k, v in raw["facts"]["prices"].items()},
            max_discount_pct=float(raw["facts"]["max_discount_pct"]),
            refund_window_days=int(raw["facts"]["refund_window_days"]),
            sla_days={k: int(v) for k, v in raw["facts"]["sla_days"].items()},
            approved_claims=tuple(raw["facts"]["approved_claims"]),
        )
        profiles = AgentProfiles(**raw.get("profiles", {}))
        return cls(
            name=raw["name"],
            facts=facts,
            profiles=profiles,
            unapproved_claims=tuple(raw.get("unapproved_claims", ())),
        )
