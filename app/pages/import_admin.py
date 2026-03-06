"""
Import / Admin Page - データ取込管理

Features:
- Excel file upload with preview and validation
- Import history
- Error log viewer
- Master data consistency check
"""

from __future__ import annotations

import streamlit as st

from app.auth import require_auth
from app.data import load_import_history
from etl.importer import (
    compute_file_checksum,
    load_column_mappings,
    process_import,
)


SOURCE_TYPE_OPTIONS: dict[str, str] = {
    "sales_item_daily": "日別・商品別売上",
    "sales_store_daily": "日別・店舗別売上",
    "receipt_line": "レシート明細",
    "settlement": "精算データ",
    "sales_dept_timeband": "時間帯別売上",
    "master_store": "店舗マスタ",
    "master_product": "商品マスタ",
}


def render() -> None:
    """Render Import / Admin page."""
    st.title("Import / Admin - データ取込管理")

    user = require_auth()
    if user is None:
        return

    tab_upload, tab_history, tab_master = st.tabs([
        "📤 アップロード",
        "📋 取込履歴",
        "🔧 マスタ管理",
    ])

    with tab_upload:
        _render_upload_section(user.username)

    with tab_history:
        _render_history_section()

    with tab_master:
        _render_master_section()


def _render_upload_section(username: str) -> None:
    """Render file upload section."""
    st.subheader("Excelファイルのアップロード")

    # Source type selector
    source_type = st.selectbox(
        "データ種別",
        options=list(SOURCE_TYPE_OPTIONS.keys()),
        format_func=lambda x: SOURCE_TYPE_OPTIONS[x],
        key="import_source_type",
    )

    # File uploader
    uploaded_file = st.file_uploader(
        "ファイルを選択 (.xlsx, .xls, .csv)",
        type=["xlsx", "xls", "csv"],
        key="import_file",
    )

    if uploaded_file is not None:
        file_content = uploaded_file.read()
        file_checksum = compute_file_checksum(file_content)

        st.info(f"ファイル: {uploaded_file.name} | サイズ: {len(file_content):,} bytes | SHA256: {file_checksum[:16]}...")

        # Dry-run validation
        with st.spinner("バリデーション中..."):
            result = process_import(
                file_content=file_content,
                filename=uploaded_file.name,
                source_type=source_type,
                imported_by=username,
                dry_run=True,
            )

        # Show validation results
        if result["status"] == "fail":
            st.error(f"❌ バリデーション失敗: {result.get('error_message', '不明なエラー')}")
            if result.get("errors"):
                st.markdown("**エラー詳細:**")
                for err in result["errors"][:20]:
                    st.markdown(
                        f"- 行 {err.get('row', '?')}, 列 `{err.get('column', '?')}`: {err.get('error', '')}"
                    )
        else:
            # Show column mapping
            mapping_used = result.get("column_mapping_used", {})
            if mapping_used:
                with st.expander("列マッピング", expanded=False):
                    for target, source in mapping_used.items():
                        st.text(f"  {source}  →  {target}")

            # Show preview
            preview = result.get("preview")
            if preview is not None and len(preview) > 0:
                st.markdown(f"**プレビュー** (先頭 {min(20, len(preview))} 行)")
                st.dataframe(preview, use_container_width=True, hide_index=True)

            # Status summary
            total = result.get("total_rows_in_file", 0)
            valid = result.get("row_count", 0)
            skipped = result.get("skipped_rows", 0)

            if result["status"] == "partial":
                st.warning(
                    f"⚠️ {skipped}行のエラーがありました（全{total}行中）。"
                    f" 有効な{valid}行をインポートします。"
                )
            else:
                st.success(f"✅ バリデーション成功: {valid}行がインポート可能です。")

            # Show errors if any
            errors = result.get("errors", [])
            if errors:
                with st.expander(f"エラー詳細 ({len(errors)}件)", expanded=False):
                    for err in errors[:50]:
                        severity_icon = "❌" if err.get("severity") == "error" else "⚠️"
                        st.markdown(
                            f"{severity_icon} 行 {err.get('row', '?')}, "
                            f"列 `{err.get('column', '?')}`: {err.get('error', '')}"
                        )

            # Confirm button
            st.divider()
            if st.button(
                f"✅ BigQueryにインポート ({valid}行)",
                type="primary",
                key="confirm_import",
                disabled=(valid == 0),
            ):
                with st.spinner("BigQueryにロード中..."):
                    try:
                        from etl.bq_loader import full_import_pipeline

                        final_result = full_import_pipeline(
                            file_content=file_content,
                            filename=uploaded_file.name,
                            source_type=source_type,
                            imported_by=username,
                        )

                        if final_result["status"] == "skipped":
                            st.warning(f"⏭️ {final_result.get('error_message', 'スキップされました')}")
                        elif final_result["status"] in ("success", "partial"):
                            st.success(
                                f"✅ インポート完了！ "
                                f"{final_result.get('row_count', 0)}行をロードしました。"
                            )
                            st.balloons()
                        else:
                            st.error(
                                f"❌ インポート失敗: {final_result.get('error_message', '不明なエラー')}"
                            )
                    except Exception as e:
                        st.error(f"❌ インポート中にエラーが発生しました: {e}")


def _render_history_section() -> None:
    """Render import history."""
    st.subheader("取込履歴")

    df_history = load_import_history()

    if df_history.empty:
        st.info("まだインポート履歴がありません。")
        return

    # Status badge mapping
    status_colors = {
        "success": "🟢",
        "partial": "🟡",
        "fail": "🔴",
        "skipped": "⏭️",
    }

    df_display = df_history.copy()
    if "status" in df_display.columns:
        df_display["ステータス"] = df_display["status"].map(
            lambda x: f"{status_colors.get(x, '⚪')} {x}"
        )

    display_cols = []
    col_rename = {
        "imported_at": "取込日時",
        "source_type": "データ種別",
        "source_file": "ファイル名",
        "imported_by": "実行者",
        "row_count": "行数",
        "ステータス": "ステータス",
        "error_message": "エラー",
    }
    for col in col_rename:
        if col in df_display.columns:
            display_cols.append(col)

    st.dataframe(
        df_display[display_cols].rename(columns=col_rename),
        use_container_width=True,
        hide_index=True,
        height=400,
    )


def _render_master_section() -> None:
    """Render master data management."""
    st.subheader("マスタ整合性チェック")

    st.info(
        "マスタ整合性チェックでは以下を検証します：\n"
        "- 売上データに存在するが商品マスタに未登録のSKU\n"
        "- 売上データに存在するが店舗マスタに未登録の店舗ID\n"
        "- 部門マスタとの不整合"
    )

    if st.button("整合性チェック実行", key="master_check"):
        st.info("BigQuery接続時に整合性チェックが実行されます。デモモードでは実行できません。")
        # In production, this would run queries against BQ to find orphan records

    st.divider()
    st.subheader("マスタ一覧")

    master_type = st.selectbox(
        "マスタ種別",
        options=["店舗マスタ", "部門マスタ", "商品マスタ (サンプル)"],
        key="master_type",
    )

    if master_type == "部門マスタ":
        import pandas as pd

        dept_data = {
            "dept_id": ["food", "produce", "seafood", "meat", "deli", "store_mgmt"],
            "dept_name": ["食品", "青果", "鮮魚", "精肉", "惣菜", "店舗管理"],
            "cost_method": [
                "moving_average", "purchase_cost", "purchase_cost",
                "purchase_cost", "purchase_cost", "purchase_cost",
            ],
            "inventory_method": [
                "theoretical", "physical_count", "physical_count",
                "physical_count", "physical_count", "physical_count",
            ],
        }
        st.dataframe(
            pd.DataFrame(dept_data),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("BigQuery接続時にマスタデータが表示されます。")
