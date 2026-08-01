# FNP-QNN Gateway — embedded CodeProject.AI node

This repository starts a complete, isolated CodeProject.AI Server 2.9.7 instance as `cpai-gateway` on host port `32173`. Compose uses the official image pinned by digest; no CodeProject.AI binaries are committed. Configuration and module data live in repository-specific Docker volumes.

## Operations

```powershell
.\infra\codeproject-ai\start.ps1
python infra/codeproject-ai/client.py health
python infra/codeproject-ai/client.py mesh
python infra/codeproject-ai/client.py detect --image <approved-test-image> --local-only
.\infra\codeproject-ai\stop.ps1
```

The shared contract is `securedme.codeproject.mesh.v1`. Normal detection calls may be routed by the mesh. `--local-only` is reserved for proving this repository's own YOLO runtime and sends the official `X-CPAI-Forwarded: true` header to prevent another hop.

## Safety and observability

- Images are bounded to 20 MiB and are never returned or logged by the connector.
- Responses contain normalized detections and operational metadata only.
- Datadog is optional, asynchronous, redacted, and fail-open; it is not part of this inference path.
- Secrets are neither required nor read from `.env`.
- CodeProject.AI 2.9.7 native mesh forwarding is validated for non-file requests. Multipart image routing from differing host ports is handled by explicit Gateway node selection; local inference remains available on every node.

