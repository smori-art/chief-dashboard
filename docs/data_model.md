# データモデル定義書

## アーキテクチャ: 星型スキーマ (Star Schema)

```
raw (原形保管) → stg (正規化/型変換/重複排除) → mart (集計/KPI)
```

## データセット

| Dataset | 用途 | 命名規則 |
|---------|------|----------|
| chief_raw | インポート元データを原形で保管 | raw_{source_type}_{YYYYMMDD} |
| chief_stg | 正規化・型変換・重複排除 | stg_{entity} |
| chief_mart | ダッシュボード用集計テーブル/ビュー | mart_{entity} / v_{kpi} |

## ディメンションテーブル

### dim_store
| Column | Type | Description |
|--------|------|-------------|
| store_id | STRING | 店舗ID (PK) |
| store_name | STRING | 店舗名 |
| open_date | DATE | 開店日 |
| region | STRING | 地域 |
| timezone | STRING | タイムゾーン (default: Asia/Bangkok) |
| is_active | BOOL | 有効フラグ |

### dim_department
| Column | Type | Description |
|--------|------|-------------|
| dept_id | STRING | 部門ID (PK) |
| dept_name | STRING | 部門名 |
| cost_method | STRING | 原価計算方式 (moving_average / purchase_cost) |
| inventory_method | STRING | 在庫方式 (theoretical / physical_count) |

### dim_product
| Column | Type | Description |
|--------|------|-------------|
| sku | STRING | 商品コード (PK) |
| product_name | STRING | 商品名 |
| dept_id | STRING | 部門ID (FK) |
| cat_l | STRING | 大分類 |
| cat_m | STRING | 中分類 |
| cat_s | STRING | 小分類 |
| uom | STRING | 単位 |
| standard_cost | NUMERIC | 標準原価 (税抜) |
| active_flag | BOOL | 有効フラグ |

### dim_date
| Column | Type | Description |
|--------|------|-------------|
| date | DATE | 日付 (PK) |
| year | INT64 | 年 |
| month | INT64 | 月 |
| ym | STRING | 年月 (YYYY-MM) |
| week | INT64 | ISO週番号 |
| dow | INT64 | 曜日 (1=Mon, 7=Sun) |
| dow_name | STRING | 曜日名 |
| is_month_end | BOOL | 月末フラグ |
| days_in_month | INT64 | 当月日数 |

### dim_timeband
| Column | Type | Description |
|--------|------|-------------|
| timeband_id | STRING | 時間帯ID (PK) |
| start_time | TIME | 開始時刻 |
| end_time | TIME | 終了時刻 |
| label | STRING | 表示名 (e.g., "09:00-10:00") |

## ファクトテーブル

### f_sales_item_daily
日別・店舗別・商品別売上

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | 日付 |
| store_id | STRING | 店舗ID |
| sku | STRING | 商品コード |
| gross_sales_ex_tax | NUMERIC | 粗売上 (税抜) |
| net_sales_ex_tax | NUMERIC | 実売上 (税抜) |
| qty | NUMERIC | 売上点数 |
| discount_amount_ex_tax | NUMERIC | 値引額 (税抜) |
| dept_id | STRING | 部門ID |
| cat_l | STRING | 大分類 |
| cat_m | STRING | 中分類 |
| cat_s | STRING | 小分類 |

### f_sales_store_daily
日別・店舗別集計売上

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | 日付 |
| store_id | STRING | 店舗ID |
| gross_sales_ex_tax | NUMERIC | 粗売上 (税抜) |
| net_sales_ex_tax | NUMERIC | 実売上 (税抜) |
| receipts | INT64 | レシート件数 |
| qty | NUMERIC | 売上点数 |

### f_receipt_line
レシート明細

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | 日付 |
| store_id | STRING | 店舗ID |
| receipt_id | STRING | レシートID |
| line_no | INT64 | 行番号 |
| sku | STRING | 商品コード |
| qty | NUMERIC | 数量 |
| unit_price_ex_tax | NUMERIC | 単価 (税抜) |
| gross_amount_ex_tax | NUMERIC | 粗金額 (税抜) |
| discount_amount_ex_tax | NUMERIC | 値引額 (税抜) |
| net_amount_ex_tax | NUMERIC | 実金額 (税抜) |
| time | TIME | 時刻 |
| dept_id | STRING | 部門ID |
| cat_l | STRING | 大分類 |
| cat_m | STRING | 中分類 |
| cat_s | STRING | 小分類 |

### f_settlement
精算データ

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | 日付 |
| store_id | STRING | 店舗ID |
| receipt_id | STRING | レシートID |
| tender_type | STRING | 決済方法 |
| amount | NUMERIC | 金額 |
| is_refund | BOOL | 返品返金フラグ |
| refund_reason_code | STRING | 返品理由コード |
| original_receipt_id | STRING | 元レシートID |

### f_sales_dept_timeband_daily
日別・時間帯別・部門別売上

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | 日付 |
| store_id | STRING | 店舗ID |
| dept_id | STRING | 部門ID |
| timeband_id | STRING | 時間帯ID |
| gross_sales_ex_tax | NUMERIC | 粗売上 (税抜) |
| qty | NUMERIC | 売上点数 |

### f_inventory_monthly
月次在庫

| Column | Type | Description |
|--------|------|-------------|
| month_end_date | DATE | 月末日 |
| store_id | STRING | 店舗ID |
| sku | STRING | 商品コード (nullable) |
| dept_id | STRING | 部門ID |
| cat_l | STRING | 大分類 |
| onhand_qty | NUMERIC | 在庫数量 |
| onhand_amount | NUMERIC | 在庫金額 |
| is_physical_count | BOOL | 実地棚卸フラグ |
| for_food_theoretical_flag | BOOL | 食品理論在庫フラグ |
| adjustment_qty | NUMERIC | 棚卸差異数量 |
| adjustment_amount | NUMERIC | 棚卸差異金額 |

### f_waste_discount_daily
日別廃棄・値下

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | 日付 |
| store_id | STRING | 店舗ID |
| sku | STRING | 商品コード (nullable) |
| dept_id | STRING | 部門ID |
| cat_l | STRING | 大分類 |
| waste_qty | NUMERIC | 廃棄数量 |
| waste_amount_ex_tax | NUMERIC | 廃棄金額 (税抜) |
| markdown_qty | NUMERIC | 値下数量 |
| markdown_amount_ex_tax | NUMERIC | 値下金額 (税抜) |

## 監査列 (全rawテーブル共通)

| Column | Type | Description |
|--------|------|-------------|
| _source_file | STRING | 元ファイル名 |
| _imported_at | TIMESTAMP | 取込日時 |
| _imported_by | STRING | 取込実行者 |
| _file_checksum | STRING | ファイルのSHA256チェックサム |
| _row_number | INT64 | 元ファイル内の行番号 |

## インポート監査テーブル

### import_audit_log
| Column | Type | Description |
|--------|------|-------------|
| import_id | STRING | インポートID (UUID) |
| source_type | STRING | データ種別 |
| source_file | STRING | ファイル名 |
| file_checksum | STRING | SHA256 |
| imported_at | TIMESTAMP | 取込日時 |
| imported_by | STRING | 実行ユーザ |
| row_count | INT64 | 行数 |
| status | STRING | success / fail / partial |
| error_message | STRING | エラー内容 |
| error_rows | STRING | エラー行のJSON |
