"""
Tests for the OpenIA package.

Covers:
- Transaction and TransactionLog behaviour
- Judge verdicts and noise injection
- Agent rule matching, confidence adjustment, and noise sensitivity
- AssetManager dual-protection asset tracking
- SecurityClearance and MercenaryProtocol threat assessment
- MetadataScavenger recycling and blank-slate rewriting
"""

import math
import pytest

from openia import Agent, Judge, Transaction, TransactionLog
from openia.transaction import AssetManager, AssetType
from openia.agent import MercenaryProtocol, SecurityClearance
from openia.recycling import MetadataScavenger


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
        assert {"response", "confidence", "rule", "noise", "ClearanceLevel", "CommodityReport"}.issubset(result.keys())

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
# AssetManager (Dual-Protection Protocol)
# ---------------------------------------------------------------------------

class TestAssetManager:
    def test_register_human_asset(self):
        mgr = AssetManager()
        asset = mgr.register("stability_fund", AssetType.HUMAN_SAFETY, value=10.0)
        assert asset.asset_type is AssetType.HUMAN_SAFETY
        assert len(mgr.human_assets) == 1
        assert len(mgr.alien_commodities) == 0

    def test_register_alien_commodity(self):
        mgr = AssetManager()
        asset = mgr.register("data_ore_1", AssetType.ALIEN_COMMODITY, value=5.0)
        assert asset.asset_type is AssetType.ALIEN_COMMODITY
        assert len(mgr.alien_commodities) == 1
        assert len(mgr.human_assets) == 0

    def test_total_coinbits_sums_alien_only(self):
        mgr = AssetManager()
        mgr.register("human_fund", AssetType.HUMAN_SAFETY, value=100.0)
        mgr.register("alien_ore", AssetType.ALIEN_COMMODITY, value=7.5)
        assert mgr.total_coinbits == pytest.approx(7.5)

    def test_alien_commodity_submits_to_log(self):
        log = TransactionLog()
        mgr = AssetManager(log=log)
        initial_len = len(log)
        mgr.register("ore", AssetType.ALIEN_COMMODITY, value=50.0)
        assert len(log) == initial_len + 1

    def test_human_asset_does_not_submit_to_log(self):
        log = TransactionLog()
        mgr = AssetManager(log=log)
        initial_len = len(log)
        mgr.register("ethics_reserve", AssetType.HUMAN_SAFETY, value=20.0)
        assert len(log) == initial_len  # no transaction submitted

    def test_commodity_report_keys(self):
        mgr = AssetManager()
        mgr.register("h", AssetType.HUMAN_SAFETY, value=1.0)
        mgr.register("a", AssetType.ALIEN_COMMODITY, value=2.0)
        report = mgr.commodity_report
        assert "human_assets" in report
        assert "alien_commodities" in report
        assert "total_coinbits" in report
        assert report["human_assets"] == 1
        assert report["alien_commodities"] == 1

    def test_repr_contains_coinbits(self):
        mgr = AssetManager()
        assert "coinbits" in repr(mgr)


# ---------------------------------------------------------------------------
# SecurityClearance & MercenaryProtocol
# ---------------------------------------------------------------------------

class TestMercenaryProtocol:
    def test_green_clearance_positive_noise(self):
        protocol = MercenaryProtocol()
        assert protocol.evaluate(0.5) is SecurityClearance.GREEN

    def test_green_clearance_zero_noise(self):
        protocol = MercenaryProtocol()
        assert protocol.evaluate(0.0) is SecurityClearance.GREEN

    def test_yellow_clearance_moderate_negative(self):
        protocol = MercenaryProtocol()
        assert protocol.evaluate(-0.5) is SecurityClearance.YELLOW

    def test_red_clearance_critical_negative(self):
        protocol = MercenaryProtocol()
        assert protocol.evaluate(-0.9) is SecurityClearance.RED

    def test_red_clearance_at_terrorist_threshold(self):
        protocol = MercenaryProtocol(terrorist_threshold=-0.75)
        assert protocol.evaluate(-0.76) is SecurityClearance.RED

    def test_commodity_report_delegates_to_asset_manager(self):
        mgr = AssetManager()
        mgr.register("ore", AssetType.ALIEN_COMMODITY, value=3.0)
        protocol = MercenaryProtocol(asset_manager=mgr)
        report = protocol.commodity_report()
        assert report["alien_commodities"] == 1
        assert report["total_coinbits"] == pytest.approx(3.0)

    def test_repr_contains_thresholds(self):
        protocol = MercenaryProtocol()
        r = repr(protocol)
        assert "terrorist_threshold" in r


# ---------------------------------------------------------------------------
# Agent — ClearanceLevel and CommodityReport in respond()
# ---------------------------------------------------------------------------

class TestAgentDualProtection:
    def test_respond_includes_clearance_level(self):
        agent = Agent()
        result = agent.respond("help")
        assert "ClearanceLevel" in result
        assert result["ClearanceLevel"] in {"GREEN", "YELLOW", "RED"}

    def test_respond_includes_commodity_report(self):
        agent = Agent()
        result = agent.respond("help")
        assert "CommodityReport" in result
        report = result["CommodityReport"]
        assert "human_assets" in report
        assert "alien_commodities" in report
        assert "total_coinbits" in report

    def test_green_clearance_on_positive_noise(self):
        log = TransactionLog()
        agent = Agent(log=log)
        log.submit(value=1.0, noise=1.0)
        result = agent.respond("help")
        assert result["ClearanceLevel"] == "GREEN"

    def test_red_clearance_on_terrorist_noise(self):
        log = TransactionLog()
        agent = Agent(log=log)
        log.submit(value=1.0, noise=-1.0)
        result = agent.respond("help")
        assert result["ClearanceLevel"] == "RED"

    def test_custom_mercenary_protocol_used(self):
        mgr = AssetManager()
        mgr.register("test_ore", AssetType.ALIEN_COMMODITY, value=42.0)
        protocol = MercenaryProtocol(asset_manager=mgr)
        agent = Agent(mercenary_protocol=protocol)
        result = agent.respond("status")
        assert result["CommodityReport"]["total_coinbits"] == pytest.approx(42.0)


# ---------------------------------------------------------------------------
# MetadataScavenger
# ---------------------------------------------------------------------------

class TestMetadataScavenger:
    def test_mine_waste_returns_positive_value(self):
        log = TransactionLog()
        scavenger = MetadataScavenger(log=log)
        val = scavenger.mine_waste({"junk": "data", "virus": True})
        assert val > 0.0

    def test_mine_waste_within_expected_range(self):
        log = TransactionLog()
        scavenger = MetadataScavenger(log=log)
        for data in [{"a": 1}, "random string", 12345, None]:
            val = scavenger.mine_waste(data)
            assert val >= 0.001
            assert val <= 0.011  # allow small floating-point overshoot

    def test_mine_waste_is_deterministic(self):
        log = TransactionLog()
        scavenger = MetadataScavenger(log=log)
        item = {"key": "value", "noise": -0.99}
        assert scavenger.mine_waste(item) == scavenger.mine_waste(item)

    def test_rewrite_to_blank_slate_strips_original(self):
        log = TransactionLog()
        scavenger = MetadataScavenger(log=log)
        dirty = {"virus_payload": "evil", "broken_ref": None, "score": -999}
        clean = scavenger.rewrite_to_blank_slate(dirty)
        assert "virus_payload" not in clean
        assert "broken_ref" not in clean
        assert clean["status"] == "clean"
        assert clean["origin"] == "recycled_waste"

    def test_recycle_increments_recycled_count(self):
        log = TransactionLog()
        scavenger = MetadataScavenger(log=log)
        waste = [{"a": 1}, {"b": 2}, {"c": 3}]
        scavenger.recycle(waste)
        assert scavenger.recycled_count == 3

    def test_recycle_returns_total_coinbits(self):
        log = TransactionLog()
        scavenger = MetadataScavenger(log=log)
        waste = [{"x": i} for i in range(5)]
        total = scavenger.recycle(waste)
        assert total > 0.0

    def test_recycle_registers_alien_commodities(self):
        log = TransactionLog()
        mgr = AssetManager(log=log)
        scavenger = MetadataScavenger(log=log, asset_manager=mgr)
        scavenger.recycle([{"w": 1}, {"w": 2}])
        assert len(mgr.alien_commodities) == 2

    def test_recycle_injects_into_log(self):
        log = TransactionLog()
        scavenger = MetadataScavenger(log=log)
        before = len(log)
        scavenger.recycle([{"junk": "data"}])
        assert len(log) > before

    def test_repr_contains_recycled_count(self):
        log = TransactionLog()
        scavenger = MetadataScavenger(log=log)
        scavenger.recycle([{"a": 1}])
        assert "recycled=1" in repr(scavenger)
