#!/bin/bash
set -e

# Write GCP service account JSON from environment variable to file
if [ -n "$GOOGLE_APPLICATION_CREDENTIALS_JSON" ]; then
    echo "$GOOGLE_APPLICATION_CREDENTIALS_JSON" > /tmp/gcp-key.json
    export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-key.json
    echo "GCP credentials written to /tmp/gcp-key.json"
fi

# Start Streamlit
exec streamlit run streamlit_app.py \
    --server.port="${PORT:-10000}" \
    --server.address=0.0.0.0 \
    --server.headless=true
