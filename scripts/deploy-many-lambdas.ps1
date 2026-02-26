# Tip: remove "api" from the folders list to skip rebuilding the API (see example below).
# This speeds up the script because /api takes the longest to package, build and deploy.
# Example:
#   $folders = @("api-bd-change-callback", "sqs-bd-change", "sqs-policy-inquiry")
#
# If you add new dependencies to /api/requirements.txt, review .\package.ps1 for setup steps.
# If you add new dependencies to any other lambda's requirements.txt, run the following
# in that lambda's folder to update the package directory:
#   mkdir package
#   pip install -r requirements.txt -t package
# None of this applies to `distributor-api` which seems to build differently.

$folders = @("api", "api-bd-change-callback", "sqs-bd-change", "sqs-policy-inquiry")

foreach ($folder in $folders) {
    Write-Host "Processing folder: $folder"
    $folderPath = Join-Path -Path (Split-Path -Path $PSCommandPath -Parent) -ChildPath "..\$folder"

    if (Test-Path $folderPath) {
        Push-Location $folderPath
        & .\package.ps1
        cd ..
        & .\scripts\deploy-one-lambda.ps1 -FunctionName $folder
        Pop-Location
    } else {
        Write-Warning "Folder not found: $folderPath"
    }
}

