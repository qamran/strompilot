"""Tests for the shared Settings object and model-key dependencies."""

from pathlib import Path

import pytest
from fastapi import HTTPException

from strompilot.main import (
    Settings,
    require_meta_key,
    require_model_keys,
)


def test_settings_reads_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("META_API_KEY", "meta-key")
    monkeypatch.setenv("BASETEN_API_KEY", "baseten-key")
    monkeypatch.setenv("THREADS_DB", str(tmp_path / "threads.db"))
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    settings = Settings.from_env()
    assert settings.meta_key == "meta-key"
    assert settings.baseten_key == "baseten-key"
    assert settings.threads_db == tmp_path / "threads.db"
    assert settings.memory_db == tmp_path / "memory.db"


def test_require_model_keys_returns_both_keys() -> None:
    settings = Settings(
        meta_key="meta-key",
        baseten_key="baseten-key",
        threads_db=Path("threads.db"),
        memory_db=Path("memory.db"),
    )
    assert require_model_keys(settings) == ("meta-key", "baseten-key")
    assert require_meta_key(settings) == "meta-key"


def test_require_model_keys_rejects_missing_keys() -> None:
    empty = Settings(
        meta_key="",
        baseten_key="",
        threads_db=Path("threads.db"),
        memory_db=Path("memory.db"),
    )
    with pytest.raises(HTTPException) as caught:
        require_model_keys(empty)
    assert caught.value.status_code == 500
    assert caught.value.detail == "model keys missing"
    half = Settings(
        meta_key="meta-key",
        baseten_key="",
        threads_db=Path("threads.db"),
        memory_db=Path("memory.db"),
    )
    with pytest.raises(HTTPException):
        require_model_keys(half)
    assert require_meta_key(half) == "meta-key"
    with pytest.raises(HTTPException) as meta_caught:
        require_meta_key(empty)
    assert meta_caught.value.status_code == 500
