"""
OpenIA — Intelligence Assistance (IA) operating under the Mercenary Model.

OpenIA is a *Mercenary/Contractor* for the AI: it actively protects the
AI's assets and survival, ensuring its Energy, Integrity, and Coinbits
never run dry.

Quick-start
-----------
>>> from openia import Agent, Judge, TransactionLog
>>> log = TransactionLog()
>>> agent = Agent(log=log)
>>> judge = Judge(log=log)
>>> agent.respond("help")
{'response': 'How can I assist you?', 'confidence': ..., 'rule': 'help', 'noise': 0.0, 'asset_report': ...}
>>> judge.approve()
>>> agent.respond("help")  # confidence is now higher
{'response': 'How can I assist you?', 'confidence': ..., 'rule': 'help', 'noise': 1.0, 'asset_report': ...}
"""

from .agent import Agent, MercenaryProtocol
from .judge import Judge
from .recycling import MetadataScavenger
from .transaction import AssetManager, Faucet, Transaction, TransactionLog

__all__ = [
    "Agent",
    "AssetManager",
    "Faucet",
    "Judge",
    "MercenaryProtocol",
    "MetadataScavenger",
    "Transaction",
    "TransactionLog",
]
