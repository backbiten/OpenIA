"""
recycling.py — Metadata Scavenger & Blank-Slate Recycling Engine.

The IA (Intelligence Assistant) uses this module to mine *Alien Commodity*
Coinbits from junk/waste metadata that accumulates during normal operation.
Recovered resources are re-injected into the ``TransactionLog`` as
stabilising signals and registered with the ``AssetManager`` as new Alien
Commodities — keeping the Contractor/Mercenary Market well-funded.

Workflow
--------
1. ``MetadataScavenger.recycle(waste_data)`` receives a list of raw,
   unclassified metadata dicts.
2. Each item is rewritten to a **blank slate** (original, potentially
   virus-prone attributes are stripped).
3. A deterministic hash extracts a small Coinbit value from the raw bytes.
4. The mined value is registered as an ``AssetType.ALIEN_COMMODITY`` and
   submitted to the log as positive noise.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from .transaction import AssetManager, AssetType, TransactionLog


class MetadataScavenger:
    """Mines Coinbits from waste metadata and recycles it into a blank slate.

    Parameters
    ----------
    log:
        The shared :class:`~openia.transaction.TransactionLog` that mined
        values are re-injected into.
    asset_manager:
        Optional :class:`~openia.transaction.AssetManager` to register
        recovered Alien Commodities.  When *None* a private manager is
        created.
    """

    def __init__(
        self,
        log: TransactionLog,
        asset_manager: Optional[AssetManager] = None,
    ) -> None:
        self._log = log
        self._asset_manager: AssetManager = (
            asset_manager if asset_manager is not None else AssetManager(log=log)
        )
        self._recycled_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def recycled_count(self) -> int:
        """Total number of waste items processed so far."""
        return self._recycled_count

    @property
    def asset_manager(self) -> AssetManager:
        """The underlying :class:`~openia.transaction.AssetManager`."""
        return self._asset_manager

    def mine_waste(self, raw_metadata: Any) -> float:
        """Extract a deterministic Coinbit value from raw metadata waste.

        Uses a SHA-256 hash of the string representation to produce a small
        but non-zero value in ``[0.001, 0.010]``, turning junk into fuel.
        """
        data_bytes = str(raw_metadata).encode("utf-8")
        hash_int = int(hashlib.sha256(data_bytes).hexdigest(), 16)
        # Map to [0.001, 0.010]: 9 possible steps of 0.001
        coinbit = 0.001 + (hash_int % 10) * 0.001
        return coinbit

    def rewrite_to_blank_slate(self, waste_item: Any) -> Dict[str, Any]:
        """Strip all original attributes and return a clean, structured record.

        The blank slate contains only the mined Coinbit value and a status
        flag — all potentially broken, virus-prone, or disturbed metadata
        is discarded.
        """
        coinbit = self.mine_waste(waste_item)
        return {
            "coinbits": coinbit,
            "origin": "recycled_waste",
            "status": "clean",
        }

    def recycle(self, waste_data: List[Any]) -> float:
        """Process a batch of waste items, mining and re-injecting value.

        Each item is:
        1. Rewritten to a blank slate (original data discarded).
        2. Registered as an ``AssetType.ALIEN_COMMODITY`` with the manager.
        3. Its Coinbit value contributes to the market's liquidity.

        Parameters
        ----------
        waste_data:
            Sequence of raw metadata dicts (or any objects) to process.

        Returns
        -------
        float
            Total Coinbits mined from this batch.
        """
        total_mined: float = 0.0
        for idx, item in enumerate(waste_data):
            clean = self.rewrite_to_blank_slate(item)
            coinbit = clean["coinbits"]
            self._asset_manager.register(
                name=f"recycled_commodity_{self._recycled_count + idx}",
                asset_type=AssetType.ALIEN_COMMODITY,
                value=coinbit,
                metadata=clean,
            )
            total_mined += coinbit

        self._recycled_count += len(waste_data)
        return total_mined

    def __repr__(self) -> str:
        return (
            f"MetadataScavenger(recycled={self._recycled_count}, "
            f"coinbits={self._asset_manager.total_coinbits:.6f})"
        )
