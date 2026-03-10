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

## Monero integration

OpenIA can use a running **monero-wallet-rpc** daemon as an optional source of
"coinbit" signals.  Each on-chain Monero transfer is converted into a
`Transaction` entry in the shared `TransactionLog`:

* **Incoming** transfers → positive noise (approval signal, up to +1).
* **Outgoing** transfers → negative noise (cost/disapproval signal, down to −1).

> **Note on `backbiten/monero`:** The repository
> `https://github.com/backbiten/monero.git` (tag `v0.18.4.3`) is the official
> Monero C++ daemon and cannot be pip-installed as a Python package directly.
> OpenIA uses the Python **`monero`** PyPI library
> ([pypi.org/project/monero](https://pypi.org/project/monero/)) as its
> wallet-RPC client, with an automatic fallback to a `requests`-based
> JSON-RPC adapter when the `monero` library is not installed.

### Prerequisites

1. Build and run **monerod** (or connect to a remote node):

   ```bash
   monerod --stagenet  # or mainnet without --stagenet
   ```

2. Start **monero-wallet-rpc** pointing at your wallet file:

   ```bash
   monero-wallet-rpc \
     --wallet-file /path/to/wallet \
     --password "" \
     --rpc-bind-port 18083 \
     --disable-rpc-login
   ```

### Installation

```bash
# Minimal: only requests-based fallback adapter
pip install requests

# Full: monero PyPI library (preferred)
pip install "openia[monero]"
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `MONERO_WALLET_RPC_URL` | `http://127.0.0.1:18083/json_rpc` | Wallet-RPC endpoint |
| `MONERO_WALLET_RPC_USER` | *(empty)* | Digest-auth username |
| `MONERO_WALLET_RPC_PASS` | *(empty)* | Digest-auth password |
| `MONERO_WALLET_ACCOUNT` | `0` | Account index to query |

### Minimal example

```python
import os
from openia import Agent, TransactionLog
from openia.monero_integration import sync_from_monero

os.environ["MONERO_WALLET_RPC_URL"] = "http://127.0.0.1:18083/json_rpc"

log = TransactionLog()
agent = Agent(log=log)

# Pull the latest incoming transfers into the log
records = sync_from_monero(log, min_confirmations=1)
print(f"Synced {len(records)} transfer(s); aggregate noise = {log.aggregate_noise:.4f}")

# Agent confidence is now influenced by Monero activity
print(agent.respond("help"))
```

### Graceful degradation

If neither the `monero` library nor `requests` is installed, calling
`sync_from_monero` raises an `ImportError` with a clear message — the rest
of OpenIA continues to work normally without Monero configured.

---

## Running the tests

```bash
python -m pytest tests/ -v
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
