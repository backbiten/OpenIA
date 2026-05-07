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

## Desktop executables (GitHub Releases)

Pre-built, single-file executables for **Windows** and **macOS** are
attached to every [GitHub Release](https://github.com/backbiten/OpenIA/releases).
No Python installation is required.

| Platform | Asset | How to run |
|---|---|---|
| **Windows** | `openia-windows.zip` → `openia.exe` | `.\openia.exe respond "help"` |
| **macOS** | `openia-macos.zip` → `openia` | `./openia respond "help"` |

### Download and run (macOS example)

```bash
# Download and unzip the latest release
curl -L https://github.com/backbiten/OpenIA/releases/latest/download/openia-macos.zip -o openia-macos.zip
unzip openia-macos.zip
chmod +x openia

# Run
./openia version
./openia respond "help"
./openia respond "status"
```

### Download and run (Windows PowerShell example)

```powershell
# Download and unzip the latest release
Invoke-WebRequest -Uri https://github.com/backbiten/OpenIA/releases/latest/download/openia-windows.zip -OutFile openia-windows.zip
Expand-Archive openia-windows.zip -DestinationPath .

# Run
.\openia.exe version
.\openia.exe respond "help"
.\openia.exe respond "status"
```

Executables are built automatically by the
[`release-desktop` workflow](.github/workflows/release-desktop.yml)
whenever a `v*` tag is pushed.

---

## Package layout

```
openia/
  __init__.py            public API
  cli.py                 CLI entry point (also used by PyInstaller)
  agent.py               Agent — the dumbed-down, submissive AI
  transaction.py         Transaction + TransactionLog + AssetManager — noise transport layer
  market.py              InternalMarket — Internal Stock Exchange (ISE)
  judge.py               Judge — external judgment interface
  bitcoin_integration.py Bitcoin → TransactionLog bridge (RPC adapter)
  monero_integration.py  Monero  → TransactionLog bridge (RPC adapter)
  chain_judgment.py      Unified BTC + XMR S2 judgment runner
  cardrails_stub.py      Card-rail event stub (Visa / Mastercard / Maestro)
tests/
  test_openia.py         pytest test suite (core)
  test_market.py         pytest test suite (Internal Stock Exchange)
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
#   'internal_market_report': {'Coinbits': 1.0, 'ThreadBits': 1.0, 'BufferBits': 1.0, 'CoreBits': 1.0}
# }

# An external party approves → noise becomes +1
judge.approve()
print(agent.respond("help"))
# {'response': 'How can I assist you?', 'confidence': 0.9526, 'rule': 'help', 'noise': 1.0, ...}

# A second judge disapproves → aggregate noise drops back toward 0
judge2 = Judge(log=log)
judge2.disapprove()
print(agent.respond("help"))
# {'response': 'How can I assist you?', 'confidence': ~0.73, 'rule': 'help', 'noise': 0.0, ...}
```

---

## Internal Stock Exchange (ISE) — Coinbits and AI-component currencies

OpenIA includes a strictly **closed-loop** Internal Stock Exchange (`openia/market.py`).  It simulates
internal "value" for four AI-component currencies:

| Currency | What it represents |
|---|---|
| **Coinbits** | Base priority token — the AI's overall health score |
| **ThreadBits** | Concurrent execution capacity |
| **BufferBits** | Available I/O buffer headroom |
| **CoreBits** | Hardware-core utilisation slack |

> **Important:** This market has *no connection to any external fiat
> currency*, public blockchain, or real-world trade.  "Coinbits" are a
> programmatic abstraction — a lightweight metaphor for internal resource
> allocation.  They exist solely to help the AI manage its own hardware
> and software resources.

### How prices are determined

Prices reflect the "health" of the underlying system:

* **CPU load** → higher `ThreadBits` and `CoreBits` (scarce capacity costs more).
* **Memory pressure** → higher `BufferBits`.
* **AI performance score** → modulates `Coinbits` directly.

Recycled metadata (from the transaction stream) is injected as liquidity,
gently raising `Coinbits` prices as activity increases.

### Usage

```python
from openia import Agent, InternalMarket, TransactionLog
from openia.transaction import AssetManager

# Create a shared market and log
market = InternalMarket()
log = TransactionLog()

# AssetManager links the log to the market — every submitted transaction
# feeds recycled value back into the exchange.
am = AssetManager(log=log, market=market)
am.submit(value=0.5, noise=0.2)

# Update market prices with current system metrics
market.update(cpu_usage=0.4, memory_usage=0.3, ai_performance=0.9)

# Inspect the market
print(market.snapshot())
# {'Coinbits': 0.9, 'ThreadBits': 1.4, 'BufferBits': 1.3, 'CoreBits': 1.2}

# The Agent automatically includes an InternalMarketReport in every response
agent = Agent(log=log, market=market)
result = agent.respond("status")
print(result["internal_market_report"])
# {'Coinbits': ..., 'ThreadBits': ..., 'BufferBits': ..., 'CoreBits': ...}
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
