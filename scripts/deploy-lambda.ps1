# .\scripts\deploy-lambda.ps1 -FunctionName event-listener

param(
    [Parameter(Mandatory=$true)]
    [string]$FunctionName,

    [string]$Region = "us-east-1",
    [string]$RuntimeVersion = "python3.12",
    [string]$Handler = "app.handler",
    [string]$Role = "arn:aws:iam::762233730742:role/lambda-execution-role",
    [string]$Description = "Lambda function"
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

# Validate source path
if (-not (Test-Path $FunctionName)) {
    Write-Status "Source path does not exist: $FunctionName" "Error"
    exit 1
}

# Verify AWS CLI is installed
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Status "AWS CLI is not installed or not in PATH" "Error"
    exit 1
}

Write-Status "Starting Lambda deployment process for: $FunctionName" "Info"
Write-Status "Source: $FunctionName | Region: $Region" "Info"

# Create a temporary directory for packaging
$tempDir = Join-Path $env:TEMP "lambda-package-$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir | Out-Null
$zipPath = Join-Path $env:TEMP "$FunctionName-$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"

try {
    # Step 1: Package the Lambda function
    Write-Status "Packaging Lambda function..." "Info"

    # Copy lib folder if it exists
    $libSource = Join-Path $FunctionName "lib"
    if (Test-Path $libSource) {
        Write-Status "Copying lib folder..." "Info"
        Copy-Item -Path $libSource -Destination $tempDir -Recurse -Force
    }

    # Copy source files to temp directory
    Copy-Item -Path (Join-Path $FunctionName "*") -Destination $tempDir -Recurse -Force

    # Install dependencies if requirements.txt exists
    if (Test-Path (Join-Path $tempDir "requirements.txt")) {
        Write-Status "Installing Python dependencies..." "Info"
        $packagesDir = Join-Path $tempDir "packages"
        New-Item -ItemType Directory -Path $packagesDir -Force | Out-Null

        # Install packages to the packages directory
        pip install -r (Join-Path $tempDir "requirements.txt") -t $packagesDir --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Status "Failed to install dependencies" "Error"
            exit 1
        }

        # Copy packages to root for Lambda
        Copy-Item -Path (Join-Path $packagesDir "*") -Destination $tempDir -Recurse -Force
        Remove-Item -Path $packagesDir -Recurse -Force
    }

    # Create ZIP file
    Compress-Archive -Path (Join-Path $tempDir "*") -DestinationPath $zipPath -Force
    Write-Status "Package created: $zipPath" "Success"

    # Step 2: Check if Lambda function exists
    Write-Status "Checking if Lambda function exists..." "Info"
    $functionExists = aws lambda get-function --function-name $FunctionName --region $Region 2>$null

    $isNewFunction = $LASTEXITCODE -ne 0

    if ($isNewFunction) {
        Write-Status "Lambda function does not exist. Creating new function..." "Info"

        # Validate role is provided for new function
        if (-not $Role) {
            Write-Status "Role must be specified when creating a new Lambda function" "Error"
            exit 1
        }

        # Create the Lambda function
        $createResponse = aws lambda create-function `
            --function-name $FunctionName `
            --runtime $RuntimeVersion `
            --role $Role `
            --handler $Handler `
            --description $Description `
            --zip-file fileb://$zipPath `
            --region $Region 2>&1

        if ($LASTEXITCODE -ne 0) {
            $createText = ($createResponse | Out-String)
            if ($createText -match "ResourceConflictException" -or $createText -match "Function already exist") {
                Write-Status "Lambda function already exists. Updating function code..." "Info"
                aws lambda update-function-code `
                    --function-name $FunctionName `
                    --zip-file fileb://$zipPath `
                    --region $Region | Out-Null

                if ($LASTEXITCODE -ne 0) {
                    Write-Status "Failed to update Lambda function" "Error"
                    exit 1
                }

                Write-Status "Lambda function updated successfully" "Success"
                Write-Status "Deployment completed successfully!" "Success"
                return
            }

            Write-Status "Failed to create Lambda function" "Error"
            exit 1
        }

        Write-Status "Lambda function created successfully" "Success"

        # Step 3: Create Function URL for new Lambda
        Write-Status "Creating Function URL..." "Info"
        $urlResponse = aws lambda create-function-url-config `
            --function-name $FunctionName `
            --auth-type NONE `
            --region $Region

        if ($LASTEXITCODE -eq 0) {
            $functionUrl = ($urlResponse | ConvertFrom-Json).FunctionUrl
            Write-Status "Function URL created: $functionUrl" "Success"
        } else {
            Write-Status "Warning: Failed to create Function URL, but function was created" "Info"
        }

    } else {
        Write-Status "Lambda function exists. Updating function code..." "Info"

        # Update the Lambda function code
        aws lambda update-function-code `
            --function-name $FunctionName `
            --zip-file fileb://$zipPath `
            --region $Region | Out-Null

        if ($LASTEXITCODE -ne 0) {
            Write-Status "Failed to update Lambda function" "Error"
            exit 1
        }

        Write-Status "Lambda function updated successfully" "Success"
    }

    Write-Status "Deployment completed successfully!" "Success"

} finally {
    # Cleanup temporary files
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force
    }
    if (Test-Path $zipPath) {
        Remove-Item -Path $zipPath -Force
        Write-Status "Cleaned up temporary files" "Info"
    }
}
