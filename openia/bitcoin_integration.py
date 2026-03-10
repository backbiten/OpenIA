"""
bitcoin_integration.py — Bitcoin → TransactionLog bridge (S2 address-based).

OpenIA can use a running **Bitcoin Core** (``bitcoind``) node as an optional
source of "coinbit" signals that populate the shared
:class:`~openia.transaction.TransactionLog`.

Judgment encoding — S2 (address-based)
---------------------------------------
* Transactions **to** an address listed in ``OPENIA_APPROVE_ADDRESSES_BTC``
  → ``noise = +1.0`` (approval).
* Transactions **to** an address listed in ``OPENIA_DISAPPROVE_ADDRESSES_BTC``
  → ``noise = -1.0`` (disapproval).
* Transactions to any other address are ignored (no ``TransactionLog`` entry).

``value`` is always the transaction amount in BTC (float).

Dependency notes
----------------
``backbiten/bitcoin`` (https://github.com/backbiten/bitcoin.git,
commit d30f149360d10de31bd7f7369aa61ce8be0837b5) is Bitcoin Core — a C++
daemon — and **cannot** be installed as a Python package.  OpenIA therefore
communicates with a running ``bitcoind`` node via the Bitcoin Core JSON-RPC
API, using the ``requests`` library.

Install with: ``pip install "openia[bitcoin]"`` or ``pip install requests``.

If ``requests`` is not available, :func:`sync_from_bitcoin` raises an
:exc:`ImportError` with a clear message.  The rest of OpenIA is unaffected.

Environment variables
---------------------
==================================  ==========================================
Variable                            Description
==================================  ==========================================
``BITCOIN_RPC_URL``                 Full URL of the ``bitcoind`` RPC endpoint
                                    (default: ``http://127.0.0.1:8332``)
``BITCOIN_RPC_USER``                RPC username (default: ``bitcoin``)
``BITCOIN_RPC_PASS``                RPC password (default: *(empty)*)
``BITCOIN_RPC_WALLET``              Wallet name to load (optional); when set,
                                    requests target
                                    ``/wallet/<name>`` sub-endpoint
``OPENIA_APPROVE_ADDRESSES_BTC``    Comma-separated BTC addresses that signal
                                    **approval** (noise = +1)
``OPENIA_DISAPPROVE_ADDRESSES_BTC`` Comma-separated BTC addresses that signal
                                    **disapproval** (noise = -1)
==================================  ==========================================
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .transaction import TransactionLog

# ---------------------------------------------------------------------------
# Optional dependency detection
# ---------------------------------------------------------------------------

_REQUESTS_AVAILABLE: bool = False

try:
    import requests as _requests  # type: ignore[import]

    _REQUESTS_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Internal constants and helpers
# ---------------------------------------------------------------------------

_DEFAULT_RPC_URL = "http://127.0.0.1:8332"
_RPC_ID = "openia"


def _get_rpc_config() -> dict:
    """Read RPC configuration from environment variables."""
    return {
        "url": os.environ.get("BITCOIN_RPC_URL", _DEFAULT_RPC_URL),
        "user": os.environ.get("BITCOIN_RPC_USER", "bitcoin"),
        "password": os.environ.get("BITCOIN_RPC_PASS", ""),
        "wallet": os.environ.get("BITCOIN_RPC_WALLET", ""),
    }


def _get_address_sets() -> tuple[set[str], set[str]]:
    """Return (approve_addresses, disapprove_addresses) from env vars."""
    raw_approve = os.environ.get("OPENIA_APPROVE_ADDRESSES_BTC", "")
    raw_disapprove = os.environ.get("OPENIA_DISAPPROVE_ADDRESSES_BTC", "")
    approve = {a.strip() for a in raw_approve.split(",") if a.strip()}
    disapprove = {a.strip() for a in raw_disapprove.split(",") if a.strip()}
    return approve, disapprove


def _classify_address(address: str, approve: set[str], disapprove: set[str]) -> Optional[float]:
    """Return +1.0, -1.0, or None based on address classification."""
    if address in approve:
        return 1.0
    if address in disapprove:
        return -1.0
    return None


# ---------------------------------------------------------------------------
# Bitcoin Core JSON-RPC adapter
# ---------------------------------------------------------------------------


def _rpc_call(cfg: dict, method: str, params: list) -> object:
    """Execute a single JSON-RPC call against ``bitcoind``.

    Parameters
    ----------
    cfg:
        RPC configuration dict from :func:`_get_rpc_config`.
    method:
        Bitcoin Core RPC method name.
    params:
        Positional parameters for the method.

    Raises
    ------
    ImportError
        If the ``requests`` package is not installed.
    RuntimeError
        If the RPC server returns an error payload.
    requests.HTTPError
        If the HTTP response carries a non-2xx status code.
    """
    if not _REQUESTS_AVAILABLE:
        raise ImportError(
            "The 'requests' package is required for the Bitcoin RPC adapter.  "
            "Install it with: pip install requests"
        )

    url = cfg["url"]
    if cfg["wallet"]:
        url = url.rstrip("/") + f"/wallet/{cfg['wallet']}"

    payload = {
        "jsonrpc": "1.1",
        "id": _RPC_ID,
        "method": method,
        "params": params,
    }

    response = _requests.post(
        url,
        json=payload,
        auth=(cfg["user"], cfg["password"]),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("error") is not None:
        raise RuntimeError(f"Bitcoin RPC error: {data['error']}")

    return data.get("result")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_from_bitcoin(
    log: "TransactionLog",
    *,
    min_confirmations: int = 1,
    count: int = 100,
) -> List[dict]:
    """Fetch recent Bitcoin wallet transactions and submit them to *log*.

    Only transactions whose output address is listed in
    ``OPENIA_APPROVE_ADDRESSES_BTC`` or ``OPENIA_DISAPPROVE_ADDRESSES_BTC``
    are processed (S2 address-based encoding):

    * **Approve address** → ``noise = +1.0``
    * **Disapprove address** → ``noise = -1.0``

    The transaction ``value`` submitted to the log is the BTC amount as a
    float (``amount`` field from Bitcoin Core ``listtransactions``).

    Uses Bitcoin Core's ``listtransactions`` RPC method.

    Parameters
    ----------
    log:
        The :class:`~openia.transaction.TransactionLog` to populate.
    min_confirmations:
        Minimum on-chain confirmations before a transaction is accepted.
    count:
        Number of recent transactions to fetch per RPC call
        (Bitcoin Core default: 10; maximum: no hard limit).

    Returns
    -------
    list[dict]
        Records of submitted transactions (``txid``, ``amount_btc``,
        ``address``, ``noise``).

    Raises
    ------
    ImportError
        If the ``requests`` library is not installed.
    RuntimeError
        If the Bitcoin Core RPC returns an error.
    """
    if not _REQUESTS_AVAILABLE:
        raise ImportError(
            "Bitcoin integration requires the 'requests' library.  "
            "Install it with: pip install requests"
        )

    cfg = _get_rpc_config()
    approve, disapprove = _get_address_sets()

    # listtransactions "*" count skip include_watchonly
    txs = _rpc_call(cfg, "listtransactions", ["*", count, 0, True])
    if not isinstance(txs, list):
        txs = []

    records: List[dict] = []
    for tx in txs:
        if tx.get("category") not in ("receive",):
            continue
        if tx.get("confirmations", 0) < min_confirmations:
            continue

        address = tx.get("address", "")
        noise = _classify_address(address, approve, disapprove)
        if noise is None:
            continue

        amount_btc = float(tx.get("amount", 0.0))
        log.submit(value=amount_btc, noise=noise)
        records.append(
            {
                "txid": tx.get("txid", ""),
                "amount_btc": amount_btc,
                "address": address,
                "noise": noise,
            }
        )

    return records
