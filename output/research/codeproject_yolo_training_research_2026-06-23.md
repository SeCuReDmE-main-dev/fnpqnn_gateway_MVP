# Objective

Verify the real CodeProject.AI YOLO and YOLO training paths before wiring the gateway.

# Environment / Stack Context

Local gateway repo: `fnpqnn_gateway_MVP`.

Local simulator repo contains Cerebrum runtime surfaces including `core/cerebrum_runtime_bridge.py` and API endpoints under `/cerebrum/runtime/*`.

# Research Questions

- Which CodeProject.AI route performs YOLO/object detection?
- Is there an explicit CodeProject.AI training module for YOLOv5 6.2?
- Which paths should the gateway expose without inventing routes?

# Findings

Confirmed by primary sources: CodeProject.AI documents object detection at `POST /v1/vision/detection` with image multipart field `image` and `min_confidence`.

Confirmed by primary sources: CodeProject.AI documents custom object detection at `POST /v1/vision/custom/<model-name>` and list models at `POST /v1/vision/custom/list`.

Confirmed by primary sources: The explicit training module is `TrainingObjectDetectionYOLOv5`, published as `Training for YoloV5 6.2`, version `1.7.0`, based on Ultralytics YOLOv5.

Confirmed by primary sources: Training module route maps include `train/create_dataset`, `train/train_model`, `train/resume_training`, `train/model_info`, and `train/dataset_info`, which the server exposes under `/v1/...`.

Confirmed by local repo truth: Cerebrum runtime exists in the simulator through `core/cerebrum_runtime_bridge.py` and API endpoints `/cerebrum/runtime/status`, `/cerebrum/runtime/ingest`, `/cerebrum/runtime/pairs`, and `/cerebrum/runtime/run`.

# Recommended Path

Wire gateway commands:

- `fnpqnn codeproject yolo-status`
- `fnpqnn codeproject yolo-training-status`

Keep model training as explicit future action. In v1, only dry-run and safe info probes should be available by default.

# Alternatives Considered

Generic `/v1/vision/detect` and `/v1/vision/custom/yolo` probes were rejected because they were not confirmed by the primary sources used here.

# Risks / Unknowns

Some installed CodeProject.AI versions or third-party modules may add extra routes. The gateway should not assume them unless detected or configured by the user.

# Sources

- https://codeproject.github.io/codeproject.ai/api/api_reference.html
- https://github.com/codeproject/CodeProject.AI-ObjectDetectionYOLOv5-3.1
- https://github.com/codeproject/CodeProject.AI-TrainingObjectDetectionYOLOv5
- https://github.com/codeproject/CodeProject.AI-TrainingObjectDetectionYOLOv5/blob/main/modulesettings.json
