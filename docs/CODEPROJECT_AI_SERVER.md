# CodeProject.AI Server Integration

CodeProject.AI Server is integrated as a local, remote, tunnel, or mesh HTTP backend.

The gateway does not vendor the server or its modules. It checks the configured URL, probes known routes, and prints support actions when modules or mesh capabilities are not available.

## Default URL

```text
http://localhost:32168
```

## Commands

```powershell
fnpqnn codeproject status --url http://localhost:32168
fnpqnn codeproject mesh-status --url http://localhost:32168
fnpqnn codeproject tunnel --url http://localhost:32168
fnpqnn codeproject yolo-status --url http://localhost:32168
fnpqnn codeproject yolo-training-status --url http://localhost:32168
fnpqnn gateway run --hook codeproject-ai --codeproject-url http://localhost:32168
fnpqnn gateway run --hook codeproject-ai-mesh --codeproject-url http://localhost:32168 --known-server ai-node-01
```

## YOLO

The gateway uses the documented CodeProject.AI object detection and training paths:

- `POST /v1/vision/detection`
- `POST /v1/vision/custom/<model-name>`
- `POST /v1/vision/custom/list`
- `POST /v1/train/create_dataset`
- `POST /v1/train/train_model`
- `POST /v1/train/resume_training`
- `POST /v1/train/model_info`
- `POST /v1/train/dataset_info`

The explicit training module is `TrainingObjectDetectionYOLOv5` / `Training for YoloV5 6.2`.

## Mesh Guidance

The gateway reports the settings to review:

- `MeshOptions`
- `EnableBroadcasting`
- `MonitorNetwork`
- `AcceptForwardedRequests`
- `AllowRequestForwarding`
- `KnownMeshHostnames`

For Docker mesh use, publish both TCP and UDP:

```text
-p 32168:32168
-p 32168:32168/udp
```

## Tunnel Boundary

VS Code tunnels, dev tunnels, remote IDE forwarded ports, and network aliases are treated as transport to a user-approved URL. The gateway does not control VS Code and does not read IDE credential stores.
