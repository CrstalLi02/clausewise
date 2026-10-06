{{- define "clausewise.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "clausewise.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
{{- end -}}

{{- define "clausewise.env" -}}
- name: STORAGE_MODE
  value: "mongo"
- name: VECTOR_BACKEND
  value: "mongo"
- name: EMBEDDING_PROVIDER
  value: {{ .Values.model.embeddingProvider | quote }}
- name: EMBEDDING_MODEL
  value: {{ .Values.model.embeddingModel | quote }}
- name: DEEPSEEK_MODEL
  value: {{ .Values.model.deepseekModel | quote }}
- name: DEEPSEEK_BASE_URL
  value: {{ .Values.model.deepseekBaseUrl | quote }}
- name: RELAY_BASE_URL
  value: {{ .Values.model.relayBaseUrl | quote }}
- name: DEEPSEEK_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "clausewise.fullname" . }}-secret
      key: DEEPSEEK_API_KEY
- name: RELAY_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "clausewise.fullname" . }}-secret
      key: RELAY_API_KEY
- name: MONGODB_URI
  valueFrom:
    secretKeyRef:
      name: {{ include "clausewise.fullname" . }}-secret
      key: MONGODB_URI
- name: REDIS_ADDR
  valueFrom:
    secretKeyRef:
      name: {{ include "clausewise.fullname" . }}-secret
      key: REDIS_ADDR
- name: AUTH_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "clausewise.fullname" . }}-secret
      key: AUTH_SECRET
- name: INTERNAL_API_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ include "clausewise.fullname" . }}-secret
      key: INTERNAL_API_TOKEN
- name: SEED_DEMO_USERS
  value: "false"
- name: PI_AGENT_ENABLED
  value: "true"
- name: PI_AGENT_URL
  value: "http://pi-agent:8100"
{{- end -}}
