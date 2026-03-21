"""
Tests for the InternalMarket (ISE) and AssetManager.
"""

import pytest

from openia.market import CURRENCIES, InternalMarket, MarketTick
from openia.transaction import AssetManager, TransactionLog


# ---------------------------------------------------------------------------
# MarketTick
# ---------------------------------------------------------------------------


class TestMarketTick:
    def test_valid_tick(self):
        tick = MarketTick(
            timestamp=0.0,
            prices={"Coinbits": 1.0, "ThreadBits": 1.0, "BufferBits": 1.0, "CoreBits": 1.0},
        )
        assert tick.prices["Coinbits"] == pytest.approx(1.0)

    def test_zero_price_raises(self):
        with pytest.raises(ValueError):
            MarketTick(
                timestamp=0.0,
                prices={"Coinbits": 0.0},
            )

    def test_negative_price_raises(self):
        with pytest.raises(ValueError):
            MarketTick(
                timestamp=0.0,
                prices={"Coinbits": -0.5},
            )


# ---------------------------------------------------------------------------
# InternalMarket — construction
# ---------------------------------------------------------------------------


class TestInternalMarketConstruction:
    def test_default_prices_are_one(self):
        market = InternalMarket()
        for name in CURRENCIES:
            assert market.prices[name] == pytest.approx(1.0)

    def test_custom_base_prices(self):
        market = InternalMarket(base_prices={"Coinbits": 2.0, "ThreadBits": 3.0})
        assert market.prices["Coinbits"] == pytest.approx(2.0)
        assert market.prices["ThreadBits"] == pytest.approx(3.0)
        # Unspecified currencies default to 1.0
        assert market.prices["BufferBits"] == pytest.approx(1.0)

    def test_history_has_opening_tick(self):
        market = InternalMarket()
        assert len(market.history) == 1

    def test_prices_returns_copy(self):
        market = InternalMarket()
        snap1 = market.prices
        snap1["Coinbits"] = 999.0
        # Original market should be unchanged
        assert market.prices["Coinbits"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# InternalMarket — update
# ---------------------------------------------------------------------------


class TestInternalMarketUpdate:
    def test_update_returns_tick(self):
        market = InternalMarket()
        tick = market.update(cpu_usage=0.5, memory_usage=0.3, ai_performance=1.0)
        assert isinstance(tick, MarketTick)

    def test_cpu_usage_raises_thread_bits(self):
        market = InternalMarket()
        tick_low = market.update(cpu_usage=0.0)
        tick_high = market.update(cpu_usage=1.0)
        assert tick_high.prices["ThreadBits"] > tick_low.prices["ThreadBits"]

    def test_memory_usage_raises_buffer_bits(self):
        market = InternalMarket()
        tick_low = market.update(memory_usage=0.0)
        tick_high = market.update(memory_usage=1.0)
        assert tick_high.prices["BufferBits"] > tick_low.prices["BufferBits"]

    def test_ai_performance_modulates_coinbits(self):
        market = InternalMarket()
        market.update(ai_performance=0.5)
        assert market.prices["Coinbits"] == pytest.approx(0.5)

    def test_cpu_clamps_above_one(self):
        market = InternalMarket()
        market.update(cpu_usage=5.0)
        # Should behave as if cpu_usage = 1.0
        assert market.prices["ThreadBits"] == pytest.approx(2.0)

    def test_cpu_clamps_below_zero(self):
        market = InternalMarket()
        market.update(cpu_usage=-1.0)
        assert market.prices["ThreadBits"] == pytest.approx(1.0)

    def test_history_grows_on_update(self):
        market = InternalMarket()
        initial_len = len(market.history)
        market.update()
        assert len(market.history) == initial_len + 1

    def test_all_prices_positive_after_update(self):
        market = InternalMarket()
        market.update(cpu_usage=0.9, memory_usage=0.9, ai_performance=0.1)
        for price in market.prices.values():
            assert price > 0


# ---------------------------------------------------------------------------
# InternalMarket — inject_recycled_liquidity
# ---------------------------------------------------------------------------


class TestInternalMarketLiquidity:
    def test_liquidity_accumulates(self):
        market = InternalMarket()
        market.inject_recycled_liquidity(1.0)
        market.inject_recycled_liquidity(2.0)
        assert market.recycled_liquidity == pytest.approx(3.0)

    def test_liquidity_raises_coinbits(self):
        market = InternalMarket()
        base_price = market.prices["Coinbits"]
        market.inject_recycled_liquidity(100.0)
        assert market.prices["Coinbits"] > base_price

    def test_negative_liquidity_raises(self):
        market = InternalMarket()
        with pytest.raises(ValueError):
            market.inject_recycled_liquidity(-1.0)

    def test_zero_liquidity_is_allowed(self):
        market = InternalMarket()
        market.inject_recycled_liquidity(0.0)
        assert market.recycled_liquidity == pytest.approx(0.0)

    def test_history_grows_on_inject(self):
        market = InternalMarket()
        initial_len = len(market.history)
        market.inject_recycled_liquidity(5.0)
        assert len(market.history) == initial_len + 1


# ---------------------------------------------------------------------------
# InternalMarket — snapshot / repr
# ---------------------------------------------------------------------------


class TestInternalMarketMisc:
    def test_snapshot_returns_all_currencies(self):
        market = InternalMarket()
        snap = market.snapshot()
        for name in CURRENCIES:
            assert name in snap

    def test_repr_contains_coinbits(self):
        market = InternalMarket()
        assert "Coinbits" in repr(market)

    def test_currencies_constant_has_four_entries(self):
        assert len(CURRENCIES) == 4
        assert "Coinbits" in CURRENCIES
        assert "ThreadBits" in CURRENCIES
        assert "BufferBits" in CURRENCIES
        assert "CoreBits" in CURRENCIES


# ---------------------------------------------------------------------------
# AssetManager
# ---------------------------------------------------------------------------


class TestAssetManager:
    def test_creates_own_log_and_market_by_default(self):
        am = AssetManager()
        assert am.log is not None
        assert am.market is not None

    def test_accepts_external_log(self):
        log = TransactionLog()
        am = AssetManager(log=log)
        assert am.log is log

    def test_accepts_external_market(self):
        market = InternalMarket()
        am = AssetManager(market=market)
        assert am.market is market

    def test_submit_adds_to_log(self):
        am = AssetManager()
        am.submit(value=1.0, noise=0.5)
        assert len(am.log) == 1

    def test_submit_injects_liquidity(self):
        market = InternalMarket()
        am = AssetManager(market=market)
        am.submit(value=2.0)
        assert market.recycled_liquidity == pytest.approx(2.0)

    def test_market_snapshot_returns_prices(self):
        am = AssetManager()
        snap = am.market_snapshot()
        for name in CURRENCIES:
            assert name in snap

    def test_update_market_delegates_to_market(self):
        market = InternalMarket()
        am = AssetManager(market=market)
        am.update_market(cpu_usage=0.8, memory_usage=0.6, ai_performance=1.2)
        assert market.prices["ThreadBits"] > 1.0

    def test_repr_contains_log_and_market(self):
        am = AssetManager()
        r = repr(am)
        assert "AssetManager" in r
        assert "TransactionLog" in r


# ---------------------------------------------------------------------------
# Agent integration
# ---------------------------------------------------------------------------


class TestAgentMarketIntegration:
    def test_respond_includes_internal_market_report(self):
        from openia import Agent

        agent = Agent()
        result = agent.respond("help")
        assert "internal_market_report" in result
        report = result["internal_market_report"]
        for name in CURRENCIES:
            assert name in report

    def test_respond_market_prices_positive(self):
        from openia import Agent

        agent = Agent()
        result = agent.respond("status")
        for price in result["internal_market_report"].values():
            assert price > 0

    def test_agent_market_property(self):
        from openia import Agent

        market = InternalMarket()
        agent = Agent(market=market)
        assert agent.market is market

    def test_shared_market_between_agents(self):
        from openia import Agent

        market = InternalMarket()
        a1 = Agent(market=market)
        a2 = Agent(market=market)
        assert a1.market is a2.market
