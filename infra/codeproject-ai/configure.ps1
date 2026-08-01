[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:32173",
    [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = "Stop"
$settings = Get-Content (Join-Path $PSScriptRoot "serversettings.json") -Raw | ConvertFrom-Json
$mesh = $settings.MeshOptions

function Set-MeshBoolean {
    param([string]$Name, [bool]$Value)
    $body = @{ name = $Name; value = $Value.ToString().ToLowerInvariant() }
    Invoke-WebRequest -Uri "$BaseUrl/v1/server/mesh/setting" -Method Post -Form $body -TimeoutSec $TimeoutSeconds | Out-Null
}

$current = Invoke-RestMethod -Uri "$BaseUrl/v1/server/mesh/status" -TimeoutSec $TimeoutSeconds
if ([bool]$current.isBroadcasting -ne [bool]$mesh.EnableStatusBroadcast) { Set-MeshBoolean -Name "EnableBroadcast" -Value $mesh.EnableStatusBroadcast }
if ([bool]$current.isMonitoring -ne [bool]$mesh.EnableStatusMonitoring) { Set-MeshBoolean -Name "EnableMonitoring" -Value $mesh.EnableStatusMonitoring }
if ([bool]$current.allowRequestForwarding -ne [bool]$mesh.AllowRequestForwarding) { Set-MeshBoolean -Name "AllowForwarding" -Value $mesh.AllowRequestForwarding }
if ([bool]$current.acceptForwardedRequests -ne [bool]$mesh.AcceptForwardedRequests) { Set-MeshBoolean -Name "AcceptForwarded" -Value $mesh.AcceptForwardedRequests }
$initialSummary = Invoke-RestMethod -Uri "$BaseUrl/v1/server/mesh/summary" -TimeoutSec $TimeoutSeconds
if ($initialSummary.localServer.isActive -ne $true) {
    Set-MeshBoolean -Name "Enable" -Value $true
    Start-Sleep -Seconds 1
}

foreach ($hostname in $mesh.KnownMeshHostnames) {
    if ($current.knownHostnames -contains $hostname) { continue }
    try {
        Invoke-WebRequest -Uri "$BaseUrl/v1/server/mesh/register/$hostname" -Method Post -TimeoutSec $TimeoutSeconds | Out-Null
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 400) {
            throw
        }
    }
}

$summary = Invoke-RestMethod -Uri "$BaseUrl/v1/server/mesh/summary" -TimeoutSec $TimeoutSeconds
[ordered]@{
    status = "success"
    base_url = $BaseUrl
    broadcasting = $summary.localServer.status.isBroadcasting
    monitoring = $summary.localServer.status.isMonitoring
    allow_forwarding = $summary.localServer.status.allowRequestForwarding
    accept_forwarded = $summary.localServer.status.acceptForwardedRequests
    known_hosts = @($summary.localServer.status.knownHostnames).Count
} | ConvertTo-Json -Compress
