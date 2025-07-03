# AI on EKS Inference Charts

This Helm chart provides deployment configurations for AI/ML inference workloads on both GPU and AWS Neuron (Inferentia) hardware.

## Overview

The chart supports the following deployment types:
- GPU-based VLLM deployments
- GPU-based Ray-VLLM deployments
- Neuron-based VLLM deployments
- Neuron-based Ray-VLLM deployments

## Prerequisites

- Kubernetes cluster with GPU or AWS Neuron nodes
- Helm 3.0+
- For GPU deployments: NVIDIA device plugin installed
- For Neuron deployments: AWS Neuron device plugin installed
- Hugging Face Hub token (stored as a Kubernetes secret named `hf-token`)

## Installation

### Create Hugging Face Token Secret

Before installing the chart, create a Kubernetes secret with your Hugging Face token:

```bash
kubectl create secret generic hf-token --from-literal=token=your_huggingface_token
```

## Configuration

The following table lists the configurable parameters of the inference-charts chart and their default values.

| Parameter                                                         | Description | Default |
|-------------------------------------------------------------------|-------------|---------|
| `global.image.pullPolicy`                                         | Global image pull policy | `IfNotPresent` |
| `inference.accelerator`                                           | Accelerator type to use (gpu or neuron) | `gpu` |
| `inference.framework`                                             | Framework type to use (vllm or rayVllm) | `vllm` |
| `inference.serviceName`                                           | Name of the inference service | `inference` |
| `inference.serviceNamespace`                                      | Namespace for the inference service | `default` |
| `inference.modelServer.image.repository`                          | Model server image repository | `vllm/vllm-openai` |
| `inference.modelServer.image.tag`                                 | Model server image tag | `latest` |
| `inference.modelServer.deployment.replicas`                       | Number of replicas | `1` |
| `inference.modelServer.deployment.minReplicas`                    | Minimum number of replicas (for Ray) | `1` |
| `inference.modelServer.deployment.maxReplicas`                    | Maximum number of replicas (for Ray) | `2` |
| `inference.modelServer.deployment.autoscaling.enabled`            | Enable Ray native autoscaling | `false` |
| `inference.modelServer.deployment.autoscaling.upscalingSpeed`     | Ray autoscaler upscaling speed | `1.0` |
| `inference.modelServer.deployment.autoscaling.downscalingSpeed`   | Ray autoscaler downscaling speed | `1.0` |
| `inference.modelServer.deployment.autoscaling.idleTimeoutSeconds` | Idle timeout before scaling down | `60` |
| `vllm.logLevel`                                                   | Log level for VLLM | `debug` |
| `vllm.port`                                                       | VLLM server port | `8004` |
| `service.type`                                                    | Service type | `ClusterIP` |
| `service.port`                                                    | Service port | `8000` |
| `fluentbit.image.repository`                                      | Fluent Bit image repository | `fluent/fluent-bit` |
| `fluentbit.image.tag`                                             | Fluent Bit image tag | `3.2.2` |

### Model Parameters

The chart provides configuration for various model parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `modelParameters.modelId` | Model ID from Hugging Face Hub | `NousResearch/Llama-3.2-1B` |
| `modelParameters.gpuMemoryUtilization` | GPU memory utilization | `0.8` |
| `modelParameters.maxModelLen` | Maximum model sequence length | `8192` |
| `modelParameters.maxNumSeqs` | Maximum number of sequences | `4` |
| `modelParameters.maxNumBatchedTokens` | Maximum number of batched tokens | `8192` |
| `modelParameters.tokenizerPoolSize` | Tokenizer pool size | `4` |
| `modelParameters.maxParallelLoadingWorkers` | Maximum parallel loading workers | `2` |
| `modelParameters.pipelineParallelSize` | Pipeline parallel size | `1` |
| `modelParameters.tensorParallelSize` | Tensor parallel size | `1` |
| `modelParameters.enablePrefixCaching` | Enable prefix caching | `true` |
| `modelParameters.numGpus` | Number of GPUs to use | `1` |

## Supported Models

The chart includes pre-configured values files for the following models:

### GPU Models

- **DeepSeek R1 Distill Llama 8B**: `values-deepseek-r1-distill-llama-8b-ray-vllm-gpu.yaml` (Ray-VLLM)
- **Llama 3.2 1B**: `values-llama-32-1b-vllm.yaml` (VLLM) and `values-llama-32-1b-ray-vllm.yaml` (Ray-VLLM)
- **Llama 4 Scout 17B**: `values-llama-4-scout-17b-vllm.yaml` (VLLM)
- **Mistral Small 24B**: `values-mistral-small-24b-ray-vllm.yaml` (Ray-VLLM)

### Neuron Models

- **DeepSeek R1 Distill Llama 8B**: `values-deepseek-r1-distill-llama-8b-vllm-neuron.yaml` (VLLM)
- **Llama 2 13B**: `values-llama-2-13b-ray-vllm-neuron.yaml` (Ray-VLLM)
- **Llama 3 70B**: `values-llama-3-70b-ray-vllm-neuron.yaml` (Ray-VLLM)
- **Llama 3.1 8B**: `values-llama-31-8b-vllm-neuron.yaml` (VLLM) and `values-llama-31-8b-ray-vllm-neuron.yaml` (Ray-VLLM)

## Ray Native Autoscaling

For Ray-VLLM deployments, you can enable Ray's native autoscaling feature which automatically scales worker nodes based on workload demand. This is more efficient than Kubernetes HPA as it understands Ray's internal workload distribution.

### Autoscaling Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `inference.autoscaling.enabled` | Enable Ray native autoscaling | `false` |
| `inference.autoscaling.minReplicas` | Minimum number of worker replicas | `1` |
| `inference.autoscaling.maxReplicas` | Maximum number of worker replicas | `10` |
| `inference.autoscaling.upscalingSpeed` | How aggressively to scale up (1.0 = normal, >1.0 = more aggressive) | `1.0` |
| `inference.autoscaling.downscalingSpeed` | How aggressively to scale down (1.0 = normal, >1.0 = more aggressive) | `1.0` |
| `inference.autoscaling.idleTimeoutSeconds` | How long to wait before scaling down idle nodes | `60` |

### Example Autoscaling Configuration

```yaml
inference:
  framework: rayVllm
  autoscaling:
    enabled: true
    minReplicas: 1
    maxReplicas: 5
    upscalingSpeed: 1.5  # Scale up more aggressively
    downscalingSpeed: 0.5  # Scale down more conservatively
    idleTimeoutSeconds: 120  # Wait 2 minutes before scaling down
```

### Deploy with Autoscaling

```bash
helm install ray-autoscale-inference ./inference-charts --values values-ray-vllm-autoscaling.yaml
```

## Examples

### Deploy GPU Ray-VLLM with DeepSeek R1 Distill Llama 8B model

```bash
helm install deepseek-gpu-inference ./inference-charts --values values-deepseek-r1-distill-llama-8b-ray-vllm-gpu.yaml
```

### Deploy GPU VLLM with Llama 3.2 1B model

```bash
helm install gpu-vllm-inference ./inference-charts --values values-llama-32-1b-vllm.yaml
```

### Deploy GPU Ray-VLLM with Llama 3.2 1B model

```bash
helm install gpu-ray-vllm-inference ./inference-charts --values values-llama-32-1b-ray-vllm.yaml
```

### Deploy Neuron VLLM with DeepSeek R1 Distill Llama 8B model

```bash
helm install deepseek-neuron-inference ./inference-charts --values values-deepseek-r1-distill-llama-8b-vllm-neuron.yaml
```

### Deploy Neuron Ray-VLLM with Llama 2 13B model

```bash
helm install llama2-neuron-inference ./inference-charts --values values-llama-2-13b-ray-vllm-neuron.yaml
```

### Deploy Neuron Ray-VLLM with Llama 3 70B model

```bash
helm install llama3-70b-neuron-inference ./inference-charts --values values-llama-3-70b-ray-vllm-neuron.yaml
```

### Deploy Neuron VLLM with Llama 3.1 8B model

```bash
helm install neuron-vllm-inference ./inference-charts --values values-llama-31-8b-vllm-neuron.yaml
```

### Deploy Neuron Ray-VLLM with Llama 3.1 8B model

```bash
helm install neuron-ray-vllm-inference ./inference-charts --values values-llama-31-8b-ray-vllm-neuron.yaml
```

### Deploy GPU Ray-VLLM with Mistral Small 24B model

```bash
helm install gpu-ray-vllm-mistral ./inference-charts --values values-mistral-small-24b-ray-vllm.yaml
```

### Custom Deployment

You can also create your own values file with custom settings:

```yaml
inference:
  accelerator: gpu  # or neuron
  framework: vllm   # or rayVllm
  serviceName: custom-inference
  serviceNamespace: default
  modelServer:
    image:
      repository: vllm/vllm-openai
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

modelParameters:
  modelId: "NousResearch/Llama-3.2-1B"
  gpuMemoryUtilization: "0.8"
  maxModelLen: "8192"
  maxNumSeqs: "4"
  maxNumBatchedTokens: "8192"
  tokenizerPoolSize: "4"
  maxParallelLoadingWorkers: "2"
  pipelineParallelSize: "1"
  tensorParallelSize: "1"
  enablePrefixCaching: true
  numGpus: 1
```

Then install the chart with your custom values:

```bash
helm install custom-inference ./inference-charts --values custom-values.yaml
```

## API Endpoints

The deployed service exposes the following OpenAI-compatible API endpoints:

- `/v1/models` - List available models
- `/v1/completions` - Text completion API
- `/v1/chat/completions` - Chat completion API
- `/metrics` - Prometheus metrics endpoint

## Observability

The chart includes Fluent Bit for log collection and exposes Prometheus metrics for monitoring. The Ray-VLLM deployment also includes configuration for Grafana dashboards.
