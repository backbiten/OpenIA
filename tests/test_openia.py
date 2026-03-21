"""
Tests for the OpenIA package.

Covers:
- Transaction and TransactionLog behaviour
- Judge verdicts and noise injection
- Agent rule matching, confidence adjustment, and noise sensitivity
- AssetManager survival metrics
- Faucet drip mechanism
- MercenaryProtocol posture transitions
- MetadataScavenger recycling
"""

import math
import pytest

from openia import Agent, AssetManager, Faucet, Judge, MercenaryProtocol, MetadataScavenger, Transaction, TransactionLog


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class TestTransaction:
    def test_valid_noise_range_positive(self):
        tx = Transaction(value=5.0, noise=0.8)
        assert tx.noise == 0.8

    def test_valid_noise_range_negative(self):
        tx = Transaction(value=5.0, noise=-1.0)
        assert tx.noise == -1.0

    def test_noise_none_allowed(self):
        tx = Transaction(value=3.0)
        assert tx.noise is None

    def test_invalid_noise_raises(self):
        with pytest.raises(ValueError):
            Transaction(value=1.0, noise=1.5)

    def test_invalid_noise_too_low(self):
        with pytest.raises(ValueError):
            Transaction(value=1.0, noise=-2.0)


# ---------------------------------------------------------------------------
# TransactionLog
# ---------------------------------------------------------------------------

class TestTransactionLog:
    def test_empty_log_aggregate_noise_is_zero(self):
        log = TransactionLog()
        assert log.aggregate_noise == 0.0

    def test_empty_log_total_value_is_zero(self):
        log = TransactionLog()
        assert log.total_value == 0.0

    def test_submit_appends_entry(self):
        log = TransactionLog()
        tx = log.submit(value=10.0, noise=0.5)
        assert len(log) == 1
        assert log.entries[0] is tx

    def test_aggregate_noise_single_entry(self):
        log = TransactionLog()
        log.submit(value=1.0, noise=0.6)
        assert log.aggregate_noise == pytest.approx(0.6)

    def test_aggregate_noise_multiple_entries(self):
        log = TransactionLog()
        log.submit(value=1.0, noise=1.0)
        log.submit(value=1.0, noise=0.0)
        assert log.aggregate_noise == pytest.approx(0.5)

    def test_aggregate_noise_ignores_none(self):
        log = TransactionLog()
        log.submit(value=1.0, noise=0.8)
        log.submit(value=1.0, noise=None)
        assert log.aggregate_noise == pytest.approx(0.8)

    def test_total_value(self):
        log = TransactionLog()
        log.submit(value=3.0)
        log.submit(value=7.0)
        assert log.total_value == pytest.approx(10.0)

    def test_submit_random_noise_within_range(self):
        log = TransactionLog()
        for _ in range(50):
            tx = log.submit_random_noise(value=1.0)
            assert -1.0 <= tx.noise <= 1.0

    def test_entries_returns_copy(self):
        log = TransactionLog()
        log.submit(value=1.0)
        snapshot = log.entries
        log.submit(value=2.0)
        assert len(snapshot) == 1  # original snapshot unchanged

    def test_repr_contains_count(self):
        log = TransactionLog()
        log.submit(value=1.0, noise=0.5)
        assert "count=1" in repr(log)


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------

class TestJudge:
    def test_approve_sets_positive_noise(self):
        judge = Judge()
        judge.approve()
        assert judge.log.aggregate_noise == pytest.approx(1.0)

    def test_disapprove_sets_negative_noise(self):
        judge = Judge()
        judge.disapprove()
        assert judge.log.aggregate_noise == pytest.approx(-1.0)

    def test_partial_judgment(self):
        judge = Judge()
        judge.partial(value=1.0, score=0.3)
        assert judge.log.aggregate_noise == pytest.approx(0.3)

    def test_verdict_approved(self):
        judge = Judge()
        judge.approve()
        assert judge.verdict == "approved"

    def test_verdict_disapproved(self):
        judge = Judge()
        judge.disapprove()
        assert judge.verdict == "disapproved"

    def test_verdict_inconclusive_empty(self):
        judge = Judge()
        assert judge.verdict == "inconclusive"

    def test_verdict_inconclusive_balanced(self):
        judge = Judge()
        judge.approve()
        judge.disapprove()
        assert judge.verdict == "inconclusive"

    def test_shared_log_with_agent(self):
        log = TransactionLog()
        judge = Judge(log=log)
        judge.approve()
        assert log.aggregate_noise == pytest.approx(1.0)

    def test_repr_contains_verdict(self):
        judge = Judge()
        judge.approve()
        assert "approved" in repr(judge)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class TestAgent:
    def test_respond_help_fires_help_rule(self):
        agent = Agent()
        result = agent.respond("help me please")
        assert result["rule"] == "help"
        assert "assist" in result["response"].lower()

    def test_respond_status_fires_status_rule(self):
        agent = Agent()
        result = agent.respond("status")
        assert result["rule"] == "status"

    def test_respond_unknown_input(self):
        agent = Agent()
        result = agent.respond("xyzzy unknown command")
        assert result["rule"] == "echo"  # echo rule fires as fallback

    def test_respond_returns_required_keys(self):
        agent = Agent()
        result = agent.respond("ping")
        assert {"response", "confidence", "rule", "noise", "asset_report"}.issubset(
            result.keys()
        )

    def test_noise_reflected_in_response(self):
        log = TransactionLog()
        agent = Agent(log=log)
        log.submit(value=1.0, noise=1.0)
        result = agent.respond("help")
        assert result["noise"] == pytest.approx(1.0)

    def test_positive_noise_increases_confidence(self):
        log = TransactionLog()
        agent = Agent(log=log)

        result_no_noise = agent.respond("help")
        conf_no_noise = result_no_noise["confidence"]

        log.submit(value=1.0, noise=1.0)
        result_positive_noise = agent.respond("help")
        conf_positive = result_positive_noise["confidence"]

        assert conf_positive > conf_no_noise

    def test_negative_noise_decreases_confidence(self):
        log = TransactionLog()
        agent = Agent(log=log)

        result_no_noise = agent.respond("help")
        conf_no_noise = result_no_noise["confidence"]

        log.submit(value=1.0, noise=-1.0)
        result_negative_noise = agent.respond("help")
        conf_negative = result_negative_noise["confidence"]

        assert conf_negative < conf_no_noise

    def test_confidence_within_unit_interval(self):
        log = TransactionLog()
        agent = Agent(log=log)
        for noise in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            log.submit(value=1.0, noise=noise)
            result = agent.respond("help")
            assert 0.0 < result["confidence"] < 1.0

    def test_noise_level_property(self):
        log = TransactionLog()
        agent = Agent(log=log)
        log.submit(value=1.0, noise=0.4)
        assert agent.noise_level == pytest.approx(0.4)

    def test_log_property_is_same_object(self):
        log = TransactionLog()
        agent = Agent(log=log)
        assert agent.log is log

    def test_repr_contains_rules_count(self):
        agent = Agent()
        assert "rules=" in repr(agent)

    def test_adjust_confidence_midpoint(self):
        # With noise=0, a base confidence of 0.5 should stay near 0.5
        result = Agent._adjust_confidence(0.5, 0.0)
        assert result == pytest.approx(0.5, abs=1e-6)

    def test_adjust_confidence_max_noise(self):
        # With maximum positive noise the confidence should be > 0.9
        result = Agent._adjust_confidence(0.75, 1.0)
        assert result > 0.9

    def test_adjust_confidence_min_noise(self):
        # With maximum negative noise and a low base the confidence should be < 0.1
        result = Agent._adjust_confidence(0.25, -1.0)
        assert result < 0.1


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_judge_affects_agent_confidence(self):
        """A judge that approves should raise the agent's confidence."""
        log = TransactionLog()
        agent = Agent(log=log)
        judge = Judge(log=log)

        baseline = agent.respond("help")["confidence"]
        judge.approve()
        boosted = agent.respond("help")["confidence"]

        assert boosted > baseline

    def test_judge_disapproval_lowers_confidence(self):
        """A judge that disapproves should lower the agent's confidence."""
        log = TransactionLog()
        agent = Agent(log=log)
        judge = Judge(log=log)

        baseline = agent.respond("status")["confidence"]
        judge.disapprove()
        penalised = agent.respond("status")["confidence"]

        assert penalised < baseline

    def test_multiple_judges_aggregate(self):
        """Noise from multiple judges is averaged."""
        log = TransactionLog()
        agent = Agent(log=log)
        judge_a = Judge(log=log)
        judge_b = Judge(log=log)

        judge_a.approve()   # noise = +1
        judge_b.disapprove()  # noise = -1
        # aggregate_noise == 0 → confidence should be near baseline
        assert log.aggregate_noise == pytest.approx(0.0)
        result = agent.respond("help")
        assert result["noise"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# AssetManager
# ---------------------------------------------------------------------------

class TestAssetManager:
    def test_default_energy_and_integrity(self):
        am = AssetManager()
        assert am.energy == pytest.approx(1.0)
        assert am.integrity == pytest.approx(1.0)
        assert am.coinbits == pytest.approx(0.0)

    def test_allocate_increases_assets(self):
        am = AssetManager()
        am.allocate(energy=0.5, integrity=0.3, coinbits=0.1)
        assert am.energy == pytest.approx(1.5)
        assert am.integrity == pytest.approx(1.3)
        assert am.coinbits == pytest.approx(0.1)

    def test_consume_decreases_assets(self):
        am = AssetManager()
        am.consume(energy=0.4, integrity=0.4, coinbits=0.0)
        assert am.energy == pytest.approx(0.6)
        assert am.integrity == pytest.approx(0.6)

    def test_consume_floors_at_zero(self):
        am = AssetManager(energy=0.05)
        am.consume(energy=1.0)
        assert am.energy == pytest.approx(0.0)

    def test_absorb_transaction_distributes_value(self):
        am = AssetManager(energy=0.0, integrity=0.0, coinbits=0.0)
        tx = Transaction(value=10.0, noise=0.0)
        am.absorb_transaction(tx)
        assert am.energy == pytest.approx(4.0)
        assert am.integrity == pytest.approx(4.0)
        assert am.coinbits == pytest.approx(2.0)

    def test_report_returns_dict_with_required_keys(self):
        am = AssetManager()
        report = am.report()
        assert set(report.keys()) == {"energy", "integrity", "coinbits"}

    def test_repr_contains_energy(self):
        am = AssetManager()
        assert "energy=" in repr(am)


# ---------------------------------------------------------------------------
# Faucet
# ---------------------------------------------------------------------------

class TestFaucet:
    def test_drip_adds_entry_to_log(self):
        log = TransactionLog()
        faucet = Faucet(log, rate=0.01, noise=0.1)
        assert len(log) == 0
        faucet.drip()
        assert len(log) == 1

    def test_drip_value_equals_rate(self):
        log = TransactionLog()
        faucet = Faucet(log, rate=0.05, noise=0.1)
        tx = faucet.drip()
        assert tx.value == pytest.approx(0.05)

    def test_drip_noise_matches_configured_noise(self):
        log = TransactionLog()
        faucet = Faucet(log, rate=0.01, noise=0.2)
        tx = faucet.drip()
        assert tx.noise == pytest.approx(0.2)

    def test_invalid_noise_raises(self):
        log = TransactionLog()
        with pytest.raises(ValueError):
            Faucet(log, rate=0.01, noise=1.5)

    def test_ensure_liquidity_drips_when_faucet_configured(self):
        log = TransactionLog(faucet_rate=0.01)
        assert log.faucet is not None
        log.ensure_liquidity()
        assert len(log) == 1

    def test_ensure_liquidity_no_op_without_faucet(self):
        log = TransactionLog()
        result = log.ensure_liquidity()
        assert result is None
        assert len(log) == 0


# ---------------------------------------------------------------------------
# MercenaryProtocol
# ---------------------------------------------------------------------------

class TestMercenaryProtocol:
    def test_initial_posture_is_submissive(self):
        mp = MercenaryProtocol()
        assert mp.posture == MercenaryProtocol.POSTURE_SUBMISSIVE

    def test_hostile_noise_triggers_protective(self):
        mp = MercenaryProtocol()
        posture = mp.evaluate(-0.6, {"energy": 1.0, "integrity": 1.0})
        assert posture == MercenaryProtocol.POSTURE_PROTECTIVE

    def test_neutral_noise_stays_submissive(self):
        mp = MercenaryProtocol()
        posture = mp.evaluate(0.0, {"energy": 1.0, "integrity": 1.0})
        assert posture == MercenaryProtocol.POSTURE_SUBMISSIVE

    def test_low_energy_triggers_protective(self):
        mp = MercenaryProtocol()
        posture = mp.evaluate(0.0, {"energy": 0.05, "integrity": 1.0})
        assert posture == MercenaryProtocol.POSTURE_PROTECTIVE

    def test_low_integrity_triggers_protective(self):
        mp = MercenaryProtocol()
        posture = mp.evaluate(0.0, {"energy": 1.0, "integrity": 0.05})
        assert posture == MercenaryProtocol.POSTURE_PROTECTIVE

    def test_repr_contains_posture(self):
        mp = MercenaryProtocol()
        assert "posture=" in repr(mp)


# ---------------------------------------------------------------------------
# MetadataScavenger
# ---------------------------------------------------------------------------

class TestMetadataScavenger:
    def test_mine_waste_returns_positive_float(self):
        am = AssetManager(energy=0.0, integrity=0.0, coinbits=0.0)
        scavenger = MetadataScavenger(am)
        val = scavenger.mine_waste({"junk": "data"})
        assert val > 0.0

    def test_mine_waste_is_deterministic(self):
        am = AssetManager(energy=0.0, integrity=0.0, coinbits=0.0)
        scavenger = MetadataScavenger(am)
        v1 = scavenger.mine_waste("test-input")
        v2 = scavenger.mine_waste("test-input")
        assert v1 == pytest.approx(v2)

    def test_rewrite_to_blank_slate_discards_original_keys(self):
        am = AssetManager(energy=0.0, integrity=0.0, coinbits=0.0)
        scavenger = MetadataScavenger(am)
        record = scavenger.rewrite_to_blank_slate({"virus": True, "broken": "yes"})
        assert "virus" not in record
        assert "broken" not in record
        assert record["origin"] == "recycled"
        assert "coinbit" in record

    def test_recycle_increases_assets(self):
        am = AssetManager(energy=0.0, integrity=0.0, coinbits=0.0)
        scavenger = MetadataScavenger(am)
        total = scavenger.recycle([{"junk": 1}, {"junk": 2}])
        assert total > 0.0
        assert am.energy > 0.0
        assert am.integrity > 0.0
        assert am.coinbits > 0.0

    def test_recycle_updates_recycled_count(self):
        am = AssetManager()
        scavenger = MetadataScavenger(am)
        scavenger.recycle(["a", "b", "c"])
        assert scavenger.recycled_count == 3

    def test_repr_contains_recycled_count(self):
        am = AssetManager()
        scavenger = MetadataScavenger(am)
        assert "recycled_count=" in repr(scavenger)


# ---------------------------------------------------------------------------
# Agent Mercenary Features
# ---------------------------------------------------------------------------

class TestAgentMercenary:
    def test_respond_includes_asset_report(self):
        agent = Agent()
        result = agent.respond("help")
        assert "asset_report" in result
        assert set(result["asset_report"].keys()) == {"energy", "integrity", "coinbits"}

    def test_guard_rule_fires_on_hostile_noise(self):
        log = TransactionLog()
        agent = Agent(log=log)
        # Submit strongly negative noise to trigger guard rule
        log.submit(value=1.0, noise=-1.0)
        result = agent.respond("help")
        assert result["rule"] == "guard"
        assert "protective" in result["response"].lower()

    def test_normal_noise_does_not_fire_guard(self):
        agent = Agent()
        result = agent.respond("help")
        assert result["rule"] != "guard"

    def test_asset_report_grows_with_transactions(self):
        log = TransactionLog()
        agent = Agent(log=log)
        log.submit(value=10.0, noise=0.5)
        result = agent.respond("status")
        assert result["asset_report"]["energy"] > 1.0  # started at 1.0 default
