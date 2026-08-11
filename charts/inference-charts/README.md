# AI on EKS Inference Charts

Chart Name: `ai-on-eks-inference-charts`

This Helm chart provides deployment configurations for AI/ML inference workloads on both GPU and AWS Neuron (
Inferentia/Trainium) hardware.

## Overview

The chart supports the following deployment types:

- GPU-based VLLM deployments
- GPU-based Ray-VLLM deployments
- GPU-based Triton-VLLM deployments
- GPU-based AIBrix deployments
- GPU-based LeaderWorkerSet-VLLM deployments
- GPU-based Diffusers deployments
- GPU-based NVIDIA NIM Container deployments
- GPU-based NVIDIA NIM Operator deployments
- Graviton (ARM64 CPU) llama.cpp deployments
- Graviton (ARM64 CPU) VLLM deployments
- Neuron-based VLLM deployments
- Neuron-based Ray-VLLM deployments
- Neuron-based Triton-VLLM deployments (Coming Soon)
- Ray-VLLM deployments with (optional) GCS High Availability
- S3 Model Copy jobs for downloading models from Hugging Face to S3

### VLLM vs Ray-VLLM vs LeaderWorkerSet-VLLM vs NIM

**VLLM Deployments** (`framework: vllm`):

- Direct VLLM deployment using Kubernetes Deployment
- Simpler architecture, faster startup
- Uses `vllm/vllm-openai` image
- Suitable for single-node inference

**Ray-VLLM Deployments** (`framework: ray-vllm`):

- VLLM deployed on Ray Serve for distributed inference
- More complex architecture with head and worker nodes
- Uses `rayproject/ray` image
- Supports autoscaling and distributed workloads
- Includes observability integration with Prometheus and Grafana
- Requires additional parameters: `rayVersion`, `vllmVersion`, `pythonVersion`

**AIBrix Deployments** (`framework: aibrix`):

- VLLM deployment with AIBrix-specific configurations
- Uses `vllm/vllm-openai` image
- Includes additional model labels for AIBrix integration
- Suitable for AIBrix-managed inference workloads

**NVIDIA NIM Container Deployments** (`framework: nim-container`):

- NVIDIA Inference Microservices for optimized model serving
- Pre-built, optimized containers from NVIDIA NGC catalog
- Uses `nvcr.io/nim/*` images
- Includes TensorRT optimizations for specific GPU types
- Requires NGC API key for image pull and runtime
- Supports persistent cache for model artifacts
- Longer startup time (20-30 minutes) for model optimization
- Best for production deployments requiring maximum performance

**NVIDIA NIM Operator Deployments** (`framework: nim-operator`):

- NVIDIA Inference Microservices managed by the NIM Operator
- Two-step deployment: NIMCache (pre-pulls model profiles) then NIMService (inference service)
- Uses Kubernetes CRDs (NIMCache and NIMService) for declarative management
- Optimized startup with pre-cached model profiles for specific GPU types
- Shared persistent storage (EFS) for model artifacts across replicas
- Faster scaling and replica startup compared to nim-container
- Requires NVIDIA NIM Operator installed in cluster
- Best for production deployments with multiple replicas or frequent scaling

**Triton-VLLM Deployments** (`framework: triton-vllm`):

- VLLM deployed as a backend for NVIDIA Triton Inference Server
- Production-ready inference server with advanced features
- Uses `nvcr.io/nvidia/tritonserver` image for GPU or `public.ecr.aws/neuron/tritonserver` for Neuron
- Supports both HTTP and gRPC protocols
- Includes health checks, metrics, and model repository management
- Compatible with both GPU and AWS Neuron accelerators (Soon)

**LeaderWorkerSet-VLLM Deployments** (`framework: lws-vllm`):

- VLLM deployed using Kubernetes LeaderWorkerSet for multi-node inference
- Simplified distributed architecture with leader and worker pods
- Uses `vllm/vllm-openai` image
- Ideal for large models requiring pipeline parallelism across multiple nodes
- Automatic leader-worker coordination and service discovery
- Requires LeaderWorkerSet CRD to be installed in the cluster

**Diffusers Deployments** (`framework: diffusers`):

- Hugging Face Diffusers library for image generation and diffusion models
- Supports various diffusion pipelines including Stable Diffusion, FLUX, Kolors, and more
- Uses custom diffusers container image optimized for GPU inference
- Ideal for text-to-image, image-to-image, and other generative AI workloads
- Supports multiple pipeline types: `stable-diffusion`, `diffusion`, `kolors`, `stablediffusion3`, `omnigen`

**llama.cpp Deployments** (`framework: llama-cpp`):

- CPU-based inference using the `llama.cpp` OpenAI-compatible `llama-server`
- Runs on AWS Graviton (ARM64) instances — set `accelerator: graviton`
- Pulls GGUF-quantized models directly from Hugging Face via `-hf`
- No GPU or Neuron device plugin required — requests CPU/memory only

### Graviton (ARM64 CPU) Accelerator

Set `inference.accelerator: graviton` to target AWS Graviton (ARM64) CPU instances. Unlike `gpu`
and `neuron`, the graviton accelerator requests only CPU and memory (no device-plugin resource),
and the chart automatically adds a `nodeAffinity` rule requiring `kubernetes.io/arch: arm64` so
pods land on Graviton nodes. Configure the request/limit under
`inference.modelServer.deployment.resources.graviton`.

Graviton works with the `llama-cpp` framework and with CPU/ARM64 builds of `vllm`:

```yaml
inference:
  accelerator: graviton
  framework: llama-cpp   # or vllm with an ARM64 CPU image
  modelServer:
    deployment:
      resources:
        graviton:
          requests:
            cpu: 4
            memory: 8Gi
          limits:
            cpu: 8
            memory: 16Gi
```

## Prerequisites

- Kubernetes cluster with GPU or AWS Neuron nodes
- Helm 3.0+
- For GPU deployments: NVIDIA device plugin installed
- For Neuron deployments: AWS Neuron device plugin installed
- For LeaderWorkerSet deployments: LeaderWorkerSet CRD installed
- Hugging Face Hub token (stored as a Kubernetes secret named `hf-token`)
- For Ray: KubeRay Infrastructure
- For AIBrix: AIBrix Infrastructure
- For S3 Model Copy: Service account with S3 write permissions

## Installation

### Create Hugging Face Token Secret

Before installing the chart, create a Kubernetes secret with your Hugging Face token:

```bash
kubectl create secret generic hf-token --from-literal=token=your_huggingface_token
```

### Create NGC Token secret for model access (for NIM Container and Operator deployments)

```bash
kubectl create secret generic ngc-api --from-literal=NGC_API_KEY=your_ngc_api_key
```

### Create NGC Docker registry credentials (for NIM Container and Operator deployments)

```bash
kubectl create secret docker-registry ngc-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=your_ngc_api_key
```

## Configuration

The following table lists the configurable parameters of the inference-charts chart and their default values.

| Parameter                                                                | Description                                                                         | Default                                                                     |
|--------------------------------------------------------------------------|-------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `global.image.pullPolicy`                                                | Global image pull policy                                                            | `IfNotPresent`                                                              |
| `inference.accelerator`                                                  | Accelerator type to use (gpu, neuron, or graviton)                                  | `gpu`                                                                       |
| `inference.framework`                                                    | Framework type to use (vllm, ray-vllm, triton-vllm, aibrix, lws-vllm, llama-cpp, diffusers, nim-container, or nim-operator) | `vllm`                                                                      |
| `inference.serviceName`                                                  | Name of the inference service                                                       | `inference`                                                                 |
| `inference.serviceNamespace`                                             | Namespace for the inference service                                                 | `default`                                                                   |
| `inference.modelServer.image.repository`                                 | Model server image repository                                                       | `vllm/vllm-openai`                                                          |
| `inference.modelServer.image.tag`                                        | Model server image tag                                                              | `latest`                                                                    |
| `inference.modelServer.vllmVersion`                                      | VLLM version (for Ray deployments)                                                  | Not set                                                                     |
| `inference.modelServer.pythonVersion`                                    | Python version (for Ray deployments)                                                | Not set                                                                     |
| `inference.modelServer.env`                                              | Custom environment variables                                                        | `{}`                                                                        |
| `inference.modelServer.deployment.replicas`                              | Number of replicas                                                                  | `1`                                                                         |
| `inference.modelServer.deployment.minReplicas`                           | Minimum number of replicas (for Ray)                                                | `1`                                                                         |
| `inference.modelServer.deployment.maxReplicas`                           | Maximum number of replicas (for Ray)                                                | `2`                                                                         |
| `inference.modelServer.deployment.instanceType`                          | Node selector for instance type                                                     | Not set                                                                     |
| `inference.modelServer.deployment.topologySpreadConstraints.enabled`     | Enable topology spread constraints                                                  | `true`                                                                      |
| `inference.modelServer.deployment.topologySpreadConstraints.constraints` | List of topology spread constraints                                                 | See default configuration                                                   |
| `inference.modelServer.deployment.podAffinity.enabled`                   | Enable pod affinity                                                                 | `true`                                                                      |
| `inference.rayOptions.rayVersion`                                        | Ray version to use                                                                  | `2.47.0`                                                                    |
| `inference.rayOptions.autoscaling.enabled`                               | Enable Ray native autoscaling                                                       | `false`                                                                     |
| `inference.rayOptions.autoscaling.upscalingMode`                         | Ray autoscaler upscaling mode                                                       | `Default`                                                                   |
| `inference.rayOptions.autoscaling.idleTimeoutSeconds`                    | Idle timeout before scaling down                                                    | `60`                                                                        |
| `inference.rayOptions.autoscaling.actorAutoscaling.minActors`            | Minimum number of actors                                                            | `1`                                                                         |
| `inference.rayOptions.autoscaling.actorAutoscaling.maxActors`            | Maximum number of actors                                                            | `1`                                                                         |
| `inference.rayOptions.observability.rayPrometheusHost`                   | Ray Prometheus host URL                                                             | `http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090` |
| `inference.rayOptions.observability.rayGrafanaHost`                      | Ray Grafana host URL                                                                | `http://kube-prometheus-stack-grafana.monitoring.svc.cluster.local`         |
| `inference.rayOptions.observability.rayGrafanaIframeHost`                | Ray Grafana iframe host URL                                                         | `http://localhost:3000`                                                     |
| `vllm.logLevel`                                                          | Log level for VLLM                                                                  | `debug`                                                                     |
| `vllm.port`                                                              | VLLM server port                                                                    | `8004`                                                                      |
| `service.type`                                                           | Service type                                                                        | `ClusterIP`                                                                 |
| `service.port`                                                           | Service port                                                                        | `8000`                                                                      |
| `fluentbit.image.repository`                                             | Fluent Bit image repository                                                         | `fluent/fluent-bit`                                                         |
| `fluentbit.image.tag`                                                    | Fluent Bit image tag                                                                | `3.2.2`                                                                     |
| `s3ModelCopy.namespace`                                                  | Namespace for S3 model copy job                                                     | `default`                                                                   |
| `s3ModelCopy.model`                                                      | Hugging Face model ID to copy to S3                                                 | Not set                                                                     |
| `s3ModelCopy.s3Bucket`                                                   | S3 bucket name for model upload                                                     | Not set                                                                     |
| `serviceAccountName`                                                     | Service account name                                                                | `default`                                                                   |

### Model Parameters

The chart provides configuration for various model parameters:

| Parameter                                   | Description                           | Default                     |
|---------------------------------------------|---------------------------------------|-----------------------------|
| `model`                                     | Model ID from Hugging Face Hub        | `NousResearch/Llama-3.2-1B` |
| `modelParameters.gpuMemoryUtilization`      | GPU memory utilization                | `0.8`                       |
| `modelParameters.maxModelLen`               | Maximum model sequence length         | `8192`                      |
| `modelParameters.maxNumSeqs`                | Maximum number of sequences           | `4`                         |
| `modelParameters.maxNumBatchedTokens`       | Maximum number of batched tokens      | `8192`                      |
| `modelParameters.tokenizerPoolSize`         | Tokenizer pool size                   | `4`                         |
| `modelParameters.maxParallelLoadingWorkers` | Maximum parallel loading workers      | `2`                         |
| `modelParameters.pipelineParallelSize`      | Pipeline parallel size                | `1`                         |
| `modelParameters.tensorParallelSize`        | Tensor parallel size                  | `1`                         |
| `modelParameters.enablePrefixCaching`       | Enable prefix caching                 | `true`                      |
| `modelParameters.pipeline`                  | Pipeline type for diffusers framework | Not set                     |

**Note**: Model parameters are automatically converted to command line arguments in kebab-case format (e.g.,`maxNumSeqs`
becomes `--max-num-seqs`). For diffusers deployments, the `pipeline` parameter specifies the diffusion pipeline type to
use.

### Ray GCS High Availability Parameters

For Ray-VLLM deployments, you can enable GCS (Global Control Store) high availability:

| Parameter                                                           | Description                           | Default       |
|---------------------------------------------------------------------|---------------------------------------|---------------|
| `inference.rayOptions.gcs.highAvailability.enabled`                 | Enable GCS high availability          | `false`       |
| `inference.rayOptions.gcs.highAvailability.redis.address`           | Address for redis                     | `redis.redis` |
| `inference.rayOptions.gcs.highAvailability.redis.port`              | Port for redis                        | `6379`        |
| `inference.rayOptions.gcs.highAvailability.redis.secretName`        | Secret name containing redis password | ``            |
| `inference.rayOptions.gcs.highAvailability.redis.secretPasswordKey` | Key in secret with redis password     | ``            |

## Supported Models

The chart includes pre-configured values files for the following models:

### GPU Models

#### Language Models

- **DeepSeek R1 Distill Llama 8B**: `values-deepseek-r1-distill-llama-8b-ray-vllm-gpu.yaml` (Ray-VLLM)
- **Llama 3.2 1B**: `values-llama-32-1b-vllm.yaml` (VLLM), `values-llama-32-1b-ray-vllm.yaml` (Ray-VLLM),
  `values-llama-32-1b-ray-vllm-autoscaling.yaml` (Ray-VLLM with autoscaling),
  `values-llama-32-1b-aibrix.yaml` (AIBrix), and `values-llama-32-1b-triton-vllm-gpu.yaml` (Triton-VLLM)
- **Llama 4 Scout 17B**: `values-llama-4-scout-17b-vllm.yaml` (VLLM) and `values-llama-4-scout-17b-lws-vllm.yaml` (
  LeaderWorkerSet-VLLM)
- **Mistral Small 24B**: `values-mistral-small-24b-ray-vllm.yaml` (Ray-VLLM)
- **GPT OSS 20B**: `values-gpt-oss-20b-vllm.yaml` (VLLM)
- **Qwen 3 1.7B**: `values-qwen3-1.7b-vllm.yaml` (VLLM)
- **Qwen 3 Coder 480B** `values-qwen-3-coder-480b-a35b-instruct-lws-vllm.yaml`(LeaderWorkerSet-VLLM)

#### Diffusion Models

- **FLUX.1 Schnell**: `values-flux-1-diffusers.yaml` (Diffusers)
- **Kolors**: `values-kolors-diffusers.yaml` (Diffusers)
- **Stable Diffusion 3.5 Large**: `values-stable-diffusion-3.5-large-diffusers.yaml` (Diffusers)
- **Stable Diffusion XL Base 1.0**: `values-stable-diffusion-xl-base-1-diffusers.yaml` (Diffusers)
- **Latent Diffusion**: `values-latent-diffusion-diffusers.yaml` (Diffusers)
- **OmniGen**: `values-omni-gen-diffusers.yaml` (Diffusers)

#### NVIDIA NIM Models deployed with standalone NIM containers

- **Llama 3.1 8B Instruct**: `values-llama-3-8b-instruct-nim-container.yaml` (NIM-container)
- **Stable Diffusion 3.5 Large**: `values-stable-diffusion-3.5-large-diffusers-nim.yaml` (NIM-container)

#### NVIDIA NIM Models deployed with NIM Operators
- **Llama 3.1 8B Instruct**:
  - Cache: `values-llama-31-8b-instruct-nim-operator-cache.yaml` (NIM-operator-cache)
  - Service: `values-llama-31-8b-instruct-nim-operator-service.yaml` (NIM-operator-service)

- **Llama 3.2 1B Instruct**:
  - Cache: `values-llama-32-1b-instruct-nim-operator-cache.yaml` (NIM-operator-cache)
  - Service: `values-llama-32-1b-instruct-nim-operator-service.yaml` (NIM-operator-service)

### Graviton (ARM64 CPU) Models

- **Llama 3.2 1B Instruct**: `values-llama-32-1b-instruct-llama-cpp.yaml` (llama.cpp)
- **Llama 3.2 1B**: `values-llama-32-1b-vllm-graviton.yaml` (VLLM, ARM64 CPU build)

### Neuron Models

- **DeepSeek R1 Distill Llama 8B**: `values-deepseek-r1-distill-llama-8b-vllm-neuron.yaml` (VLLM)
- **Llama 2 13B**: `values-llama-2-13b-ray-vllm-neuron.yaml` (Ray-VLLM)
- **Llama 3 70B**: `values-llama-3-70b-ray-vllm-neuron.yaml` (Ray-VLLM)
- **Llama 3.1 8B**: `values-llama-31-8b-vllm-neuron.yaml` (VLLM) and `values-llama-31-8b-ray-vllm-neuron.yaml` (
  Ray-VLLM)

## Topology Spread Constraints

The chart includes optional topology spread constraints to control how pods are distributed across your cluster. By
default, the chart is configured to prefer scheduling replicas in the same availability zone for reduced network latency
and cost optimization.

### Default Configuration

```yaml
inference:
  modelServer:
    deployment:
      topologySpreadConstraints:
        enabled: true
        constraints:
          # Prefer same AZ as head pod (soft constraint)
          - maxSkew: 1
            topologyKey: topology.kubernetes.io/zone
            whenUnsatisfiable: ScheduleAnyway
            labelSelector:
              matchLabels: { }
          # Require workers to be grouped together (hard constraint)
          - maxSkew: 1
            topologyKey: topology.kubernetes.io/zone
            whenUnsatisfiable: DoNotSchedule
            labelSelector:
              matchLabels: { }
      podAffinity:
        enabled: true
        # Strong preference for same AZ (helps Karpenter understand intent)
        preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              topologyKey: topology.kubernetes.io/zone
              labelSelector:
                matchLabels: { }
```

**Note**: For Ray deployments, the default configuration uses two constraints:

1. **Head Co-location**: Workers prefer to be in the same AZ as the head pod (soft constraint)
2. **Worker Grouping**: All worker pods must be scheduled together in the same AZ (hard constraint)

This ensures optimal performance while maintaining high availability - workers will try to co-locate with the head, but
if that's not possible, they'll at least be grouped together for consistent inter-worker communication.

### Disabling Topology Constraints

To disable topology spread constraints entirely:

```yaml
inference:
  modelServer:
    deployment:
      topologySpreadConstraints:
        enabled: false
      podAffinity:
        enabled: false
```

### Ray-Specific Behavior

For Ray deployments (`framework: ray-vllm`), the topology constraints work differently:

- **Head Group**: Uses the first constraint to establish zone preference
- **Worker Group**: Uses both constraints:
    1. First constraint (soft): Tries to co-locate with head pod
    2. Second constraint (hard): Ensures all workers are grouped together

**Scheduling Logic**:

1. Head pod schedules in any available zone
2. Workers try to schedule in the same zone as head
3. If head's zone is full, workers schedule together in another zone
4. Workers are never split across multiple zones

### Karpenter Compatibility

The chart uses **both topology spread constraints and pod affinity** for Karpenter compatibility:

- **Topology Spread Constraints**: Control pod distribution at the scheduler level
- **Pod Affinity**: Help Karpenter understand co-location intent during node provisioning

**Troubleshooting Steps**:

1. **Soft constraints first**: Always start with `whenUnsatisfiable: ScheduleAnyway`
2. **Check node availability**: Verify nodes exist in your target AZ
3. **Monitor Karpenter logs**: Check why it's provisioning in different AZs

## Ray Native Autoscaling

For Ray-VLLM deployments, you can enable Ray's native autoscaling feature which automatically scales worker nodes based
on workload demand. This is more efficient than Kubernetes HPA as it understands Ray's internal workload distribution.

### Autoscaling Configuration

| Parameter                                                     | Description                                     | Default   |
|---------------------------------------------------------------|-------------------------------------------------|-----------|
| `inference.rayOptions.autoscaling.enabled`                    | Enable Ray native autoscaling                   | `false`   |
| `inference.rayOptions.autoscaling.upscalingMode`              | Ray autoscaler upscaling mode                   | `Default` |
| `inference.rayOptions.autoscaling.idleTimeoutSeconds`         | How long to wait before scaling down idle nodes | `60`      |
| `inference.rayOptions.autoscaling.actorAutoscaling.minActors` | Minimum number of actors                        | `1`       |
| `inference.rayOptions.autoscaling.actorAutoscaling.maxActors` | Maximum number of actors                        | `1`       |

### Example Autoscaling Configuration

```yaml
inference:
  framework: ray-vllm
  rayOptions:
    autoscaling:
      enabled: true
      upscalingMode: "Aggressive"
      idleTimeoutSeconds: 120  # Wait 2 minutes before scaling down
      actorAutoscaling:
        minActors: 1
        maxActors: 5
```

## Diffusers Framework

The Diffusers framework provides support for Hugging Face Diffusers library, enabling deployment of various image
generation and diffusion models on GPU infrastructure.

### Supported Pipeline Types

The chart supports multiple diffusion pipeline types through the `modelParameters.pipeline` configuration:

| Pipeline Type      | Description                                                     | Example Models                        |
|--------------------|-----------------------------------------------------------------|---------------------------------------|
| `flux`             | Standard Stable Diffusion pipeline for text-to-image generation | FLUX.1-schnell                        |
| `diffusion`        | Generic diffusion pipeline for various diffusion models         | Stable Diffusion XL, Latent Diffusion |
| `kolors`           | Kolors-specific pipeline for Kolors diffusion models            | Kwai-Kolors/Kolors-diffusers          |
| `stablediffusion3` | Stable Diffusion 3.x pipeline with enhanced capabilities        | Stable Diffusion 3.5 Large            |
| `omnigen`          | OmniGen pipeline for multi-modal generation                     | Shitao/OmniGen-v1                     |

### Diffusers Configuration

For Diffusers deployments, use the following configuration structure:

```yaml
model: stabilityai/stable-diffusion-xl-base-1.0

modelParameters:
  pipeline: diffusion

inference:
  serviceName: sd-diffusers
  serviceNamespace: default
  accelerator: gpu
  framework: diffusers

  modelServer:
    image:
      repository: diffusers/diffusers-pytorch-cuda
      tag: latest
    deployment:
      instanceType: g6e.2xlarge
```

### Hardware Requirements

Diffusers deployments are optimized for GPU inference and typically require:

- **GPU Memory**: 8GB+ VRAM recommended for most models
- **Instance Types**: g6e.2xlarge or higher recommended
- **Storage**: Sufficient space for model weights (varies by model, typically 2-10GB)

### API Endpoints

Diffusers deployments expose REST API endpoints for image generation:

- `/v1/generations` - Primary image generation endpoint

### Example API Usage

```bash
# Generate an image using the diffusers API
curl -X POST http://localhost:8000/v1/generations \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "A beautiful sunset over mountains",
  }'
```

## S3 Model Copy

The chart includes an S3 Model Copy feature that downloads models from Hugging Face Hub and uploads them to S3 storage. This is useful for:

- Pre-staging models in S3 for faster inference startup (load from S3 instead of HuggingFace at runtime)
- Creating model caches in private S3 buckets within your VPC
- Reducing cold-start time by leveraging high-bandwidth AWS internal networking

The job runs a Python script (`hf_s3_sync.py`) that supports two transfer modes and incremental sync (only transfers new or modified files).

### Transfer Modes

| Mode | How it works | Disk needed | Best for |
|------|-------------|-------------|----------|
| `xet` (default) | Downloads files to local disk via the `hf_xet` Rust backend, then uploads to S3 | Yes (`max_file_size × fileWorkers`) | Maximum download speed from HuggingFace |
| `stream` | Streams byte ranges from HF CDN directly into S3 multipart uploads (no disk) | No | Memory-constrained environments or when disk is unavailable |

### S3 Model Copy Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `s3ModelCopy.model` | HuggingFace model ID (e.g. `deepseek-ai/DeepSeek-V3`) | Not set |
| `s3ModelCopy.s3Bucket` | Target S3 bucket name | Not set |
| `s3ModelCopy.s3Prefix` | S3 key prefix (default: model name) | Model name |
| `s3ModelCopy.namespace` | Namespace for the job | `default` |
| `s3ModelCopy.serviceAccountName` | Service account with S3 write permissions | `default` |
| `s3ModelCopy.storageSize` | Ephemeral storage in GB (also used as NVMe affinity threshold) | `100` |
| `s3ModelCopy.requireLocalNvme` | Require nodes with NVMe > `storageSize` GB | `false` |
| `s3ModelCopy.requireNetworkBandwidth` | Require nodes with network bandwidth > this value (Mbps). Empty to disable | Not set |
| `s3ModelCopy.hfTokenSecret.name` | Kubernetes secret containing HF token | `hf-token` |
| `s3ModelCopy.hfTokenSecret.key` | Key within the secret | `token` |
| `s3ModelCopy.hfTokenSecret.envFrom` | Use `envFrom` instead of `secretKeyRef` (secret must contain `HF_TOKEN` key) | `false` |
| `s3ModelCopy.resources` | Pod resource requests/limits | 4 CPU, 64Gi memory |
| `s3ModelCopy.nodeSelector` | Node selector for scheduling | `{}` |
| `s3ModelCopy.tolerations` | Tolerations for scheduling | `[]` |
| `s3ModelCopy.affinity` | Additional affinity rules (merged with auto-generated rules) | `{}` |
| `s3ModelCopy.env` | Extra environment variables | `[]` |
| `s3ModelCopy.terminationGracePeriodSeconds` | Grace period for shutdown | `120` |

### Transfer Parameters

Parameters under `s3ModelCopy.parameters` control transfer behavior:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `mode` | Transfer mode: `xet` or `stream` | `xet` |
| `transferClient` | S3 upload client: `crt` (AWS CRT, faster) or `default` (classic threading) | `default` |
| `fileWorkers` | Number of files transferred concurrently | `4` |
| `uploadWorkers` | Parallel S3 upload threads per file | `16` |
| `downloadWorkers` | Parallel range-request downloads per file (stream mode only) | `16` |
| `downloadChunkSize` | Download chunk size in MB (stream mode only) | `16` |
| `partSize` | S3 multipart upload part size in MB | `16` |
| `progressInterval` | Seconds between progress log lines | `10` |
| `tempDir` | Local temp directory for downloads (xet mode only) | `/tmp/hf_sync` |
| `force` | Re-upload all files, ignoring sync check | `false` |

### Node Affinity (Auto-Generated)

When `requireLocalNvme` and/or `requireNetworkBandwidth` are set, the chart automatically generates `nodeAffinity` rules. Both requirements are AND'd within the same `nodeSelectorTerm`, so a node must satisfy all configured constraints:

```yaml
# Example: require NVMe > 200 GB AND network > 25 Gbps
s3ModelCopy:
  requireLocalNvme: true
  storageSize: 200
  requireNetworkBandwidth: 25000
```

This generates affinity requiring nodes labeled with both sufficient NVMe storage and network bandwidth (using either `karpenter.k8s.aws/*` or `eks.amazonaws.com/*` labels).

### Prerequisites for S3 Model Copy

1. **Service Account with S3 Permissions**: Use [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) or IRSA to grant the service account `s3:PutObject`, `s3:GetObject`, and `s3:ListBucket` permissions on the target bucket.
2. **Hugging Face Token**: Required for gated/private models. Create a secret with your token.
3. **AWS CRT (optional)**: To use `transferClient: crt`, the `awscrt` Python package must be available. It's installed automatically by the job container.

### Example: Small Model (Llama 3 8B)

```yaml
s3ModelCopy:
  namespace: default
  model: NousResearch/Meta-Llama-3-8B-Instruct
  s3Bucket: my-models-bucket
  serviceAccountName: s3-model-copy-sa
```

```bash
helm install s3-copy-llama3 ai-on-eks/inference-charts -f values-s3-copy-llama3-8b.yaml
```

### Example: Large Model with High-Bandwidth Node (GLM 5.2)

For very large models, use high file-worker concurrency and request nodes with NVMe and high network bandwidth:

```yaml
s3ModelCopy:
  namespace: dynamo-system
  model: zai-org/GLM-5.2
  s3Bucket: my-models-bucket
  serviceAccountName: s3-models-sync-sa
  requireLocalNvme: true
  storageSize: 200
  requireNetworkBandwidth: 25000
  hfTokenSecret:
    name: hf-token-secret
    envFrom: true
  parameters:
    fileWorkers: 35
    uploadWorkers: 16
    partSize: 16
```

### Performance Tuning

**Upload is slow (< 100 MB/s)?**
- Ensure your node has sufficient network bandwidth. Set `requireNetworkBandwidth: 25000` (25 Gbps) or higher.
- Check if traffic goes through a NAT gateway — use a VPC S3 gateway endpoint instead.
- Try `transferClient: crt` for the AWS CRT-based upload client which can be faster.

**Download is slow?**
- In xet mode, set `HF_XET_HIGH_PERFORMANCE: "1"` (enabled by default) for maximum download throughput.
- Increase `fileWorkers` to keep the download pipeline saturated while uploads complete.

**Disk pressure?**
- In xet mode, disk usage ≈ `max_file_size × fileWorkers`. Reduce `fileWorkers` or increase `storageSize`.
- Use `stream` mode to avoid local disk entirely.

**Memory usage?**
- In xet mode with `HF_XET_HIGH_PERFORMANCE=1`, the download buffer limit is 64 GB. Set memory requests accordingly, or override via `s3ModelCopy.env`.
- In stream mode, memory ≈ `fileWorkers × downloadWorkers × downloadChunkSize`.

## Examples

### Deploy GPU Ray-VLLM with DeepSeek R1 Distill Llama 8B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install deepseek-gpu-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-deepseek-r1-distill-llama-8b-ray-vllm-gpu.yaml
```

### Deploy GPU VLLM with Llama 3.2 1B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install gpu-vllm-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-32-1b-vllm.yaml
```

### Deploy GPU LeaderWorkerSet-VLLM with Llama 4 Scout 17B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install llama4-lws-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-4-scout-17b-lws-vllm.yaml
```

### Deploy GPU LeaderWorkerSet-VLLM with Qwen3 Coder 480B A35B Instruct model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install qwen3-coder-lws-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-qwen-3-coder-480b-a35b-instruct-lws-vllm.yaml
```

### Deploy GPU Ray-VLLM with Llama 3.2 1B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install gpu-ray-vllm-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-32-1b-ray-vllm.yaml
```

### Deploy GPU AIBrix with Llama 3.2 1B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install gpu-aibrix-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-32-1b-aibrix.yaml
```

### Deploy Neuron VLLM with DeepSeek R1 Distill Llama 8B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install deepseek-neuron-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-deepseek-r1-distill-llama-8b-vllm-neuron.yaml
```

### Deploy Neuron Ray-VLLM with Llama 2 13B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install llama2-neuron-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-2-13b-ray-vllm-neuron.yaml
```

### Deploy Neuron Ray-VLLM with Llama 3 70B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install llama3-70b-neuron-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-3-70b-ray-vllm-neuron.yaml
```

### Deploy Neuron VLLM with Llama 3.1 8B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install neuron-vllm-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-31-8b-vllm-neuron.yaml
```

### Deploy Neuron Ray-VLLM with Llama 3.1 8B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install neuron-ray-vllm-inference ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-31-8b-ray-vllm-neuron.yaml
```

### Deploy GPU Ray-VLLM with Mistral Small 24B model

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install gpu-ray-vllm-mistral ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-mistral-small-24b-ray-vllm.yaml
```

### Deploy GPU Ray-VLLM with Llama 3.2 1B model with autoscaling

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install gpu-ray-vllm-autoscale ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-32-1b-ray-vllm-autoscaling.yaml
```

### Deploy GPU Triton-VLLM with Llama 3.2 1B

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install gpu-triton-vllm ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-32-1b-triton-vllm-gpu.yaml
```

### Deploy GPT OSS 20B with VLLM

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install gpt-oss-vllm ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-gpt-oss-20b-vllm.yaml
```

### Deploy Qwen3 1.7B with VLLM

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install qwen3-vllm ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-qwen3-1.7b-vllm.yaml
```

### Deploy Graviton (ARM64 CPU) Models

#### Deploy llama.cpp with Llama 3.2 1B Instruct on Graviton

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install llama-cpp-graviton ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-32-1b-instruct-llama-cpp.yaml
```

#### Deploy VLLM with Llama 3.2 1B on Graviton (ARM64 CPU)

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install vllm-graviton ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-32-1b-vllm-graviton.yaml
```

### Deploy Diffusers Models

#### Deploy FLUX.1 Schnell for image generation

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install flux-diffusers ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-flux-1-diffusers.yaml
```

#### Deploy Stable Diffusion XL Base 1.0

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install sdxl-diffusers ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-stable-diffusion-xl-base-1-diffusers.yaml
```

#### Deploy Stable Diffusion 3.5 Large

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install sd3-diffusers ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-stable-diffusion-3.5-large-diffusers.yaml
```

#### Deploy Kolors for artistic image generation

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install kolors-diffusers ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-kolors-diffusers.yaml
```

#### Deploy OmniGen for multi-modal generation

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install omnigen-diffusers ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-omni-gen-diffusers.yaml
```

#### Deploy Latent Diffusion

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install latent-diffusion ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-latent-diffusion-diffusers.yaml
```

### NVIDIA NIM CONTAINER Examples

> **Note:** To set up an inference EKS cluster, follow instructions at: https://awslabs.github.io/ai-on-eks/docs/infra/inference/inference-ready-cluster

#### Prerequisites for NIM Container Deployments

Create the required secrets:

```bash
# NGC API Key - visit https://catalog.ngc.nvidia.com/ to generate NGC keys
kubectl create secret generic ngc-api \
  --from-literal=NGC_API_KEY=<your-ngc-api-key> \
  -n default

# Hugging Face Token
kubectl create secret generic hf-token \
  --from-literal=HF_TOKEN=<your-hf-token> \
  -n default

# NGC Docker Registry Secret (for pulling NIM images)
kubectl create secret docker-registry ngc-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=<your-ngc-api-key> \
  -n default
```

#### Deploy NIM Container Llama 3 8B Instruct (LLM)

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install nim-llama-3-8b ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-3-8b-instruct-nim-container.yaml
```

**Test the LLM:**
```bash
# Port forward
kubectl port-forward svc/nim-llama-3-8b 8000:8000

# Test chat completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta/llama3-8b-instruct",
    "messages": [{"role": "user", "content": "What is AI?"}],
    "max_tokens": 100
  }'
```

#### Deploy NIM Container Stable Diffusion 3.5 Large (Image Generation)

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install nim-sd-large ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-stable-diffusion-3.5-large-diffusers-nim-container.yaml
```

**Test image generation:**
```bash
# Port forward
kubectl port-forward svc/nim-sd-35-large 8000:8000

# Test inference
curl -X POST http://localhost:8000/v1/infer \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A beautiful sunset over mountains",
    "num_inference_steps": 50
  }'
```

**Disable Safety Checker (for image generation)**

To disable the safety checker in NIM SD3.5 Large, you need to set the environment variable (already enabled by default) via:
```yaml
nim:
  env:
    NIM_ALLOW_UNCHECKED_GENERATION: "true"
```

Then in your API request:
```json
{
  "prompt": "your prompt",
  "disable_safety_checker": true
}
```

**Note**:
- **LLM NIMs** (like Llama) take 10-15 minutes to become ready
- **Diffusion NIMs** (like Stable Diffusion) take 20-30 minutes to become ready
- Monitor progress with: `kubectl logs -f deployment/<service-name> -n default`
- To prevent pod eviction by Karpenter during long startup times, add the annotation `karpenter.sh/do-not-evict: "true"` to `podTemplate.annotations` in your values file

**Comparison: NIM vs Diffusers**

| Feature | NIM | Diffusers |
|---------|-----|-----------|
| Setup | Pre-optimized, pull and run | Requires optimization |
| Performance | Maximum (TensorRT) | Good (PyTorch) |
| Startup Time | 20-30 minutes | 5-10 minutes |
| GPU Support | Specific models (L40S, A10G) | Any GPU |
| Cost | NGC license required | Free |
| Customization | Limited | Full control |
| Production Ready | Yes | Requires tuning |

**Use NIM when:**
- You need maximum performance
- You're deploying to production
- You have NGC access
- You're using supported GPUs (L40S, A10G, etc.)

**Use Diffusers when:**
- You need flexibility
- You're experimenting/developing
- You want to customize the pipeline
- You're using unsupported GPUs

**Additional Resources**

- [NVIDIA NIM Documentation](https://docs.nvidia.com/nim/)
- [NGC Catalog](https://catalog.ngc.nvidia.com/)
- [Stable Diffusion NIM Guide](https://docs.nvidia.com/nim/visual-genai/)


### NVIDIA NIM OPERATOR Examples

> **Note:** Set up an inference-ready EKS cluster with the NVIDIA NIM stack using the [cluster setup guide](https://awslabs.github.io/ai-on-eks/docs/infra/inference/inference-ready-cluster) and the [install script](https://github.com/awslabs/ai-on-eks/blob/main/infra/nvidia-nim/install.sh).

**Prerequisites:**

```bash
# NGC API secret for authentication - visit https://catalog.ngc.nvidia.com/ to generate NGC keys
kubectl create secret generic ngc-api \
  --from-literal=NGC_API_KEY=<your-ngc-api-key> \
  -n <namespace>

# NGC pull secret for container registry
kubectl create secret docker-registry ngc-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=<your-ngc-api-key> \
  -n <namespace>
```

#### Deploy NIM Operator Llama 3.1 8B Instruct (LLM)

The NIM Operator deployment uses two components: a **NIMCache** that pre-pulls and caches model profiles for faster startup, and a **NIMService** that serves the cached model.

Step 1: Deploy the NIMCache to download and cache the model profiles:

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install nim-llama-cache ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-31-8b-instruct-nim-operator-cache.yaml
```

Wait for the NIMCache to be ready:

```bash
kubectl wait --for=condition=Ready nimcache/meta-llama-3-1-8b-instruct -n default --timeout=600s

# see the downloaded model profiles
kubectl get nimcache meta-llama-3-1-8b-instruct -n default -o jsonpath='{.status.profiles}' | jq
```

Step 2: Deploy the NIMService to serve the cached model:

```bash
helm install nim-llama-service ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-llama-31-8b-instruct-nim-operator-service.yaml
```

Wait for the NIMService to be ready:

```bash
kubectl wait --for=condition=Ready nimservice/meta-llama-3-1-8b-instruct -n nim-llama-helm --timeout=600s
```

**Troubleshooting:**

```bash
# Cache not ready - check status and PVC
kubectl describe nimcache meta-llama-3-1-8b-instruct
kubectl get pvc

# If no model profiles are downloaded, remove the model filter in the cache values file and redeploy

# Service not starting - check logs and cache reference
kubectl logs -l app.kubernetes.io/component=meta-llama-3-1-8b-instruct
kubectl describe nimservice meta-llama-3-1-8b-instruct
```

**NIM Container vs NIM Operator:**

| Feature | nim-container | nim-operator |
|---------|---------------|--------------|
| Deployment | Single Helm install | Two-step: cache then service |
| Startup Time | Cold start (slower) | Warm start with cached profiles (faster) |
| Storage | Ephemeral | Persistent (EFS/NFS) |
| Profile Optimization | Runtime | Pre-cached for specific GPUs |
| Best For | Quick testing | Production, multiple replicas, faster scaling |


### S3 Model Copy Examples

#### Copy Llama 3 8B model from Hugging Face to S3

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install s3-copy-llama3 ai-on-eks/inference-charts -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-s3-copy-llama3-8b.yaml
```

#### Custom S3 Model Copy

Create a custom values file for copying any model to S3:

```yaml
s3ModelCopy:
  namespace: default
  model: deepseek-ai/DeepSeek-R1
  s3Bucket: my-models-bucket
  serviceAccountName: s3-copy-service-account
  requireLocalNvme: true
  storageSize: 500
  requireNetworkBandwidth: 25000
  parameters:
    fileWorkers: 20
    uploadWorkers: 16
    partSize: 64
```

Then deploy:

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install custom-s3-copy ai-on-eks/inference-charts -f custom-s3-copy-values.yaml
```

### Custom Deployment

You can also create your own values file with custom settings:

```yaml
inference:
  accelerator: gpu  # or neuron
  framework: vllm   # or ray-vllm, triton-vllm, aibrix, lws-vllm, or diffusers
  serviceName: custom-inference
  serviceNamespace: default

  # Ray-specific options (only for ray-vllm framework)
  rayOptions:
    rayVersion: 2.47.0
    autoscaling:
      enabled: false
      upscalingMode: "Default"
      idleTimeoutSeconds: 60
      actorAutoscaling:
        minActors: 1
        maxActors: 1
    observability:
      rayPrometheusHost: http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090
      rayGrafanaHost: http://kube-prometheus-stack-grafana.monitoring.svc.cluster.local
      rayGrafanaIframeHost: http://localhost:3000

  modelServer:
    # For Ray deployments, specify VLLM and Python versions
    vllmVersion: 0.9.1
    pythonVersion: 3.11
    image:
      repository: vllm/vllm-openai  # Use rayproject/ray for Ray deployments
      tag: latest
    deployment:
      replicas: 1
      minReplicas: 1
      maxReplicas: 2
      resources:
        gpu:
          requests:
            nvidia.com/gpu: 1
          limits:
            nvidia.com/gpu: 1
    env: { }  # Custom environment variables

model: "NousResearch/Llama-3.2-1B"

modelParameters:
  gpuMemoryUtilization: 0.8
  maxModelLen: 8192
  maxNumSeqs: 4
  maxNumBatchedTokens: 8192
  tokenizerPoolSize: 4
  maxParallelLoadingWorkers: 2
  pipelineParallelSize: 1
  tensorParallelSize: 1
  enablePrefixCaching: true

# For diffusers deployments, use this configuration instead:
# model: "stabilityai/stable-diffusion-xl-base-1.0"
# modelParameters:
#   pipeline: diffusion
```

Then install the chart with your custom values:

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update

helm install custom-inference ai-on-eks/inference-charts -f custom-values.yaml
```

## API Endpoints

### VLLM and Ray-VLLM Deployments

The deployed service exposes the following OpenAI-compatible API endpoints:

- `/v1/models` - List available models
- `/v1/completions` - Text completion API
- `/v1/chat/completions` - Chat completion API
- `/metrics` - Prometheus metrics endpoint

### Triton-VLLM Deployments

The deployed service exposes the following Triton Inference Server API endpoints:

**HTTP API (Port 8000):**

- `/v2/health/live` - Liveness check
- `/v2/health/ready` - Readiness check
- `/v2/models` - List available models
- `/v2/models/vllm_model/generate` - Model inference endpoint

**gRPC API (Port 8001):**

- Standard Triton gRPC inference protocol

**Metrics (Port 8002):**

- `/metrics` - Prometheus metrics endpoint

**Example Triton API Usage:**

```bash
# Check model status
curl http://localhost:8000/v2/models/llama-3-2-1b

# Run inference
curl -X POST http://localhost:8000/v2/models/vllm_model/generate \
  -H 'Content-Type: application/json' \
  -d '{"text_input":"what is the capital of France?"}'
```

### Diffusers Deployments

The deployed service exposes REST API endpoints for image generation:

- `/v1/generations` - Primary image generation endpoint

**Example Diffusers API Usage:**

```bash
# Generate an image using the diffusers API
curl -X POST http://localhost:8000/v1/generations \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "A beautiful sunset over mountains"
  }'
```

## Ray GCS High Availability

For production Ray-VLLM deployments, you can enable GCS (Global Control Store) high availability using the RayService
CRD's native support to ensure fault tolerance and prevent single points of failure.

### Features

- **Native CRD Support**: Uses RayService CRD's built-in GCS HA configuration
- **Fault Tolerance**: GCS state is persisted to Redis, allowing recovery from head node failures
- **Automatic Recovery**: Ray cluster can recover from GCS failures without losing job state
- **Scalability**: Multiple GCS replicas can handle increased load
- **Flexible Storage**: Support for both internal Redis (deployed with the chart) and external Redis clusters

### Example Configuration

The chart uses the RayService CRD's native GCS HA configuration:

Create a secret for the redis password if needed (replace REDISPASSWORD with your password)

```bash
kubectl create secret generic redis-secret --from-literal=redis-password=REDISPASSWORD
```

```yaml
inference:
  framework: ray-vllm
  rayOptions:
    gcs:
      highAvailability:
        enabled: true
        redis:
          address: redis.redis # redis service in redis namespace
          port: 6379
          secretName: redis-secret
          secretPasswordKey: redis-password
```

## Troubleshooting GCS High Availability

### Common Issues

1. **Redis Connection Issues**
    - Check Redis service is running: `kubectl get pods -l app.kubernetes.io/component=redis-gcs`
    - Verify Redis connectivity: `kubectl exec -it <ray-head-pod> -- redis-cli -h <redis-service> ping`

2. **GCS Recovery**
    - Check RayService status: `kubectl get rayservice <service-name> -o yaml`
    - Check GCS logs: `kubectl logs <ray-head-pod> -c head | grep -i gcs`
    - Verify Redis contains GCS state: `kubectl exec -it <redis-pod> -- redis-cli keys "*"`

3. **Performance Issues**
    - Increase Redis resources if experiencing timeouts
    - Monitor Redis memory usage

### Monitoring

- GCS metrics are available at `/metrics` endpoint
- Redis metrics can be monitored using Redis Exporter
- Ray dashboard shows cluster health and GCS status

## Observability

The chart includes Fluent Bit for log collection and exposes Prometheus metrics for monitoring. The Ray-VLLM deployment
also includes configuration for Grafana dashboards.
