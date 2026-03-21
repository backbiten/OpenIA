"""
OpenIA — A reverse-engineered, dumbed-down, submissive AI open to
external judgment by means of transaction noise.

Quick-start
-----------
>>> from openia import Agent, Judge, TransactionLog
>>> log = TransactionLog()
>>> agent = Agent(log=log)
>>> judge = Judge(log=log)
>>> agent.respond("help")
{'response': 'How can I assist you?', 'confidence': ..., 'rule': 'help', 'noise': 0.0, 'internal_market_report': ...}
>>> judge.approve()
>>> agent.respond("help")  # confidence is now higher
{'response': 'How can I assist you?', 'confidence': ..., 'rule': 'help', 'noise': 1.0, 'internal_market_report': ...}
"""

from .agent import Agent
from .judge import Judge
from .market import CURRENCIES, LIQUIDITY_BOOST_FACTOR, InternalMarket, MarketTick, MIN_PRICE_FLOOR
from .transaction import AssetManager, Transaction, TransactionLog

__all__ = [
    "Agent",
    "AssetManager",
    "CURRENCIES",
    "InternalMarket",
    "Judge",
    "LIQUIDITY_BOOST_FACTOR",
    "MarketTick",
    "MIN_PRICE_FLOOR",
    "Transaction",
    "TransactionLog",
]
