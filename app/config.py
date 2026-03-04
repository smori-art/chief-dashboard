"""
Application configuration loader.
Reads from environment variables and config.yaml.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


@dataclass
class AppConfig:
    """Application configuration."""

    # GCP / BigQuery
    gcp_project_id: str = ""
    bq_dataset_raw: str = "chief_raw"
    bq_dataset_stg: str = "chief_stg"
    bq_dataset_mart: str = "chief_mart"
    gcs_bucket: str = ""

    # Auth
    auth_mode: str = "simple"  # simple | entraid
    auth_users: dict[str, dict[str, str]] = field(default_factory=dict)

    # Entra ID
    entraid_tenant_id: str = ""
    entraid_client_id: str = ""
    entraid_client_secret: str = ""
    entraid_redirect_uri: str = ""

    # Teams
    teams_mode: str = "webhook"
    teams_webhook_url: str = ""

    # App
    app_title: str = "Chief Dashboard - タイ食品スーパー月次ダッシュボード"
    app_timezone: str = "Asia/Bangkok"
    data_retention_months: int = 36
    cache_ttl_seconds: int = 300

    # Departments
    departments: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls) -> AppConfig:
        """Load configuration from env vars and optional config.yaml."""
        config = cls()

        # From environment
        config.gcp_project_id = os.getenv("GCP_PROJECT_ID", "")
        config.bq_dataset_raw = os.getenv("BQ_DATASET_RAW", "chief_raw")
        config.bq_dataset_stg = os.getenv("BQ_DATASET_STG", "chief_stg")
        config.bq_dataset_mart = os.getenv("BQ_DATASET_MART", "chief_mart")
        config.gcs_bucket = os.getenv("GCS_BUCKET", "")
        config.auth_mode = os.getenv("AUTH_MODE", "simple")
        config.teams_mode = os.getenv("TEAMS_MODE", "webhook")
        config.teams_webhook_url = os.getenv("TEAMS_WEBHOOK_URL", "")
        config.entraid_tenant_id = os.getenv("ENTRAID_TENANT_ID", "")
        config.entraid_client_id = os.getenv("ENTRAID_CLIENT_ID", "")
        config.entraid_client_secret = os.getenv("ENTRAID_CLIENT_SECRET", "")
        config.entraid_redirect_uri = os.getenv("ENTRAID_REDIRECT_URI", "")

        # Parse simple auth users
        auth_users_str = os.getenv("AUTH_USERS", "admin:admin:admin")
        for entry in auth_users_str.split(","):
            parts = entry.strip().split(":")
            if len(parts) >= 3:
                config.auth_users[parts[0]] = {
                    "password": parts[1],
                    "role": parts[2],
                }
            elif len(parts) == 2:
                config.auth_users[parts[0]] = {
                    "password": parts[1],
                    "role": "viewer",
                }

        # Load config.yaml if present
        config_path = Path(__file__).parent.parent / "config.yaml"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                yaml_config: dict[str, Any] = yaml.safe_load(f) or {}

            app_section = yaml_config.get("app", {})
            config.app_title = app_section.get("title", config.app_title)
            config.app_timezone = app_section.get("timezone", config.app_timezone)
            config.data_retention_months = app_section.get(
                "data_retention_months", config.data_retention_months
            )
            config.cache_ttl_seconds = app_section.get(
                "cache_ttl_seconds", config.cache_ttl_seconds
            )
            config.departments = yaml_config.get("departments", [])
        else:
            # Default departments
            config.departments = [
                {"id": "food", "name": "食品"},
                {"id": "produce", "name": "青果"},
                {"id": "seafood", "name": "鮮魚"},
                {"id": "meat", "name": "精肉"},
                {"id": "deli", "name": "惣菜"},
                {"id": "store_mgmt", "name": "店舗管理"},
            ]

        return config


# Singleton
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get application config singleton."""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config
