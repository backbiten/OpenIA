"""
Tests for openia.cardrails_stub (card-rail event stub adapter).

All tests use in-memory event dicts — no network access required.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from openia import TransactionLog
from openia.cardrails_stub import ingest_card_events, ingest_card_events_from_file


# ---------------------------------------------------------------------------
# Basic ingestion
# ---------------------------------------------------------------------------

class TestIngestCardEvents:
    def test_approve_id_yields_positive_noise(self):
        """An event with a merchant_id in approve set → noise = +1."""
        log = TransactionLog()
        events = [{"merchant_id": "MID-001", "amount": 50.0}]
        records = ingest_card_events(
            log, events,
            approve_ids={"MID-001"},
            disapprove_ids=set(),
        )
        assert len(records) == 1
        assert records[0]["noise"] == pytest.approx(1.0)
        assert log.aggregate_noise == pytest.approx(1.0)

    def test_disapprove_id_yields_negative_noise(self):
        """An event with a merchant_id in disapprove set → noise = -1."""
        log = TransactionLog()
        events = [{"merchant_id": "MID-BAD", "amount": 25.0}]
        records = ingest_card_events(
            log, events,
            approve_ids=set(),
            disapprove_ids={"MID-BAD"},
        )
        assert len(records) == 1
        assert records[0]["noise"] == pytest.approx(-1.0)
        assert log.aggregate_noise == pytest.approx(-1.0)

    def test_unknown_id_is_ignored(self):
        """An event with an identifier not in either set is skipped."""
        log = TransactionLog()
        events = [{"merchant_id": "MID-UNKNOWN", "amount": 100.0}]
        records = ingest_card_events(
            log, events,
            approve_ids={"MID-001"},
            disapprove_ids={"MID-BAD"},
        )
        assert records == []
        assert len(log) == 0

    def test_value_equals_event_amount(self):
        """The submitted log value equals the event amount."""
        log = TransactionLog()
        events = [{"merchant_id": "MID-001", "amount": 99.99}]
        ingest_card_events(log, events, approve_ids={"MID-001"}, disapprove_ids=set())
        assert log.entries[0].value == pytest.approx(99.99)

    def test_account_id_fallback(self):
        """Falls back to 'account_id' when 'merchant_id' is absent."""
        log = TransactionLog()
        events = [{"account_id": "ACC-007", "amount": 10.0}]
        records = ingest_card_events(
            log, events,
            approve_ids={"ACC-007"},
            disapprove_ids=set(),
        )
        assert len(records) == 1
        assert records[0]["noise"] == pytest.approx(1.0)

    def test_missing_amount_is_skipped(self):
        """An event without a valid 'amount' field is gracefully skipped."""
        log = TransactionLog()
        events = [{"merchant_id": "MID-001"}]
        records = ingest_card_events(
            log, events,
            approve_ids={"MID-001"},
            disapprove_ids=set(),
        )
        assert records == []
        assert len(log) == 0

    def test_multiple_events_mixed(self):
        """Multiple events with mixed IDs produce correct noise entries."""
        log = TransactionLog()
        events = [
            {"merchant_id": "MID-GOOD", "amount": 10.0},
            {"merchant_id": "MID-BAD", "amount": 5.0},
            {"merchant_id": "MID-OTHER", "amount": 3.0},
        ]
        records = ingest_card_events(
            log, events,
            approve_ids={"MID-GOOD"},
            disapprove_ids={"MID-BAD"},
        )
        assert len(records) == 2
        assert records[0]["noise"] == pytest.approx(1.0)
        assert records[1]["noise"] == pytest.approx(-1.0)
        assert len(log) == 2
        assert log.aggregate_noise == pytest.approx(0.0)

    def test_extra_fields_preserved(self):
        """Extra fields (currency, network) are passed through to records."""
        log = TransactionLog()
        events = [{
            "merchant_id": "MID-001",
            "amount": 20.0,
            "currency": "USD",
            "network": "visa",
            "txid": "card-tx-001",
        }]
        records = ingest_card_events(
            log, events,
            approve_ids={"MID-001"},
            disapprove_ids=set(),
        )
        assert records[0]["currency"] == "USD"
        assert records[0]["network"] == "visa"
        assert records[0]["txid"] == "card-tx-001"

    def test_empty_events_list(self):
        """An empty events list produces no log entries."""
        log = TransactionLog()
        records = ingest_card_events(
            log, [],
            approve_ids={"MID-001"},
            disapprove_ids=set(),
        )
        assert records == []
        assert len(log) == 0


# ---------------------------------------------------------------------------
# Environment variable integration
# ---------------------------------------------------------------------------

class TestCardEventsEnvVars:
    def test_reads_approve_ids_from_env(self, monkeypatch):
        """approve_ids defaults to OPENIA_APPROVE_IDS_CARD env var."""
        monkeypatch.setenv("OPENIA_APPROVE_IDS_CARD", "ENV-001,ENV-002")
        monkeypatch.setenv("OPENIA_DISAPPROVE_IDS_CARD", "")

        log = TransactionLog()
        events = [{"merchant_id": "ENV-001", "amount": 7.5}]
        records = ingest_card_events(log, events)

        assert len(records) == 1
        assert records[0]["noise"] == pytest.approx(1.0)

    def test_reads_disapprove_ids_from_env(self, monkeypatch):
        """disapprove_ids defaults to OPENIA_DISAPPROVE_IDS_CARD env var."""
        monkeypatch.setenv("OPENIA_APPROVE_IDS_CARD", "")
        monkeypatch.setenv("OPENIA_DISAPPROVE_IDS_CARD", "ENV-BAD")

        log = TransactionLog()
        events = [{"merchant_id": "ENV-BAD", "amount": 3.0}]
        records = ingest_card_events(log, events)

        assert len(records) == 1
        assert records[0]["noise"] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# File-based ingestion
# ---------------------------------------------------------------------------

class TestIngestCardEventsFromFile:
    def test_loads_list_from_json_file(self):
        """Loads a JSON array of events from a file."""
        events = [
            {"merchant_id": "MID-001", "amount": 15.0},
            {"merchant_id": "MID-BAD", "amount": 5.0},
        ]
        log = TransactionLog()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            json.dump(events, fh)
            fpath = fh.name

        records = ingest_card_events_from_file(
            log,
            fpath,
            approve_ids={"MID-001"},
            disapprove_ids={"MID-BAD"},
        )
        assert len(records) == 2
        assert len(log) == 2

    def test_loads_single_dict_from_json_file(self):
        """A JSON file containing a single dict is treated as one event."""
        event = {"merchant_id": "MID-001", "amount": 8.0}
        log = TransactionLog()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            json.dump(event, fh)
            fpath = fh.name

        records = ingest_card_events_from_file(
            log,
            fpath,
            approve_ids={"MID-001"},
            disapprove_ids=set(),
        )
        assert len(records) == 1
        assert records[0]["noise"] == pytest.approx(1.0)

    def test_missing_file_raises(self):
        """FileNotFoundError is raised when the path does not exist."""
        log = TransactionLog()
        with pytest.raises(FileNotFoundError):
            ingest_card_events_from_file(log, "/nonexistent/path/events.json")

    def test_invalid_json_raises(self):
        """json.JSONDecodeError is raised for malformed JSON files."""
        log = TransactionLog()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("not valid json {{")
            fpath = fh.name

        with pytest.raises(json.JSONDecodeError):
            ingest_card_events_from_file(log, fpath)


# ---------------------------------------------------------------------------
# Effect on Agent confidence
# ---------------------------------------------------------------------------

class TestCardRailsAgentIntegration:
    def test_card_approval_raises_agent_confidence(self):
        """Card-rail approval events increase the agent's confidence."""
        from openia import Agent

        log = TransactionLog()
        agent = Agent(log=log)

        baseline = agent.respond("help")["confidence"]

        events = [{"merchant_id": "VISA-GOOD", "amount": 100.0}]
        ingest_card_events(log, events, approve_ids={"VISA-GOOD"}, disapprove_ids=set())

        boosted = agent.respond("help")["confidence"]
        assert boosted > baseline

    def test_card_disapproval_lowers_agent_confidence(self):
        """Card-rail disapproval events decrease the agent's confidence."""
        from openia import Agent

        log = TransactionLog()
        agent = Agent(log=log)

        baseline = agent.respond("help")["confidence"]

        events = [{"merchant_id": "MASTERCARD-BAD", "amount": 50.0}]
        ingest_card_events(log, events, approve_ids=set(), disapprove_ids={"MASTERCARD-BAD"})

        penalised = agent.respond("help")["confidence"]
        assert penalised < baseline
