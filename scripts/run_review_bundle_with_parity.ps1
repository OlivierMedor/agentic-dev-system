param (
    [Parameter(Mandatory=$true)]
    [string]$Story,
    [string]$BaseRef = "origin/main",
    [switch]$StrictClean,
    [switch]$AllowGeneratedArtifacts
)

$ErrorActionPreference = "Stop"

$tempFile = Join-Path $env:TEMP "host_identity_temp_$([guid]::NewGuid()).json"
$resolvedTempFile = (Get-Item -ErrorAction SilentlyContinue $tempFile)

$exitCode = 0

try {
    # 1. Generate the host identity JSON at temporary path
    Write-Output "Generating host identity..."
    $genScript = Join-Path $PSScriptRoot "generate_host_identity.ps1"
    & $genScript -ProjectRoot "$PSScriptRoot\.." -BaseRef $BaseRef -OutputPath $tempFile

    # 2. Build the Docker compose command arguments
    # Note: .host_identity_temp.json is written at OS temp directory, which we explicitly mount
    $dockerFile = "/tmp/host_identity_temp.json"
    
    $dockerArgs = @("run", "--rm", "-v", "${tempFile}:${dockerFile}:ro", "dev", "agentic", "review-bundle", "--story", $Story, "--base-ref", $BaseRef, "--host-identity-file", $dockerFile)
    if ($StrictClean) {
        $dockerArgs += "--strict-clean"
    }
    if ($AllowGeneratedArtifacts) {
        $dockerArgs += "--allow-generated-artifacts"
    }

    # 3. Execute Docker compose run
    Write-Output "Running review-bundle inside Docker with host parity..."
    & docker compose $dockerArgs

    $exitCode = $LASTEXITCODE
} catch {
    Write-Error "Error in host/container parity review workflow: $_"
    $exitCode = 1
} finally {
    # 4. Clean up temporary host identity file
    if (Test-Path $tempFile) {
        Write-Output "Cleaning up temporary host identity file..."
        Remove-Item -Force $tempFile
    }
}

exit $exitCode
