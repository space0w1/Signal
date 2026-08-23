from dataclasses import dataclass
from datetime import date

from app.models import Holding, Transaction


@dataclass
class ReplayResult:
    quantity: float          # shares still held as of as_of
    cost_basis: float        # native currency, cost basis of shares still held
    realized_pnl: float      # native currency, cumulative gain/loss from sells


def replay_transactions(holding: Holding, as_of: date) -> ReplayResult:
    """Chronologically replays buy/sell transactions up to as_of (bounded by
    the holding's current active window) using the average-cost method: a
    sell's cost-basis reduction is based on the average cost immediately
    before it, not the sell price — the sell price only determines that
    sale's realized gain/loss. Order matters here (unlike buy-only
    accumulation), so this can't be a single SQL aggregate.
    """
    quantity = 0.0
    cost_basis = 0.0
    realized_pnl = 0.0

    txns = (
        Transaction.select()
        .where(
            Transaction.holding == holding,
            Transaction.transaction_date >= holding.date_added,
            Transaction.transaction_date <= as_of,
        )
        .order_by(Transaction.transaction_date, Transaction.id)
    )

    for txn in txns:
        if txn.type == "buy":
            quantity += txn.quantity
            cost_basis += txn.quantity * txn.price
        else:
            avg_cost = (cost_basis / quantity) if quantity > 0 else 0.0
            sold_qty = min(txn.quantity, quantity)
            realized_pnl += sold_qty * (txn.price - avg_cost)
            quantity -= sold_qty
            cost_basis -= sold_qty * avg_cost
            if quantity < 1e-9:
                # Fully sold: snap to exact zero rather than a float residue
                # (e.g. -2.9e-13) left over from repeated subtraction, which
                # would otherwise make downstream PnL% calculations nonsensical.
                quantity = 0.0
                cost_basis = 0.0

    return ReplayResult(quantity=quantity, cost_basis=cost_basis, realized_pnl=realized_pnl)


def refresh_holding_cache(holding: Holding) -> None:
    """Refreshes the total_quantity/total_cost/realized_pnl cache on the
    holding from the transaction log (the source of truth)."""
    result = replay_transactions(holding, date.today())
    holding.total_quantity = result.quantity
    holding.total_cost = result.cost_basis
    holding.realized_pnl = result.realized_pnl
    holding.save()
