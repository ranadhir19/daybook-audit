# One day at Fernbrook Supply Co. — seed 7, both modes

Generated work: 54 items (26 orders, 10 refunds, 4 campaigns,
14 tickets). Every incident below is real output of
`python3 examples/trace_day.py --seed 7` — nothing is staged.

## The naive fleet's day

**11 commitments reached a customer in violation of the company's own
facts.** Six orders (#0, #5, #12, #25, #28, #29) were promised faster
than the delivery SLA allows; three invoices (#27, #29, #32) went out
at totals that do not match the price list and the quoted discount;
one refund (#8) was granted outside the 30-day window.

**Four items vanished.** Orders #2, #3 and #49 and ticket #11 were
lost at handoffs. Nobody was notified; in the naive mode there is no
conductor load to report — the silence is the finding.

**Seven items failed visibly** (tickets #6, #9, #38; orders #13, #14,
#18, #48) — mostly work that arrived at a stage missing a field it
needed, with no way to get it back.

## The same day, governed

Same items, same seeded error draws. **Zero violations reached a
customer and nothing vanished.** The gate corrected 10 commitments
before they landed (7 delivery promises extended to the SLA, 1 refund
denied as out-of-window, 2 invoice totals recomputed). Handoff
receipts recovered 8 required fields that transit had dropped. Three
would-be losses became conductor interventions instead of orphans.

Two tickets (#6, #38) still failed — the product was never captured
at intake, and no receipt can restore a field nobody ever held. That
is the residual class the 20-day audit quantifies: governance cannot
fix intake.
