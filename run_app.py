import os
import logging

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
# debug-level cho pipeline để thấy từng câu; bỏ dòng này nếu quá nhiều log
logging.getLogger("pipeline").setLevel(logging.DEBUG)

# tắt noise từ lib bên ngoài
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("langgraph").setLevel(logging.WARNING)

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
