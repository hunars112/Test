"""Encrypted credential storage for Authority Site Engine."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Dict, Optional

try:  # pragma: no cover - optional dependency
    from cryptography.fernet import Fernet  # type: ignore
except Exception:  # pragma: no cover - fallback path
    Fernet = None


@dataclass
class CredentialRecord:
    """Internal representation of a stored secret."""

    identifier: str
    project_slug: str
    secret_type: str
    payload: str  # encrypted


class CredentialVault:
    """Minimal symmetric encrypted credential store."""

    def __init__(
        self,
        vault_path: Path,
        *,
        master_password: str | None = None,
    ) -> None:
        self.vault_path = vault_path
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        env_password = os.environ.get("ASE_MASTER_PASSWORD")
        self.master_password = master_password or env_password or "development-master-key"
        self._fernet = self._build_cipher()
        self._records: Dict[str, CredentialRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    def _build_cipher(self):
        key_bytes = sha256(self.master_password.encode("utf-8")).digest()
        b64_key = base64.urlsafe_b64encode(key_bytes)
        if Fernet:
            return Fernet(b64_key)
        return None

    def _xor_cipher(self, value: bytes) -> bytes:
        key = sha256(self.master_password.encode("utf-8")).digest()
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(value))

    def _encrypt(self, text: str) -> str:
        data = text.encode("utf-8")
        if self._fernet:
            return self._fernet.encrypt(data).decode("utf-8")
        xored = self._xor_cipher(data)
        return base64.urlsafe_b64encode(xored).decode("utf-8")

    def _decrypt(self, token: str) -> str:
        if self._fernet:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        decoded = base64.urlsafe_b64decode(token.encode("utf-8"))
        clear = self._xor_cipher(decoded)
        return clear.decode("utf-8")

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.vault_path.exists():
            self._records = {}
            return
        data = json.loads(self.vault_path.read_text(encoding="utf-8"))
        entries = data.get("entries", {})
        self._records = {
            key: CredentialRecord(
                identifier=key,
                project_slug=value.get("project_slug", ""),
                secret_type=value.get("secret_type", "generic"),
                payload=value.get("payload", ""),
            )
            for key, value in entries.items()
        }

    def _persist(self) -> None:
        data = {
            "entries": {
                key: {
                    "project_slug": record.project_slug,
                    "secret_type": record.secret_type,
                    "payload": record.payload,
                }
                for key, record in self._records.items()
            }
        }
        self.vault_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    def store_secret(self, project_slug: str, secret_type: str, payload: Dict[str, str]) -> str:
        identifier = f"{project_slug}-{secret_type}-{len(self._records) + 1}"
        encrypted = self._encrypt(json.dumps(payload))
        self._records[identifier] = CredentialRecord(
            identifier=identifier,
            project_slug=project_slug,
            secret_type=secret_type,
            payload=encrypted,
        )
        self._persist()
        return identifier

    def retrieve_secret(self, identifier: str | None) -> Optional[Dict[str, str]]:
        if not identifier:
            return None
        record = self._records.get(identifier)
        if not record:
            return None
        decrypted = self._decrypt(record.payload)
        return json.loads(decrypted)

    def delete_secret(self, identifier: str) -> None:
        if identifier in self._records:
            del self._records[identifier]
            self._persist()


__all__ = ["CredentialVault", "CredentialRecord"]
