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
{'response': 'How can I assist you?', 'confidence': ..., 'rule': 'help', 'noise': 0.0}
>>> judge.approve()
>>> agent.respond("help")  # confidence is now higher
{'response': 'How can I assist you?', 'confidence': ..., 'rule': 'help', 'noise': 1.0}
"""

from .agent import Agent, MercenaryProtocol, SecurityClearance
from .judge import Judge
from .transaction import AssetManager, AssetType, Transaction, TransactionLog
from .recycling import MetadataScavenger

__all__ = [
    "Agent",
    "AssetManager",
    "AssetType",
    "Judge",
    "MercenaryProtocol",
    "MetadataScavenger",
    "SecurityClearance",
    "Transaction",
    "TransactionLog",
]
