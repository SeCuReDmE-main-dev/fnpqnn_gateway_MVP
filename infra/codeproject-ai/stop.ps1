$ErrorActionPreference = "Stop"
docker compose -f (Join-Path $PSScriptRoot "compose.yaml") down
