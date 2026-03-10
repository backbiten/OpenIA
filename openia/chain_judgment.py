"""
chain_judgment.py — Unified Bitcoin + Monero → TransactionLog judgment.

This module provides a single entry point (:func:`run_chain_judgment`) that
pulls transactions from **both** Bitcoin (BTC) and Monero (XMR) chains and
applies S2 address-based judgment rules to populate a shared
:class:`~openia.transaction.TransactionLog`.

Judgment encoding — S2 (address-based)
---------------------------------------
For each chain, two sets of addresses are read from environment variables:

* **BTC approve addresses** (``OPENIA_APPROVE_ADDRESSES_BTC``) →
  transactions received at these addresses submit ``noise = +1.0``
* **BTC disapprove addresses** (``OPENIA_DISAPPROVE_ADDRESSES_BTC``) →
  transactions received at these addresses submit ``noise = -1.0``
* **XMR approve addresses** (``OPENIA_APPROVE_ADDRESSES_XMR``) →
  transfers received at these addresses submit ``noise = +1.0``
* **XMR disapprove addresses** (``OPENIA_DISAPPROVE_ADDRESSES_XMR``) →
  transfers received at these addresses submit ``noise = -1.0``

``value`` is always the transaction amount (BTC or XMR) as a float.

Each chain adapter is optional — if neither the required libraries nor
``requests`` are available, the adapter is silently skipped and a warning
is included in the returned report.  The core OpenIA package remains fully
functional regardless of blockchain configuration.

Environment variables
---------------------
See :mod:`openia.bitcoin_integration` and :mod:`openia.monero_integration`
for the full list of per-chain environment variables.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .transaction import TransactionLog

logger = logging.getLogger(__name__)


def run_chain_judgment(
    log: "TransactionLog",
    *,
    btc_min_confirmations: int = 1,
    btc_count: int = 100,
    xmr_min_confirmations: int = 1,
    xmr_max_transfers: Optional[int] = None,
    skip_btc: bool = False,
    skip_xmr: bool = False,
) -> Dict[str, object]:
    """Pull BTC and XMR transactions and apply S2 judgment to *log*.

    Parameters
    ----------
    log:
        The shared :class:`~openia.transaction.TransactionLog` to populate.
    btc_min_confirmations:
        Minimum Bitcoin confirmations before a transaction is accepted.
    btc_count:
        Maximum number of recent Bitcoin transactions to inspect per call.
    xmr_min_confirmations:
        Minimum Monero confirmations before a transfer is accepted.
    xmr_max_transfers:
        Maximum number of Monero transfers to inspect (``None`` = no limit).
    skip_btc:
        If ``True``, skip the Bitcoin adapter entirely.
    skip_xmr:
        If ``True``, skip the Monero adapter entirely.

    Returns
    -------
    dict
        Report with keys:

        * ``"btc_records"`` — list of BTC transaction dicts submitted to log
        * ``"xmr_records"`` — list of XMR transfer dicts submitted to log
        * ``"btc_error"``   — error message string if BTC adapter failed, else ``None``
        * ``"xmr_error"``   — error message string if XMR adapter failed, else ``None``
    """
    report: Dict[str, object] = {
        "btc_records": [],
        "xmr_records": [],
        "btc_error": None,
        "xmr_error": None,
    }

    # ------------------------------------------------------------------
    # Bitcoin
    # ------------------------------------------------------------------
    if not skip_btc:
        try:
            from .bitcoin_integration import sync_from_bitcoin  # noqa: PLC0415

            btc_records = sync_from_bitcoin(
                log,
                min_confirmations=btc_min_confirmations,
                count=btc_count,
            )
            report["btc_records"] = btc_records
            logger.debug("BTC: submitted %d record(s) to TransactionLog", len(btc_records))
        except ImportError as exc:
            report["btc_error"] = str(exc)
            logger.warning("BTC adapter unavailable: %s", exc)
        except Exception as exc:  # noqa: BLE001
            report["btc_error"] = str(exc)
            logger.error("BTC sync failed: %s", exc)

    # ------------------------------------------------------------------
    # Monero
    # ------------------------------------------------------------------
    if not skip_xmr:
        try:
            from .monero_integration import sync_from_monero  # noqa: PLC0415

            xmr_records = sync_from_monero(
                log,
                min_confirmations=xmr_min_confirmations,
                max_transfers=xmr_max_transfers,
            )
            report["xmr_records"] = xmr_records
            logger.debug("XMR: submitted %d record(s) to TransactionLog", len(xmr_records))
        except ImportError as exc:
            report["xmr_error"] = str(exc)
            logger.warning("XMR adapter unavailable: %s", exc)
        except Exception as exc:  # noqa: BLE001
            report["xmr_error"] = str(exc)
            logger.error("XMR sync failed: %s", exc)

    return report
