"""
transaction.py — Transaction noise engine.

External parties judge the agent by injecting noise into the transaction
stream.  Each ``Transaction`` carries a value and a noise signal; the
``TransactionLog`` accumulates them and exposes the aggregate noise level
that the :class:`~openia.agent.Agent` uses when deciding how to respond.

:class:`AssetManager` extends the log with an optional link to the
Internal Stock Exchange (:class:`~openia.market.InternalMarket`), so that
transaction activity can feed back into internal resource pricing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .market import InternalMarket


@dataclass
class Transaction:
    """A single external transaction with an optional noise signal.

    Parameters
    ----------
    value:
        The payload of the transaction (e.g. a coin-bit amount or any
        numeric signal).
    noise:
        A float in *[-1, 1]* representing external judgment.  Positive
        noise nudges the agent toward a more helpful response; negative
        noise is a penalty signal.  ``None`` means no judgment was
        attached.
    """

    value: float
    noise: Optional[float] = None

    def __post_init__(self) -> None:
        if self.noise is not None and not (-1.0 <= self.noise <= 1.0):
            raise ValueError("noise must be in the range [-1, 1]")


class TransactionLog:
    """Append-only log of :class:`Transaction` objects.

    The log is the sole channel through which outside parties influence
    the agent — they submit transactions, and the agent observes the
    aggregate noise level.
    """

    def __init__(self) -> None:
        self._entries: List[Transaction] = []

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def submit(self, value: float, noise: Optional[float] = None) -> Transaction:
        """Append a new transaction and return it.

        Parameters
        ----------
        value:
            Transaction payload.
        noise:
            Optional judgment signal in *[-1, 1]*.
        """
        tx = Transaction(value=value, noise=noise)
        self._entries.append(tx)
        return tx

    def submit_random_noise(self, value: float) -> Transaction:
        """Submit a transaction whose noise is drawn uniformly from [-1, 1].

        Useful for simulating an environment where external actors
        continuously broadcast judgment without a fixed opinion.
        """
        noise = random.uniform(-1.0, 1.0)
        return self.submit(value=value, noise=noise)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def entries(self) -> List[Transaction]:
        """Immutable view of all recorded transactions."""
        return list(self._entries)

    @property
    def aggregate_noise(self) -> float:
        """Mean noise across all transactions that carry a noise signal.

        Returns ``0.0`` when no noisy transactions have been recorded.
        """
        noisy = [tx.noise for tx in self._entries if tx.noise is not None]
        if not noisy:
            return 0.0
        return sum(noisy) / len(noisy)

    @property
    def total_value(self) -> float:
        """Sum of all transaction values."""
        return sum(tx.value for tx in self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return (
            f"TransactionLog(count={len(self)}, "
            f"total_value={self.total_value:.4f}, "
            f"aggregate_noise={self.aggregate_noise:.4f})"
        )


# ---------------------------------------------------------------------------
# AssetManager
# ---------------------------------------------------------------------------


class AssetManager:
    """Connects a :class:`TransactionLog` to the Internal Stock Exchange.

    The ``AssetManager`` wraps a ``TransactionLog`` and, optionally, an
    :class:`~openia.market.InternalMarket`.  Every time a transaction is
    submitted, the manager reflects the total transaction value back into
    the market as recycled liquidity, keeping the internal token supply
    aligned with real transaction activity.

    Parameters
    ----------
    log:
        The underlying :class:`TransactionLog`.  If *None* a new one is
        created.
    market:
        An :class:`~openia.market.InternalMarket` instance.  If *None*
        one is created automatically.

    Examples
    --------
    >>> from openia.transaction import AssetManager
    >>> am = AssetManager()
    >>> am.submit(value=0.5, noise=0.2)
    Transaction(value=0.5, noise=0.2)
    >>> am.market_snapshot()["Coinbits"] > 0
    True
    """

    def __init__(
        self,
        log: Optional[TransactionLog] = None,
        market: Optional["InternalMarket"] = None,
    ) -> None:
        self._log: TransactionLog = log if log is not None else TransactionLog()
        # Lazy import avoids a circular dependency at module level.
        if market is None:
            from .market import InternalMarket  # noqa: PLC0415

            market = InternalMarket()
        self._market: "InternalMarket" = market

    # ------------------------------------------------------------------
    # Delegated log interface
    # ------------------------------------------------------------------

    def submit(self, value: float, noise: Optional[float] = None) -> Transaction:
        """Submit a transaction and synchronise market liquidity.

        The transaction ``value`` is injected as recycled liquidity into the
        :class:`~openia.market.InternalMarket`, gently raising internal
        token prices proportional to overall activity.
        """
        tx = self._log.submit(value=value, noise=noise)
        self._market.inject_recycled_liquidity(abs(value))
        return tx

    @property
    def log(self) -> TransactionLog:
        """The underlying :class:`TransactionLog`."""
        return self._log

    @property
    def market(self) -> "InternalMarket":
        """The linked :class:`~openia.market.InternalMarket`."""
        return self._market

    # ------------------------------------------------------------------
    # Market helpers
    # ------------------------------------------------------------------

    def market_snapshot(self) -> Dict[str, float]:
        """Return current internal market prices."""
        return self._market.snapshot()

    def update_market(
        self,
        *,
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0,
        ai_performance: float = 1.0,
    ) -> None:
        """Propagate system-resource metrics to the internal market."""
        self._market.update(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            ai_performance=ai_performance,
        )

    def __repr__(self) -> str:
        return (
            f"AssetManager(log={self._log!r}, market={self._market!r})"
        )
