import json
import re
import secrets
import uuid
from pathlib import Path
from typing import List, Optional

import bcrypt
from pydantic import BaseModel, Field

ENV_PATH = Path(".env")


def provider_slug(name: str) -> str:
    """Normalize provider name for use in model IDs: lowercase, strip dots/spaces."""
    return re.sub(r"[.\s]+", "", name).lower()


class Provider(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    base_url: str
    api_key: str
    models: List[str] = []
    enabled: bool = True
    models_auto: bool = True


def _read_env() -> dict:
    if not ENV_PATH.exists():
        return {}
    result = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, val = stripped.partition("=")
        key = key.strip()
        val = val.strip()
        if val.startswith("'") and val.endswith("'") and len(val) >= 2:
            val = val[1:-1]
        elif val.startswith('"') and val.endswith('"') and len(val) >= 2:
            val = val[1:-1]
            val = val.replace('\\"', '"').replace("\\'", "'").replace("\\n", "\n").replace("\\\\", "\\")
        result[key] = val
    return result


def _write_key(key: str, value: str):
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    if "'" not in value:
        encoded = f"'{value}'"
    else:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        encoded = f'"{escaped}"'
    new_line = f"{key}={encoded}"
    pattern = re.compile(rf"^{re.escape(key)}\s*=")
    found = False
    new_lines = []
    for line in lines:
        if pattern.match(line.strip()):
            new_lines.append(new_line)
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(new_line)
    content = "\n".join(new_lines)
    if content and not content.endswith("\n"):
        content += "\n"
    ENV_PATH.write_text(content, encoding="utf-8")


class AppConfig:
    def __init__(self):
        self._bootstrap()
        self.reload()

    def _bootstrap(self):
        vals = _read_env()
        if not vals.get("SESSION_SECRET"):
            _write_key("SESSION_SECRET", secrets.token_hex(32))
        if not vals.get("HOST"):
            _write_key("HOST", "0.0.0.0")
        if not vals.get("PORT"):
            _write_key("PORT", "8000")
        if "PROVIDERS" not in vals:
            _write_key("PROVIDERS", "[]")

    def reload(self):
        vals = _read_env()
        self.host = vals.get("HOST", "0.0.0.0")
        self.port = int(vals.get("PORT", "8000"))
        self.session_secret = vals.get("SESSION_SECRET") or secrets.token_hex(32)
        self.password_hash = vals.get("DASHBOARD_PASSWORD_HASH", "")
        self.proxy_api_key = vals.get("PROXY_API_KEY", "")
        providers_raw = vals.get("PROVIDERS", "[]")
        try:
            self.providers: List[Provider] = [Provider(**p) for p in json.loads(providers_raw)]
        except Exception:
            self.providers = []

    def is_setup(self) -> bool:
        return bool(self.password_hash)

    def set_password(self, password: str):
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        self.password_hash = hashed
        _write_key("DASHBOARD_PASSWORD_HASH", hashed)

    def verify_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode(), self.password_hash.encode())
        except Exception:
            return False

    def find_provider_for_model(self, model: str) -> Optional[tuple]:
        if "/" in model:
            pname, mname = model.split("/", 1)
            for p in self.providers:
                if p.enabled and provider_slug(p.name) == provider_slug(pname):
                    return (p, mname)
        for p in self.providers:
            if p.enabled and model in p.models:
                return (p, model)
        for p in self.providers:
            if p.enabled:
                return (p, model)
        return None

    def get_provider(self, provider_id: str) -> Optional[Provider]:
        for p in self.providers:
            if p.id == provider_id:
                return p
        return None

    def _save_providers(self):
        _write_key("PROVIDERS", json.dumps([p.model_dump() for p in self.providers]))

    def add_provider(self, provider: Provider):
        self.providers.append(provider)
        self._save_providers()

    def update_provider(self, provider_id: str, updated: Provider):
        for i, p in enumerate(self.providers):
            if p.id == provider_id:
                self.providers[i] = updated
                break
        self._save_providers()

    def delete_provider(self, provider_id: str):
        self.providers = [p for p in self.providers if p.id != provider_id]
        self._save_providers()

    def set_proxy_api_key(self, key: str):
        self.proxy_api_key = key
        _write_key("PROXY_API_KEY", key)

    def set_host_port(self, host: str, port: int):
        self.host = host
        self.port = port
        _write_key("HOST", host)
        _write_key("PORT", str(port))


config = AppConfig()
