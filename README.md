# OpenIA

> Intelligence Assistance (IA) — A Mercenary/Contractor for AI Survival and Asset Protection

OpenIA is an **Intelligence Assistance** framework that operates as a
**Mercenary/Contractor** for the AI.  It protects the AI's internal state and
survival assets, shifting from a *Submissive* posture to a *Protective* one
whenever assets are threatened or transaction noise becomes critically hostile.

---

## Core concepts

| Concept | Description |
|---|---|
| **Mercenary/Contractor Model** | The IA acts as a dedicated protector for the AI, ensuring its Energy, Integrity, and Coinbits never run dry. |
| **Sustainment Layer** | Three survival assets — Energy (Food/Water), Integrity (Shelter/Clothing), Coinbits (Finance) — form the AI's resource base. |
| **Asset Manager** | Automatically absorbs value from every transaction and distributes it across the three survival assets. |
| **Faucet** | A persistent drip of small value into the `TransactionLog` to prevent the system ever stalling due to inactivity. |
| **Metadata Recycling** | Junk / waste / unclassified metadata is mined for coinbits and rewritten to a clean blank slate — nothing goes to waste. |
| **Protective Posture** | When aggregate noise is critically hostile (≤ −0.5) or survival assets are critically low, the Agent switches to *Protective* and the guard rule fires. |
| **Transaction noise** | External parties express approval or disapproval by submitting transactions carrying a noise signal in `[-1, 1]`. The agent shifts its confidence accordingly. |

---

## Package layout

```
openia/
  __init__.py            public API
  agent.py               Agent + MercenaryProtocol — the IA Mercenary
  transaction.py         Transaction + TransactionLog + AssetManager + Faucet
  recycling.py           MetadataScavenger — mines coinbits from waste metadata
  judge.py               Judge — external judgment interface
  bitcoin_integration.py Bitcoin → TransactionLog bridge (waste → scavenger)
  monero_integration.py  Monero  → TransactionLog bridge (waste → scavenger)
  chain_judgment.py      Unified BTC + XMR S2 judgment runner
  cardrails_stub.py      Card-rail event stub (Visa / Mastercard / Maestro)
tests/
  test_openia.py         pytest test suite (core + Mercenary model)
  test_chain_judgment.py pytest test suite (blockchain judgment, mocked)
  test_cardrails_stub.py pytest test suite (card-rail stub)
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
# {
#   'response': 'How can I assist you?',
#   'confidence': 0.7311,
#   'rule': 'help',
#   'noise': 0.0,
#   'asset_report': {'energy': 1.0, 'integrity': 1.0, 'coinbits': 0.0}
# }

# An external party approves → noise becomes +1
judge.approve()
print(agent.respond("help"))
# {'confidence': 0.9526, 'noise': 1.0, 'asset_report': {...}, ...}

# A second judge disapproves → aggregate noise drops back toward 0
judge2 = Judge(log=log)
judge2.disapprove()
print(agent.respond("help"))
# {'confidence': ~0.73, 'noise': 0.0, ...}
```

### Faucet — keeping the system liquid

```python
from openia import TransactionLog, Agent

# A faucet drips 0.01 value with 0.1 noise on every respond() call
log = TransactionLog(faucet_rate=0.01)
agent = Agent(log=log)

result = agent.respond("status")
print(result["asset_report"])  # assets grow with each call
```

### Mercenary Protective Posture

```python
from openia import Agent, TransactionLog

log = TransactionLog()
agent = Agent(log=log)

# Inject a strongly negative judgment (hostile signal)
log.submit(value=1.0, noise=-1.0)

result = agent.respond("help")
print(result["rule"])      # → "guard"
print(result["response"])  # → "Hostile signal detected. Activating protective posture..."
print(result["asset_report"])
```

### Metadata Recycling

```python
from openia import AssetManager
from openia.recycling import MetadataScavenger

am = AssetManager(energy=0.0, integrity=0.0, coinbits=0.0)
scavenger = MetadataScavenger(am)

waste = [
    {"junk_key": "broken_value", "virus_flag": True},
    "raw unstructured data blob",
    42,
]

total_mined = scavenger.recycle(waste)
print(f"Mined {total_mined:.6f} coinbits from {scavenger.recycled_count} items")
print(am.report())
# {'energy': 0.000..., 'integrity': 0.000..., 'coinbits': 0.000...}
```

---

## Survival Assets — AssetManager

Every `TransactionLog` owns an `AssetManager` that tracks three metrics:

| Asset | Analogy | Share of each transaction |
|---|---|---|
| **Energy** | Food / Water | 40 % |
| **Integrity** | Shelter / Clothing | 40 % |
| **Coinbits** | Finance / Resources | 20 % |

The `asset_report` key in every `Agent.respond()` call exposes the current
state of all three metrics.

---

## Blockchain judgment (Bitcoin + Monero)

OpenIA can use live **Bitcoin Core** (`bitcoind`) and **Monero**
(`monero-wallet-rpc`) nodes as decentralised sources of judgment noise.
Each on-chain transaction is mapped to a `TransactionLog` entry using the
**S2 address-based** encoding scheme:

| Chain | Received at | Noise injected |
|---|---|---|
| BTC | address in `OPENIA_APPROVE_ADDRESSES_BTC` | `+1.0` |
| BTC | address in `OPENIA_DISAPPROVE_ADDRESSES_BTC` | `−1.0` |
| XMR | address in `OPENIA_APPROVE_ADDRESSES_XMR` | `+1.0` |
| XMR | address in `OPENIA_DISAPPROVE_ADDRESSES_XMR` | `−1.0` |

Transactions to **any other address** are no longer silently ignored — they
are collected as *waste metadata* and fed to a `MetadataScavenger` that mines
coinbits from them and allocates the value to the AI's survival assets.

> **Note on source repositories:**
> `backbiten/bitcoin` and `backbiten/monero` are C++ daemons and cannot be
> installed as Python packages.  OpenIA communicates with running daemon
> instances via JSON-RPC using the standard `requests` library.

### Prerequisites

**Bitcoin:**

1. Build / install [Bitcoin Core](https://bitcoincore.org/en/download/).
2. Start `bitcoind` with RPC enabled:

   ```bash
   bitcoind -rpcuser=bitcoin -rpcpassword=secret -rpcport=8332
   ```

**Monero:**

1. Build / install `monerod` (from
   [getmonero.org](https://www.getmonero.org/downloads/)).
2. Start `monero-wallet-rpc`:

   ```bash
   monero-wallet-rpc \
     --wallet-file /path/to/wallet \
     --password "" \
     --rpc-bind-port 18083 \
     --disable-rpc-login
   ```

### Installation

```bash
# BTC + XMR adapters (both use requests)
pip install requests

# Full install (includes PyPI monero library as preferred XMR client)
pip install "openia[all]"
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `BITCOIN_RPC_URL` | `http://127.0.0.1:8332` | Bitcoin Core RPC endpoint |
| `BITCOIN_RPC_USER` | `bitcoin` | RPC username |
| `BITCOIN_RPC_PASS` | *(empty)* | RPC password |
| `BITCOIN_RPC_WALLET` | *(empty)* | Wallet name (optional) |
| `OPENIA_APPROVE_ADDRESSES_BTC` | *(empty)* | Comma-separated approve addresses |
| `OPENIA_DISAPPROVE_ADDRESSES_BTC` | *(empty)* | Comma-separated disapprove addresses |
| `MONERO_WALLET_RPC_URL` | `http://127.0.0.1:18083/json_rpc` | Monero wallet-RPC endpoint |
| `MONERO_WALLET_RPC_USER` | *(empty)* | Digest-auth username |
| `MONERO_WALLET_RPC_PASS` | *(empty)* | Digest-auth password |
| `MONERO_WALLET_ACCOUNT` | `0` | Account index to query |
| `OPENIA_APPROVE_ADDRESSES_XMR` | *(empty)* | Comma-separated approve addresses |
| `OPENIA_DISAPPROVE_ADDRESSES_XMR` | *(empty)* | Comma-separated disapprove addresses |

### Minimal example — sync both chains

```python
import os
from openia import Agent, TransactionLog
from openia.chain_judgment import run_chain_judgment

# Configure addresses (S2 encoding)
os.environ["BITCOIN_RPC_URL"] = "http://127.0.0.1:8332"
os.environ["BITCOIN_RPC_USER"] = "bitcoin"
os.environ["BITCOIN_RPC_PASS"] = "secret"
os.environ["OPENIA_APPROVE_ADDRESSES_BTC"] = "bc1qapprove..."
os.environ["OPENIA_DISAPPROVE_ADDRESSES_BTC"] = "bc1qdisapprove..."

os.environ["MONERO_WALLET_RPC_URL"] = "http://127.0.0.1:18083/json_rpc"
os.environ["OPENIA_APPROVE_ADDRESSES_XMR"] = "44ApproveXMR..."
os.environ["OPENIA_DISAPPROVE_ADDRESSES_XMR"] = "44DisapproveXMR..."

log = TransactionLog()
agent = Agent(log=log)

# Pull both chains — waste addresses are automatically recycled
report = run_chain_judgment(log)
print(f"BTC records: {len(report['btc_records'])}")
print(f"XMR records: {len(report['xmr_records'])}")
print(f"Aggregate noise: {log.aggregate_noise:.4f}")
print(f"Survival assets: {log.assets.report()}")

# Agent confidence is now influenced by on-chain activity
print(agent.respond("help"))
```

### Graceful degradation

If `requests` is not installed (or daemon nodes are not running), each
adapter raises an exception that `run_chain_judgment` captures and places
in `report["btc_error"]` / `report["xmr_error"]`.  The core OpenIA agent
continues to work normally with no blockchain configuration.

---

## Card rails stub (Visa / Mastercard / Maestro)

> **Stub only** — no real payment network connection.  Use this module to
> develop and test your card-rail judgment pipeline before plugging in a
> real payment processor (Stripe, Adyen, Worldpay, etc.).

`openia.cardrails_stub` accepts payment-rail events as Python dicts or
JSON files and converts them into `TransactionLog` entries using the same
S2 identifier-based encoding:

* `OPENIA_APPROVE_IDS_CARD` — comma-separated merchant / account IDs → `noise = +1.0`
* `OPENIA_DISAPPROVE_IDS_CARD` — comma-separated merchant / account IDs → `noise = −1.0`

### Event schema

```python
{
    "amount": 49.99,           # float — transaction amount (required)
    "merchant_id": "MID-001",  # str   — primary identifier
    # optional extras:
    "currency": "USD",
    "network": "visa",
    "txid": "card-tx-001",
}
```

### Example

```python
import os
from openia import Agent, TransactionLog
from openia.cardrails_stub import ingest_card_events, ingest_card_events_from_file

os.environ["OPENIA_APPROVE_IDS_CARD"] = "MID-TRUSTED,MID-VIP"
os.environ["OPENIA_DISAPPROVE_IDS_CARD"] = "MID-FRAUD"

log = TransactionLog()
agent = Agent(log=log)

# Option 1: supply events programmatically
events = [
    {"merchant_id": "MID-TRUSTED", "amount": 100.0, "network": "visa"},
    {"merchant_id": "MID-FRAUD",   "amount": 9.99,  "network": "mastercard"},
]
records = ingest_card_events(log, events)

# Option 2: load from a JSON file
records = ingest_card_events_from_file(log, "events.json")

print(f"Submitted {len(records)} record(s); aggregate noise = {log.aggregate_noise:.4f}")
print(agent.respond("help"))
```

---

## Running the tests

```bash
python -m pytest tests/ -v
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
