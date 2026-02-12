"""Configuration management for p2r."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Tuple


CONFIG_FILE_NAME = ".p2r_config.json"
ENV_TOKEN_KEY = "P2R_MINERU_TOKEN"
ENV_API_BASE_URL_KEY = "P2R_MINERU_API_BASE_URL"
ENV_CONFIG_PATH_KEY = "P2R_CONFIG_PATH"
CONFIG_VERSION = 2


def get_config_path() -> Path:
    """Get the path to the configuration file.

    Returns:
        Path to ~/.p2r_config.json
    """
    env_path = os.getenv(ENV_CONFIG_PATH_KEY)
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / CONFIG_FILE_NAME


def get_default_profile() -> Dict[str, Any]:
    return {
        "export": {
            "markdown_dir": ".",
            "html_dir": ".",
            "keep_images": False,
            "images_dir": None,
            "keep_raw": False,
            "raw_dir": None,
        },
        "html": True,
        # null means: inherit global image_upload.enabled
        "upload_images": None,
    }


def get_default_config() -> Dict[str, Any]:
    """Get default configuration template.

    Returns:
        Dictionary containing default configuration values
    """
    return {
        "version": CONFIG_VERSION,
        "default_profile": "default",
        "profiles": {
            "default": get_default_profile(),
        },
        "mineru": {
            "api_token": "",
            # MinerU official API base URL (see doc/mineru_api_reference.md).
            "api_base_url": "https://mineru.net/api/v4",
            "poll_interval": 3,  # seconds
            "max_poll_time": 600,  # 10 minutes
        },
        "output": {
            "temp_dir": "/tmp/p2r",
            # When image upload/rewrite fails, p2r falls back to saving the full MinerU output here.
            # If null/empty, p2r will use a folder under the current working directory.
            "failure_dir": None,
        },
        "ui": {
            # Preferred editor command for `p2r config`.
            "editor": "",
        },
        "image_upload": {
            # When enabled, p2r can upload extracted images to an image bed and rewrite Markdown links.
            "enabled": False,
            # Supported modes: "command" (run a local command per image) or "picgo_server" (HTTP endpoint).
            "mode": "picgo_server",
            # Command template; {file} will be replaced with the local image path.
            # Example: picgo upload "{file}"
            "command": "",
            # Optional: PicGo server endpoint (used when mode="picgo_server")
            "picgo_server": {
                "url": "http://127.0.0.1:36677/upload",
                # If your PicGo server has a secret enabled, set it here.
                "secret": "",
            },
        },
    }


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    """Merge src into dst recursively (in-place) and return dst."""
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)  # type: ignore[index]
        else:
            dst[k] = v
    return dst


def _is_v2_config(cfg: Dict[str, Any]) -> bool:
    if cfg.get("version") == CONFIG_VERSION:
        return True
    return isinstance(cfg.get("profiles"), dict) and isinstance(cfg.get("default_profile"), str)


def _migrate_to_v2(cfg: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Return (v2_cfg, migrated). Never mutates the input dict."""
    base = get_default_config()

    # If already v2-ish, merge defaults to fill missing keys.
    if _is_v2_config(cfg):
        merged = json.loads(json.dumps(base))
        _deep_merge(merged, cfg)
        merged["version"] = CONFIG_VERSION
        return merged, False

    # v1 -> v2: deep merge preserves known sections and avoids losing unknown keys.
    merged = json.loads(json.dumps(base))
    _deep_merge(merged, cfg)

    merged["version"] = CONFIG_VERSION
    if not isinstance(merged.get("profiles"), dict):
        merged["profiles"] = {"default": get_default_profile()}
    if "default" not in merged["profiles"]:
        merged["profiles"]["default"] = get_default_profile()
    if not isinstance(merged.get("default_profile"), str) or not merged["default_profile"].strip():
        merged["default_profile"] = "default"

    return merged, True


def _normalize_and_validate(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize config for runtime use. Best-effort (tries not to raise)."""
    cfg.setdefault("mineru", {})
    cfg.setdefault("output", {})
    cfg.setdefault("ui", {})
    cfg.setdefault("image_upload", {})
    cfg.setdefault("profiles", {})
    cfg["version"] = CONFIG_VERSION

    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
        cfg["profiles"] = profiles

    if not profiles:
        cfg["profiles"] = {"default": get_default_profile()}
        profiles = cfg["profiles"]

    default_profile = cfg.get("default_profile")
    if (
        not isinstance(default_profile, str)
        or not default_profile.strip()
        or default_profile not in profiles
    ):
        cfg["default_profile"] = "default" if "default" in profiles else next(iter(profiles.keys()))

    # Fill missing profile fields.
    for name, prof in list(profiles.items()):
        if not isinstance(prof, dict):
            profiles[name] = get_default_profile()
            continue
        merged_prof = json.loads(json.dumps(get_default_profile()))
        _deep_merge(merged_prof, prof)
        profiles[name] = merged_prof

    return cfg


def get_profile(cfg: Dict[str, Any], name: str) -> Dict[str, Any]:
    profiles = cfg.get("profiles", {})
    if not isinstance(profiles, dict):
        raise KeyError("config.profiles is not a dict")
    prof = profiles.get(name)
    if prof is None:
        raise KeyError(f"Unknown profile: {name!r}")
    if not isinstance(prof, dict):
        raise TypeError(f"Profile {name!r} is not an object")
    return prof


def get_default_profile_name(cfg: Dict[str, Any]) -> str:
    name = cfg.get("default_profile")
    if isinstance(name, str) and name.strip():
        return name
    return "default"


def load_config() -> Dict[str, Any]:
    """Load configuration from file and environment.

    Environment variables take precedence over config file.
    If config file doesn't exist, creates it with default values.

    Returns:
        Configuration dictionary
    """
    config_path = get_config_path()

    # If config file doesn't exist, create it with defaults (best-effort).
    if not config_path.exists():
        config: Dict[str, Any] = get_default_config()
        try:
            save_config(config)
        except OSError:
            # In restricted environments (sandbox/CI) we may not be able to write to the user's home.
            # Still return defaults (env vars can override) so the CLI can run.
            pass
    else:
        # Load existing config (best-effort). If unreadable/corrupt, fall back to defaults.
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            config = loaded if isinstance(loaded, dict) else get_default_config()
        except (OSError, json.JSONDecodeError):
            config = get_default_config()

    config, migrated = _migrate_to_v2(config)
    config = _normalize_and_validate(config)
    if migrated:
        try:
            save_config(config)
        except OSError:
            pass

    def _sanitize_url(value: Any) -> Any:
        # URLs should never contain whitespace; newlines commonly appear from copy/paste.
        if isinstance(value, str):
            return re.sub(r"\s+", "", value)
        return value

    # Migrate legacy default base URL to the official MinerU API endpoint.
    mineru_cfg = config.setdefault("mineru", {})
    legacy_default = "https://cloud-api.magicpdf.com/api/v1"
    if (
        isinstance(mineru_cfg.get("api_base_url"), str)
        and _sanitize_url(mineru_cfg["api_base_url"]) == legacy_default
    ):
        mineru_cfg["api_base_url"] = get_default_config()["mineru"]["api_base_url"]
        try:
            save_config(config)
        except OSError:
            pass

    # Environment variable takes precedence
    env_token = os.getenv(ENV_TOKEN_KEY)
    if env_token:
        config.setdefault("mineru", {})["api_token"] = env_token.strip()

    # Optional override for API base URL (useful for debugging / self-hosting).
    env_api_base_url = os.getenv(ENV_API_BASE_URL_KEY)
    if env_api_base_url:
        config.setdefault("mineru", {})["api_base_url"] = _sanitize_url(env_api_base_url)

    # Optional override for config-driven image upload.
    # (Kept intentionally small: users can always edit config JSON for full options.)
    env_upload_enabled = os.getenv("P2R_IMAGE_UPLOAD_ENABLED")
    if env_upload_enabled is not None:
        config.setdefault("image_upload", {})["enabled"] = env_upload_enabled.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    env_upload_mode = os.getenv("P2R_IMAGE_UPLOAD_MODE")
    if env_upload_mode:
        config.setdefault("image_upload", {})["mode"] = env_upload_mode.strip()
    env_upload_cmd = os.getenv("P2R_IMAGE_UPLOAD_COMMAND")
    if env_upload_cmd:
        config.setdefault("image_upload", {})["command"] = env_upload_cmd
    env_picgo_server_url = os.getenv("P2R_PICGO_SERVER_URL")
    if env_picgo_server_url:
        config.setdefault("image_upload", {}).setdefault("picgo_server", {})[
            "url"
        ] = env_picgo_server_url.strip()
    env_picgo_server_secret = os.getenv("P2R_PICGO_SERVER_SECRET")
    if env_picgo_server_secret:
        config.setdefault("image_upload", {}).setdefault("picgo_server", {})[
            "secret"
        ] = env_picgo_server_secret.strip()

    # Normalize values that may accidentally contain whitespace/newlines.
    if "api_token" in mineru_cfg and isinstance(mineru_cfg["api_token"], str):
        mineru_cfg["api_token"] = mineru_cfg["api_token"].strip()
    if "api_base_url" in mineru_cfg and isinstance(mineru_cfg["api_base_url"], str):
        mineru_cfg["api_base_url"] = _sanitize_url(mineru_cfg["api_base_url"]).strip()

    return config


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file.

    Sets file permissions to 600 (user read/write only) for security.

    Args:
        config: Configuration dictionary to save
    """
    config_path = get_config_path()

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config file
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    # Set permissions to 600 (user read/write only)
    config_path.chmod(0o600)


def get_api_token() -> str:
    """Get MinerU API token from config or environment.

    Returns:
        API token string

    Raises:
        ValueError: If token is not configured
    """
    config = load_config()
    token = config.get("mineru", {}).get("api_token", "")

    if not token:
        raise ValueError(
            f"MinerU API token not configured. "
            f"Please set it in {get_config_path()} or via {ENV_TOKEN_KEY} environment variable."
        )

    return token


def update_token(token: str) -> None:
    """Update API token in configuration file.

    Args:
        token: New API token
    """
    config = load_config()
    config.setdefault("mineru", {})["api_token"] = token
    save_config(config)
