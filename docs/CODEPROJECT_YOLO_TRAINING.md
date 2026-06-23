# CodeProject.AI YOLO And Training Module

Status: confirmed by primary sources.

## Inference Module Routes

CodeProject.AI documents standard object detection as:

```text
POST http://localhost:32168/v1/vision/detection
```

The request uses multipart form data:

- `image`: image file
- `min_confidence`: confidence threshold, default `0.4`

Custom object detection uses:

```text
POST http://localhost:32168/v1/vision/custom/<model-name>
POST http://localhost:32168/v1/vision/custom/list
```

## Explicit Training Module

The module shown in the CodeProject.AI UI is:

```text
Module ID: TrainingObjectDetectionYOLOv5
Name: Training for YoloV5 6.2
Version: 1.7.0
Category: Training
Stack: Python, PyTorch, YOLO
Based on: Ultralytics YOLOv5
Repo: https://github.com/codeproject/CodeProject.AI-TrainingObjectDetectionYOLOv5
```

Documented training routes:

```text
POST /v1/train/create_dataset
POST /v1/train/train_model
POST /v1/train/resume_training
POST /v1/train/model_info
POST /v1/train/dataset_info
```

The gateway only probes safe info endpoints by default. Dataset creation and training are long-running actions and must be exposed later as explicit user-approved commands.

## Gateway Commands

```powershell
fnpqnn codeproject yolo-status --url http://localhost:32168 --dry-run
fnpqnn codeproject yolo-status --url http://localhost:32168 --image .\sample.jpg
fnpqnn codeproject yolo-training-status --url http://localhost:32168 --dry-run
fnpqnn codeproject yolo-training-status --url http://localhost:32168 --model-name my-model
fnpqnn codeproject yolo-training-status --url http://localhost:32168 --dataset-name my-dataset
```

## Cerebrum / Simulator Relation

Local repository verification found Cerebrum runtime surfaces in the simulator:

- `core/cerebrum_runtime_bridge.py`
- `GET /cerebrum/runtime/status`
- `POST /cerebrum/runtime/ingest`
- `POST /cerebrum/runtime/pairs`
- `POST /cerebrum/runtime/run`

CodeProject.AI remains the YOLO/instruct backend. Cerebrum/FNP-QNN remains the simulator runtime. The native agent or gateway handoff transforms YOLO outputs into simulator gate or runtime events through CLI/HTTP artifacts.

## Sources

- https://codeproject.github.io/codeproject.ai/api/api_reference.html
- https://github.com/codeproject/CodeProject.AI-ObjectDetectionYOLOv5-3.1
- https://github.com/codeproject/CodeProject.AI-TrainingObjectDetectionYOLOv5
- https://github.com/codeproject/CodeProject.AI-TrainingObjectDetectionYOLOv5/blob/main/modulesettings.json
