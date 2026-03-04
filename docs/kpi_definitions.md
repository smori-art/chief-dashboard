# KPI定義書 - Chief Dashboard

## 1. 売上 (Sales)

### 1.1 粗売上 (Gross Sales)
- **定義**: 値引前の税抜売上金額
- **計算式**: `SUM(gross_sales_ex_tax)`
- **粒度**: 日次 × 店舗 × SKU
- **ソース**: f_sales_item_daily, f_sales_store_daily

### 1.2 実売上 (Net Sales)
- **定義**: 値引後の税抜売上金額（返品返金控除前）
- **計算式**: `SUM(net_sales_ex_tax)`
- **粒度**: 日次 × 店舗 × SKU
- **ソース**: f_sales_item_daily, f_sales_store_daily

### 1.3 返品返金額 (Refund Amount)
- **定義**: 精算データから特定した返品返金の金額
- **計算式**: `SUM(amount) WHERE is_refund = TRUE` (from f_settlement)
- **粒度**: 日次 × 店舗
- **ソース**: f_settlement

### 1.4 純売上 (Net Sales after Refund)
- **定義**: 実売上から返品返金を控除した最終売上
- **計算式**: `net_sales_ex_tax - refund_amount`
- **粒度**: 日次 × 店舗

### 1.5 値引額 (Discount Amount)
- **定義**: 粗売上と実売上の差分
- **計算式**: `gross_sales_ex_tax - net_sales_ex_tax`
- **粒度**: 日次 × 店舗 × SKU

### 1.6 値引率 (Discount Rate)
- **計算式**: `discount_amount / gross_sales_ex_tax * 100`

## 2. 粗利 (Gross Profit)

### 2.1 原価 (COGS)

#### 食品部門: 移動平均原価
- **定義**: 移動平均法で算出した原価
- **計算式**: `qty × moving_avg_cost_per_unit`
- **moving_avg_cost**: 日次/SKU/店舗で保持。入荷時に再計算:
  `new_avg = (existing_qty × old_avg + received_qty × received_cost) / (existing_qty + received_qty)`
- **MVP**: 原価テーブル未整備の場合、仕入原価の近似値で開始

#### その他部門: 仕入原価
- **定義**: 最新の仕入原価 × 数量
- **計算式**: `qty × purchase_cost_per_unit`

### 2.2 粗利額 (Gross Profit Amount)
- **計算式**: `net_sales_ex_tax - cogs`

### 2.3 粗利率 (Gross Margin %)
- **計算式**: `gross_profit / net_sales_ex_tax × 100`

### 2.4 粗利悪化要因分解
- **売価要因**: 単価変動 × 前期数量
- **数量要因**: 数量変動 × 前期単価
- **値引要因**: 値引額の増減
- **原価要因**: 原価変動 × 当期数量
- MVP: 近似的にgross_profit差分の内訳を可視化

## 3. 在庫 (Inventory)

### 3.1 食品部門: 理論在庫
- **定義**: 前日理論在庫 + 入荷 - 売上 - 調整
- **計算式**: `prev_theoretical + receiving - sales_qty - adjustments`
- **補正**: 月次実地棚卸で差分をadjustmentとして記録
- **ソース**: f_inventory_monthly

### 3.2 その他部門: 月末実地棚卸
- **定義**: 月末の実地棚卸値をそのまま採用
- **ソース**: f_inventory_monthly (is_physical_count = TRUE)

### 3.3 在庫金額
- **計算式**: `onhand_qty × unit_cost`

### 3.4 在庫回転率
- **計算式**: `COGS(月) / 平均在庫金額`

## 4. 欠品率 (Out-of-Stock Rate)

### 4.1 レシート推定 (Receipt-based Estimation)
- **定義**: 過去の販売パターンから期待需要を推定し、実績との乖離で欠品を検知
- **MVP計算式**:
  1. 期待値 = 同曜日・直近8週の売上中央値
  2. 欠品疑い = 当日売上が0、または期待値の20%以下
  3. 欠品率 = 欠品疑いSKU数 / 有効SKU数 × 100

### 4.2 在庫・発注データ (Inventory/Order-based)
- **定義**: 在庫0かつ発注残ありの状態
- **計算式**: `COUNT(SKU WHERE onhand_qty = 0 AND has_pending_order) / total_active_sku × 100`
- **MVP**: データ列が不足する場合はプレースホルダ（将来拡張ポイント）

### 4.3 欠品率比較
- 両方の指標を並べて乖離を分析

## 5. 廃棄・値引 (Waste & Markdown)

### 5.1 廃棄額 (Waste Amount)
- **計算式**: `SUM(waste_amount_ex_tax)`
- **廃棄率**: `waste_amount / net_sales_ex_tax × 100`

### 5.2 値下額 (Markdown Amount)
- **計算式**: `SUM(markdown_amount_ex_tax)`
- **値下率**: `markdown_amount / gross_sales_ex_tax × 100`

## 6. 着地見込み (Forecast)

### 6.1 当月着地見込み
- **定義**: 当月途中での月末売上予測
- **計算式(MVP)**:
  `forecast = actual_to_date / elapsed_days × total_days_in_month`
- **改善案**: 曜日加重、前年同月のパターン反映

## 7. 構成比 (Composition Ratio)

### 7.1 売上構成比
- **計算式**: `department_sales / total_sales × 100`

### 7.2 粗利構成比
- **計算式**: `department_gross_profit / total_gross_profit × 100`

---

## 更新タイミング

| 更新種別 | タイミング | 内容 |
|---------|-----------|------|
| 日次仮更新 | 毎日 2:00 AM (ICT) | 前日分データ取込、mart再計算 |
| 月次確定 | 毎月5日 | 前月分を確定、棚卸データ反映 |
| 着地見込み | 日次 | 当月7日以降、着地見込みを更新 |
