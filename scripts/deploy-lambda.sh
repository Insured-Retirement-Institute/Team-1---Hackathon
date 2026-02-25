#!/bin/bash
# Deploy Lambda function
# Usage: ./scripts/deploy-lambda.sh <function-name>
# Example: ./scripts/deploy-lambda.sh api-insurance-carrier

set -e

FUNCTION_NAME=$1
REGION=${2:-us-east-1}
RUNTIME="python3.12"
HANDLER="app.lambda_handler"
ROLE="arn:aws:iam::762233730742:role/lambda-execution-role"

if [ -z "$FUNCTION_NAME" ]; then
    echo "Usage: $0 <function-name> [region]"
    echo "Example: $0 api-insurance-carrier us-east-1"
    exit 1
fi

if [ ! -d "$FUNCTION_NAME" ]; then
    echo "[Error] Directory not found: $FUNCTION_NAME"
    exit 1
fi

echo "[Info] Deploying Lambda function: $FUNCTION_NAME"
echo "[Info] Region: $REGION"

# Create temp directory
TEMP_DIR=$(mktemp -d)
ZIP_FILE="/tmp/${FUNCTION_NAME}-$(date +%Y%m%d-%H%M%S).zip"

cleanup() {
    rm -rf "$TEMP_DIR"
    rm -f "$ZIP_FILE"
    echo "[Info] Cleaned up temporary files"
}
trap cleanup EXIT

# Copy source files
echo "[Info] Packaging Lambda function..."
cp -r "$FUNCTION_NAME"/* "$TEMP_DIR/"

# Install dependencies if requirements.txt exists
if [ -f "$TEMP_DIR/requirements.txt" ]; then
    echo "[Info] Installing Python dependencies..."
    pip install -r "$TEMP_DIR/requirements.txt" -t "$TEMP_DIR/" --quiet
fi

# Create ZIP file
cd "$TEMP_DIR"
zip -r "$ZIP_FILE" . -q
cd - > /dev/null
echo "[Success] Package created: $ZIP_FILE"

# Check if function exists
echo "[Info] Checking if Lambda function exists..."
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" 2>/dev/null; then
    echo "[Info] Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://$ZIP_FILE" \
        --region "$REGION" > /dev/null
    echo "[Success] Lambda function updated!"
else
    echo "[Info] Creating new Lambda function..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE" \
        --handler "$HANDLER" \
        --zip-file "fileb://$ZIP_FILE" \
        --region "$REGION" > /dev/null

    echo "[Success] Lambda function created!"

    # Create Function URL
    echo "[Info] Creating Function URL..."
    URL_RESPONSE=$(aws lambda create-function-url-config \
        --function-name "$FUNCTION_NAME" \
        --auth-type NONE \
        --region "$REGION" 2>/dev/null || true)

    if [ -n "$URL_RESPONSE" ]; then
        FUNCTION_URL=$(echo "$URL_RESPONSE" | jq -r '.FunctionUrl')
        echo "[Success] Function URL: $FUNCTION_URL"
    fi
fi

echo "[Success] Deployment completed!"
