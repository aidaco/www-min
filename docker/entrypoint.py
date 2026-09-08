"""Require explicit runtime configuration; never start the self-updating webhook."""

import os
from pathlib import Path
import tomllib

path = Path("/config/wwwmin/config.toml")
with path.open("rb") as stream:
    config = tomllib.load(stream)
if config.get("cd", {}).get("enabled", True):
    raise SystemExit("Container configuration must explicitly disable in-app CD")
secret = config.get("security", {}).get("jwt_secret", "")
if not secret or secret == "correct horse battery staple":
    raise SystemExit("An explicit non-default JWT secret is required")
os.execv("/app/.venv/bin/wwwmin", ["wwwmin", "serve"])
