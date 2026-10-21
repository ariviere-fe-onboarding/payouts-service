from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from payouts.config import Config, ConfigError, load_config
from payouts.crypto import FieldCipher
from payouts.main import create_app
from payouts.seed import seed


def test_bank_numbers_are_encrypted_at_rest(config: Config) -> None:
    app = create_app(config)
    with app.state.session_factory() as session:
        seed(session, FieldCipher(config.encryption_key))
        raw = session.execute(text("SELECT * FROM bank_accounts")).all()
    app.state.engine.dispose()
    dump = repr(raw)
    assert "000123456789" not in dump
    assert "110000000" not in dump


def test_seed_is_idempotent(config: Config) -> None:
    app = create_app(config)
    cipher = FieldCipher(config.encryption_key)
    with app.state.session_factory() as session:
        assert seed(session, cipher) == 4
        assert seed(session, cipher) == 0
    app.state.engine.dispose()


def test_cipher_round_trip() -> None:
    cipher = FieldCipher(Fernet.generate_key().decode("ascii"))
    assert cipher.decrypt(cipher.encrypt("000123456789")) == "000123456789"


def test_config_requires_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("PAYOUTS_WEBHOOK_SECRET", "PAYOUTS_SERVICE_TOKEN", "PAYOUTS_ENCRYPTION_KEY"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError, match="PAYOUTS_WEBHOOK_SECRET"):
        load_config(tmp_path / "missing.env")


def test_config_reads_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("PAYOUTS_WEBHOOK_SECRET", "PAYOUTS_SERVICE_TOKEN", "PAYOUTS_ENCRYPTION_KEY"):
        monkeypatch.delenv(key, raising=False)
    key = Fernet.generate_key().decode("ascii")
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        f"PAYOUTS_WEBHOOK_SECRET={'a' * 40}\n"
        f"PAYOUTS_SERVICE_TOKEN={'b' * 40}\n"
        f"PAYOUTS_ENCRYPTION_KEY={key}\n",
        encoding="utf-8",
    )
    loaded = load_config(env)
    assert loaded.service_token == "b" * 40
    assert loaded.encryption_key == key
