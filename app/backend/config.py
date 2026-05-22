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
TTS_INSTRUCT: str = os.getenv("TTS_INSTRUCT", "female, moderate pitch, middle-aged")

DB_PATH: Path = Path("app/data/lessons.db")

TAVILY_API_KEY: str = os.environ["TAVILY_API_KEY"]
SEARCH_MAX_RESULTS: int = int(os.getenv("SEARCH_MAX_RESULTS", "5"))
SEARCH_TIMEOUT: float = float(os.getenv("SEARCH_TIMEOUT", "10"))

VOICE_PRESETS: dict[str, str] = {
    "female_warm":  "female, moderate pitch, middle-aged",
    "female_young": "female, high pitch, young adult",
    "male_mid":     "male, low pitch, middle-aged",
    "male_young":   "male, moderate pitch, young adult",
    "male_deep":    "male, very low pitch, middle-aged",
    "elderly":      "male, low pitch, elderly",
}
