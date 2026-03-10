"""
monero_integration.py — Monero → TransactionLog bridge.

OpenIA can use a running ``monero-wallet-rpc`` daemon as a source of
"coinbit" signals that populate the shared
:class:`~openia.transaction.TransactionLog`.

Dependency notes
----------------
``backbiten/monero`` (https://github.com/backbiten/monero.git, tag v0.18.4.3)
is the official Monero C++ daemon and cannot be installed as a Python package
directly.  Two Python integration paths are therefore provided, in priority
order:

1. **monero** (PyPI) — a pure-Python wallet-RPC client.
   Install with ``pip install "openia[monero]"`` or ``pip install monero``.
   Source: https://pypi.org/project/monero/

2. **requests fallback** — a minimal JSON-RPC adapter that communicates
   directly with ``monero-wallet-rpc`` over HTTP without any additional
   Python package beyond ``requests``.
   Install with ``pip install requests``.

Both paths are optional.  If neither ``monero`` nor ``requests`` is
available, calling :func:`sync_from_monero` raises an :exc:`ImportError`
with a descriptive message.

Environment variables
---------------------
============================  ==============================================
Variable                      Description
============================  ==============================================
``MONERO_WALLET_RPC_URL``     Full URL of the wallet-RPC endpoint
                              (default: ``http://127.0.0.1:18083/json_rpc``)
``MONERO_WALLET_RPC_USER``    Digest-auth username (optional)
``MONERO_WALLET_RPC_PASS``    Digest-auth password (optional)
``MONERO_WALLET_ACCOUNT``     Account index to query (default: ``0``)
============================  ==============================================
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

# Always define these names so that tests can patch them even when the monero
# library is not installed.
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


def _amount_to_noise(amount_xmr: float, direction: str = "in") -> float:
    """Map an XMR amount and direction to a noise signal in *[-1, 1]*.

    Incoming transfers produce positive noise (approval signal); outgoing
    transfers produce negative noise (cost/disapproval signal).  The
    magnitude saturates at ±1 for transfers of ≥ 1 XMR.
    """
    magnitude = min(abs(amount_xmr), 1.0)
    return magnitude if direction == "in" else -magnitude


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

    if "error" in data:
        raise RuntimeError(f"Monero RPC error: {data['error']}")

    return data.get("result", {})


def _sync_via_requests(
    log: "TransactionLog",
    cfg: dict,
    min_confirmations: int,
    include_outgoing: bool,
    max_transfers: Optional[int],
) -> List[dict]:
    """Fetch transfers via the raw JSON-RPC adapter and populate *log*."""
    params: dict = {
        "account_index": cfg["account_index"],
        "in": True,
        "out": include_outgoing,
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

    records: List[dict] = []
    transfers: List[dict] = []

    for key in ("in", "out", "pending", "pool"):
        transfers.extend(result.get(key, []))

    if max_transfers is not None:
        transfers = transfers[:max_transfers]

    for tx in transfers:
        confirmations = tx.get("confirmations", 0)
        if confirmations < min_confirmations:
            continue

        amount_xmr = tx.get("amount", 0) / _PICONERO
        direction = "in" if tx.get("type") in ("in", "pending", "pool") else "out"
        noise = _amount_to_noise(amount_xmr, direction)

        log.submit(value=amount_xmr, noise=noise)
        records.append(
            {
                "txid": tx.get("txid", ""),
                "amount_xmr": amount_xmr,
                "direction": direction,
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
    include_outgoing: bool,
    max_transfers: Optional[int],
) -> List[dict]:
    """Fetch transfers via the Python ``monero`` library and populate *log*."""
    parsed = urllib.parse.urlparse(cfg["url"])
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 18083

    kwargs: dict = {
        "host": host,
        "port": port,
    }
    if cfg["user"]:
        kwargs["user"] = cfg["user"]
        kwargs["password"] = cfg["password"]

    wallet = _Wallet(_JSONRPCWallet(**kwargs))

    records: List[dict] = []

    # Collect incoming transfers
    incoming = list(wallet.incoming())
    transfers: List[tuple] = [("in", tx) for tx in incoming]

    if include_outgoing:
        outgoing = list(wallet.outgoing())
        transfers.extend(("out", tx) for tx in outgoing)

    if max_transfers is not None:
        transfers = transfers[:max_transfers]

    for direction, payment in transfers:
        # payment.transaction.confirmations may not always be present
        confirmations = getattr(
            getattr(payment, "transaction", None), "confirmations", None
        )
        if confirmations is not None and confirmations < min_confirmations:
            continue

        amount_xmr = float(payment.amount)
        noise = _amount_to_noise(amount_xmr, direction)

        log.submit(value=amount_xmr, noise=noise)
        txid = ""
        tx = getattr(payment, "transaction", None)
        if tx is not None:
            txid = str(getattr(tx, "hash", ""))

        records.append(
            {
                "txid": txid,
                "amount_xmr": amount_xmr,
                "direction": direction,
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
    include_outgoing: bool = False,
    max_transfers: Optional[int] = None,
) -> List[dict]:
    """Fetch recent Monero wallet transfers and submit them to *log*.

    Each transfer is converted into a
    :class:`~openia.transaction.Transaction` entry:

    * **Incoming** transfers produce *positive* noise proportional to their
      XMR amount (capped at +1).
    * **Outgoing** transfers (when *include_outgoing* is ``True``) produce
      *negative* noise.

    Uses the Python ``monero`` library if available, otherwise falls back to
    a ``requests``-based JSON-RPC adapter.

    Parameters
    ----------
    log:
        The :class:`~openia.transaction.TransactionLog` to populate.
    min_confirmations:
        Minimum on-chain confirmations required.  Use ``0`` to include
        unconfirmed transactions.
    include_outgoing:
        When *True*, outgoing transfers are also submitted with negative
        noise.  Default is *False* (incoming only).
    max_transfers:
        Cap on the number of transfers processed.  ``None`` means no cap.

    Returns
    -------
    list of dict
        Summary records ``{"txid", "amount_xmr", "direction", "noise"}`` for
        each transfer submitted to the log.

    Raises
    ------
    ImportError
        If neither the ``monero`` Python library nor the ``requests`` package
        is installed.
    RuntimeError
        If the wallet-RPC call fails.
    """
    if not _MONERO_LIB_AVAILABLE and not _REQUESTS_AVAILABLE:
        raise ImportError(
            "Monero integration requires either the 'monero' Python package "
            "(pip install \"openia[monero]\") or the 'requests' package "
            "(pip install requests).  Neither was found.\n\n"
            "Note: backbiten/monero (https://github.com/backbiten/monero.git, "
            "tag v0.18.4.3) is the Monero C++ daemon and cannot be "
            "pip-installed as a Python package directly."
        )

    cfg = _get_rpc_config()

    if _MONERO_LIB_AVAILABLE:
        return _sync_via_monero_lib(log, cfg, min_confirmations, include_outgoing, max_transfers)

    return _sync_via_requests(log, cfg, min_confirmations, include_outgoing, max_transfers)
