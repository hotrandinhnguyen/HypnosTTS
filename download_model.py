import os
os.environ["HF_ENDPOINT"] = "https://huggingface.co"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"
os.environ["HF_HUB_DISABLE_XET"] = "1"

from huggingface_hub import snapshot_download
import time

repos = ["k2-fsa/OmniVoice", "openai/whisper-large-v3-turbo"]
for repo_id in repos:
    print(f"\n#### Downloading {repo_id} ####", flush=True)
    attempts = 0
    while True:
        attempts += 1
        print(f"=== Attempt {attempts} ===", flush=True)
        try:
            path = snapshot_download(
                repo_id,
                max_workers=1,
                etag_timeout=60,
            )
            print(f"OK: {path}", flush=True)
            break
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}", flush=True)
            if attempts >= 50:
                raise
            time.sleep(5)
