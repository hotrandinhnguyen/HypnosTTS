from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parents[2] / ".env")

OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

REF_AUDIO_PATH: Path = Path(os.getenv("REF_AUDIO_PATH", "app/data/reference.wav"))
REF_TEXT_PATH: Path = Path(os.getenv("REF_TEXT_PATH", "app/data/reference.txt"))

TTS_MODEL: str = os.getenv("TTS_MODEL", "k2-fsa/OmniVoice")
TTS_DEVICE: str = os.getenv("TTS_DEVICE", "cuda:0")
TTS_NUM_STEPS: int = int(os.getenv("TTS_NUM_STEPS", "16"))
TTS_INSTRUCT: str = os.getenv("TTS_INSTRUCT", "male, calm, low pitch")

DB_PATH: Path = Path("app/data/lessons.db")

VOICE_PRESETS: dict[str, str] = {
    "male_mid":     "male, low pitch, middle-aged",
    "male_young":   "male, moderate pitch, young adult",
    "male_deep":    "male, very low pitch, middle-aged",
    "female_warm":  "female, moderate pitch, middle-aged",
    "female_young": "female, high pitch, young adult",
    "elderly":      "male, low pitch, elderly",
}
