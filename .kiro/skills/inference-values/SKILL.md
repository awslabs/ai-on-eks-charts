---
name: inference-values
description: Author a values-<model>.yaml file for the inference-charts Helm chart. Use when adding a new model (vLLM, Ray-vLLM, LeaderWorkerSet, Triton, AIBrix, NIM, or Neuron) to this repository, including modelParameters conventions, framework selection, GPU sizing, and validation steps.
---

# Add a Model Values File to inference-charts

Every supported model in this repo is one values file: `charts/inference-charts/values-<model>-<framework>.yaml`. Deploying it is `helm install <release> ai-on-eks/inference-charts -f <values-file>`. This skill covers authoring a correct file and validating it before opening a PR.

## File Naming

`values-<model-name>-<framework>.yaml`, all kebab-case:

- Model name: lowercase, dots dropped or kept per existing precedent (`llama-32-1b`, `qwen3-1.7b`, `glm-5-2`), parameter count included when the family has multiple sizes (`llama-3-70b`).
- Framework suffix: `vllm`, `ray-vllm`, `lws-vllm`, `triton-vllm`, `aibrix`, `diffusers`, `nim-container`, `nim-operator-cache`, `nim-operator-service`. Neuron variants append `-neuron` (`values-llama-31-8b-vllm-neuron.yaml`).
- S3 staging companions are prefixed `values-s3-copy-` (`values-s3-copy-glm-5-2.yaml`).

## Choose a Framework

| Situation                                                     | framework                                | Template used                                       |
| ------------------------------------------------------------- | ---------------------------------------- | --------------------------------------------------- |
| Model fits one node, standard serving                         | `vllm`                                   | `vllm-deployment.yaml`                              |
| Needs Ray autoscaling / GCS HA                                | `ray-vllm`                               | `ray-vllm-deployment.yaml`                          |
| Model spans MULTIPLE nodes (weights > single-node GPU memory) | `lws-vllm`                               | `lws-deployment.yaml`                               |
| Triton front-end required                                     | `triton-vllm`                            | `triton-vllm-deployment.yaml`                       |
| AIBrix runtime                                                | `aibrix`                                 | `vllm-deployment.yaml` (adds `--served-model-name`) |
| Image generation                                              | `diffusers`                              | `diffusers-deployment.yaml`                         |
| NVIDIA NIM                                                    | `nim-container` / NIM operator values    | `nim-*.yaml`                                        |
| Trainium/Inferentia                                           | any vllm variant + `accelerator: neuron` | same, neuron resources                              |

## The modelParameters Contract (most common mistake)

`modelParameters` keys are **camelCase** and are converted by `templates/_helpers.tpl` (`inference-charts.modelParameters`) into `vllm serve` CLI flags:

- Every key is kebab-cased into a flag: `maxModelLen: 131072` → `--max-model-len 131072`.
- Booleans render as bare flags: `enablePrefixCaching: true` → `--enable-prefix-caching`; `false` omits the flag entirely.
- Do NOT write raw CLI strings or `args:` overrides — always go through `modelParameters`.
- If `tensorParallelSize` is omitted, the chart defaults it to the pod's GPU request (or 2× neuron cores). Set it explicitly for clarity on multi-GPU nodes.
- Multi-node (`lws-vllm`): set both `pipelineParallelSize` (number of nodes) and `tensorParallelSize` (GPUs per node). See `values-qwen-3-coder-480b-a35b-instruct-lws-vllm.yaml` (PP=4, TP=8).

Common parameters for tool-calling / agentic models:

```yaml
modelParameters:
  maxModelLen: 131072 # model context window
  tensorParallelSize: 8 # GPUs per node
  gpuMemoryUtilization: 0.92
  enablePrefixCaching: true # big win for multi-turn tool loops
  enableAutoToolChoice: true
  toolCallParser: <parser> # see parser table below
  reasoningParser: <parser> # only for reasoning models
```

### Tool-call parser quick reference (verify against the pinned vLLM version)

| Model family       | `toolCallParser` |
| ------------------ | ---------------- |
| GLM-4.5/4.6/4.7    | `glm45`          |
| GLM-5.x            | `glm47`          |
| Kimi K2/K3         | `kimi_k2`        |
| DeepSeek V3.x / R1 | `deepseek_v31`   |
| Qwen 2.5/3         | `hermes`         |
| Llama 3.1/3.3/4    | `llama3_json`    |
| Mistral family     | `mistral`        |

Parser names change between vLLM releases — confirm with `vllm serve --help` in the pinned image tag before submitting.

## Sizing and Instance Selection

1. Estimate weights: `params × bytes-per-param × 1.2 overhead` (FP8 = 1 byte, BF16 = 2 bytes).
2. Fit against per-node GPU memory: g6e.48xlarge = 8× L40S (384 GB), p5.48xlarge = 8× H100 (640 GB), p5en.48xlarge = 8× H200 (1128 GB).
3. Prefer the CHEAPEST instance the model fits on with KV-cache headroom (~20%+ beyond weights). Don't put a 13B model on a P-family node.
4. If it doesn't fit one node → `lws-vllm` with `pipelineParallelSize` = node count.
5. Always pin `instanceType` under `deployment:` — it becomes a `nodeSelector` and helps Karpenter provision correctly.

## Image

Use the AWS vLLM Deep Learning Container with an explicit tag (never `latest`):

```yaml
image:
  repository: public.ecr.aws/deep-learning-containers/vllm
  tag: 0.10.2-gpu-py312-ec2 # match tag used by sibling values files
```

Check the model's minimum vLLM version (new architectures land in specific releases) against the DLC tag.

## Large Models: S3 Model Copy

For weights over ~100 GB, add a companion `values-s3-copy-<model>.yaml` using the `s3ModelCopy` block (see `values-s3-copy-glm-5-2.yaml`) so pods pull from S3 instead of re-downloading from HF Hub on every scale-out. Set `requireLocalNvme: true` and `storageSize` ≥ `fileWorkers × largest-shard-GB`.

## Validation Checklist (run all before PR)

```bash
cd charts/inference-charts

# 1. Lint
helm lint . -f values-<model>-<framework>.yaml

# 2. Render and inspect the exact vllm serve command
helm template test . -f values-<model>-<framework>.yaml | grep -A2 "vllm serve"

# 3. Confirm nodeSelector pin rendered
helm template test . -f values-<model>-<framework>.yaml | grep -A1 nodeSelector
```

Verify in the rendered output:

- [ ] Every `modelParameters` key became the intended `--flag` (kebab-case, booleans bare)
- [ ] `--tensor-parallel-size` matches the GPU request
- [ ] Parser names valid for the pinned image's vLLM version
- [ ] `nodeSelector: node.kubernetes.io/instance-type: <instance>` present
- [ ] GPU requests == limits
- [ ] `serviceName` kebab-case and matches the file name

Then update `charts/inference-charts/README.md` — add the model under **Supported Models** in the correct section (Language / Diffusion / NIM / Neuron), alphabetized with the existing entries.

## PR Conventions

- One model (or one model + its s3-copy companion) per PR.
- Title: `feat: add <Model> <framework> values` (see merged PRs #12, #8 for precedent).
- Include the rendered `vllm serve` line in the PR description as proof of validation.
- Real deployment evidence (pod logs, benchmark) strengthens the PR but a clean `helm template` render is the minimum bar.
