"""
judge.py — External judgment interface.

A :class:`Judge` wraps a :class:`~openia.transaction.TransactionLog` and
provides a higher-level API for outside parties to *evaluate* the agent.
Judgment is always expressed through transaction noise so the agent remains
open to — but not directly controlled by — external opinion.
"""

from __future__ import annotations

from typing import Optional

from .transaction import TransactionLog


class Judge:
    """Issues verdicts against an agent via transaction noise.

    Parameters
    ----------
    log:
        The shared :class:`~openia.transaction.TransactionLog` that both
        the judge and the agent observe.  If *None* a new log is created.
    """

    def __init__(self, log: Optional[TransactionLog] = None) -> None:
        self._log: TransactionLog = log if log is not None else TransactionLog()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def log(self) -> TransactionLog:
        """The underlying transaction log."""
        return self._log

    def approve(self, value: float = 1.0) -> None:
        """Signal approval with maximum positive noise (+1)."""
        self._log.submit(value=value, noise=1.0)

    def disapprove(self, value: float = 1.0) -> None:
        """Signal disapproval with maximum negative noise (-1)."""
        self._log.submit(value=value, noise=-1.0)

    def partial(self, value: float, score: float) -> None:
        """Issue a partial verdict.

        Parameters
        ----------
        value:
            Transaction payload.
        score:
            Judgment signal in *[-1, 1]*.  Positive = approval,
            negative = disapproval.
        """
        self._log.submit(value=value, noise=score)

    @property
    def verdict(self) -> str:
        """Human-readable verdict derived from the aggregate noise level."""
        noise = self._log.aggregate_noise
        if noise > 0.5:
            return "approved"
        if noise < -0.5:
            return "disapproved"
        return "inconclusive"

    def __repr__(self) -> str:
        return (
            f"Judge(verdict={self.verdict!r}, "
            f"aggregate_noise={self._log.aggregate_noise:.4f})"
        )
