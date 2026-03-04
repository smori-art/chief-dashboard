# 運用手順書

## 1. ローカル起動手順

### 前提条件
- Python 3.10+
- pip

### 手順

```bash
# 1. リポジトリをクローン
git clone <repository-url>
cd chief-dashboard

# 2. 仮想環境を作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 依存パッケージをインストール
pip install -r requirements.txt

# 4. 環境変数を設定
cp .env.example .env
# .env を編集して必要な値を設定

# 5. Streamlit を起動
streamlit run streamlit_app.py

# ブラウザで http://localhost:8501 にアクセス
# デフォルトログイン: admin / admin
```

### BigQuery接続なしで動かす場合
- BigQuery未接続の場合、自動的にデモデータが生成されます
- すべての画面をデモデータで確認できます

### BigQuery接続して動かす場合

```bash
# 1. GCPプロジェクトを設定
export GCP_PROJECT_ID=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# 2. BigQueryデータセットを作成
bq mk --dataset ${GCP_PROJECT_ID}:chief_raw
bq mk --dataset ${GCP_PROJECT_ID}:chief_stg
bq mk --dataset ${GCP_PROJECT_ID}:chief_mart

# 3. DDLを実行 (PROJECT_IDを置換)
# sql/raw/create_raw_tables.sql
# sql/stg/create_stg_tables.sql
# sql/mart/create_mart_tables.sql
# sql/views/ 配下のビューSQL

# 4. .envにBQ設定を追加
echo "GCP_PROJECT_ID=your-project-id" >> .env
echo "BQ_DATASET_RAW=chief_raw" >> .env
echo "BQ_DATASET_STG=chief_stg" >> .env
echo "BQ_DATASET_MART=chief_mart" >> .env
```

## 2. GCPデプロイ手順 (Cloud Run)

### 前提条件
- GCP Project
- gcloud CLI 認証済み
- Artifact Registry / Cloud Run API 有効化

### 手順

```bash
# 1. Artifact Registry リポジトリ作成
gcloud artifacts repositories create chief-dashboard \
    --repository-format=docker \
    --location=asia-southeast1

# 2. Docker イメージのビルド＆プッシュ
gcloud builds submit --config=infra/cloudbuild.yaml

# 3. 環境変数をSecret Managerに設定
gcloud secrets create chief-auth-users --data-file=- <<< "admin:strongpassword:admin"
gcloud secrets create chief-teams-webhook --data-file=- <<< "https://..."

# 4. Cloud Run にデプロイ (Cloud Build が自動実行)
# または手動デプロイ:
gcloud run deploy chief-dashboard \
    --image=asia-southeast1-docker.pkg.dev/${PROJECT_ID}/chief-dashboard/app:latest \
    --region=asia-southeast1 \
    --port=8501 \
    --memory=1Gi \
    --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},BQ_DATASET_RAW=chief_raw,BQ_DATASET_STG=chief_stg,BQ_DATASET_MART=chief_mart"

# 5. サービスアカウントにBigQuery権限を付与
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/bigquery.jobUser"
```

## 3. データ取り込み運用フロー

### 日次運用 (仮更新)

1. **LSCからExcelエクスポート**
   - 前日分のデータを以下の形式でエクスポート:
     - 日別・商品別売上
     - 日別・店舗別売上
     - レシート明細
     - 精算データ
     - 時間帯別売上

2. **ダッシュボードからアップロード**
   - Import/Admin ページにアクセス
   - データ種別を選択してファイルをアップロード
   - バリデーション結果を確認
   - 「BigQueryにインポート」をクリック

3. **自動集計** (Cloud Scheduler設定時)
   - 毎日 2:00 AM (ICT) に mart テーブルを更新
   - 当月の着地見込みを再計算

### 月次運用 (確定)

1. **月次データ確認** (毎月5日まで)
   - 前月の全データが取り込まれていることを確認
   - Import/Admin の取込履歴で欠落がないかチェック

2. **棚卸データの取り込み**
   - 月末棚卸データをExcelでアップロード
   - 食品部門: 理論在庫との差分がadjustmentとして記録

3. **月次レポート生成**
   - Export/Report ページでPDFを生成
   - Teamsチャネルに送信

4. **マスタ整合性チェック**
   - Import/Admin のマスタ管理で整合性チェックを実行
   - 未登録SKU、未登録店舗がないか確認

## 4. トラブルシューティング

### インポートが失敗する
- エラーメッセージを確認
- 必須列が揃っているか確認
- 日付形式、数値形式を確認
- ファイルサイズ上限 (100MB) を超えていないか

### ダッシュボードが遅い
- BigQuery接続の場合: mart テーブルが最新か確認
- キャッシュをクリア: ブラウザでページをリロード
- データ量が多い場合: フィルタで絞り込む

### PDF生成が失敗する
- WeasyPrintのインストールを確認
- システム依存パッケージ (libpango等) がインストールされているか確認
- Docker環境では Dockerfile で既にインストール済み

### Teams送信が失敗する
- Webhook URLが正しいか確認
- ネットワーク接続を確認
- Webhook URLの有効期限を確認

## 5. Cloud Scheduler 設定 (日次/月次自動実行)

```bash
# 日次: mart テーブル更新 (2:00 AM ICT)
gcloud scheduler jobs create http chief-daily-refresh \
    --schedule="0 19 * * *" \
    --uri="https://chief-dashboard-xxxxx-as.a.run.app/api/refresh" \
    --http-method=POST \
    --time-zone="UTC" \
    --attempt-deadline=600s

# 月次: 着地見込み確定 (毎月5日 8:00 AM ICT)
gcloud scheduler jobs create http chief-monthly-finalize \
    --schedule="0 1 5 * *" \
    --uri="https://chief-dashboard-xxxxx-as.a.run.app/api/finalize" \
    --http-method=POST \
    --time-zone="UTC" \
    --attempt-deadline=900s
```
