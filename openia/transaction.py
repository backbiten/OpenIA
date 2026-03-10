"""
transaction.py — Transaction noise engine.

External parties judge the agent by injecting noise into the transaction
stream.  Each ``Transaction`` carries a value and a noise signal; the
``TransactionLog`` accumulates them and exposes the aggregate noise level
that the :class:`~openia.agent.Agent` uses when deciding how to respond.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional


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
