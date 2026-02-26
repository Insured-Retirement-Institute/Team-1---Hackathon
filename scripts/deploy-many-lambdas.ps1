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

