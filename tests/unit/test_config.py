"""
Unit tests for application configuration.
"""

from __future__ import annotations

import os

import pytest


class TestAppConfig:
    """Tests for AppConfig loading."""

    def test_loads_defaults(self) -> None:
        # Ensure clean state
        from app.config import AppConfig

        config = AppConfig()
        assert config.auth_mode == "simple"
        assert config.bq_dataset_raw == "chief_raw"
        assert config.bq_dataset_stg == "chief_stg"
        assert config.bq_dataset_mart == "chief_mart"
        assert config.app_timezone == "Asia/Bangkok"

    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.config import AppConfig

        monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
        monkeypatch.setenv("AUTH_MODE", "simple")
        monkeypatch.setenv("AUTH_USERS", "testuser:testpass:admin")

        config = AppConfig.load()
        assert config.gcp_project_id == "test-project"
        assert config.auth_mode == "simple"
        assert "testuser" in config.auth_users
        assert config.auth_users["testuser"]["role"] == "admin"

    def test_default_departments(self) -> None:
        from app.config import AppConfig

        config = AppConfig.load()
        assert len(config.departments) >= 6

    def test_parse_multiple_users(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.config import AppConfig

        monkeypatch.setenv("AUTH_USERS", "user1:pass1:admin,user2:pass2:viewer")
        config = AppConfig.load()
        assert "user1" in config.auth_users
        assert "user2" in config.auth_users
        assert config.auth_users["user1"]["role"] == "admin"
        assert config.auth_users["user2"]["role"] == "viewer"
