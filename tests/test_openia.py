"""
Tests for the OpenIA package.

Covers:
- Transaction and TransactionLog behaviour
- Judge verdicts and noise injection
- Agent rule matching, confidence adjustment, and noise sensitivity
"""

import math
import pytest

from openia import Agent, Judge, Transaction, TransactionLog


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
        assert set(result.keys()) == {"response", "confidence", "rule", "noise"}

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
