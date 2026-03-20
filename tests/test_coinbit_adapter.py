"""
Tests for openia.coinbit_adapter.

All tests are self-contained and require no network access, no external RPC
nodes, and no third-party dependencies beyond pytest.
"""

from __future__ import annotations

import pytest

from openia import TransactionLog
from openia.coinbit_adapter import (
    COINBIT_TO_SATOSHIS,
    _coinbit_to_btc_map,
    batch_settle_to_btc,
    coinbits_to_satoshis,
    ingest_coinbit_events,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_map() -> None:
    """Empty the global in-memory mapping between tests."""
    _coinbit_to_btc_map.clear()


# ---------------------------------------------------------------------------
# coinbits_to_satoshis
# ---------------------------------------------------------------------------


class TestCoinbitsToSatoshis:
    def test_one_coinbit(self):
        assert coinbits_to_satoshis(1.0) == COINBIT_TO_SATOSHIS

    def test_zero_coinbits(self):
        assert coinbits_to_satoshis(0.0) == 0

    def test_fractional_coinbits_exact(self):
        # 0.5 coinbits → 50 sats (with default COINBIT_TO_SATOSHIS = 100)
        assert coinbits_to_satoshis(0.5) == 50

    def test_fractional_coinbits_floor(self):
        # 0.009 * 100 = 0.9 → floor → 0
        assert coinbits_to_satoshis(0.009) == 0

    def test_fractional_coinbits_floor_rounds_down(self):
        # 1.999 * 100 = 199.9 → floor → 199
        assert coinbits_to_satoshis(1.999) == 199

    def test_large_amount(self):
        assert coinbits_to_satoshis(1_000_000.0) == 1_000_000 * COINBIT_TO_SATOSHIS

    def test_negative_clamped_to_zero(self):
        assert coinbits_to_satoshis(-5.0) == 0

    def test_very_small_positive_clamped(self):
        # 0.001 * 100 = 0.1 → floor → 0
        assert coinbits_to_satoshis(0.001) == 0

    def test_returns_int(self):
        result = coinbits_to_satoshis(2.5)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# ingest_coinbit_events
# ---------------------------------------------------------------------------


class TestIngestCoinbitEvents:
    def _make_event(self, txid: str = "cb-1", amount: float = 1.0, **kwargs) -> dict:
        return {"txid": txid, "amount_coinbits": amount, **kwargs}

    # --- basic ingestion ---

    def test_single_valid_event_appends_to_log(self):
        log = TransactionLog()
        events = [self._make_event("cb-1", 1.0)]
        records = ingest_coinbit_events(log, events)
        assert len(records) == 1
        assert len(log) == 1

    def test_record_fields(self):
        log = TransactionLog()
        events = [self._make_event("cb-42", 2.5, sender="alice", receiver="bob")]
        records = ingest_coinbit_events(log, events)
        r = records[0]
        assert r["coinbit_txid"] == "cb-42"
        assert r["amount_coinbits"] == pytest.approx(2.5)
        assert r["amount_sats"] == coinbits_to_satoshis(2.5)
        assert r["sender"] == "alice"
        assert r["receiver"] == "bob"

    def test_submit_in_sats_default(self):
        """By default, log value equals satoshi equivalent."""
        log = TransactionLog()
        events = [self._make_event("cb-1", 3.0)]
        ingest_coinbit_events(log, events, submit_in_sats=True)
        expected = float(coinbits_to_satoshis(3.0))
        assert log.entries[0].value == pytest.approx(expected)

    def test_submit_in_coinbits(self):
        """When submit_in_sats=False, log value equals coinbit amount."""
        log = TransactionLog()
        events = [self._make_event("cb-1", 4.0)]
        ingest_coinbit_events(log, events, submit_in_sats=False)
        assert log.entries[0].value == pytest.approx(4.0)

    def test_noise_is_none(self):
        """Coinbit events carry no noise signal."""
        log = TransactionLog()
        events = [self._make_event("cb-1", 1.0)]
        ingest_coinbit_events(log, events)
        assert log.entries[0].noise is None

    def test_btc_address_passed_through(self):
        log = TransactionLog()
        events = [self._make_event("cb-1", 1.0, btc_address="bc1qtest")]
        records = ingest_coinbit_events(log, events)
        assert records[0]["btc_address"] == "bc1qtest"

    def test_multiple_valid_events(self):
        log = TransactionLog()
        events = [
            self._make_event("cb-1", 1.0),
            self._make_event("cb-2", 2.0),
            self._make_event("cb-3", 3.0),
        ]
        records = ingest_coinbit_events(log, events)
        assert len(records) == 3
        assert len(log) == 3

    def test_total_value_in_log(self):
        log = TransactionLog()
        events = [
            self._make_event("cb-1", 1.0),
            self._make_event("cb-2", 2.0),
        ]
        ingest_coinbit_events(log, events)
        expected = float(coinbits_to_satoshis(1.0) + coinbits_to_satoshis(2.0))
        assert log.total_value == pytest.approx(expected)

    def test_empty_events_list(self):
        log = TransactionLog()
        records = ingest_coinbit_events(log, [])
        assert records == []
        assert len(log) == 0

    # --- invalid / malformed events ---

    def test_missing_txid_skipped(self):
        log = TransactionLog()
        events = [{"amount_coinbits": 1.0}]  # no txid
        records = ingest_coinbit_events(log, events)
        assert records == []
        assert len(log) == 0

    def test_missing_amount_skipped(self):
        log = TransactionLog()
        events = [{"txid": "cb-1"}]  # no amount_coinbits
        records = ingest_coinbit_events(log, events)
        assert records == []
        assert len(log) == 0

    def test_non_numeric_amount_skipped(self):
        log = TransactionLog()
        events = [{"txid": "cb-1", "amount_coinbits": "lots"}]
        records = ingest_coinbit_events(log, events)
        assert records == []
        assert len(log) == 0

    def test_invalid_event_among_valid_events(self):
        """An invalid event is skipped; valid events are still processed."""
        log = TransactionLog()
        events = [
            {"txid": "cb-good", "amount_coinbits": 1.0},
            {"amount_coinbits": 2.0},  # missing txid
            {"txid": "cb-also-good", "amount_coinbits": 3.0},
        ]
        records = ingest_coinbit_events(log, events)
        assert len(records) == 2
        assert len(log) == 2
        assert records[0]["coinbit_txid"] == "cb-good"
        assert records[1]["coinbit_txid"] == "cb-also-good"


# ---------------------------------------------------------------------------
# batch_settle_to_btc — dry-run
# ---------------------------------------------------------------------------


class TestBatchSettleToBtcDryRun:
    def setup_method(self):
        _clear_map()

    def _records(self, merchant: str, amount_coinbits: float, btc_address: str = "bc1qtest") -> list:
        log = TransactionLog()
        events = [
            {
                "txid": f"cb-{merchant}-1",
                "amount_coinbits": amount_coinbits,
                "btc_address": btc_address,
            }
        ]
        return ingest_coinbit_events(log, events)

    # --- meets threshold ---

    def test_returns_settlement_when_threshold_met(self):
        records = self._records("merchant-A", 200.0)  # 200 * 100 = 20_000 sats
        result = batch_settle_to_btc(
            {"merchant-A": records},
            threshold_sats=10_000,
            dry_run=True,
        )
        assert len(result) == 1

    def test_simulated_txid_format(self):
        records = self._records("merchant-A", 200.0)
        result = batch_settle_to_btc(
            {"merchant-A": records},
            threshold_sats=10_000,
            dry_run=True,
        )
        assert result[0]["btc_txid"].startswith("simulated-btc-merchant-A-")

    def test_settlement_record_fields(self):
        records = self._records("merchant-A", 200.0, btc_address="bc1qabc")
        result = batch_settle_to_btc(
            {"merchant-A": records},
            threshold_sats=10_000,
            dry_run=True,
        )
        r = result[0]
        assert r["merchant"] == "merchant-A"
        assert r["total_sats"] == coinbits_to_satoshis(200.0)
        assert r["dest_address"] == "bc1qabc"
        assert "cb-merchant-A-1" in r["coinbit_txids"]

    def test_mapping_populated_after_settlement(self):
        records = self._records("merchant-B", 150.0)
        batch_settle_to_btc(
            {"merchant-B": records},
            threshold_sats=5_000,
            dry_run=True,
        )
        assert "cb-merchant-B-1" in _coinbit_to_btc_map

    def test_mapping_value_matches_btc_txid(self):
        records = self._records("merchant-C", 100.0)
        result = batch_settle_to_btc(
            {"merchant-C": records},
            threshold_sats=1_000,
            dry_run=True,
        )
        btc_txid = result[0]["btc_txid"]
        assert _coinbit_to_btc_map["cb-merchant-C-1"] == btc_txid

    def test_multiple_coinbit_txids_all_mapped(self):
        log = TransactionLog()
        events = [
            {"txid": "cb-m1", "amount_coinbits": 50.0, "btc_address": "bc1qx"},
            {"txid": "cb-m2", "amount_coinbits": 60.0, "btc_address": "bc1qx"},
        ]
        records = ingest_coinbit_events(log, events)
        result = batch_settle_to_btc(
            {"merchant-M": records},
            threshold_sats=1_000,
            dry_run=True,
        )
        btc_txid = result[0]["btc_txid"]
        assert _coinbit_to_btc_map["cb-m1"] == btc_txid
        assert _coinbit_to_btc_map["cb-m2"] == btc_txid
        # 50 + 60 = 110 coinbits → 110 * 100 = 11_000 sats
        assert result[0]["total_sats"] == coinbits_to_satoshis(50.0) + coinbits_to_satoshis(60.0)

    # --- below threshold ---

    def test_below_threshold_skipped(self):
        records = self._records("merchant-D", 0.5)  # 50 sats
        result = batch_settle_to_btc(
            {"merchant-D": records},
            threshold_sats=10_000,
            dry_run=True,
        )
        assert result == []

    def test_below_threshold_no_mapping_entry(self):
        records = self._records("merchant-E", 0.1)
        batch_settle_to_btc(
            {"merchant-E": records},
            threshold_sats=50_000,
            dry_run=True,
        )
        assert "cb-merchant-E-1" not in _coinbit_to_btc_map

    def test_exact_threshold_settles(self):
        # 100 coinbits * 100 sats/coinbit = 10_000 sats exactly
        records = self._records("merchant-F", 100.0)
        result = batch_settle_to_btc(
            {"merchant-F": records},
            threshold_sats=10_000,
            dry_run=True,
        )
        assert len(result) == 1

    # --- missing btc_address ---

    def test_no_btc_address_skipped(self):
        log = TransactionLog()
        events = [{"txid": "cb-naddr", "amount_coinbits": 500.0}]
        records = ingest_coinbit_events(log, events)
        result = batch_settle_to_btc(
            {"merchant-G": records},
            threshold_sats=1_000,
            dry_run=True,
        )
        assert result == []

    def test_empty_unsettled_dict(self):
        result = batch_settle_to_btc({}, threshold_sats=1_000, dry_run=True)
        assert result == []

    # --- multiple merchants ---

    def test_mixed_merchants_only_qualifying_settle(self):
        records_a = self._records("merchant-A", 200.0)  # 20_000 sats ≥ threshold
        records_b = self._records("merchant-B", 0.5)   # 50 sats < threshold
        result = batch_settle_to_btc(
            {"merchant-A": records_a, "merchant-B": records_b},
            threshold_sats=10_000,
            dry_run=True,
        )
        merchants_settled = [r["merchant"] for r in result]
        assert "merchant-A" in merchants_settled
        assert "merchant-B" not in merchants_settled
