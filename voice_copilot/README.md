---
title: MoMo Voice AI Financial Copilot
emoji: 🎙️
colorFrom: pink
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# MoMo Voice AI Financial Copilot (`voice_copilot/`)

Developer B layer integrating Vietnamese Voice ASR, Financial ITN, and Guardrailed Multi-Turn Tool Calling with Developer A's **Fintech Sandbox API** (`/v1`).

## Architecture
1. **Audio Preprocessing (`app/audio_preprocess.py`):** 16kHz mono polyphase resampling, DC removal, energy-based VAD silence trimming (prevents ASR hallucinations on silent clips), and RMS/peak normalization.
2. **Vietnamese ASR (`app/stt_service.py`):** `g-group-ai-lab/gipformer1.5-68M-rnnt` (INT8 ONNX via `sherpa-onnx`, CPU-ready).
3. **Vietnamese Financial ITN (`app/vi_financial_itn.py`):**
   - Spoken phone/account digits (`"không chín một hai..."` -> `"0912..."`).
   - Currency slang & compound numbers (`"một trăm năm mươi ca"` -> `"150000"`, `"hai lít rưỡi"` -> `"250000"`, `"một củ rưỡi"` -> `"1500000"`).
   - 35+ Vietnamese banks & e-wallets ASR phonetic normalization (`"việt com banh"` -> `"Vietcombank"`, `"bê i đê vê"` -> `"BIDV"`, `"tếch com banh"` -> `"Techcombank"`, `"mờ bê"` -> `"MB Bank"`, `"mô mô"` -> `"MoMo"`, etc.) with context-aware protection against false positives.
4. **Protocol-Based Agent Guardrails (`app/agent_guards.py`):**
   - `AllowedToolGuard`: Strictly blocks LLM from calling payment approval/execution endpoints.
   - `FinancialSchemaGuard`: Enforces positive integer VND amounts.
   - `PrerequisiteContactGuard`: Blocks hallucinated IDs and enforces disambiguation when `find_contacts` returns `is_ambiguous: true`.
   - `DuplicateWriteGuard`: Prevents duplicate state-mutating calls in the same turn.
5. **Multi-Turn Tool Loop & Sandbox Bridge (`app/agent_loop.py`, `app/sandbox_bridge.py`):**
   - Strictly separates `agent_token` (read/draft/quote) from `user_token` (human-in-the-loop approval & execution).

## Run Both Services Locally

### 1. Start Fintech Sandbox API (port `8000`)
From repo root:
```bash
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Start Voice AI Copilot Workspace (port `7860`)
```bash
cd voice_copilot
pip install -r requirements.txt
set GEMINI_API_KEY=your_gemini_api_key
set SANDBOX_BASE_URL=http://127.0.0.1:8000/v1
uvicorn app.main:app --host 127.0.0.1 --port 7860
```

Open **http://127.0.0.1:7860** to test live Microphone voice commands, Smart Payment Routing, Human-in-the-Loop approval, and Exact Integer Bill Splitting.
