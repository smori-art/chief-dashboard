"""
Export / Report Page - レポート出力

Features:
- PDF generation from current filter state
- Teams channel/user message sending
"""

from __future__ import annotations

import streamlit as st

from app.auth import require_auth
from app.components import render_sidebar_filters
from app.data import load_sales_monthly
from app.pdf_generator import generate_report_pdf
from app.teams_sender import send_teams_message


def render() -> None:
    """Render Export / Report page."""
    st.title("Export / Report - レポート出力")

    user = require_auth()
    if user is None:
        return

    filters = render_sidebar_filters()

    tab_pdf, tab_teams = st.tabs(["📄 PDF出力", "💬 Teams送信"])

    with tab_pdf:
        _render_pdf_section(filters)

    with tab_teams:
        _render_teams_section(filters, user.username)


def _render_pdf_section(filters: dict) -> None:
    """Render PDF generation section."""
    st.subheader("PDF レポート生成")

    st.markdown(
        f"**現在のフィルタ条件:**\n"
        f"- 期間: {filters.get('ym', 'N/A')}\n"
        f"- 店舗: {len(filters.get('store_ids', []))} 店舗選択中\n"
        f"- 部門: {len(filters.get('dept_ids', []))} 部門選択中\n"
        f"- 売上表示: {'実売上' if filters.get('sales_type') == 'net' else '粗売上'}"
    )

    st.markdown(
        "**PDF内容:**\n"
        "1. サマリKPI (売上/粗利/粗利率/値引率)\n"
        "2. 部門別構成比\n"
        "3. 粗利悪化Top要因\n"
        "4. 欠品/値引の要点"
    )

    if st.button("📄 PDF生成", type="primary", key="generate_pdf"):
        with st.spinner("PDF生成中..."):
            try:
                pdf_bytes = generate_report_pdf(filters)
                if pdf_bytes:
                    st.success("✅ PDF生成完了！")
                    st.download_button(
                        label="📥 PDFをダウンロード",
                        data=pdf_bytes,
                        file_name=f"chief_report_{filters.get('ym', 'latest')}.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.warning("PDFの生成に失敗しました。WeasyPrintがインストールされているか確認してください。")
            except Exception as e:
                st.error(f"PDF生成エラー: {e}")
                st.info(
                    "WeasyPrintが未インストールの場合:\n"
                    "`pip install weasyprint`\n\n"
                    "システム依存パッケージが必要な場合があります。"
                )


def _render_teams_section(filters: dict, username: str) -> None:
    """Render Teams send section."""
    st.subheader("Teams メッセージ送信")

    send_mode = st.radio(
        "送信方式",
        options=["Webhook (簡易)", "Microsoft Graph API (将来)"],
        horizontal=True,
        key="teams_send_mode",
    )

    if "Graph" in send_mode:
        st.info("Microsoft Graph API連携は将来のリリースで対応予定です。")
        return

    # Webhook mode
    st.markdown("**メッセージ内容**")

    message_text = st.text_area(
        "メッセージ",
        value=(
            f"📊 Chief Dashboard 月次レポート\n"
            f"期間: {filters.get('ym', 'N/A')}\n"
            f"作成者: {username}\n\n"
            f"詳細はダッシュボードをご確認ください。"
        ),
        height=150,
        key="teams_message",
    )

    attach_pdf = st.checkbox("PDFを添付する", value=True, key="teams_attach_pdf")

    if st.button("💬 Teamsに送信", type="primary", key="send_teams"):
        with st.spinner("送信中..."):
            try:
                pdf_bytes = None
                if attach_pdf:
                    pdf_bytes = generate_report_pdf(filters)

                success = send_teams_message(
                    message=message_text,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=f"chief_report_{filters.get('ym', 'latest')}.pdf",
                )

                if success:
                    st.success("✅ Teamsへの送信が完了しました！")
                else:
                    st.error("❌ 送信に失敗しました。Webhook URLを確認してください。")
            except Exception as e:
                st.error(f"送信エラー: {e}")
