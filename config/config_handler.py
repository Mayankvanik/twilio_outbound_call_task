import json
import os

CONFIG_PATH = "twilio_config.json"

def load_config() -> dict:
    """Load credentials from the JSON file"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def save_config(data: dict):
    """Save credentials to the JSON file"""
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)
