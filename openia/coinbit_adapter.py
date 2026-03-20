"""
coinbit_adapter.py — Simple coinbit ↔ Bitcoin compatibility adapter.

Coinbits are a lightweight off-chain payment unit — a "cheaper version of
Bitcoin" — where 1 coinbit maps to a fixed number of satoshis
(:data:`COINBIT_TO_SATOSHIS`).  This module provides:

1. **Conversion helpers** — :func:`coinbits_to_satoshis` turns a coinbit
   amount into integer satoshis (floor-rounded, non-negative).

2. **Event ingestion** — :func:`ingest_coinbit_events` validates a list of
   raw coinbit event dicts, normalises them into :class:`CoinbitEvent`
   objects, converts amounts, and appends :class:`~openia.transaction.Transaction`
   entries to a shared :class:`~openia.transaction.TransactionLog`.

3. **Batched settlement** — :func:`batch_settle_to_btc` aggregates
   per-merchant coinbit receipts and, when a threshold is reached, either
   *simulates* a Bitcoin txid (dry-run / default) or calls Bitcoin Core
   JSON-RPC ``sendtoaddress`` (when *requests* is available and
   ``dry_run=False``).  An in-memory :data:`_coinbit_to_btc_map` records
   the coinbit-txid → btc-txid mapping.

Usage example
-------------
::

    from openia import TransactionLog
    from openia.coinbit_adapter import ingest_coinbit_events, batch_settle_to_btc

    log = TransactionLog()

    events = [
        {"txid": "cb-001", "amount_coinbits": 50.0,
         "sender": "alice", "receiver": "merchant-A",
         "btc_address": "bc1qmerchant..."},
    ]
    records = ingest_coinbit_events(log, events)

    unsettled = {"merchant-A": records}
    settlements = batch_settle_to_btc(unsettled, threshold_sats=1000, dry_run=True)
    # [{'merchant': 'merchant-A', 'total_sats': 5000, 'btc_txid': 'simulated-btc-...', ...}]

Caveats / production notes
---------------------------
* The ``_coinbit_to_btc_map`` is **in-memory only** — persist it to a
  database in production to survive restarts and enable reconciliation.
* Fee estimation and UTXO selection are omitted; production settlement
  should subtract the estimated miner fee from ``btc_amount_btc``.
* Rounding uses ``math.floor``; any fractional satoshi is lost.  For
  high-volume systems track the accumulated rounding error and compensate
  periodically.
* ``dry_run=False`` with a real RPC node requires the ``requests`` package
  (``pip install requests``) and a running ``bitcoind`` daemon with RPC
  credentials.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import requests  # optional — only used for live BTC settlement
except ImportError:
    requests = None  # type: ignore[assignment]

from .transaction import TransactionLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Number of satoshis per 1 coinbit (integer).  Adjust to reflect the
#: desired market-parity or platform policy.
COINBIT_TO_SATOSHIS: int = 100

# In-memory mapping: coinbit_txid → btc_txid.
# Persisting this to a database is required in production.
_coinbit_to_btc_map: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CoinbitEvent:
    """Normalised representation of a single coinbit payment event.

    Parameters
    ----------
    txid:
        Unique identifier for this coinbit transaction.
    amount_coinbits:
        Payment amount expressed in coinbits.
    sender:
        Sending party identifier (wallet address, username, etc.).
    receiver:
        Receiving party identifier.
    timestamp:
        Optional Unix epoch timestamp of the event.
    memo:
        Optional free-text memo attached to the payment.
    """

    txid: str
    amount_coinbits: float
    sender: str
    receiver: str
    timestamp: Optional[float] = None
    memo: Optional[str] = None


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def coinbits_to_satoshis(amount_coinbits: float) -> int:
    """Convert a coinbit amount to integer satoshis (floor-rounded, ≥ 0).

    Parameters
    ----------
    amount_coinbits:
        Amount in coinbits (may be fractional).

    Returns
    -------
    int
        Equivalent satoshis, floored to the nearest integer.  Negative
        inputs are clamped to ``0``.

    Examples
    --------
    >>> coinbits_to_satoshis(1.0)
    100
    >>> coinbits_to_satoshis(0.5)
    50
    >>> coinbits_to_satoshis(0.004)
    0
    """
    return max(int(math.floor(amount_coinbits * COINBIT_TO_SATOSHIS)), 0)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def ingest_coinbit_events(
    log: TransactionLog,
    events: List[Dict],
    *,
    submit_in_sats: bool = True,
) -> List[Dict]:
    """Validate and ingest a list of coinbit event dicts into *log*.

    Each dict in *events* must supply at least ``txid`` and
    ``amount_coinbits``.  Optional keys: ``sender``, ``receiver``,
    ``timestamp``, ``memo``, ``btc_address``.

    Invalid or malformed events are skipped with a warning log message;
    they never raise an exception.

    Parameters
    ----------
    log:
        The :class:`~openia.transaction.TransactionLog` to populate.
    events:
        Raw coinbit event dicts.
    submit_in_sats:
        When ``True`` (default), the value recorded in *log* is the
        satoshi equivalent of the coinbit amount.  When ``False``, the
        raw coinbit amount is recorded instead.

    Returns
    -------
    list[dict]
        One record per successfully ingested event, containing:
        ``coinbit_txid``, ``amount_coinbits``, ``amount_sats``,
        ``submit_value``, ``sender``, ``receiver``.  Pass-through fields
        (e.g. ``btc_address``) are included when present in the source
        event.
    """
    records: List[Dict] = []
    for ev in events:
        try:
            cb = CoinbitEvent(
                txid=str(ev["txid"]),
                amount_coinbits=float(ev["amount_coinbits"]),
                sender=str(ev.get("sender", "")),
                receiver=str(ev.get("receiver", "")),
                timestamp=ev.get("timestamp"),
                memo=ev.get("memo"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping invalid coinbit event: %s", exc)
            continue

        sats = coinbits_to_satoshis(cb.amount_coinbits)
        submit_value = float(sats) if submit_in_sats else cb.amount_coinbits
        log.submit(value=submit_value, noise=None)

        record: Dict = {
            "coinbit_txid": cb.txid,
            "amount_coinbits": cb.amount_coinbits,
            "amount_sats": sats,
            "submit_value": submit_value,
            "sender": cb.sender,
            "receiver": cb.receiver,
        }
        # Pass through btc_address so batch_settle_to_btc can find it later.
        if "btc_address" in ev:
            record["btc_address"] = ev["btc_address"]
        records.append(record)

    return records


# ---------------------------------------------------------------------------
# Batched settlement
# ---------------------------------------------------------------------------


def _get_btc_rpc_cfg(cfg: Optional[Dict]) -> Dict:
    """Return a normalised RPC config dict.

    Expected keys: ``url``, ``user``, ``password``, ``wallet``.
    Missing keys fall back to safe defaults (localhost, no auth, no wallet).
    """
    cfg = cfg or {}
    return {
        "url": cfg.get("url", "http://127.0.0.1:8332"),
        "user": cfg.get("user", None),
        "password": cfg.get("password", None),
        "wallet": cfg.get("wallet", ""),
    }


def batch_settle_to_btc(
    unsettled_by_merchant: Dict[str, List[Dict]],
    *,
    threshold_sats: int = 10_000,
    rpc_cfg: Optional[Dict] = None,
    dry_run: bool = True,
) -> List[Dict]:
    """Aggregate per-merchant coinbit receipts and settle to Bitcoin.

    For each merchant in *unsettled_by_merchant*:

    1. Sum the ``amount_sats`` across all records.
    2. Skip if the total is below *threshold_sats* or no ``btc_address``
       is available.
    3. Either simulate a Bitcoin txid (``dry_run=True``, default) or call
       Bitcoin Core RPC ``sendtoaddress`` (``dry_run=False``).
    4. Record the coinbit-txid → btc-txid mapping in
       :data:`_coinbit_to_btc_map`.

    Parameters
    ----------
    unsettled_by_merchant:
        Mapping of ``merchant_id`` → list of records produced by
        :func:`ingest_coinbit_events`.
    threshold_sats:
        Minimum aggregate satoshi balance that triggers settlement.
    rpc_cfg:
        Optional Bitcoin Core RPC configuration dict (keys: ``url``,
        ``user``, ``password``, ``wallet``).  Ignored in dry-run mode.
    dry_run:
        When ``True`` (default), no network call is made and a
        deterministic simulated txid is returned instead.

    Returns
    -------
    list[dict]
        Settlement records for merchants that met the threshold, each
        containing: ``merchant``, ``total_sats``, ``btc_txid``,
        ``coinbit_txids``, ``dest_address``.

    Notes
    -----
    * Live RPC calls require the ``requests`` package.  If ``requests`` is
      not installed, settlement falls back to dry-run mode regardless of
      the *dry_run* flag.
    * Production deployments should persist :data:`_coinbit_to_btc_map` to
      a database to survive process restarts and support reconciliation.
    """
    results: List[Dict] = []
    cfg = _get_btc_rpc_cfg(rpc_cfg)

    for merchant, records in unsettled_by_merchant.items():
        total_sats = sum(int(r["amount_sats"]) for r in records)
        coinbit_txids = [r["coinbit_txid"] for r in records]

        if total_sats < threshold_sats:
            logger.debug(
                "Merchant %s total %d sats below threshold %d — skipping",
                merchant,
                total_sats,
                threshold_sats,
            )
            continue

        dest_address: Optional[str] = None
        for r in records:
            dest_address = r.get("btc_address") or None
            if dest_address:
                break

        if not dest_address:
            logger.warning(
                "No destination BTC address for merchant %s — skip settlement",
                merchant,
            )
            continue

        btc_amount_btc = total_sats / 1e8  # satoshis → BTC

        if dry_run or requests is None:
            btc_txid = f"simulated-btc-{merchant}-{total_sats}"
            logger.info(
                "Dry-run settlement for %s → %s (%d sats)",
                merchant,
                dest_address,
                total_sats,
            )
        else:
            # Real settlement via Bitcoin Core JSON-RPC.
            # Production: add fee estimation, UTXO selection, retry logic.
            url = cfg["url"].rstrip("/")
            if cfg["wallet"]:
                url = f"{url}/wallet/{cfg['wallet']}"
            payload = {
                "jsonrpc": "1.1",
                "id": "coinbit-settle",
                "method": "sendtoaddress",
                "params": [dest_address, btc_amount_btc],
            }
            resp = requests.post(
                url,
                json=payload,
                auth=(cfg["user"], cfg["password"]),
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise RuntimeError(f"BTC RPC error: {data['error']}")
            btc_txid = data.get("result")

        for txid in coinbit_txids:
            _coinbit_to_btc_map[txid] = btc_txid

        results.append(
            {
                "merchant": merchant,
                "total_sats": total_sats,
                "btc_txid": btc_txid,
                "coinbit_txids": coinbit_txids,
                "dest_address": dest_address,
            }
        )

    return results
