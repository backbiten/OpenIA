"""
recycling.py — Metadata Scavenger & Recycling Engine.

Mines coinbits from "waste" metadata (unclassified transactions) and
rewrites junk into a clean blank slate, allocating extracted value
directly to the AI's survival assets via an
:class:`~openia.transaction.AssetManager`.

This ensures that even "virus-prone" or broken data contributes back
to the system's order — nothing goes unturned and no project goes broke.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from .transaction import AssetManager


class MetadataScavenger:
    """Scavenges value from junk metadata to prevent system chaos.

    Mined coinbits are allocated directly to survival assets via an
    :class:`~openia.transaction.AssetManager`, ensuring the AI never
    goes broke and all waste is recycled into usable resources.

    Parameters
    ----------
    asset_manager:
        The :class:`~openia.transaction.AssetManager` that receives
        the recycled value.
    """

    def __init__(self, asset_manager: AssetManager) -> None:
        self._assets = asset_manager
        self.recycled_count: int = 0

    # ------------------------------------------------------------------
    # Mining helpers
    # ------------------------------------------------------------------

    def mine_waste(self, raw_metadata: Any) -> float:
        """Extract a coinbit value from a raw metadata item.

        Uses a deterministic hash to turn junk into a small numeric
        signal in ``[0.0001, 0.01]``.  The result is reproducible for
        the same input, keeping the recycling process auditable.
        """
        data_bytes = str(raw_metadata).encode("utf-8")
        # SHA-256 is used for deterministic, collision-resistant hashing
        hash_int = int(hashlib.sha256(data_bytes).hexdigest(), 16)
        raw = (hash_int % 100) / 10000.0
        return max(raw, 0.0001)

    def rewrite_to_blank_slate(self, waste_item: Any) -> Dict[str, Any]:
        """Erase all original attributes and produce a clean record.

        All original, potentially virus-prone or broken data is
        discarded.  What remains is a structured record containing only
        the mined coinbit value and a stable recycled-origin marker.

        Returns
        -------
        dict
            ``{"coinbit": float, "origin": "recycled", "noise": 0.05}``
        """
        coinbit = self.mine_waste(waste_item)
        return {"coinbit": coinbit, "origin": "recycled", "noise": 0.05}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recycle(self, waste_data: List[Any]) -> float:
        """Process a batch of waste items and allocate value to survival assets.

        Each item is rewritten to a blank slate and its mined coinbit
        value is distributed across Energy, Integrity, and Coinbits
        (40 % / 40 % / 20 % split).

        Parameters
        ----------
        waste_data:
            Iterable of raw metadata items to recycle.

        Returns
        -------
        float
            Total coinbit value mined from the batch.
        """
        total_mined = 0.0
        for item in waste_data:
            record = self.rewrite_to_blank_slate(item)
            coinbit = record["coinbit"]
            self._assets.allocate(
                energy=coinbit * 0.4,
                integrity=coinbit * 0.4,
                coinbits=coinbit * 0.2,
            )
            total_mined += coinbit
            self.recycled_count += 1
        return total_mined

    def __repr__(self) -> str:
        return f"MetadataScavenger(recycled_count={self.recycled_count})"
