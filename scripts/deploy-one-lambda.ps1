# .\scripts\deploy-one-lambda.ps1 -FunctionName api

param(
    [Parameter(Mandatory=$true)]
    [string]$FunctionName,
    [string]$Region = "us-east-1"
)

# Colors for output
$ErrorColor = "Red"
$SuccessColor = "Green"
$InfoColor = "Cyan"

function Write-Status {
    param([string]$Message, [string]$Type = "Info")
    $color = @{
        "Error" = $ErrorColor
        "Success" = $SuccessColor
        "Info" = $InfoColor
    }[$Type]
    Write-Host "[$Type] $Message" -ForegroundColor $color
}

$zipPath = Resolve-Path (Join-Path $FunctionName "lambda_package.zip") -ErrorAction SilentlyContinue

# Validate zip exists
if (-not $zipPath -or -not (Test-Path $zipPath)) {
    Write-Status "lambda_package.zip not found in folder: $FunctionName" "Error"
    exit 1
}

# Verify AWS CLI is installed
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Status "AWS CLI is not installed or not in PATH" "Error"
    exit 1
}

Write-Status "Deploying $zipPath to Lambda function: $FunctionName" "Info"

aws lambda update-function-code `
    --function-name $FunctionName `
    --zip-file fileb://$zipPath `
    --region $Region | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Status "Failed to update Lambda function" "Error"
    exit 1
}

Write-Status "Deployment completed successfully!" "Success"
