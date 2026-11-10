# Qwen3.5 / Qwen3.6 dense models on AWS Trainium2 via the vLLM-Neuron plugin.
#
# Base: AWS Neuron vLLM Inference DLC that ships the EXACT pinned stack the
# sample repo validates against:
#   vllm-neuron 0.24.0.1.1.0 + libtorch-neuronx-lite 2.11.0.1.0.1284
#   vllm 0.24.0, Neuron SDK 2.32.0, trn2/trn3.
# Image table:
#   https://github.com/aws-neuron/deep-learning-containers#vllm-inference-neuronx
FROM public.ecr.aws/neuron/pytorch-inference-vllm-neuronx:0.24.0.1.1.0-neuronx-py313-sdk2.32.0-ubuntu24.04

# Pin the sample repo to a reviewed commit for reproducible builds; override at
# build time with --build-arg QWEN_REF=<sha>.
ARG QWEN_REPO=https://github.com/aws-samples/sample-qwen3.5-qwen3.6-dense-trainium.git
ARG QWEN_REF=main

USER root
WORKDIR /opt/qwen

# 1. Fetch the model package (src/) and the REQUIRED overrides.
RUN set -eux; \
    git clone --depth 1 --branch "${QWEN_REF}" "${QWEN_REPO}" /tmp/qwen; \
    cp -r /tmp/qwen/src       /opt/qwen/src; \
    cp -r /tmp/qwen/overrides /opt/qwen/overrides; \
    rm -rf /tmp/qwen

# 2. Apply the two REQUIRED core-file overrides into the installed packages
#    (DeltaNet state-slot lifecycle + .data.copy_() graph-aliasing fix) and
#    clear the empty NEFF cache. apply.sh verifies the pinned package versions
#    first and aborts on mismatch. The DLC sets VLLM_CACHE_ROOT to a non-home
#    path, so opt in to the cache-clear guard (the cache is empty at build).
RUN QWEN36_ALLOW_CUSTOM_CACHE_DELETE=1 /opt/qwen/overrides/apply.sh

# 3. vLLM wrapper ahead of the stock CLI on PATH. It converts the chart's
#    `vllm serve <model>` into the sample's validated launcher.
COPY vllm-launch /opt/qwen/bin/vllm
RUN chmod +x /opt/qwen/bin/vllm
ENV PATH="/opt/qwen/bin:${PATH}" \
    PYTHONPATH="/opt/qwen/src" \
    VLLM_CACHE_ROOT="/var/tmp/neuron-compile-cache"

RUN mkdir -p /models /var/tmp/neuron-compile-cache

# The chart overrides command/args; keep a sane default for manual runs.
ENTRYPOINT []
CMD ["vllm", "serve", "Qwen/Qwen3.5-4B"]
