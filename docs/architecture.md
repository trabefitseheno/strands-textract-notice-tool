# Architecture

Editable draw.io version (AWS icons, numbered steps): [architecture.drawio](architecture.drawio). Open it at app.diagrams.net or in draw.io desktop.

```mermaid
flowchart LR
    U[User: text, or path / s3:// URI of a photo, scan or PDF] --> A[Strands Agent<br/>Amazon Bedrock · Nova Lite]
    A -- "input is text" --> R[Plain-language rewrite]
    A -- "input is a file" --> T["@tool read_notice_document"]
    T -- "local file: upload (SSE)" --> S3[(S3 bucket<br/>private · encrypted · 1-day expiry)]
    T --> TX[Amazon Textract<br/>DetectDocumentText / async PDF]
    S3 --> TX
    TX -- "text · confidence · pages" --> T
    T -- "JSON: ok, text, confidence, warning, error" --> A
    A --> R
```

**Decision point.** The model chooses whether to call the tool from the tool's docstring alone.
No router code, no regex: the agent loop is unchanged.

**Failure paths** (all returned as `ok:false` JSON so the agent can tell the user instead of guessing):
unsupported type, missing file, oversize file, missing bucket, Textract rejection, PDF job failure,
PDF timeout. Low mean confidence returns `ok:true` with `low_confidence` and a warning.
