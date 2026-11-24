import os


STT_REPO_ID = os.getenv("STT_REPO_ID", "g-group-ai-lab/gipformer1.5-68M-rnnt")
STT_MODEL_DIR = os.getenv("STT_MODEL_DIR", "./models/gipformer")
STT_USE_INT8 = os.getenv("STT_USE_INT8", "true").lower() == "true"
STT_NUM_THREADS = int(os.getenv("STT_NUM_THREADS", "2"))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

SANDBOX_BASE_URL = os.getenv("SANDBOX_BASE_URL", "http://127.0.0.1:8000/v1")
