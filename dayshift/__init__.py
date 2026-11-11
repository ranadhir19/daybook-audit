"""dayshift — a consistency audit for department agent fleets.

Simulates seeded business days for a small company whose departments
(sales, finance, marketing, support, fulfilment) are staffed by agents,
then audits the operation: which external commitments contradicted the
company's own facts, what the handoffs lost, and what fell on the floor.
"""

__all__ = ["company", "engine", "checkers", "audit"]
__version__ = "0.1.0"
