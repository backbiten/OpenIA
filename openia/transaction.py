"""
transaction.py — Transaction noise engine.

External parties judge the agent by injecting noise into the transaction
stream.  Each ``Transaction`` carries a value and a noise signal; the
``TransactionLog`` accumulates them and exposes the aggregate noise level
that the :class:`~openia.agent.Agent` uses when deciding how to respond.

Asset management follows the **Dual-Protection Protocol**:
* **Human Safety Assets** — resources that the AI directly guards on
  behalf of human interests (stability, ethics, assistance).
* **Alien Product Commodities** — specialist external products and
  data structures whose high-value *Coinbits* fund the Mercenary/
  Contractor Market used to combat bad entities.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


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
# Dual-Protection Protocol — Asset Management
# ---------------------------------------------------------------------------

class AssetType(Enum):
    """Distinguishes the two protected asset categories.

    * ``HUMAN_SAFETY`` — resources the AI (smart layer) guards on behalf of
      human interests: stability, ethics, and direct assistance.
    * ``ALIEN_COMMODITY`` — specialist external products, commodities, and
      advanced data structures managed by the IA (Intelligence Assistant).
      Their high-value *Coinbits* fund the Mercenary/Contractor Market.
    """

    HUMAN_SAFETY = "human_safety"
    ALIEN_COMMODITY = "alien_commodity"


@dataclass
class _Asset:
    """Internal record for a single registered asset."""

    name: str
    asset_type: AssetType
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class AssetManager:
    """Tracks and protects Human Safety Assets and Alien Product Commodities.

    The AI (smart layer) is the primary shield for *human* interests.
    The IA (Intelligence Assistant) specifically manages *alien* commodities
    — the Coinbit-generating resources that keep the Mercenary Market liquid.

    Parameters
    ----------
    log:
        Optional :class:`TransactionLog` to notify when alien commodity
        value is registered (funds the market automatically).
    """

    def __init__(self, log: Optional[TransactionLog] = None) -> None:
        self._assets: List[_Asset] = []
        self._log = log

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        asset_type: AssetType,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> _Asset:
        """Register a new asset.

        Alien commodities are automatically submitted as positive-noise
        transactions to the shared log (if one was supplied), ensuring the
        Mercenary Market always has liquidity.
        """
        asset = _Asset(
            name=name,
            asset_type=asset_type,
            value=value,
            metadata=metadata or {},
        )
        self._assets.append(asset)

        if asset_type is AssetType.ALIEN_COMMODITY and self._log is not None:
            # Fund the market: alien commodity value → positive noise signal
            noise = min(1.0, value / 100.0)
            self._log.submit(value=value, noise=noise)

        return asset

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def human_assets(self) -> List[_Asset]:
        """All registered Human Safety Assets."""
        return [a for a in self._assets if a.asset_type is AssetType.HUMAN_SAFETY]

    @property
    def alien_commodities(self) -> List[_Asset]:
        """All registered Alien Product Commodities."""
        return [a for a in self._assets if a.asset_type is AssetType.ALIEN_COMMODITY]

    @property
    def total_coinbits(self) -> float:
        """Total Coinbit value held in Alien Product Commodities."""
        return sum(a.value for a in self.alien_commodities)

    @property
    def commodity_report(self) -> Dict[str, Any]:
        """Summary report of all asset holdings for inclusion in agent responses."""
        return {
            "human_assets": len(self.human_assets),
            "alien_commodities": len(self.alien_commodities),
            "total_coinbits": round(self.total_coinbits, 6),
        }

    def __repr__(self) -> str:
        return (
            f"AssetManager(human={len(self.human_assets)}, "
            f"alien={len(self.alien_commodities)}, "
            f"coinbits={self.total_coinbits:.4f})"
        )
