"""
cardrails_stub.py — Card-rail event stub adapter (Visa / Mastercard / Maestro).

.. warning::
   **This is a stub adapter.**  It does **not** connect to any real payment
   network.  Real Visa / Mastercard / Maestro integration requires a licensed
   payment processor (e.g., Stripe, Adyen, Worldpay) and is outside the scope
   of OpenIA.  This module exists so that the rest of the system can be
   developed and tested without live network access.

Purpose
-------
Accept payment-rail events — supplied by the user as Python dicts or loaded
from a JSON file — and convert them into
:class:`~openia.transaction.TransactionLog` entries using the same
S2 (identifier-based) judgment encoding used for blockchain adapters.

Judgment encoding — S2 (identifier-based)
------------------------------------------
Card-rail events carry a ``merchant_id`` (or ``account_id``) field.  Two
sets of identifiers are read from environment variables:

* ``OPENIA_APPROVE_IDS_CARD``     — comma-separated IDs → ``noise = +1.0``
* ``OPENIA_DISAPPROVE_IDS_CARD``  — comma-separated IDs → ``noise = -1.0``

Any event whose identifier is not in either set is ignored.

``value`` is the ``amount`` field of the event (float, required).

Event schema
------------
Each event dict must have at minimum:

.. code-block:: python

    {
        "amount": 12.50,           # float — transaction amount (required)
        "merchant_id": "MID-001",  # str   — identifier for classification
                                   #         (or "account_id" as fallback)
    }

Optional fields (passed through to the returned record):

* ``"currency"`` — ISO 4217 code (e.g., ``"USD"``)
* ``"txid"``     — internal transaction reference
* ``"network"``  — ``"visa"``, ``"mastercard"``, ``"maestro"``, etc.

Environment variables
---------------------
================================  ==========================================
Variable                          Description
================================  ==========================================
``OPENIA_APPROVE_IDS_CARD``       Comma-separated merchant/account IDs that
                                  signal **approval** (noise = +1)
``OPENIA_DISAPPROVE_IDS_CARD``    Comma-separated merchant/account IDs that
                                  signal **disapproval** (noise = -1)
================================  ==========================================
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

if TYPE_CHECKING:
    from .transaction import TransactionLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_id_sets() -> tuple[set[str], set[str]]:
    """Return (approve_ids, disapprove_ids) from environment variables."""
    raw_approve = os.environ.get("OPENIA_APPROVE_IDS_CARD", "")
    raw_disapprove = os.environ.get("OPENIA_DISAPPROVE_IDS_CARD", "")
    approve = {s.strip() for s in raw_approve.split(",") if s.strip()}
    disapprove = {s.strip() for s in raw_disapprove.split(",") if s.strip()}
    return approve, disapprove


def _classify_id(identifier: str, approve: set[str], disapprove: set[str]) -> Optional[float]:
    """Return +1.0, -1.0, or None based on identifier classification."""
    if identifier in approve:
        return 1.0
    if identifier in disapprove:
        return -1.0
    return None


def _extract_identifier(event: dict) -> str:
    """Extract the primary identifier from an event dict."""
    return str(event.get("merchant_id") or event.get("account_id") or "")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest_card_events(
    log: "TransactionLog",
    events: List[dict],
    *,
    approve_ids: Optional[set[str]] = None,
    disapprove_ids: Optional[set[str]] = None,
) -> List[dict]:
    """Process a list of card-rail event dicts and submit matches to *log*.

    Parameters
    ----------
    log:
        The :class:`~openia.transaction.TransactionLog` to populate.
    events:
        List of event dicts (see module docstring for schema).
    approve_ids:
        Explicit set of approve identifiers.  When ``None``, the value of
        ``OPENIA_APPROVE_IDS_CARD`` is used.
    disapprove_ids:
        Explicit set of disapprove identifiers.  When ``None``, the value of
        ``OPENIA_DISAPPROVE_IDS_CARD`` is used.

    Returns
    -------
    list[dict]
        Records of transactions submitted to the log.  Each record contains
        ``txid``, ``amount``, ``identifier``, ``noise``, and any extra fields
        present in the original event.
    """
    if approve_ids is None or disapprove_ids is None:
        env_approve, env_disapprove = _get_id_sets()
        if approve_ids is None:
            approve_ids = env_approve
        if disapprove_ids is None:
            disapprove_ids = env_disapprove

    records: List[dict] = []
    for event in events:
        identifier = _extract_identifier(event)
        noise = _classify_id(identifier, approve_ids, disapprove_ids)
        if noise is None:
            logger.debug("Card event identifier %r not in approve/disapprove sets; skipped", identifier)
            continue

        try:
            amount = float(event["amount"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Card event missing valid 'amount' field: %s — skipped", exc)
            continue

        log.submit(value=amount, noise=noise)
        record: dict = {
            "txid": event.get("txid", ""),
            "amount": amount,
            "identifier": identifier,
            "noise": noise,
        }
        for extra_key in ("currency", "network"):
            if extra_key in event:
                record[extra_key] = event[extra_key]
        records.append(record)

    return records


def ingest_card_events_from_file(
    log: "TransactionLog",
    path: Union[str, Path],
    *,
    approve_ids: Optional[set[str]] = None,
    disapprove_ids: Optional[set[str]] = None,
) -> List[dict]:
    """Load card-rail events from a JSON file and ingest them into *log*.

    The JSON file must contain either a single event dict or a list of event
    dicts.

    Parameters
    ----------
    log:
        The :class:`~openia.transaction.TransactionLog` to populate.
    path:
        Filesystem path to the JSON file.
    approve_ids:
        Explicit approve identifiers (``None`` = read from env var).
    disapprove_ids:
        Explicit disapprove identifiers (``None`` = read from env var).

    Returns
    -------
    list[dict]
        Same as :func:`ingest_card_events`.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    json.JSONDecodeError
        If the file does not contain valid JSON.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    return ingest_card_events(log, data, approve_ids=approve_ids, disapprove_ids=disapprove_ids)
