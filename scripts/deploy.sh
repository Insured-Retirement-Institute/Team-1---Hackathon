#!/usr/bin/env bash
# Usage:
#   ./scripts/deploy.sh api-broker-dealer
#   ./scripts/deploy.sh api-clearinghouse
#   ./scripts/deploy.sh api-insurance-carrier
#   ./scripts/deploy.sh sqs-policy-inquiry
#   ./scripts/deploy.sh sqs-bd-change
#   ./scripts/deploy.sh api-bd-change-callback
#   ./scripts/deploy.sh all

set -euo pipefail

REGION="us-east-1"
FUNCTIONS=(
  "api-broker-dealer"
  "api-clearinghouse"
  "api-insurance-carrier"
  "sqs-policy-inquiry"
  "sqs-bd-change"
  "api-bd-change-callback"
)

deploy_function() {
  local FUNCTION_NAME="$1"
  local DIR="$FUNCTION_NAME"

  if [[ ! -d "$DIR" ]]; then
    echo "ERROR: Directory '$DIR' not found. Run from repo root." >&2
    exit 1
  fi

  echo "▶ Packaging $FUNCTION_NAME..."

  local TMP_DIR
  TMP_DIR=$(mktemp -d)
  local ZIP_FILE="/tmp/${FUNCTION_NAME}-$(date +%Y%m%d-%H%M%S).zip"

  # Install dependencies and copy source into temp dir
  pip3 install -r "$DIR/requirements.txt" -t "$TMP_DIR" --quiet
  cp -r "$DIR"/. "$TMP_DIR/"

  # Create zip (exclude pyc / __pycache__)
  (cd "$TMP_DIR" && zip -r "$ZIP_FILE" . -x "*.pyc" -x "*/__pycache__/*" > /dev/null)
  echo "  Package: $ZIP_FILE ($(du -sh "$ZIP_FILE" | cut -f1))"

  # Cleanup temp dir
  rm -rf "$TMP_DIR"

  echo "▶ Deploying $FUNCTION_NAME to Lambda..."
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_FILE" \
    --region "$REGION" \
    --output text \
    --query 'FunctionArn'

  echo "▶ Waiting for update to complete..."
  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

  rm -f "$ZIP_FILE"
  echo "✓ $FUNCTION_NAME deployed successfully"
  echo
}

TARGET="${1:-}"

if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 <function-name|all>"
  echo "  Functions: ${FUNCTIONS[*]}"
  exit 1
fi

if [[ "$TARGET" == "all" ]]; then
  for fn in "${FUNCTIONS[@]}"; do
    deploy_function "$fn"
  done
else
  deploy_function "$TARGET"
fi
