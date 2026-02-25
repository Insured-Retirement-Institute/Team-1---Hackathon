# .\scripts\package-lambda.ps1 -FunctionName api

param(
    [string]$FunctionName = "api-broker-dealer",
    [string]$OutputDir = ".\build",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

# Resolve paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$functionDir = Join-Path $projectRoot $FunctionName
$buildDir = Join-Path $projectRoot $OutputDir
$zipFile = Join-Path $buildDir "$FunctionName.zip"

# Cleanup if requested
if ($Clean -and (Test-Path $buildDir)) {
    Write-Host "Cleaning build directory..." -ForegroundColor Yellow
    Remove-Item $buildDir -Recurse -Force
}

# Create build directory
if (-not (Test-Path $buildDir)) {
    Write-Host "Creating build directory..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $buildDir | Out-Null
}

# Create lambda package directory
$lambdaPackage = Join-Path $buildDir "lambda-package"
if (Test-Path $lambdaPackage) {
    Remove-Item $lambdaPackage -Recurse -Force
}
New-Item -ItemType Directory -Path $lambdaPackage | Out-Null

Write-Host " "
Write-Host "Packaging $FunctionName Lambda function..." -ForegroundColor Green

# Copy app.py
Write-Host "Copying application files..."
Copy-Item -Path "$functionDir\app.py" -Destination $lambdaPackage -Force

# Copy lambdas folder
Write-Host "Copying lib folder..."
$lambdasSource = Join-Path $projectRoot "lib"
$lambdasDest = Join-Path $lambdaPackage "lib"
if (Test-Path $lambdasSource) {
    Copy-Item -Path $lambdasSource -Destination $lambdasDest -Recurse -Force
}

# Install dependencies from function directory
Write-Host "Installing dependencies..."
$requirementsFile = Join-Path $functionDir "requirements.txt"
if (Test-Path $requirementsFile) {
    & pip install --target $lambdaPackage --requirement $requirementsFile -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error installing dependencies" -ForegroundColor Red
        exit 1
    }
}

# Create zip file
Write-Host "Creating zip file..."
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
}

# Use built-in compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$compressionLevel = [System.IO.Compression.CompressionLevel]::Optimal
[System.IO.Compression.ZipFile]::CreateFromDirectory($lambdaPackage, $zipFile, $compressionLevel, $false)

# Get zip file size
$zipSize = (Get-Item $zipFile).Length / 1MB
Write-Host " "
Write-Host "Lambda package created successfully" -ForegroundColor Green
Write-Host "  Location: $zipFile" -ForegroundColor Cyan
Write-Host ("  Size: " + [Math]::Round($zipSize, 2) + " MB") -ForegroundColor Cyan

# Cleanup package directory
Remove-Item $lambdaPackage -Recurse -Force

Write-Host " "
Write-Host "Ready to deploy with:" -ForegroundColor Green
Write-Host ("  .\scripts\deploy-lambda.ps1 -FunctionName " + $FunctionName) -ForegroundColor Cyan