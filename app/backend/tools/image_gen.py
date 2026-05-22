"""Unified image generation interface — provider selected via IMAGE_PROVIDER env var."""
import logging

from app.backend.config import IMAGE_PROVIDER

log = logging.getLogger("image_gen")


async def generate_image(prompt: str) -> bytes:
    """Return PNG bytes for the given prompt using the configured provider."""
    log.info("[ImageGen] provider=%s", IMAGE_PROVIDER)
    if IMAGE_PROVIDER == "local":
        from app.backend.tools.image_gen_local import generate
    elif IMAGE_PROVIDER == "remote":
        from app.backend.tools.image_gen_remote import generate
    else:
        from app.backend.tools.image_gen_dalle import generate
    return await generate(prompt)
