import json
from pathlib import Path

# CONFIG_PATH = 'C:\\python\\task\\twillo\\twilio_config.json' #Path(__file__).parent / "twilio_config.json"
CONFIG_PATH = Path(__file__).parent.parent / "twilio_config.json"


def load_twilio_config() -> dict:
    # if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)
    return {}

def save_twilio_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)
