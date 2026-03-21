"""
market.py — Internal Stock Exchange (ISE) for OpenIA.

Simulates a strictly **closed-loop** market for internal AI-component
cryptocurrencies.  The market exists purely as a programmatic
resource-allocation and data-governance mechanism; it has no connection
to any external fiat currency, real-world trade, or public blockchain.

Internal currencies
-------------------
* **Coinbits**   — the base priority token (think: CPU time slots).
* **ThreadBits** — represent concurrent execution threads.
* **BufferBits** — represent available I/O buffer capacity.
* **CoreBits**   — represent hardware-core utilisation headroom.

All values are dimensionless floats.  They are intentionally a
"programmatic joke" — a lightweight metaphor for the AI's ability to
allocate its own internal resources.

Typical usage
-------------
>>> from openia.market import InternalMarket
>>> market = InternalMarket()
>>> report = market.snapshot()
>>> report["Coinbits"]
1.0
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Names of all currencies traded on the Internal Stock Exchange.
CURRENCIES: List[str] = ["Coinbits", "ThreadBits", "BufferBits", "CoreBits"]

#: Minimum allowed price for any internal currency.
MIN_PRICE_FLOOR: float = 0.01

#: Multiplier applied to the log-recycled-liquidity boost for Coinbits.
LIQUIDITY_BOOST_FACTOR: float = 0.01

# ---------------------------------------------------------------------------
# MarketTick — a single time-stamped price snapshot
# ---------------------------------------------------------------------------


@dataclass
class MarketTick:
    """A single ISE price snapshot.

    Parameters
    ----------
    timestamp:
        Unix epoch float at the moment the tick was recorded.
    prices:
        Mapping of currency name → current internal value (always > 0).
    liquidity:
        Total recycled-metadata value fed into the market at this tick.
    """

    timestamp: float
    prices: Dict[str, float]
    liquidity: float = 0.0

    def __post_init__(self) -> None:
        for name, price in self.prices.items():
            if price <= 0:
                raise ValueError(
                    f"Market price for '{name}' must be positive, got {price}"
                )


# ---------------------------------------------------------------------------
# InternalMarket
# ---------------------------------------------------------------------------


class InternalMarket:
    """The Internal Stock Exchange (ISE) for OpenIA.

    Tracks simulated "value" for each internal AI-component currency.
    Prices are updated by calling :meth:`update` with current resource
    metrics.  The market never contacts external systems.

    Parameters
    ----------
    base_prices:
        Initial prices for each currency.  Defaults to ``1.0`` for all.
    """

    def __init__(
        self,
        base_prices: Optional[Dict[str, float]] = None,
    ) -> None:
        self._prices: Dict[str, float] = {
            name: (base_prices or {}).get(name, 1.0) for name in CURRENCIES
        }
        self._history: List[MarketTick] = []
        self._recycled_liquidity: float = 0.0

        # Record the opening tick
        self._record_tick()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def prices(self) -> Dict[str, float]:
        """Current prices for all currencies (read-only copy)."""
        return dict(self._prices)

    @property
    def history(self) -> List[MarketTick]:
        """Immutable list of all recorded :class:`MarketTick` objects."""
        return list(self._history)

    @property
    def recycled_liquidity(self) -> float:
        """Total liquidity injected from recycled metadata so far."""
        return self._recycled_liquidity

    def update(
        self,
        *,
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0,
        ai_performance: float = 1.0,
    ) -> MarketTick:
        """Recompute internal prices based on system resource metrics.

        Parameters
        ----------
        cpu_usage:
            CPU utilisation in the range *[0, 1]*.  Higher load → scarcer
            thread / core capacity → higher ThreadBits / CoreBits prices.
        memory_usage:
            Memory utilisation in the range *[0, 1]*.  Higher pressure →
            higher BufferBits price.
        ai_performance:
            A dimensionless AI health score (0 = broken, 1 = nominal,
            >1 = outstanding).  Modulates the base Coinbits price.

        Returns
        -------
        MarketTick
            The tick recorded after the update.
        """
        cpu_usage = max(0.0, min(1.0, cpu_usage))
        memory_usage = max(0.0, min(1.0, memory_usage))
        ai_performance = max(0.0, ai_performance)

        # Coinbits reflect overall AI health
        self._prices["Coinbits"] = max(MIN_PRICE_FLOOR, ai_performance)

        # ThreadBits and CoreBits become more valuable when CPU is scarce
        scarcity_cpu = 1.0 + cpu_usage  # [1, 2]
        self._prices["ThreadBits"] = round(scarcity_cpu, 6)
        self._prices["CoreBits"] = round(1.0 + cpu_usage * 0.5, 6)

        # BufferBits reflect memory pressure
        self._prices["BufferBits"] = round(1.0 + memory_usage, 6)

        return self._record_tick()

    def inject_recycled_liquidity(self, amount: float) -> None:
        """Feed recycled-metadata value into the exchange's liquidity pool.

        This is the connection point for the metadata recycling engine.
        The injected *amount* raises the Coinbits price slightly, simulating
        a supply of "mined" tokens entering the market.

        Parameters
        ----------
        amount:
            Non-negative float representing the recycled value.
        """
        if amount < 0:
            raise ValueError(f"Liquidity amount must be non-negative, got {amount}")
        self._recycled_liquidity += amount
        # A small, diminishing boost: log(1 + recycled)
        boost = math.log1p(self._recycled_liquidity) * LIQUIDITY_BOOST_FACTOR
        self._prices["Coinbits"] = max(MIN_PRICE_FLOOR, self._prices["Coinbits"] + boost)
        self._record_tick()

    def snapshot(self) -> Dict[str, float]:
        """Return current prices as a plain dict (currency → price)."""
        return self.prices

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_tick(self) -> MarketTick:
        tick = MarketTick(
            timestamp=time.time(),
            prices=dict(self._prices),
            liquidity=self._recycled_liquidity,
        )
        self._history.append(tick)
        return tick

    def __repr__(self) -> str:
        prices_str = ", ".join(
            f"{name}={price:.4f}" for name, price in self._prices.items()
        )
        return f"InternalMarket({prices_str})"
