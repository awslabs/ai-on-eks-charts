{{/*
Expand the name of the chart.
*/}}
{{- define "benchmark-charts.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "benchmark-charts.fullname" -}}
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
{{- define "benchmark-charts.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "benchmark-charts.labels" -}}
helm.sh/chart: {{ include "benchmark-charts.chart" . }}
{{ include "benchmark-charts.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "benchmark-charts.selectorLabels" -}}
app.kubernetes.io/name: {{ include "benchmark-charts.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Use an owned release-specific account unless an existing name is supplied. */}}
{{- define "benchmark-charts.serviceAccountName" -}}
{{- if .Values.benchmark.serviceAccount.create -}}
{{- default (printf "%s-sa" (include "benchmark-charts.fullname" .) | trunc 63 | trimSuffix "-") .Values.benchmark.serviceAccount.name -}}
{{- else -}}
{{- required "benchmark.serviceAccount.name is required when create=false" .Values.benchmark.serviceAccount.name -}}
{{- end -}}
{{- end -}}
