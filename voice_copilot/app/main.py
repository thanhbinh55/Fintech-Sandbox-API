from contextlib import asynccontextmanager
from pathlib import Path
import time
import uuid

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.agent_loop import FintechCopilotAgent
from app.config import LLM_MODEL, LLM_PROVIDER, SANDBOX_BASE_URL, STT_REPO_ID
from app.sandbox_bridge import SandboxAPIError, SandboxBridge
from app.stt_service import GipformerSTTService
from app.vi_financial_itn import normalize_vietnamese_financial_itn


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_INDEX = BASE_DIR / "static" / "index.html"

stt_service = GipformerSTTService()
sandbox_bridge = SandboxBridge()
copilot_agent: FintechCopilotAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global copilot_agent
    stt_service.load()
    copilot_agent = FintechCopilotAgent(bridge=sandbox_bridge)
    yield


app = FastAPI(
    title="MoMo AI Financial Copilot Workspace",
    description="Gipformer 1.5 ASR + Vietnamese Financial ITN + Guardrailed Multi-Turn Agent + Fintech Sandbox API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionInitRequest(BaseModel):
    scenario: str = "scenario_a"
    display_name: str = "MoMo Contest Demo"


class ChatRequest(BaseModel):
    session_id: str
    text: str


class ApproveExecuteRequest(BaseModel):
    session_id: str
    payment_intent_id: str
    quote_id: str


class SettleSplitRequest(BaseModel):
    session_id: str
    split_id: str
    request_id: str


@app.get("/")
async def index():
    if not STATIC_INDEX.exists():
        raise HTTPException(status_code=404, detail="UI file not found")
    return FileResponse(STATIC_INDEX)


@app.get("/health")
async def health():
    sandbox_ok = False
    try:
        health_url = SANDBOX_BASE_URL.rsplit("/v1", 1)[0] + "/health"
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(health_url)
            sandbox_ok = r.status_code == 200
    except Exception:
        sandbox_ok = False

    return {
        "status": "ok",
        "stt_ready": stt_service.recognizer is not None,
        "stt_model": STT_REPO_ID,
        "llm_provider": copilot_agent.provider_name if copilot_agent else LLM_PROVIDER,
        "llm_model": copilot_agent.model_name if copilot_agent else LLM_MODEL,
        "sandbox_url": SANDBOX_BASE_URL,
        "sandbox_ok": sandbox_ok,
    }


@app.post("/api/stt")
async def transcribe_only(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")
    try:
        raw_text, norm_text, stt_ms, stats = stt_service.transcribe_audio_bytes(audio_bytes)
        return {
            "raw_transcript": raw_text,
            "transcript": norm_text,
            "stt_latency_ms": stt_ms,
            "audio_stats": stats,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"STT error: {exc}") from exc


@app.post("/api/session/init")
async def init_session(req: SessionInitRequest):
    try:
        state = await sandbox_bridge.create_session(
            scenario=req.scenario, display_name=req.display_name
        )
        accounts = await sandbox_bridge.get_account_snapshot(state.session_id)
        return {
            "session_id": state.session_id,
            "scenario": state.scenario,
            "accounts": accounts,
        }
    except SandboxAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sandbox unavailable: {exc}") from exc


@app.post("/api/session/{session_id}/reset")
async def reset_session(session_id: str):
    try:
        await sandbox_bridge.reset_session(session_id)
        accounts = await sandbox_bridge.get_account_snapshot(session_id)
        return {"session_id": session_id, "accounts": accounts}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/session/{session_id}/accounts")
async def get_accounts(session_id: str):
    try:
        accounts = await sandbox_bridge.get_account_snapshot(session_id)
        return {"session_id": session_id, "accounts": accounts}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/api/chat")
async def chat_turn(req: ChatRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    agent = copilot_agent or FintechCopilotAgent(bridge=sandbox_bridge)
    t0 = time.perf_counter()
    try:
        normalized_text = normalize_vietnamese_financial_itn(req.text.strip())
        result = await agent.run_turn(req.session_id, normalized_text)
        accounts = await sandbox_bridge.get_account_snapshot(req.session_id)
        return {
            "raw_transcript": req.text.strip(),
            "normalized_transcript": normalized_text,
            "stt_latency_ms": None,
            "total_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "accounts": accounts,
            **result,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Copilot error: {exc}") from exc


@app.post("/api/voice-chat")
async def voice_chat_turn(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    agent = copilot_agent or FintechCopilotAgent(bridge=sandbox_bridge)
    t0 = time.perf_counter()
    try:
        raw_text, norm_text, stt_ms, stats = stt_service.transcribe_audio_bytes(audio_bytes)
        if not norm_text:
            raise HTTPException(
                status_code=422,
                detail="Không phát hiện giọng nói rõ ràng (hoặc âm thanh quá nhỏ). Vui lòng nói lại gần Micro hơn.",
            )
        result = await agent.run_turn(session_id, norm_text)
        accounts = await sandbox_bridge.get_account_snapshot(session_id)
        return {
            "raw_transcript": raw_text,
            "normalized_transcript": norm_text,
            "audio_stats": stats,
            "stt_latency_ms": stt_ms,
            "total_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "accounts": accounts,
            **result,
        }
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Voice pipeline error: {exc}") from exc


@app.post("/api/human/approve-execute")
async def human_approve_and_execute(req: ApproveExecuteRequest):
    try:
        res = await sandbox_bridge.approve_and_execute_payment(
            session_id=req.session_id,
            payment_intent_id=req.payment_intent_id,
            quote_id=req.quote_id,
            idempotency_key=f"hitl_{uuid.uuid4().hex[:12]}",
        )
        return res
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/api/human/settle-split")
async def human_settle_split(req: SettleSplitRequest):
    try:
        res = await sandbox_bridge.settle_split_share(
            session_id=req.session_id,
            split_id=req.split_id,
            request_id=req.request_id,
        )
        accounts = await sandbox_bridge.get_account_snapshot(req.session_id)
        return {**res, "accounts": accounts}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
