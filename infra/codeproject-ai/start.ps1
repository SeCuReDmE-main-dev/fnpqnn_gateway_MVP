[CmdletBinding()]
param([int]$ReadyTimeoutSeconds = 90)

$ErrorActionPreference = "Stop"
$network = "securedme-education-cpai-mesh"
$compose = Join-Path $PSScriptRoot "compose.yaml"
$existing = docker network ls --filter "name=^$network$" --format "{{.Name}}"
if (-not $existing) {
    docker network create --driver bridge --attachable $network | Out-Null
}

docker compose -f $compose up -d
$deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
do {
    try {
        $ping = Invoke-RestMethod "http://127.0.0.1:32173/v1/server/status/ping" -TimeoutSec 3
        if ($ping.success) { break }
    } catch {}
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

if (-not $ping.success) {
    throw "NODE_UNAVAILABLE: CodeProject.AI did not become ready before the timeout."
}

& (Join-Path $PSScriptRoot "configure.ps1")
