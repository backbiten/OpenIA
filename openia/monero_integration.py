"""
monero_integration.py — Monero → TransactionLog bridge (S2 address-based).

OpenIA can use a running ``monero-wallet-rpc`` daemon as an optional source of
"coinbit" signals that populate the shared
:class:`~openia.transaction.TransactionLog`.

Judgment encoding — S2 (address-based)
---------------------------------------
* Transfers **to** an address listed in ``OPENIA_APPROVE_ADDRESSES_XMR``
  → ``noise = +1.0`` (approval).
* Transfers **to** an address listed in ``OPENIA_DISAPPROVE_ADDRESSES_XMR``
  → ``noise = -1.0`` (disapproval).
* Transfers to any other address are ignored (no ``TransactionLog`` entry).

``value`` is always the transfer amount in XMR (float).

Dependency notes
----------------
``backbiten/monero`` (https://github.com/backbiten/monero.git, tag v0.18.4.3)
is the official Monero C++ daemon and **cannot** be installed as a Python
package.  Two Python integration paths are therefore provided, in priority
order:

1. **monero** (PyPI) — a pure-Python wallet-RPC client.
   Install with ``pip install "openia[monero]"`` or ``pip install monero``.
2. **requests fallback** — a minimal JSON-RPC adapter that communicates
   directly with ``monero-wallet-rpc`` over HTTP.
   Install with ``pip install requests``.

If neither dependency is available, :func:`sync_from_monero` raises an
:exc:`ImportError` with a clear message.  The rest of OpenIA is unaffected.

Environment variables
---------------------
=================================  ==========================================
Variable                           Description
=================================  ==========================================
``MONERO_WALLET_RPC_URL``          Wallet-RPC endpoint
                                   (default: ``http://127.0.0.1:18083/json_rpc``)
``MONERO_WALLET_RPC_USER``         Digest-auth username (optional)
``MONERO_WALLET_RPC_PASS``         Digest-auth password (optional)
``MONERO_WALLET_ACCOUNT``          Account index to query (default: ``0``)
``OPENIA_APPROVE_ADDRESSES_XMR``   Comma-separated list of Monero addresses
                                   that signal **approval** (noise = +1)
``OPENIA_DISAPPROVE_ADDRESSES_XMR`` Comma-separated list of Monero addresses
                                   that signal **disapproval** (noise = -1)
=================================  ==========================================
"""

from __future__ import annotations

import os
import urllib.parse
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .transaction import TransactionLog

# ---------------------------------------------------------------------------
# Optional dependency detection
# ---------------------------------------------------------------------------

_MONERO_LIB_AVAILABLE: bool = False
_REQUESTS_AVAILABLE: bool = False

_Wallet = None
_JSONRPCWallet = None

try:
    from monero.wallet import Wallet as _Wallet  # type: ignore[import]
    from monero.backends.jsonrpc import JSONRPCWallet as _JSONRPCWallet  # type: ignore[import]

    _MONERO_LIB_AVAILABLE = True
except ImportError:
    pass

try:
    import requests as _requests  # type: ignore[import]

    _REQUESTS_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Internal constants and helpers
# ---------------------------------------------------------------------------

_DEFAULT_RPC_URL = "http://127.0.0.1:18083/json_rpc"
_PICONERO = 1_000_000_000_000  # 1 XMR = 1e12 piconeros


def _get_rpc_config() -> dict:
    """Read RPC configuration from environment variables."""
    return {
        "url": os.environ.get("MONERO_WALLET_RPC_URL", _DEFAULT_RPC_URL),
        "user": os.environ.get("MONERO_WALLET_RPC_USER", ""),
        "password": os.environ.get("MONERO_WALLET_RPC_PASS", ""),
        "account_index": int(os.environ.get("MONERO_WALLET_ACCOUNT", "0")),
    }


def _get_address_sets() -> tuple[set[str], set[str]]:
    """Return (approve_addresses, disapprove_addresses) from env vars."""
    raw_approve = os.environ.get("OPENIA_APPROVE_ADDRESSES_XMR", "")
    raw_disapprove = os.environ.get("OPENIA_DISAPPROVE_ADDRESSES_XMR", "")
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
# Requests-based fallback RPC adapter
# ---------------------------------------------------------------------------


def _rpc_call(
    url: str,
    method: str,
    params: dict,
    user: str = "",
    password: str = "",
) -> dict:
    """Execute a single JSON-RPC 2.0 call against ``monero-wallet-rpc``.

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
            "The 'requests' package is required for the fallback Monero RPC "
            "adapter.  Install it with: pip install requests"
        )

    payload = {"jsonrpc": "2.0", "id": "0", "method": method, "params": params}
    auth = None
    if user:
        from requests.auth import HTTPDigestAuth  # type: ignore[import]

        auth = HTTPDigestAuth(user, password)

    response = _requests.post(url, json=payload, auth=auth, timeout=30)
    response.raise_for_status()
    data = response.json()

    if data.get("error") is not None:
        raise RuntimeError(f"Monero RPC error: {data['error']}")

    return data.get("result", {})


def _sync_via_requests(
    log: "TransactionLog",
    cfg: dict,
    min_confirmations: int,
    max_transfers: Optional[int],
    approve: set[str],
    disapprove: set[str],
) -> List[dict]:
    """Fetch transfers via the raw JSON-RPC adapter and populate *log*."""
    params: dict = {
        "account_index": cfg["account_index"],
        "in": True,
        "out": False,
        "pending": min_confirmations == 0,
        "failed": False,
        "pool": min_confirmations == 0,
        "filter_by_height": False,
    }

    result = _rpc_call(
        url=cfg["url"],
        method="get_transfers",
        params=params,
        user=cfg["user"],
        password=cfg["password"],
    )

    transfers: List[dict] = []
    for key in ("in", "pending", "pool"):
        transfers.extend(result.get(key, []))

    if max_transfers is not None:
        transfers = transfers[:max_transfers]

    records: List[dict] = []
    for tx in transfers:
        confirmations = tx.get("confirmations", 0)
        if confirmations < min_confirmations:
            continue

        address = tx.get("address", "")
        noise = _classify_address(address, approve, disapprove)
        if noise is None:
            continue

        amount_xmr = tx.get("amount", 0) / _PICONERO
        log.submit(value=amount_xmr, noise=noise)
        records.append(
            {
                "txid": tx.get("txid", ""),
                "amount_xmr": amount_xmr,
                "address": address,
                "noise": noise,
            }
        )

    return records


# ---------------------------------------------------------------------------
# monero (PyPI) library adapter
# ---------------------------------------------------------------------------


def _sync_via_monero_lib(
    log: "TransactionLog",
    cfg: dict,
    min_confirmations: int,
    max_transfers: Optional[int],
    approve: set[str],
    disapprove: set[str],
) -> List[dict]:
    """Fetch transfers via the Python ``monero`` library and populate *log*."""
    parsed = urllib.parse.urlparse(cfg["url"])
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 18083

    kwargs: dict = {"host": host, "port": port}
    if cfg["user"]:
        kwargs["user"] = cfg["user"]
        kwargs["password"] = cfg["password"]

    wallet = _Wallet(_JSONRPCWallet(**kwargs))

    incoming = list(wallet.incoming())

    if max_transfers is not None:
        incoming = incoming[:max_transfers]

    records: List[dict] = []
    for payment in incoming:
        confirmations = getattr(
            getattr(payment, "transaction", None), "confirmations", None
        )
        if confirmations is not None and confirmations < min_confirmations:
            continue

        address = str(getattr(payment, "local_address", "") or "")
        noise = _classify_address(address, approve, disapprove)
        if noise is None:
            continue

        amount_xmr = float(payment.amount)
        log.submit(value=amount_xmr, noise=noise)

        txid = ""
        tx = getattr(payment, "transaction", None)
        if tx is not None:
            txid = str(getattr(tx, "hash", ""))

        records.append(
            {
                "txid": txid,
                "amount_xmr": amount_xmr,
                "address": address,
                "noise": noise,
            }
        )

    return records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_from_monero(
    log: "TransactionLog",
    *,
    min_confirmations: int = 1,
    max_transfers: Optional[int] = None,
) -> List[dict]:
    """Fetch recent Monero wallet transfers and submit them to *log*.

    Only transfers to addresses listed in ``OPENIA_APPROVE_ADDRESSES_XMR`` or
    ``OPENIA_DISAPPROVE_ADDRESSES_XMR`` are processed (S2 address-based
    encoding):

    * **Approve address** → ``noise = +1.0``
    * **Disapprove address** → ``noise = -1.0``

    The transfer ``value`` submitted to the log is the XMR amount as a float.

    Parameters
    ----------
    log:
        The :class:`~openia.transaction.TransactionLog` to populate.
    min_confirmations:
        Minimum on-chain confirmations before a transfer is accepted.
    max_transfers:
        If set, only process the first *N* transfers.

    Returns
    -------
    list[dict]
        Records of submitted transactions (``txid``, ``amount_xmr``,
        ``address``, ``noise``).

    Raises
    ------
    ImportError
        If neither the ``monero`` library nor ``requests`` is installed.
    """
    if not _MONERO_LIB_AVAILABLE and not _REQUESTS_AVAILABLE:
        raise ImportError(
            "Monero integration requires either the 'monero' library "
            "(pip install monero) or the 'requests' library "
            "(pip install requests).  Neither is currently installed."
        )

    cfg = _get_rpc_config()
    approve, disapprove = _get_address_sets()

    if _MONERO_LIB_AVAILABLE:
        return _sync_via_monero_lib(log, cfg, min_confirmations, max_transfers, approve, disapprove)
    return _sync_via_requests(log, cfg, min_confirmations, max_transfers, approve, disapprove)
