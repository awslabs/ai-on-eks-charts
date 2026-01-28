# AI on EKS Charts

A comprehensive collection of Helm charts for deploying AI workloads on Amazon Elastic Kubernetes Service (EKS). This
repository provides configurations for various AI models including large language models (LLMs), diffusion models, and
other machine learning inference services.

## Features

- **Multiple Inference Engines**: Support for vLLM, Ray, Triton, and Diffusers
- **Model Variety**: Pre-configured charts for popular models including:
    - Llama 2/3/3.1/3.2 series
    - DeepSeek R1 Distill
    - Mistral models
    - Qwen models
    - Stable Diffusion variants
    - Flux and other diffusion models
- **Scalability**: Auto-scaling configurations and distributed inference support
- **Hardware Optimization**: GPU and AWS Neuron support
- **Batteries Included**: Includes monitoring, logging, and best practices

## Quick Start

0. Create a [Hugging Face Token](https://huggingface.co/docs/hub/en/security-tokens) and store it in a kubernetes
   secret (replace `your_huggingface_token` with the actual token)

```bash
kubectl create secret generic hf-token --from-literal=token=your_huggingface_token
```

1. Add the Helm repository:

```bash
helm repo add ai-on-eks https://awslabs.github.io/ai-on-eks-charts/
helm repo update
```

2. Install a model (example with Qwen 3 1.7B):

```bash
helm install qwen3-1-7b ai-on-eks/inference-charts \
  -f https://raw.githubusercontent.com/awslabs/ai-on-eks-charts/refs/heads/main/charts/inference-charts/values-qwen3-1.7b-vllm.yaml
```

## Available Models

### Language Models

- **Llama Series**: 2-13B, 3-70B, 3-8b-instruct, 3.1-8B, 3.2-1B, 4-Scout-17B
- **DeepSeek**: R1 Distill Llama 8B
- **Mistral**: Small 24B
- **Qwen**: 3 Coder 480B, 3-1.7B
- **GPT-OSS**: 20B

### Diffusion Models

- **Stable Diffusion**: XL Base 1.0, 3.5 Large
- **Flux**: Flux-1
- **Kolors**: Kolors diffusion model
- **OmniGen**: Multi-modal generation
- **Latent Diffusion**: Various configurations

## Inference Engines

- **vLLM**: High-throughput LLM serving
- **Ray + vLLM**: Distributed inference with Ray
- **Triton + vLLM**: NVIDIA Triton integration
- **Diffusers**: Hugging Face diffusion models
- **LWS (LeaderWorkerSet)**: Kubernetes-native distributed serving
- **NIM (NVIDIA Inference Microservices)** - NVIDIA GPU optimized inference containers (needs NGC Key)

## Hardware Support

- **GPU**: NVIDIA GPU acceleration
- **AWS Neuron**: AWS Inferentia/Trainium chips
- **CPU**: CPU-only deployments
- **Auto-scaling**: Horizontal pod autoscaling support

## Configuration

Each model has its own values file in `charts/inference-charts/`. Key configuration options include:

- **Resource allocation**: CPU, memory, and GPU requirements
- **Model parameters**: Model path, quantization, tensor parallelism
- **Scaling**: Replica count and autoscaling settings
- **Storage**: Model storage and caching configuration

Example customization:

```bash
helm install my-model ai-on-eks/inference-charts \
  -f charts/inference-charts/values-llama-32-1b-vllm.yaml \
  --set replicaCount=3 \
  --set resources.limits.nvidia.com/gpu=2
```

## Development

To contribute or modify charts:

1. Clone the repository
2. Make changes to chart templates or values
3. Test with `helm template` or `helm install --dry-run`
4. Submit a pull request

## Monitoring and Observability

The charts include optional components for:

- Prometheus metrics collection
- Fluent Bit log aggregation
- Health checks and readiness probes
- Performance monitoring

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## Support

For issues and questions:

- Check existing [GitHub Issues](https://github.com/awslabs/ai-on-eks-charts/issues)
- Review the [Contributing Guide](CONTRIBUTING.md)
- Consult individual chart README files

## License

This project is licensed under the Apache-2.0 License.
