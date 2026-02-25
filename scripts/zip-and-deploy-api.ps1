# Zip the api folder (no requirements install - dependencies are on Lambda layer)
# and upload to AWS Lambda.
#
# Usage:
#   .\scripts\zip-and-deploy-api.ps1 -FunctionName api
#   .\scripts\zip-and-deploy-api.ps1 -FunctionName my-api -Region us-west-2

param(
    [Parameter(Mandatory=$true)]
    [string]$FunctionName,

    [string]$Region = "us-east-1",
    [string]$Handler = "app.handler",
    [string]$Role = "arn:aws:iam::762233730742:role/lambda-execution-role",
    [string]$RuntimeVersion = "python3.12",
    [string]$Description = "API Lambda function"
)

$ErrorActionPreference = "Continue"

# Helpers
function Write-Status {
    param([string]$Message, [string]$Type = "Info")
    switch ($Type) {
        "Error"   { $color = "Red"    }
        "Success" { $color = "Green"  }
        "Warn"    { $color = "Yellow" }
        default   { $color = "Cyan"   }
    }
    Write-Host "[$Type] $Message" -ForegroundColor $color
}

# Verify AWS CLI
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Status "AWS CLI is not installed or not in PATH." "Error"
    exit 1
}

$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$apiDir      = Join-Path $projectRoot "api"

if (-not (Test-Path $apiDir)) {
    Write-Status "api directory not found at: $apiDir" "Error"
    exit 1
}

# Build a temp staging directory and zip path
$stagingDir = Join-Path $env:TEMP "lambda-api-$(Get-Random)"
$zipPath    = Join-Path $env:TEMP "$FunctionName-$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"

try {
    # ── 1. Stage files ───────────────────────────────────────────────────────
    Write-Status "Staging api folder contents..." "Info"
    New-Item -ItemType Directory -Path $stagingDir | Out-Null

    # Folders to exclude from the package
    $excludeDirs = @("examples", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules")

    Get-ChildItem -Path $apiDir | ForEach-Object {
        if ($_.PSIsContainer) {
            if ($excludeDirs -notcontains $_.Name) {
                Copy-Item -Path $_.FullName -Destination (Join-Path $stagingDir $_.Name) -Recurse -Force
            } else {
                Write-Status "Skipping excluded folder: $($_.Name)" "Warn"
            }
        } else {
            # Skip requirements.txt — dependencies live on the Lambda layer
            if ($_.Name -ne "requirements.txt") {
                Copy-Item -Path $_.FullName -Destination $stagingDir -Force
            }
        }
    }

    # Remove any nested __pycache__ dirs that were copied inside sub-folders
    Get-ChildItem -Path $stagingDir -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force

    # ── 2. Zip ───────────────────────────────────────────────────────────────
    Write-Status "Creating zip package..." "Info"
    Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -Force

    $zipSizeMB = [Math]::Round((Get-Item $zipPath).Length / 1MB, 2)
    Write-Status "Package ready: $zipPath ($zipSizeMB MB)" "Success"

    # ── 3. Deploy to Lambda ──────────────────────────────────────────────────
    Write-Status "Checking if Lambda function '$FunctionName' exists..." "Info"
    aws lambda get-function --function-name $FunctionName --region $Region > $null 2>&1
    $getExitCode = $LASTEXITCODE
    Write-Status "get-function exit code: $getExitCode" "Info"

    if ($getExitCode -eq 0) {
        Write-Status "Function exists. Updating code..." "Info"

        aws lambda update-function-code `
            --function-name $FunctionName `
            --zip-file "fileb://$zipPath" `
            --region $Region
        $updateExitCode = $LASTEXITCODE

        if ($updateExitCode -ne 0) {
            Write-Status "Failed to update Lambda function code (exit $updateExitCode)." "Error"
            exit 1
        }

        Write-Status "Lambda function code updated successfully." "Success"

    } else {
        Write-Status "Function not found. Creating '$FunctionName'..." "Info"

        aws lambda create-function `
            --function-name $FunctionName `
            --runtime $RuntimeVersion `
            --role $Role `
            --handler $Handler `
            --description $Description `
            --zip-file "fileb://$zipPath" `
            --region $Region
        $createExitCode = $LASTEXITCODE

        if ($createExitCode -ne 0) {
            Write-Status "Failed to create Lambda function (exit $createExitCode)." "Error"
            exit 1
        }

        Write-Status "Lambda function created successfully." "Success"

        # Optionally create a Function URL
        Write-Status "Adding Function URL (NONE auth)..." "Info"
        $urlJson = aws lambda create-function-url-config `
            --function-name $FunctionName `
            --auth-type NONE `
            --region $Region 2>&1
        $urlExitCode = $LASTEXITCODE

        if ($urlExitCode -eq 0) {
            $functionUrl = ($urlJson | ConvertFrom-Json).FunctionUrl
            Write-Status "Function URL: $functionUrl" "Success"
        } else {
            Write-Status "Could not create Function URL (non-fatal)." "Warn"
        }
    }

    Write-Status "Deployment complete!" "Success"

} finally {
    # Clean up temp files
    if (Test-Path $stagingDir) { Remove-Item -Path $stagingDir -Recurse -Force }
    if (Test-Path $zipPath)    { Remove-Item -Path $zipPath -Force }
    Write-Status "Temporary files cleaned up." "Info"
}
