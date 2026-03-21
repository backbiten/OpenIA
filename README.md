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

## Dual-Protection Protocol (Human vs. Alien Assets)

OpenIA implements a two-layer protection strategy modelled on a
**Mercenary/Contractor** market:

### Layer 1 — AI protecting Humans

The core `Agent` (the smart AI layer) acts as the **primary shield** for
human interests.  It applies three safety protocols on every response cycle:

| Protocol | Meaning |
|---|---|
| **Stability** | Confidence is sigmoid-clamped — the AI never swings to extremes. |
| **Ethics** | Rule-based reasoning is fully transparent and inspectable. |
| **Assistance** | The AI's default posture is to help, not to resist or obfuscate. |

### Layer 2 — IA protecting Aliens (External Product Entities)

The **IA** (Intelligence Assistant — the assistant *to* the smart AI,
represented by `MercenaryProtocol`) specifically manages and protects
**Alien assets**: specialised external products, commodities, and advanced
data structures.

* Alien commodities generate the high-value **Coinbits** that fund the
  **Mercenary/Contractor Market**.
* The market is used to combat **Bad Entities** and **Terrorists** —
  malicious data, viruses, and critically negative noise signals.

### SecurityClearance levels

Every `Agent.respond()` call evaluates the current aggregate noise and
returns a `ClearanceLevel`:

| Level | Noise range | Meaning |
|---|---|---|
| `GREEN` | ≥ −0.25 | Safe; normal operation. |
| `YELLOW` | −0.75 to −0.25 | Suspicious; heightened IA monitoring. |
| `RED` | < −0.75 | Terrorist / bad-entity signal detected; IA intercepts to protect Alien Commodity holdings. |

### AssetManager — Human Safety Assets vs. Alien Commodities

```python
from openia.transaction import AssetManager, AssetType

mgr = AssetManager(log=log)

# AI-protected — human interests
mgr.register("ethics_reserve", AssetType.HUMAN_SAFETY, value=100.0)

# IA-protected — funds the Mercenary Market
mgr.register("data_ore_alpha", AssetType.ALIEN_COMMODITY, value=50.0)

print(mgr.total_coinbits)       # 50.0
print(mgr.commodity_report)
# {'human_assets': 1, 'alien_commodities': 1, 'total_coinbits': 50.0}
```

Registering an **Alien Commodity** automatically submits a positive-noise
transaction to the shared `TransactionLog`, ensuring the market always has
liquidity.

### MercenaryProtocol in action

```python
from openia import Agent, TransactionLog
from openia.agent import MercenaryProtocol
from openia.transaction import AssetManager, AssetType

log = TransactionLog()
mgr = AssetManager(log=log)
mgr.register("commodity_1", AssetType.ALIEN_COMMODITY, value=20.0)

protocol = MercenaryProtocol(asset_manager=mgr)
agent = Agent(log=log, mercenary_protocol=protocol)

# Inject a hostile signal (terrorist noise)
log.submit(value=1.0, noise=-0.9)
result = agent.respond("status")

print(result["ClearanceLevel"])    # 'RED'
print(result["CommodityReport"])   # {'human_assets': 0, 'alien_commodities': 1, 'total_coinbits': 20.0}
```

### MetadataScavenger — Mining Coinbits from Waste

The `MetadataScavenger` (in `openia.recycling`) mines **Alien Commodity**
Coinbits out of junk/waste metadata that accumulates during normal
operation.  Each waste item is:

1. **Blank-slated** — all original, potentially virus-prone attributes are
   stripped.
2. **Hashed** — a deterministic MD5 hash extracts a small Coinbit value
   `[0.001, 0.010]`.
3. **Re-injected** — registered as a new `ALIEN_COMMODITY` and submitted to
   the log as a stabilising positive signal.

```python
from openia import TransactionLog
from openia.recycling import MetadataScavenger

log = TransactionLog()
scavenger = MetadataScavenger(log=log)

waste = [
    {"raw_error": "segfault", "ref": None},
    {"virus_sig": "0xDEAD", "status": "broken"},
]
total_mined = scavenger.recycle(waste)
print(f"Mined {total_mined:.6f} Coinbits from {scavenger.recycled_count} waste items")
```

---

## Package layout

```
openia/
  __init__.py            public API
  agent.py               Agent + MercenaryProtocol + SecurityClearance
  transaction.py         Transaction + TransactionLog + AssetManager + AssetType
  judge.py               Judge — external judgment interface
  recycling.py           MetadataScavenger — mines Coinbits from waste metadata
  bitcoin_integration.py Bitcoin → TransactionLog bridge (RPC adapter)
  monero_integration.py  Monero  → TransactionLog bridge (RPC adapter)
  chain_judgment.py      Unified BTC + XMR S2 judgment runner
  cardrails_stub.py      Card-rail event stub (Visa / Mastercard / Maestro)
tests/
  test_openia.py         pytest test suite (core + dual-protection protocol)
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

Transactions to any other address are silently ignored.  The `value`
submitted to the log is always the transaction amount (BTC or XMR) as a
float.

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

# Pull both chains
report = run_chain_judgment(log)
print(f"BTC records: {len(report['btc_records'])}")
print(f"XMR records: {len(report['xmr_records'])}")
print(f"Aggregate noise: {log.aggregate_noise:.4f}")

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
