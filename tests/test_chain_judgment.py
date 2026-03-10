"""
Tests for openia.chain_judgment (unified BTC + XMR S2 judgment).

All blockchain calls are fully mocked — no real nodes required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openia import TransactionLog
from openia.chain_judgment import run_chain_judgment


# ---------------------------------------------------------------------------
# BTC — approval
# ---------------------------------------------------------------------------

class TestChainJudgmentBTC:
    def test_btc_approve_address_yields_positive_noise(self, monkeypatch):
        """A BTC tx received at an approve address → noise = +1."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_BTC", "bc1approve")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_BTC", "")

        fake_tx = {
            "category": "receive",
            "address": "bc1approve",
            "amount": 0.001,
            "confirmations": 3,
            "txid": "btx001",
        }

        log = TransactionLog()
        with patch("openia.bitcoin_integration._requests") as mock_req:
            mock_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": [fake_tx], "error": None}),
                raise_for_status=MagicMock(),
            )
            report = run_chain_judgment(log, skip_xmr=True)

        assert report["btc_error"] is None
        assert len(report["btc_records"]) == 1
        assert report["btc_records"][0]["noise"] == pytest.approx(1.0)
        assert log.aggregate_noise == pytest.approx(1.0)

    def test_btc_disapprove_address_yields_negative_noise(self, monkeypatch):
        """A BTC tx received at a disapprove address → noise = -1."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_BTC", "")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_BTC", "bc1disapprove")

        fake_tx = {
            "category": "receive",
            "address": "bc1disapprove",
            "amount": 0.005,
            "confirmations": 6,
            "txid": "btx002",
        }

        log = TransactionLog()
        with patch("openia.bitcoin_integration._requests") as mock_req:
            mock_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": [fake_tx], "error": None}),
                raise_for_status=MagicMock(),
            )
            report = run_chain_judgment(log, skip_xmr=True)

        assert report["btc_error"] is None
        assert len(report["btc_records"]) == 1
        assert report["btc_records"][0]["noise"] == pytest.approx(-1.0)
        assert log.aggregate_noise == pytest.approx(-1.0)

    def test_btc_unknown_address_ignored(self, monkeypatch):
        """A BTC tx to an unknown address produces no log entry."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_BTC", "bc1approve")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_BTC", "bc1disapprove")

        fake_tx = {
            "category": "receive",
            "address": "bc1other",
            "amount": 0.01,
            "confirmations": 1,
            "txid": "btx003",
        }

        log = TransactionLog()
        with patch("openia.bitcoin_integration._requests") as mock_req:
            mock_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": [fake_tx], "error": None}),
                raise_for_status=MagicMock(),
            )
            report = run_chain_judgment(log, skip_xmr=True)

        assert report["btc_records"] == []
        assert len(log) == 0

    def test_btc_insufficient_confirmations_ignored(self, monkeypatch):
        """A BTC tx with fewer confirmations than required is ignored."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_BTC", "bc1approve")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_BTC", "")

        fake_tx = {
            "category": "receive",
            "address": "bc1approve",
            "amount": 0.001,
            "confirmations": 0,
            "txid": "btx004",
        }

        log = TransactionLog()
        with patch("openia.bitcoin_integration._requests") as mock_req:
            mock_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": [fake_tx], "error": None}),
                raise_for_status=MagicMock(),
            )
            report = run_chain_judgment(log, btc_min_confirmations=1, skip_xmr=True)

        assert report["btc_records"] == []
        assert len(log) == 0

    def test_btc_value_is_transaction_amount(self, monkeypatch):
        """The submitted transaction value equals the BTC amount."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_BTC", "bc1approve")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_BTC", "")

        fake_tx = {
            "category": "receive",
            "address": "bc1approve",
            "amount": 0.123,
            "confirmations": 1,
            "txid": "btx005",
        }

        log = TransactionLog()
        with patch("openia.bitcoin_integration._requests") as mock_req:
            mock_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": [fake_tx], "error": None}),
                raise_for_status=MagicMock(),
            )
            run_chain_judgment(log, skip_xmr=True)

        assert log.entries[0].value == pytest.approx(0.123)

    def test_btc_import_error_captured(self, monkeypatch):
        """If requests is unavailable for BTC, error is captured gracefully."""
        log = TransactionLog()
        with patch("openia.bitcoin_integration._REQUESTS_AVAILABLE", False):
            report = run_chain_judgment(log, skip_xmr=True)

        assert report["btc_error"] is not None
        assert len(log) == 0


# ---------------------------------------------------------------------------
# XMR — approval / disapproval
# ---------------------------------------------------------------------------

class TestChainJudgmentXMR:
    def _make_rpc_response(self, txs: list, direction_key: str = "in") -> dict:
        return {"result": {direction_key: txs}, "error": None}

    def test_xmr_approve_address_yields_positive_noise(self, monkeypatch):
        """An XMR transfer to an approve address → noise = +1."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_XMR", "xmrapprove")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_XMR", "")

        fake_tx = {
            "txid": "xmrtx001",
            "amount": 1_000_000_000_000,  # 1 XMR in piconeros
            "address": "xmrapprove",
            "confirmations": 5,
            "type": "in",
        }

        log = TransactionLog()
        with patch("openia.monero_integration._requests") as mock_req:
            mock_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=self._make_rpc_response([fake_tx])),
                raise_for_status=MagicMock(),
            )
            report = run_chain_judgment(log, skip_btc=True)

        assert report["xmr_error"] is None
        assert len(report["xmr_records"]) == 1
        assert report["xmr_records"][0]["noise"] == pytest.approx(1.0)
        assert log.aggregate_noise == pytest.approx(1.0)

    def test_xmr_disapprove_address_yields_negative_noise(self, monkeypatch):
        """An XMR transfer to a disapprove address → noise = -1."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_XMR", "")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_XMR", "xmrdisapprove")

        fake_tx = {
            "txid": "xmrtx002",
            "amount": 500_000_000_000,  # 0.5 XMR
            "address": "xmrdisapprove",
            "confirmations": 2,
            "type": "in",
        }

        log = TransactionLog()
        with patch("openia.monero_integration._requests") as mock_req:
            mock_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=self._make_rpc_response([fake_tx])),
                raise_for_status=MagicMock(),
            )
            report = run_chain_judgment(log, skip_btc=True)

        assert report["xmr_error"] is None
        assert len(report["xmr_records"]) == 1
        assert report["xmr_records"][0]["noise"] == pytest.approx(-1.0)
        assert log.aggregate_noise == pytest.approx(-1.0)

    def test_xmr_unknown_address_ignored(self, monkeypatch):
        """An XMR transfer to an unknown address produces no log entry."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_XMR", "xmrapprove")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_XMR", "xmrdisapprove")

        fake_tx = {
            "txid": "xmrtx003",
            "amount": 200_000_000_000,
            "address": "xmrother",
            "confirmations": 3,
            "type": "in",
        }

        log = TransactionLog()
        with patch("openia.monero_integration._requests") as mock_req:
            mock_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=self._make_rpc_response([fake_tx])),
                raise_for_status=MagicMock(),
            )
            report = run_chain_judgment(log, skip_btc=True)

        assert report["xmr_records"] == []
        assert len(log) == 0

    def test_xmr_value_is_xmr_amount(self, monkeypatch):
        """The submitted transaction value equals the XMR amount (float)."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_XMR", "xmrapprove")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_XMR", "")

        piconeros = 250_000_000_000  # 0.25 XMR
        fake_tx = {
            "txid": "xmrtx004",
            "amount": piconeros,
            "address": "xmrapprove",
            "confirmations": 1,
            "type": "in",
        }

        log = TransactionLog()
        with patch("openia.monero_integration._requests") as mock_req:
            mock_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=self._make_rpc_response([fake_tx])),
                raise_for_status=MagicMock(),
            )
            run_chain_judgment(log, skip_btc=True)

        assert log.entries[0].value == pytest.approx(0.25)

    def test_xmr_import_error_captured(self, monkeypatch):
        """If requests is unavailable for XMR, error is captured gracefully."""
        log = TransactionLog()
        with (
            patch("openia.monero_integration._MONERO_LIB_AVAILABLE", False),
            patch("openia.monero_integration._REQUESTS_AVAILABLE", False),
        ):
            report = run_chain_judgment(log, skip_btc=True)

        assert report["xmr_error"] is not None
        assert len(log) == 0


# ---------------------------------------------------------------------------
# Both chains together
# ---------------------------------------------------------------------------

class TestChainJudgmentCombined:
    def test_both_chains_aggregate_noise(self, monkeypatch):
        """BTC approval + XMR disapproval → aggregate noise = 0."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_BTC", "bc1approve")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_BTC", "")
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_XMR", "")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_XMR", "xmrdisapprove")

        btc_tx = {
            "category": "receive",
            "address": "bc1approve",
            "amount": 0.001,
            "confirmations": 3,
            "txid": "btx_combined",
        }
        xmr_tx = {
            "txid": "xmr_combined",
            "amount": 1_000_000_000_000,
            "address": "xmrdisapprove",
            "confirmations": 3,
            "type": "in",
        }

        log = TransactionLog()
        with (
            patch("openia.bitcoin_integration._requests") as mock_btc_req,
            patch("openia.monero_integration._requests") as mock_xmr_req,
        ):
            mock_btc_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": [btc_tx], "error": None}),
                raise_for_status=MagicMock(),
            )
            mock_xmr_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": {"in": [xmr_tx]}, "error": None}),
                raise_for_status=MagicMock(),
            )
            report = run_chain_judgment(log)

        assert report["btc_error"] is None
        assert report["xmr_error"] is None
        assert len(report["btc_records"]) == 1
        assert len(report["xmr_records"]) == 1
        # +1 and -1 average to 0
        assert log.aggregate_noise == pytest.approx(0.0)

    def test_skip_btc_flag(self, monkeypatch):
        """skip_btc=True means no BTC records regardless of mock data."""
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_BTC", "bc1approve")
        monkeypatch.setenv("OPENIA_APPROVE_ADDRESSES_XMR", "xmrapprove")
        monkeypatch.setenv("OPENIA_DISAPPROVE_ADDRESSES_XMR", "")

        xmr_tx = {
            "txid": "xmr_skip",
            "amount": 1_000_000_000_000,
            "address": "xmrapprove",
            "confirmations": 1,
            "type": "in",
        }

        log = TransactionLog()
        with patch("openia.monero_integration._requests") as mock_xmr_req:
            mock_xmr_req.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": {"in": [xmr_tx]}, "error": None}),
                raise_for_status=MagicMock(),
            )
            report = run_chain_judgment(log, skip_btc=True)

        assert report["btc_records"] == []
        assert len(report["xmr_records"]) == 1
