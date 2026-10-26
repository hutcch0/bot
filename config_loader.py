import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

REQUIRED_KEYS = [
    "TOKEN",
    "APPLICATION_ID",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DB",
    "REPORT_CHANNEL_ID",
    "MOD_LOG_CHANNEL_ID",
]

ENV_MAP = {
    "TOKEN": "DISCORD_TOKEN",
    "APPLICATION_ID": "DISCORD_APPLICATION_ID",
    "MYSQL_HOST": "MYSQL_HOST",
    "MYSQL_PORT": "MYSQL_PORT",
    "MYSQL_USER": "MYSQL_USER",
    "MYSQL_PASSWORD": "MYSQL_PASSWORD",
    "MYSQL_DB": "MYSQL_DB",
    "REPORT_CHANNEL_ID": "REPORT_CHANNEL_ID",
    "MOD_LOG_CHANNEL_ID": "MOD_LOG_CHANNEL_ID",
}


def load_config() -> dict:
    config: dict = {}

    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config.update(json.load(handle))

    for key, env_name in ENV_MAP.items():
        value = os.getenv(env_name)
        if value is not None and value != "":
            if key in {"APPLICATION_ID", "REPORT_CHANNEL_ID", "MOD_LOG_CHANNEL_ID"}:
                config[key] = int(value)
            elif key == "MYSQL_PORT":
                config[key] = int(value)
            else:
                config[key] = value

    missing = [key for key in REQUIRED_KEYS if key not in config]
    if missing:
        raise ValueError(f"Missing required config keys: {missing}")

    config["MYSQL_PORT"] = int(config["MYSQL_PORT"])
    config["APPLICATION_ID"] = int(config["APPLICATION_ID"])
    config["REPORT_CHANNEL_ID"] = int(config["REPORT_CHANNEL_ID"])
    config["MOD_LOG_CHANNEL_ID"] = int(config["MOD_LOG_CHANNEL_ID"])

    return config
