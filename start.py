"""One-command runner for Fintech Sandbox API."""
import os
import sys

# Ensure .env exists
if not os.path.exists(".env") and os.path.exists(".env.example"):
    import shutil
    shutil.copy(".env.example", ".env")

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("=" * 60)
    print("🚀 FINTECH SANDBOX API")
    print(f"👉 Swagger UI:   http://localhost:{port}/docs")
    print(f"👉 Health Check: http://localhost:{port}/health")
    print("=" * 60)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
