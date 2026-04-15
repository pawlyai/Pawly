"""
Model hot-reload registry — mirrors the prompt hot-reload pattern in prompts/system.py.

Edit models_config.yaml while the bot is running and set MODEL_HOT_RELOAD=true
to pick up changes without restarting.

Admin commands (/set_model, /show_models, /reload_models) in admin.py also
write to and reload from this file.
"""

import os
import pathlib

import yaml

_MODELS_FILE = pathlib.Path(__file__).parent / "models_config.yaml"
_CACHE: dict = {"mtime": None, "models": None}

_KNOWN_KEYS = ("main_model", "urgent_model", "extraction_model")


def _load_models() -> dict:
    hot_reload = os.getenv("MODEL_HOT_RELOAD", "").lower() in {"1", "true", "yes"}
    mtime = _MODELS_FILE.stat().st_mtime

    if not hot_reload and _CACHE["models"] is not None:
        return _CACHE["models"]
    if hot_reload and _CACHE["models"] is not None and _CACHE["mtime"] == mtime:
        return _CACHE["models"]

    with _MODELS_FILE.open("r", encoding="utf-8") as f:
        cfg: dict = yaml.safe_load(f) or {}

    _CACHE["mtime"] = mtime
    _CACHE["models"] = cfg
    return cfg


def reload_model_config() -> dict:
    """Force reload from disk (clears cache)."""
    _CACHE["mtime"] = None
    _CACHE["models"] = None
    return _load_models()


def get_model(key: str, fallback: str) -> str:
    """Return the current model name for *key*, or *fallback* if not set."""
    return _load_models().get(key) or fallback


def get_all_models() -> dict:
    """Return the full model config dict."""
    return _load_models()


def get_model_for_triage(triage_level: str, main_fallback: str, urgent_fallback: str) -> str:
    """
    Return the appropriate model based on rule-triage level.

    RED or ORANGE → urgent_model (more capable model for serious cases)
    GREEN         → main_model   (default, cost-efficient model)
    """
    models = _load_models()
    if triage_level in ("RED", "ORANGE"):
        return models.get("urgent_model") or urgent_fallback
    return models.get("main_model") or main_fallback


def write_model(key: str, value: str) -> None:
    """Update a single key in models_config.yaml and reload the cache."""
    if key not in _KNOWN_KEYS:
        raise ValueError(f"Unknown model key '{key}'. Valid keys: {_KNOWN_KEYS}")
    with _MODELS_FILE.open("r", encoding="utf-8") as f:
        cfg: dict = yaml.safe_load(f) or {}
    cfg[key] = value
    with _MODELS_FILE.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=True)
    reload_model_config()
