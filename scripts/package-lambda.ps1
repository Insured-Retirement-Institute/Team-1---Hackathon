# Package Lambda function with dependencies in the same layer
# .\scripts\package-lambda.ps1

param(
    [string]$ApiFolder = "./api",
    [string]$OutputPath = "./build"
)

# Create output directory
if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputPath | Out-Null

# Copy API code
Copy-Item -Path $ApiFolder -Destination $OutputPath -Recurse

# Copy packages to the same layer
$sitePackagesPath = "./packages"

if (Test-Path $sitePackagesPath) {
    Copy-Item -Path "$sitePackagesPath/*" -Destination "$OutputPath/api" -Recurse
}

# Create zip file for Lambda deployment
$zipName = "api-package-$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"
Compress-Archive -Path $OutputPath -DestinationPath $zipName -Force

Write-Host "Package created: $zipName"
Write-Host "Ready for Lambda deployment"