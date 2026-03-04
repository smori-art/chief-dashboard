"""
Teams Message Sender.

Supports:
- Webhook (MVP): Send messages via Incoming Webhook
- Microsoft Graph API (future): Send via Graph with file attachment

The abstraction allows switching from Webhook to Graph
by changing config only.
"""

from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from typing import Any

import requests
from loguru import logger

from app.config import get_config


class TeamsSender(ABC):
    """Abstract Teams message sender."""

    @abstractmethod
    def send(
        self,
        message: str,
        pdf_bytes: bytes | None = None,
        pdf_filename: str | None = None,
    ) -> bool:
        """Send a message to Teams. Returns True on success."""
        ...


class WebhookTeamsSender(TeamsSender):
    """Send messages via Teams Incoming Webhook."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(
        self,
        message: str,
        pdf_bytes: bytes | None = None,
        pdf_filename: str | None = None,
    ) -> bool:
        if not self.webhook_url:
            logger.error("Teams Webhook URL is not configured")
            return False

        # Build Adaptive Card payload
        card_body: list[dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": "Chief Dashboard レポート",
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": "TextBlock",
                "text": message,
                "wrap": True,
            },
        ]

        if pdf_bytes and pdf_filename:
            card_body.append({
                "type": "TextBlock",
                "text": f"📎 添付: {pdf_filename} ({len(pdf_bytes):,} bytes)",
                "isSubtle": True,
                "size": "Small",
            })

        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": card_body,
                    },
                }
            ],
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if response.status_code in (200, 202):
                logger.info("Teams webhook message sent successfully")
                return True
            else:
                logger.error(
                    f"Teams webhook failed: {response.status_code} {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"Teams webhook error: {e}")
            return False


class GraphTeamsSender(TeamsSender):
    """
    Send messages via Microsoft Graph API.
    Placeholder for future implementation.

    Will support:
    - Channel messages with PDF attachment
    - Upload to SharePoint/OneDrive and send link
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        channel_id: str,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.channel_id = channel_id

    def send(
        self,
        message: str,
        pdf_bytes: bytes | None = None,
        pdf_filename: str | None = None,
    ) -> bool:
        # TODO: Implement Microsoft Graph API integration
        # 1. Get access token via MSAL
        # 2. Upload PDF to SharePoint/OneDrive
        # 3. Send channel message with link to file
        logger.warning("Graph API sender not yet implemented")
        return False


def get_teams_sender() -> TeamsSender:
    """Factory: return the configured Teams sender."""
    config = get_config()
    if config.teams_mode == "graph":
        return GraphTeamsSender(
            tenant_id=config.entraid_tenant_id,
            client_id=os.getenv("TEAMS_GRAPH_CLIENT_ID", ""),
            client_secret=os.getenv("TEAMS_GRAPH_CLIENT_SECRET", ""),
            channel_id=os.getenv("TEAMS_CHANNEL_ID", ""),
        )
    return WebhookTeamsSender(webhook_url=config.teams_webhook_url)


def send_teams_message(
    message: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str | None = None,
) -> bool:
    """
    Send a message to Teams using the configured sender.

    Args:
        message: Message text
        pdf_bytes: Optional PDF content to attach
        pdf_filename: Optional PDF filename

    Returns:
        True if send was successful
    """
    sender = get_teams_sender()
    return sender.send(message, pdf_bytes, pdf_filename)
