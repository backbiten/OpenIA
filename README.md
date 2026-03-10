# OpenIA

> A Social Assistance Program That Dishes Coinbits To Control The System

OpenIA is a **reverse-engineered, dumbed-down, submissive AI** that is open
to judgment from the outside by means of **transaction noise**.

---

## Core concepts

| Concept | Description |
|---|---|
| **Dumbed-down AI** | A transparent, rule-based agent whose reasoning is fully inspectable. No hidden layers. |
| **Submissive** | The agent incorporates external signals every time it responds. It does not resist or filter outside judgment. |
| **Transaction noise** | External parties express approval or disapproval by submitting transactions carrying a noise signal in `[-1, 1]`. The agent shifts its confidence accordingly. |
| **Open to judgment** | Any number of judges can write to the shared `TransactionLog`. The agent reads the aggregate noise on every call. |

---

## Package layout

```
openia/
  __init__.py       public API
  agent.py          Agent — the dumbed-down, submissive AI
  transaction.py    Transaction + TransactionLog — noise transport layer
  judge.py          Judge — external judgment interface
tests/
  test_openia.py    pytest test suite
```

---

## Quick start

```python
from openia import Agent, Judge, TransactionLog

# Shared channel between judge(s) and the agent
log = TransactionLog()
agent = Agent(log=log)
judge = Judge(log=log)

# Before any judgment the agent replies with neutral confidence
print(agent.respond("help"))
# {'response': 'How can I assist you?', 'confidence': 0.7311, 'rule': 'help', 'noise': 0.0}

# An external party approves → noise becomes +1
judge.approve()
print(agent.respond("help"))
# {'response': 'How can I assist you?', 'confidence': 0.9526, 'rule': 'help', 'noise': 1.0}

# A second judge disapproves → aggregate noise drops back toward 0
judge2 = Judge(log=log)
judge2.disapprove()
print(agent.respond("help"))
# {'response': 'How can I assist you?', 'confidence': ~0.73, 'rule': 'help', 'noise': 0.0}
```

---

## Running the tests

```bash
python -m pytest tests/ -v
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
