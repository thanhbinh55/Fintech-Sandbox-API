"""Export OpenAPI schema to openapi.json file."""
import json
from pathlib import Path
from app.main import app

output_path = Path(__file__).resolve().parent.parent / "openapi.json"
openapi_data = app.openapi()

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(openapi_data, f, indent=2, ensure_ascii=False)

print(f"OpenAPI schema successfully written to {output_path}")
