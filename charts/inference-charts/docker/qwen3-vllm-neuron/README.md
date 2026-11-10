# Qwen3.5 / Qwen3.6 dense — vLLM-Neuron plugin container

Builds the serving image used by
`charts/inference-charts/values-qwen3-5-4b-vllm-neuron.yaml`.

## What it is

AWS Neuron **vLLM Inference DLC `0.24.0.1.1.0` (Neuron SDK 2.32.0)** — which
ships the exact pinned stack the sample repo validates against (`vllm-neuron
0.24.0.1.1.0`, `libtorch-neuronx-lite 2.11.0.1.0.1284`, `vllm 0.24.0`) — plus:

1. the sample's `qwen3_6` model package (`src/`), auto-registered in every
   Python process by its bundled `sitecustomize.py`;
2. the two **REQUIRED** core-file overrides applied via `overrides/apply.sh`
   (DeltaNet state-slot lifecycle + `.data.copy_()` graph-aliasing fix) —
   without them batched decode silently crosses sequences / degrades to
   gibberish;
3. a `vllm` wrapper (`vllm-launch`) that turns the chart's standard
   `vllm serve <model> <flags>` into the sample's validated launcher
   (`src/_serve_main.py`), so the coordinated Neuron config (single-shot
   prefill buckets, bounded `vision_neuron_config`, on-device greedy sampling,
   chunked-prefill + prefix-caching disabled, `--additional-config`) is always
   built. Weights are pulled to the pod at startup.

## Build and push

Build on **linux/amd64** (the DLC is x86-only) — e.g. CodeBuild, an EC2
builder, or `docker buildx --platform linux/amd64`.

```bash
ACCOUNT=ACCOUNT_ID
REGION=us-west-2
REPO=qwen3-vllm-neuron
TAG=0.24.0.1.1.0
IMAGE="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO}:${TAG}"

aws ecr create-repository --repository-name "${REPO}" --region "${REGION}" || true

# Base DLC lives in ECR Public; log in there too if the daemon is not already.
aws ecr-public get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin public.ecr.aws
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

docker buildx build --platform linux/amd64 \
  --build-arg QWEN_REF=main \
  -t "${IMAGE}" --push .
```

Pin `--build-arg QWEN_REF=<commit-sha>` for reproducible releases.

## Hardware requirement

vLLM-Neuron `0.24` runs on **Trn2 / Trn3 only** (not Trn1 / Inf2). The sample
is validated on `trn2.3xlarge` (LNC=2) at TP=4. The target cluster must have a
Karpenter NodePool able to provision Trn2/Trn3.
