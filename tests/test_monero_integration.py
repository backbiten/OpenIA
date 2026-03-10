"""
Tests for openia.monero_integration.

Covers:
- Module can be imported even when neither 'monero' nor 'requests' is installed
- _amount_to_noise mapping
- sync_from_monero raises ImportError when no deps are available
- sync_from_monero (requests path) submits correct TransactionLog entries
- sync_from_monero (monero lib path) submits correct TransactionLog entries
- Environment variable configuration is respected
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openia.transaction import TransactionLog


# ---------------------------------------------------------------------------
# Import resilience
# ---------------------------------------------------------------------------


class TestImportResilience:
    def test_module_importable_always(self):
        """monero_integration can be imported even if deps are absent."""
        import openia.monero_integration  # noqa: F401 — must not raise

    def test_availability_flags_are_bool(self):
        import openia.monero_integration as mi

        assert isinstance(mi._MONERO_LIB_AVAILABLE, bool)
        assert isinstance(mi._REQUESTS_AVAILABLE, bool)


# ---------------------------------------------------------------------------
# _amount_to_noise
# ---------------------------------------------------------------------------


class TestAmountToNoise:
    def setup_method(self):
        from openia import monero_integration as mi

        self.mi = mi

    def test_incoming_small_amount(self):
        noise = self.mi._amount_to_noise(0.5, "in")
        assert noise == pytest.approx(0.5)

    def test_incoming_large_amount_clamped(self):
        noise = self.mi._amount_to_noise(10.0, "in")
        assert noise == pytest.approx(1.0)

    def test_outgoing_small_amount(self):
        noise = self.mi._amount_to_noise(0.25, "out")
        assert noise == pytest.approx(-0.25)

    def test_outgoing_large_amount_clamped(self):
        noise = self.mi._amount_to_noise(5.0, "out")
        assert noise == pytest.approx(-1.0)

    def test_zero_amount(self):
        assert self.mi._amount_to_noise(0.0, "in") == pytest.approx(0.0)

    def test_noise_in_range(self):
        for amount in [0.0, 0.1, 0.5, 1.0, 2.0]:
            for direction in ("in", "out"):
                noise = self.mi._amount_to_noise(amount, direction)
                assert -1.0 <= noise <= 1.0


# ---------------------------------------------------------------------------
# sync_from_monero — ImportError when neither dep is present
# ---------------------------------------------------------------------------


class TestSyncImportError:
    def test_raises_import_error_when_no_deps(self):
        """sync_from_monero raises ImportError if both monero and requests are absent."""
        import openia.monero_integration as mi

        log = TransactionLog()

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", False),
            patch.object(mi, "_REQUESTS_AVAILABLE", False),
        ):
            with pytest.raises(ImportError, match="monero"):
                mi.sync_from_monero(log)

    def test_import_error_message_mentions_backbiten(self):
        import openia.monero_integration as mi

        log = TransactionLog()

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", False),
            patch.object(mi, "_REQUESTS_AVAILABLE", False),
        ):
            with pytest.raises(ImportError, match="backbiten/monero"):
                mi.sync_from_monero(log)


# ---------------------------------------------------------------------------
# sync_from_monero — requests fallback path
# ---------------------------------------------------------------------------


class TestSyncViaRequests:
    def _make_rpc_result(self, transfers_in, transfers_out=None):
        """Build a fake get_transfers RPC result dict."""
        result = {"in": transfers_in}
        if transfers_out:
            result["out"] = transfers_out
        return result

    def _make_transfer(self, txid, amount_piconero, confirmations=2, tx_type="in"):
        return {
            "txid": txid,
            "amount": amount_piconero,
            "confirmations": confirmations,
            "type": tx_type,
        }

    def test_incoming_transfers_submitted_to_log(self):
        import openia.monero_integration as mi

        log = TransactionLog()
        piconero = mi._PICONERO

        rpc_result = self._make_rpc_result(
            [
                self._make_transfer("txabc", int(0.5 * piconero)),
                self._make_transfer("txdef", int(1.0 * piconero)),
            ]
        )

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", False),
            patch.object(mi, "_REQUESTS_AVAILABLE", True),
            patch.object(mi, "_rpc_call", return_value=rpc_result),
        ):
            records = mi.sync_from_monero(log)

        assert len(log) == 2
        assert len(records) == 2

    def test_noise_values_correct(self):
        import openia.monero_integration as mi

        log = TransactionLog()
        piconero = mi._PICONERO

        rpc_result = self._make_rpc_result(
            [self._make_transfer("tx1", int(0.5 * piconero))]
        )

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", False),
            patch.object(mi, "_REQUESTS_AVAILABLE", True),
            patch.object(mi, "_rpc_call", return_value=rpc_result),
        ):
            records = mi.sync_from_monero(log)

        assert records[0]["noise"] == pytest.approx(0.5)
        assert records[0]["direction"] == "in"
        assert log.aggregate_noise == pytest.approx(0.5)

    def test_outgoing_produces_negative_noise(self):
        import openia.monero_integration as mi

        log = TransactionLog()
        piconero = mi._PICONERO

        rpc_result = {
            "in": [],
            "out": [self._make_transfer("txout", int(0.3 * piconero), tx_type="out")],
        }

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", False),
            patch.object(mi, "_REQUESTS_AVAILABLE", True),
            patch.object(mi, "_rpc_call", return_value=rpc_result),
        ):
            records = mi.sync_from_monero(log, include_outgoing=True)

        assert records[0]["noise"] == pytest.approx(-0.3)
        assert log.aggregate_noise == pytest.approx(-0.3)

    def test_max_transfers_limits_results(self):
        import openia.monero_integration as mi

        log = TransactionLog()
        piconero = mi._PICONERO

        rpc_result = self._make_rpc_result(
            [self._make_transfer(f"tx{i}", int(0.1 * piconero)) for i in range(10)]
        )

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", False),
            patch.object(mi, "_REQUESTS_AVAILABLE", True),
            patch.object(mi, "_rpc_call", return_value=rpc_result),
        ):
            records = mi.sync_from_monero(log, max_transfers=3)

        assert len(log) == 3
        assert len(records) == 3

    def test_empty_wallet_returns_empty_records(self):
        import openia.monero_integration as mi

        log = TransactionLog()

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", False),
            patch.object(mi, "_REQUESTS_AVAILABLE", True),
            patch.object(mi, "_rpc_call", return_value={}),
        ):
            records = mi.sync_from_monero(log)

        assert len(log) == 0
        assert records == []

    def test_env_vars_used_for_rpc_config(self, monkeypatch):
        import openia.monero_integration as mi

        log = TransactionLog()
        captured = {}

        def fake_rpc_call(url, method, params, user="", password=""):
            captured["url"] = url
            captured["user"] = user
            captured["password"] = password
            return {}

        monkeypatch.setenv("MONERO_WALLET_RPC_URL", "http://mynode:18083/json_rpc")
        monkeypatch.setenv("MONERO_WALLET_RPC_USER", "alice")
        monkeypatch.setenv("MONERO_WALLET_RPC_PASS", "s3cr3t")

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", False),
            patch.object(mi, "_REQUESTS_AVAILABLE", True),
            patch.object(mi, "_rpc_call", side_effect=fake_rpc_call),
        ):
            mi.sync_from_monero(log)

        assert captured["url"] == "http://mynode:18083/json_rpc"
        assert captured["user"] == "alice"
        assert captured["password"] == "s3cr3t"


# ---------------------------------------------------------------------------
# sync_from_monero — monero PyPI library path
# ---------------------------------------------------------------------------


class TestSyncViaMoneroLib:
    def _make_fake_payment(self, amount_xmr: float, txhash: str = "abc123", confirmations: int = 2):
        """Build a fake payment object matching the monero library API."""
        tx = MagicMock()
        tx.hash = txhash
        tx.confirmations = confirmations

        payment = MagicMock()
        payment.amount = amount_xmr
        payment.transaction = tx
        return payment

    def test_incoming_transferred_to_log(self):
        import openia.monero_integration as mi

        log = TransactionLog()
        fake_payments = [
            self._make_fake_payment(0.5, "tx1"),
            self._make_fake_payment(1.0, "tx2"),
        ]

        mock_wallet = MagicMock()
        mock_wallet.incoming.return_value = fake_payments
        mock_wallet.outgoing.return_value = []

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", True),
            patch.object(mi, "_Wallet", return_value=mock_wallet),
            patch.object(mi, "_JSONRPCWallet", return_value=MagicMock()),
        ):
            records = mi.sync_from_monero(log)

        assert len(log) == 2
        assert len(records) == 2

    def test_noise_correct_for_incoming(self):
        import openia.monero_integration as mi

        log = TransactionLog()
        fake_payments = [self._make_fake_payment(0.75, "txA")]

        mock_wallet = MagicMock()
        mock_wallet.incoming.return_value = fake_payments
        mock_wallet.outgoing.return_value = []

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", True),
            patch.object(mi, "_Wallet", return_value=mock_wallet),
            patch.object(mi, "_JSONRPCWallet", return_value=MagicMock()),
        ):
            records = mi.sync_from_monero(log)

        assert records[0]["noise"] == pytest.approx(0.75)
        assert log.aggregate_noise == pytest.approx(0.75)

    def test_outgoing_produces_negative_noise(self):
        import openia.monero_integration as mi

        log = TransactionLog()
        mock_wallet = MagicMock()
        mock_wallet.incoming.return_value = []
        mock_wallet.outgoing.return_value = [self._make_fake_payment(0.4, "txB")]

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", True),
            patch.object(mi, "_Wallet", return_value=mock_wallet),
            patch.object(mi, "_JSONRPCWallet", return_value=MagicMock()),
        ):
            records = mi.sync_from_monero(log, include_outgoing=True)

        assert records[0]["noise"] == pytest.approx(-0.4)

    def test_max_transfers_limits_results(self):
        import openia.monero_integration as mi

        log = TransactionLog()
        fake_payments = [self._make_fake_payment(0.1, f"tx{i}") for i in range(10)]

        mock_wallet = MagicMock()
        mock_wallet.incoming.return_value = fake_payments
        mock_wallet.outgoing.return_value = []

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", True),
            patch.object(mi, "_Wallet", return_value=mock_wallet),
            patch.object(mi, "_JSONRPCWallet", return_value=MagicMock()),
        ):
            records = mi.sync_from_monero(log, max_transfers=4)

        assert len(log) == 4

    def test_txid_extracted_from_transaction_hash(self):
        import openia.monero_integration as mi

        log = TransactionLog()
        fake_payments = [self._make_fake_payment(0.2, "deadbeef")]

        mock_wallet = MagicMock()
        mock_wallet.incoming.return_value = fake_payments
        mock_wallet.outgoing.return_value = []

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", True),
            patch.object(mi, "_Wallet", return_value=mock_wallet),
            patch.object(mi, "_JSONRPCWallet", return_value=MagicMock()),
        ):
            records = mi.sync_from_monero(log)

        assert records[0]["txid"] == "deadbeef"


# ---------------------------------------------------------------------------
# Integration: sync_from_monero feeds the Agent
# ---------------------------------------------------------------------------


class TestMoneroAgentIntegration:
    def test_monero_noise_influences_agent_confidence(self):
        """Monero transactions submitted via sync_from_monero affect Agent output."""
        import openia.monero_integration as mi
        from openia import Agent

        log = TransactionLog()
        agent = Agent(log=log)

        baseline_confidence = agent.respond("help")["confidence"]

        # Simulate a large incoming transfer (noise = +1.0)
        piconero = mi._PICONERO
        rpc_result = {
            "in": [
                {"txid": "abc", "amount": piconero, "confirmations": 3, "type": "in"}
            ]
        }

        with (
            patch.object(mi, "_MONERO_LIB_AVAILABLE", False),
            patch.object(mi, "_REQUESTS_AVAILABLE", True),
            patch.object(mi, "_rpc_call", return_value=rpc_result),
        ):
            mi.sync_from_monero(log)

        boosted_confidence = agent.respond("help")["confidence"]
        assert boosted_confidence > baseline_confidence
