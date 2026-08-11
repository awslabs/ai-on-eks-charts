{{/*
Expand the name of the chart.
*/}}
{{- define "inference-charts.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "inference-charts.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "inference-charts.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "inference-charts.labels" -}}
helm.sh/chart: {{ include "inference-charts.chart" . }}
{{ include "inference-charts.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "inference-charts.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inference-charts.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component labels for VLLM
*/}}
{{- define "inference-charts.vllmComponentLabels" -}}
app.kubernetes.io/component: {{.Values.inference.serviceName}}
{{- end }}

{{/*
Component labels for Ray-VLLM
*/}}
{{- define "inference-charts.rayVllmComponentLabels" -}}
app.kubernetes.io/component: {{.Values.inference.serviceName}}
{{- end }}

{{- define "inference-charts.modelParameters" -}}
{{- $modelParameters := .Values.modelParameters -}}
{{- $args := list -}}
{{ $tpsize := 1 -}}
{{- range $key, $value := $modelParameters -}}
  {{- if kindIs "bool" $value -}}
    {{- if $value -}}
      {{- $args = append $args (printf "--%s" ($key | kebabcase)) -}}
    {{- end -}}
  {{- else -}}
    {{- $args = append $args (printf "--%s %v" ($key | kebabcase) $value) -}}
  {{- end -}}
{{- end -}}
{{- if eq .Values.inference.framework "aibrix" }}
    {{- $args = append $args (printf "--served-model-name %s" .Values.inference.serviceName) }}
{{- else if .Values.modelPath }}
    {{- $args = append $args (printf "--served-model-name %s" .Values.model) }}
{{- end }}
{{- if .Values.vllm.loadFormat }}
    {{- $args = append $args (printf "--load-format %s" .Values.vllm.loadFormat ) }}
{{- end}}
{{- if and (not (.Values.modelParameters | default dict).tensorParallelSize) (ne .Values.inference.accelerator "graviton")}}
    {{- if eq .Values.inference.accelerator "neuron"}}
        {{- $tpsize = mul (index .Values.inference.modelServer.deployment.resources.neuron.requests "aws.amazon.com/neuron") 2}}
    {{- else }}
        {{- $tpsize = (index .Values.inference.modelServer.deployment.resources.gpu.requests "nvidia.com/gpu")}}
    {{- end }}
    {{- $args = append $args (printf "--tensor-parallel-size %s" ($tpsize | toString) ) }}
{{- end}}
{{- printf "%s" (join " " $args) | trimSuffix " " -}}
{{- end -}}

{{/*
Select the modelServer resources block for the configured accelerator.
gpu → resources.gpu, neuron → resources.neuron, graviton → resources.graviton.
Falls back to the gpu block for unknown accelerators.
*/}}
{{- define "inference-charts.acceleratorResources" -}}
{{- $resources := .Values.inference.modelServer.deployment.resources -}}
{{- if eq .Values.inference.accelerator "neuron" -}}
{{- toYaml $resources.neuron -}}
{{- else if eq .Values.inference.accelerator "graviton" -}}
{{- toYaml $resources.graviton -}}
{{- else -}}
{{- toYaml $resources.gpu -}}
{{- end -}}
{{- end -}}

{{/*
Compute VLLM_CPU_KVCACHE_SPACE (in GiB) for graviton + vllm deployments.
If .Values.vllm.cpuKvCacheSpace is set, it is used verbatim. Otherwise the value is
derived as floor(graviton memory request in GiB * .Values.vllm.cpuKvCacheUtilization).

The request (not the limit) is used deliberately: on the CPU backend vLLM sizes the KV
cache against the node's free RAM, not the pod cgroup. The request is what Kubernetes
guarantees and is always <= node allocatable, so a fraction of it cannot exceed the
node's memory. cpuKvCacheUtilization is the CPU analogue of --gpu-memory-utilization:
the remaining fraction of the request covers model weights + framework/runtime overhead.
Falls back to the limit if no request is set. Only Gi/G suffixed values support
auto-derivation; anything else (or a non-positive result) yields an empty string so the
env var is omitted and vLLM falls back to its own default.
*/}}
{{- define "inference-charts.vllmCpuKvCacheSpace" -}}
{{- if .Values.vllm.cpuKvCacheSpace -}}
{{- .Values.vllm.cpuKvCacheSpace -}}
{{- else -}}
{{- $graviton := .Values.inference.modelServer.deployment.resources.graviton -}}
{{- $mem := (($graviton.requests).memory) | default (($graviton.limits).memory) | default "" | toString -}}
{{- $fraction := .Values.vllm.cpuKvCacheUtilization | default 0.0 | float64 -}}
{{- if and (or (hasSuffix "Gi" $mem) (hasSuffix "G" $mem)) (gt $fraction 0.0) -}}
{{- $gib := $mem | trimSuffix "Gi" | trimSuffix "G" | int -}}
{{- $space := floor (mulf $gib $fraction) | int -}}
{{- if gt $space 0 -}}
{{- $space -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Node affinity requiring ARM64 nodes. Used by graviton deployments so they land on
Graviton (arm64) instances regardless of instanceType being set.
*/}}
{{- define "inference-charts.gravitonNodeAffinity" -}}
nodeAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    nodeSelectorTerms:
      - matchExpressions:
          - key: kubernetes.io/arch
            operator: In
            values:
              - arm64
{{- end -}}

{{- define "inference-charts.s3ModelCopyName" -}}
{{- printf "s3modelcopy-%s" .Values.s3ModelCopy.model | lower | replace "/" "-" | replace "_" "-" | replace "." "-" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Extra labels from values.yaml applied to all resources
*/}}
{{- define "inference-charts.extraLabels" -}}
{{- with .Values.extraLabels }}
{{- toYaml . }}
{{- end }}
{{- end }}

{{/*
Render CLI arguments for hf_s3_sync.py from s3ModelCopy.parameters map.
Boolean true  → --flag (present)
Boolean false → omitted
Other values  → --flag value
Keys are converted from camelCase to kebab-case.
*/}}
{{- define "inference-charts.s3ModelCopyParameters" -}}
{{- $args := list -}}
{{- range $key, $value := .Values.s3ModelCopy.parameters -}}
  {{- if kindIs "bool" $value -}}
    {{- if $value -}}
      {{- $args = append $args (printf "--%s" ($key | kebabcase)) -}}
    {{- end -}}
  {{- else -}}
    {{- $args = append $args (printf "--%s %v" ($key | kebabcase) $value) -}}
  {{- end -}}
{{- end -}}
{{- if .Values.s3ModelCopy.s3Prefix -}}
  {{- $args = append $args (printf "--prefix %s" .Values.s3ModelCopy.s3Prefix) -}}
{{- else -}}
  {{- $args = append $args (printf "--prefix %s" .Values.s3ModelCopy.model) -}}
{{- end -}}
{{- printf "%s" (join " " $args) | trimSuffix " " -}}
{{- end -}}

{{/*
Build the affinity block for the s3-copy Job.
Auto-generates nodeAffinity nodeSelectorTerms from requireLocalNvme and requireNetworkBandwidth.
When both are true, their expressions are AND'd within the same nodeSelectorTerm
(multiple matchExpressions in one term = AND). Two terms are generated — one for
karpenter.k8s.aws labels and one for eks.amazonaws.com labels — OR'd together so
either label provider satisfies the requirement.
*/}}
{{- define "inference-charts.s3ModelCopyAffinity" -}}
{{- $affinity := deepCopy (.Values.s3ModelCopy.affinity | default dict) -}}
{{- $autoTerms := list -}}
{{/* Build matchExpressions lists per label provider (karpenter vs eks) */}}
{{- $karpenterExprs := list -}}
{{- $eksExprs := list -}}
{{- if .Values.s3ModelCopy.requireLocalNvme -}}
  {{- $storageGi := toString (int .Values.s3ModelCopy.storageSize) -}}
  {{- $karpenterExprs = append $karpenterExprs (dict "key" "karpenter.k8s.aws/instance-local-nvme" "operator" "Gt" "values" (list $storageGi)) -}}
  {{- $eksExprs = append $eksExprs (dict "key" "eks.amazonaws.com/instance-local-nvme" "operator" "Gt" "values" (list $storageGi)) -}}
{{- end -}}
{{- if .Values.s3ModelCopy.requireNetworkBandwidth -}}
  {{- $bwMbps := toString (int .Values.s3ModelCopy.requireNetworkBandwidth) -}}
  {{- $karpenterExprs = append $karpenterExprs (dict "key" "karpenter.k8s.aws/instance-network-bandwidth" "operator" "Gt" "values" (list $bwMbps)) -}}
  {{- $eksExprs = append $eksExprs (dict "key" "eks.amazonaws.com/instance-network-bandwidth" "operator" "Gt" "values" (list $bwMbps)) -}}
{{- end -}}
{{/* Each term contains all expressions AND'd; the two terms are OR'd */}}
{{- if $karpenterExprs -}}
  {{- $autoTerms = append $autoTerms (dict "matchExpressions" $karpenterExprs) -}}
{{- end -}}
{{- if $eksExprs -}}
  {{- $autoTerms = append $autoTerms (dict "matchExpressions" $eksExprs) -}}
{{- end -}}
{{- if $autoTerms -}}
  {{- $existingNodeAffinity := index $affinity "nodeAffinity" | default dict -}}
  {{- $existingRequired := index $existingNodeAffinity "requiredDuringSchedulingIgnoredDuringExecution" | default dict -}}
  {{- $existingTerms := index $existingRequired "nodeSelectorTerms" | default list -}}
  {{- $mergedTerms := concat $existingTerms $autoTerms -}}
  {{- $_ := set $affinity "nodeAffinity" (dict "requiredDuringSchedulingIgnoredDuringExecution" (dict "nodeSelectorTerms" $mergedTerms)) -}}
{{- end -}}
{{- if $affinity }}
affinity:
  {{- toYaml $affinity | nindent 2 }}
{{- end -}}
{{- end -}}

{{/*
Render resources for the s3-copy Job container.
Merges s3ModelCopy.resources with ephemeral-storage derived from storageSize.
*/}}
{{- define "inference-charts.s3ModelCopyResources" -}}
{{- $resources := deepCopy (.Values.s3ModelCopy.resources | default dict) -}}
{{- if .Values.s3ModelCopy.storageSize -}}
  {{- $storage := printf "%dGi" (int .Values.s3ModelCopy.storageSize) -}}
  {{- $requests := index $resources "requests" | default dict -}}
  {{- $_ := set $requests "ephemeral-storage" $storage -}}
  {{- $_ := set $resources "requests" $requests -}}
  {{- $limits := index $resources "limits" | default dict -}}
  {{- $_ := set $limits "ephemeral-storage" $storage -}}
  {{- $_ := set $resources "limits" $limits -}}
{{- end -}}
{{- toYaml $resources -}}
{{- end -}}
