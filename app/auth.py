"""
Authentication module.
MVP: Simple username/password login.
Future: Entra ID (OIDC) integration.

The auth layer is abstracted so switching from simple → Entra ID
requires only changing the config and implementing the EntraID adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import streamlit as st

from app.config import get_config


@dataclass
class User:
    """Authenticated user."""

    username: str
    role: str  # admin, manager, viewer
    display_name: str = ""


class AuthProvider(ABC):
    """Abstract authentication provider."""

    @abstractmethod
    def login_ui(self) -> User | None:
        """Render login UI and return User if authenticated."""
        ...

    @abstractmethod
    def logout(self) -> None:
        """Logout current user."""
        ...

    @abstractmethod
    def get_current_user(self) -> User | None:
        """Get currently authenticated user."""
        ...


class SimpleAuthProvider(AuthProvider):
    """Simple username/password authentication for MVP."""

    def login_ui(self) -> User | None:
        """Render simple login form."""
        config = get_config()

        if "authenticated_user" in st.session_state:
            return st.session_state["authenticated_user"]

        st.markdown(
            '<div style="text-align:center;padding:2rem 0 1rem">'
            '<h2 style="font-weight:700;color:#0F172A;margin:0">Chief Dashboard</h2>'
            '<p style="color:#64748B;font-size:0.9rem;margin-top:4px">'
            'タイ食品スーパー 月次ダッシュボード</p></div>',
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input("ユーザー名", key="login_username")
            password = st.text_input(
                "パスワード", type="password", key="login_password"
            )
            submitted = st.form_submit_button("ログイン", use_container_width=True)

        if submitted:
            if username in config.auth_users:
                user_info = config.auth_users[username]
                if user_info["password"] == password:
                    user = User(
                        username=username,
                        role=user_info["role"],
                        display_name=username,
                    )
                    st.session_state["authenticated_user"] = user
                    st.rerun()
                else:
                    st.error("パスワードが正しくありません。")
            else:
                st.error("ユーザーが見つかりません。")

        return None

    def logout(self) -> None:
        """Clear session state."""
        if "authenticated_user" in st.session_state:
            del st.session_state["authenticated_user"]

    def get_current_user(self) -> User | None:
        """Get current user from session."""
        return st.session_state.get("authenticated_user")


class EntraIDAuthProvider(AuthProvider):
    """
    Microsoft Entra ID (Azure AD) OIDC authentication.
    Placeholder for future implementation.
    """

    def login_ui(self) -> User | None:
        config = get_config()
        st.warning("Entra ID認証は現在設定中です。管理者に連絡してください。")
        st.markdown(
            f"Tenant ID: `{config.entraid_tenant_id}`\n\n"
            f"Client ID: `{config.entraid_client_id}`"
        )
        # TODO: Implement OIDC flow with msal
        return None

    def logout(self) -> None:
        if "authenticated_user" in st.session_state:
            del st.session_state["authenticated_user"]

    def get_current_user(self) -> User | None:
        return st.session_state.get("authenticated_user")


def get_auth_provider() -> AuthProvider:
    """Factory: return the configured auth provider."""
    config = get_config()
    if config.auth_mode == "entraid":
        return EntraIDAuthProvider()
    return SimpleAuthProvider()


def require_auth() -> User | None:
    """
    Gate function: ensures user is authenticated.
    Returns User if authenticated, None if login form is shown.
    """
    provider = get_auth_provider()
    user = provider.get_current_user()
    if user is not None:
        return user
    return provider.login_ui()


def show_user_info_sidebar() -> None:
    """Show user info and logout button in sidebar."""
    provider = get_auth_provider()
    user = provider.get_current_user()
    if user:
        with st.sidebar:
            st.markdown(f"**{user.display_name}** ({user.role})")
            if st.button("ログアウト", key="logout_btn"):
                provider.logout()
                st.rerun()
