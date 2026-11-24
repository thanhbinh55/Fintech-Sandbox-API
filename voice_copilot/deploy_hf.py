import argparse
import os
from pathlib import Path
from huggingface_hub import HfApi


def main():
    parser = argparse.ArgumentParser(description="Deploy Voice-Pay MVP to Hugging Face Spaces (Docker)")
    parser.add_argument("--space-id", required=True, help="Target HF Space ID, e.g. username/momo-voice-pay-mvp")
    parser.add_argument("--private", action="store_true", help="Create as a private Space")
    args = parser.parse_args()

    hf_token = os.getenv("HF_TOKEN")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not hf_token:
        raise SystemExit("ERROR: HF_TOKEN environment variable is required (Write token from huggingface.co/settings/tokens).")
    if not gemini_key:
        raise SystemExit("ERROR: GEMINI_API_KEY environment variable is required.")

    api = HfApi(token=hf_token)
    print(f"Creating or verifying Docker Space: {args.space_id}...")
    api.create_repo(
        repo_id=args.space_id,
        repo_type="space",
        space_sdk="docker",
        private=args.private,
        exist_ok=True,
    )

    print("Setting GEMINI_API_KEY secret on Space...")
    api.add_space_secret(repo_id=args.space_id, key="GEMINI_API_KEY", value=gemini_key)

    project_dir = Path(__file__).resolve().parent
    print(f"Uploading {project_dir} to Space {args.space_id}...")
    api.upload_folder(
        folder_path=str(project_dir),
        repo_id=args.space_id,
        repo_type="space",
        ignore_patterns=["models/*", "__pycache__/*", "*.pyc", ".venv/*", ".git/*"],
    )

    print(f"Done! Your Space is building at: https://huggingface.co/spaces/{args.space_id}")


if __name__ == "__main__":
    main()
