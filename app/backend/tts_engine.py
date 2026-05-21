import io
import os
import threading
import numpy as np
import soundfile as sf
import torch

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

_lock = threading.Lock()
_model = None

# instruct string -> VoiceClonePrompt (cached after first use)
_voice_prompts: dict = {}
_vp_lock = threading.Lock()


def _load_model():
    global _model
    from omnivoice import OmniVoice
    from app.backend.config import TTS_MODEL, TTS_DEVICE

    _model = OmniVoice.from_pretrained(
        TTS_MODEL,
        device_map=TTS_DEVICE,
        dtype=torch.float16,
    )


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _load_model()
    return _model


def _build_voice_prompt(instruct: str):
    """Generate a seed utterance with `instruct`, then create a VoiceClonePrompt.
    Result is cached — subsequent calls for the same instruct are instant.
    """
    with _vp_lock:
        if instruct in _voice_prompts:
            return _voice_prompts[instruct]

        model = get_model()
        # Fixed seed → deterministic seed audio
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        seed_text = (
            "Xin chào, đây là bài học hôm nay. "
            "Chúng ta sẽ cùng nhau khám phá một chủ đề rất thú vị."
        )
        audio_list = model.generate(text=seed_text, instruct=instruct, num_step=16)
        seed_audio = audio_list[0]  # np.ndarray (T,)

        seed_tensor = torch.from_numpy(seed_audio).unsqueeze(0)  # (1, T)
        prompt = model.create_voice_clone_prompt(
            ref_audio=(seed_tensor, model.sampling_rate),
            ref_text=seed_text,
        )
        _voice_prompts[instruct] = prompt
        return prompt


def synthesize(
    text: str,
    ref_audio: str = "",
    ref_text: str = "",
    instruct: str = "",
    num_steps: int = 16,
) -> bytes:
    model = get_model()

    if ref_audio and os.path.isfile(ref_audio):
        # Voice Cloning từ file mẫu người dùng — ưu tiên cao nhất
        kwargs: dict = {"text": text, "num_step": num_steps, "ref_audio": ref_audio}
        if ref_text:
            kwargs["ref_text"] = ref_text
    elif instruct:
        # Voice Design: dùng VoiceClonePrompt đã cache → giọng nhất quán mọi câu
        prompt = _build_voice_prompt(instruct)
        kwargs = {"text": text, "num_step": num_steps, "voice_clone_prompt": prompt}
    else:
        # Auto voice — không khuyến khích (giọng random mỗi câu)
        kwargs = {"text": text, "num_step": num_steps}

    audio_list = model.generate(**kwargs)
    audio: np.ndarray = audio_list[0]
    buf = io.BytesIO()
    sf.write(buf, audio, 24000, format="WAV", subtype="PCM_16")
    return buf.getvalue()
