# Fintech Sandbox API

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A stateful, reproducible financial sandbox backend simulating core capabilities of a modern Vietnamese e-wallet (e.g., MoMo-style wallet, bank transfer, card payments, smart routing, and group bill splitting).

Designed specifically as the execution backend for an AI Financial Copilot (MoMo Tech Contest 2026).

> [!WARNING]
> **SIMULATION ONLY**: This project is an independent sandbox simulation for technical evaluation and AI testing. It does NOT connect to real banking networks, real MoMo APIs, or live payment rails. All balances, bank accounts, cards, rewards, and transfers are purely simulated.

---

## Features

- **Isolated Demo Environments:** Multi-tenant session isolation with deterministic seeding scenarios (`scenario_a`, `scenario_b`, `scenario_c`).
- **Scoped Security:** Distinct permissions for `user`, `agent`, and `demo-control` roles.
- **Natural-Language Payment Lifecycle:** Recipient resolution with ambiguous contact detection, payment draft creation, quote generation, approval snapshot locking, and simulated execution.
- **Smart Payment Routing:** Deterministic ranking of payment sources based on fees, immediate discounts, and estimated cashback with transparent explanation codes.
- **Exact VND Bill Splitting:** Zero-floating-point integer VND allocation, shared item distribution, proportional tax/fee sharing, deterministic remainder rounding, and collection tracking.
- **Double-Entry Ledger:** Atomic debit/credit tracking for all simulated movements.
- **Developer B Integration:** Pre-built typed Python SDK (`fintech_sandbox_client`) and Gemini Function Calling Guide.

---

## Quickstart

### Local Setup with UV

```bash
# Create venv and install dependencies
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run database migrations / initialization
python -m scripts.seed_demo

# Start application
uvicorn app.main:app --reload --port 8000
```

### Docker Setup

```bash
docker compose up --build
```

Access Swagger UI at: `http://localhost:8000/docs`

