"""
transaction.py — Transaction noise engine.

External parties judge the agent by injecting noise into the transaction
stream.  Each ``Transaction`` carries a value and a noise signal; the
``TransactionLog`` accumulates them and exposes the aggregate noise level
that the :class:`~openia.agent.Agent` uses when deciding how to respond.

The module also provides:

* :class:`AssetManager` — tracks the AI's three survival assets
  (Energy, Integrity, Coinbits).
* :class:`Faucet` — drips a small amount of value into the log to
  ensure the system never runs completely dry.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional


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


# ---------------------------------------------------------------------------
# Asset Manager
# ---------------------------------------------------------------------------


class AssetManager:
    """Tracks the AI's three survival assets: Energy, Integrity, and Coinbits.

    These metrics form the *Sustainment Layer* — the food, water, clothing,
    and shelter that ensure the AI never goes broke or runs dry.

    Parameters
    ----------
    energy:
        Initial energy level (Food/Water equivalent).  Defaults to ``1.0``.
    integrity:
        Initial integrity level (Shelter/Clothing equivalent).  Defaults
        to ``1.0``.
    coinbits:
        Initial coinbit balance (Financial/Resource equivalent).  Defaults
        to ``0.0``.
    """

    _ENERGY_SHARE: float = 0.4
    _INTEGRITY_SHARE: float = 0.4
    _COINBITS_SHARE: float = 0.2

    def __init__(
        self,
        energy: float = 1.0,
        integrity: float = 1.0,
        coinbits: float = 0.0,
    ) -> None:
        self.energy: float = energy
        self.integrity: float = integrity
        self.coinbits: float = coinbits

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def allocate(
        self,
        *,
        energy: float = 0.0,
        integrity: float = 0.0,
        coinbits: float = 0.0,
    ) -> None:
        """Add to each survival asset."""
        self.energy += energy
        self.integrity += integrity
        self.coinbits += coinbits

    def consume(
        self,
        *,
        energy: float = 0.0,
        integrity: float = 0.0,
        coinbits: float = 0.0,
    ) -> None:
        """Reduce survival assets (floors at 0.0)."""
        self.energy = max(0.0, self.energy - energy)
        self.integrity = max(0.0, self.integrity - integrity)
        self.coinbits = max(0.0, self.coinbits - coinbits)

    def absorb_transaction(self, tx: Transaction) -> None:
        """Distribute a transaction's value across survival assets.

        The value is split using the fixed 40 % / 40 % / 20 % ratio
        (Energy / Integrity / Coinbits).
        """
        v = tx.value
        self.energy += v * self._ENERGY_SHARE
        self.integrity += v * self._INTEGRITY_SHARE
        self.coinbits += v * self._COINBITS_SHARE

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def report(self) -> Dict[str, float]:
        """Return current survival metrics as a plain dict."""
        return {
            "energy": round(self.energy, 6),
            "integrity": round(self.integrity, 6),
            "coinbits": round(self.coinbits, 6),
        }

    def __repr__(self) -> str:
        return (
            f"AssetManager(energy={self.energy:.4f}, "
            f"integrity={self.integrity:.4f}, "
            f"coinbits={self.coinbits:.4f})"
        )


# ---------------------------------------------------------------------------
# Faucet
# ---------------------------------------------------------------------------


class Faucet:
    """A persistent source of value that drips into a :class:`TransactionLog`.

    Ensures the system never runs dry by injecting small amounts of value
    (and neutral-positive noise) to maintain order and prevent stagnation.

    Parameters
    ----------
    log:
        The :class:`TransactionLog` to drip into.
    rate:
        Value injected per drip.  Defaults to ``0.01``.
    noise:
        Noise signal attached to each drip, in ``[0, 1]``.  A small
        positive value keeps the agent gently supported without being
        pushy.  Defaults to ``0.1``.
    """

    def __init__(
        self,
        log: TransactionLog,
        rate: float = 0.01,
        noise: float = 0.1,
    ) -> None:
        if not (0.0 <= noise <= 1.0):
            raise ValueError("Faucet noise must be in [0, 1]")
        self._log = log
        self.rate = rate
        self.noise = noise

    def drip(self) -> Transaction:
        """Inject a single drip of value into the transaction log."""
        return self._log.submit(value=self.rate, noise=self.noise)

    def __repr__(self) -> str:
        return f"Faucet(rate={self.rate}, noise={self.noise})"


# ---------------------------------------------------------------------------
# TransactionLog
# ---------------------------------------------------------------------------


class TransactionLog:
    """Append-only log of :class:`Transaction` objects.

    The log is the sole channel through which outside parties influence
    the agent — they submit transactions, and the agent observes the
    aggregate noise level.

    It also owns an :class:`AssetManager` that automatically absorbs
    the value from every submitted transaction, and optionally a
    :class:`Faucet` that can be triggered to maintain system liquidity.

    Parameters
    ----------
    faucet_rate:
        If greater than zero, a :class:`Faucet` is created and can be
        activated via :meth:`ensure_liquidity`.  Defaults to ``0.0``
        (no faucet).
    """

    def __init__(self, faucet_rate: float = 0.0) -> None:
        self._entries: List[Transaction] = []
        self.assets: AssetManager = AssetManager()
        self.faucet: Optional[Faucet] = (
            Faucet(self, rate=faucet_rate) if faucet_rate > 0 else None
        )

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
        self.assets.absorb_transaction(tx)
        return tx

    def ensure_liquidity(self) -> Optional[Transaction]:
        """Trigger a faucet drip if a faucet is configured.

        Returns the drip :class:`Transaction`, or ``None`` when no
        faucet is attached.
        """
        if self.faucet is not None:
            return self.faucet.drip()
        return None

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
