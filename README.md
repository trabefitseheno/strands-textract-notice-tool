# strands-textract-notice-tool

Give a Strands agent **one new tool**: `read_notice_document`, backed by Amazon Textract.
Built for the AWS "Weekend Challenge: Give your Agent a Tool".

> All sample notices are synthetic (an invented town). No real people or data.

## Problem

The starting agent (built first, tagged `v0-baseline`; Strands Agents SDK on Amazon Bedrock, Nova Lite) rewrites a public notice in
plain language and states the deadline. It only understands **text**. Residents often have a
photo of a flyer or a scanned PDF, so the agent can't help them.

## Before / after

| Input | Before (no tool) | After (`read_notice_document`) |
|---|---|---|
| Photo of a notice (PNG) | Cannot read it; may even invent an example notice | Calls Textract, rewrites, keeps dates and amounts |
| Scanned PDF | same | same |
| Plain text | works | works, **tool not called** |
| Unsupported / corrupt file | n/a | Tool returns a clear error; the agent reports it, invents nothing |

Run it yourself: `python -m evals.run_evals --mode dry` prints the table.
Live results: see [Evaluation](#evaluation).

## Architecture

See [docs/architecture.md](docs/architecture.md) (Mermaid diagram).

## How the tool plugs into a Strands agent (the reusable pattern)

```python
from strands import Agent, tool

@tool
def read_notice_document(source: str) -> str:
    """Extract text from a photo, scan or PDF. Call FIRST when the input is a file path or
    s3:// URI ending in .png/.jpg/.pdf. Do NOT call it when the text is already in the message.

    Args:
        source: Local file path or s3://bucket/key URI.
    Returns: JSON {ok, text, confidence, page_count, low_confidence, warning, error}.
    """
    return read_document(source).model_dump_json()   # typed Pydantic result, never raises

agent = Agent(model=model, system_prompt=PROMPT, tools=[read_notice_document])
```

Why it works reliably:
1. **The docstring is the router.** It says *when* to call and *when not to*.
2. **Typed, JSON result that never raises.** Errors come back as `ok:false` with a message the
   model can relay, so it doesn't hallucinate content.
3. **Confidence is part of the contract.** Low OCR confidence returns a warning the agent passes on.
4. **AWS clients are injectable** (`TextractReader(s3=..., textract=...)`), so the tool is unit-testable
   without credentials.

To reuse it for another document type, change the docstring and the file-type checks in
`tools/read_notice_document.py`.

## Repo layout

```
agent/     baseline.py (before), agent_with_tool.py (after), common.py
tools/     read_notice_document.py  (the one new tool)
infra/     template.yaml  (S3 bucket + least-privilege IAM managed policy)
samples/   3 synthetic notices (+ make_samples.py)
evals/     run_evals.py (before/after table), dry_model.py
tests/     mocked-boto3 unit tests, dry-eval test, 1 real integration test
docs/      architecture, demo script, Builder Center article
```

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                   # unit tests + dry eval, no AWS needed
python -m evals.run_evals --mode dry     # before/after table, no AWS needed
```

Live (needs AWS credentials, Bedrock model access to Amazon Nova Lite, Textract in the region):

```bash
export AWS_PROFILE=<your-profile> AWS_REGION=us-east-1
aws cloudformation deploy --stack-name notice-tool --template-file infra/template.yaml \
    --capabilities CAPABILITY_IAM
export NOTICE_BUCKET=$(aws cloudformation describe-stacks --stack-name notice-tool \
    --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text)
python -m agent.baseline "Explain this notice: samples/water_shutoff.png"          # BEFORE
python -m agent.agent_with_tool "Explain this notice: samples/water_shutoff.png"   # AFTER
python -m evals.run_evals --mode live
pytest -m integration
```

`BEDROCK_MODEL_ID` overrides the model (default `amazon.nova-lite-v1:0`; some regions need an
inference-profile ID).

## IAM

`infra/template.yaml` creates a managed policy to attach to the identity running the agent:
`s3:PutObject/GetObject` on `uploads/*` of the one bucket only; `textract:DetectDocumentText`,
`StartDocumentTextDetection`, `GetDocumentTextDetection`; `bedrock:InvokeModel*`.
(Textract and Bedrock actions don't support resource scoping the same way, so they use `*`; narrow
Bedrock to your model ARN if you prefer.) No credentials are stored in this repo.

## Cost notes

Approximate, check current pricing pages: Textract text detection is about $1.50 per 1,000 pages;
Nova Lite is a few cents per million tokens; S3 storage here is negligible because objects expire
after 1 day. A full eval run is a handful of Textract pages and a few thousand tokens, i.e. well
under a dollar. The stack has no always-on resources.

## Tear-down

```bash
aws s3 rm "s3://$NOTICE_BUCKET" --recursive
aws cloudformation delete-stack --stack-name notice-tool
aws cloudformation wait stack-delete-complete --stack-name notice-tool
```

## Evaluation

`evals/run_evals.py` runs identical inputs through both agents and checks: tool called iff a file
was given; key dates/amounts survive; bad input is reported, not invented.

- `--mode dry` uses a scripted stand-in for the model and a fake Textract. It proves the **wiring**
  (schema, result handling, error paths, no tool call on text) but says nothing about the real
  model's judgement. It runs in CI-free, offline form as `tests/test_evals_dry.py`.
- `--mode live` uses real Bedrock and Textract. Results (Nova Lite, us-east-1, one run, temperature 0):

```
case         | BEFORE (baseline)     | AFTER (with tool)       | tool calls (after)
image_clean  | FAIL (cannot read)    | PASS                    | read_notice_document
image_photo  | FAIL (cannot read)    | PASS                    | read_notice_document
pdf          | FAIL (cannot read)    | PASS                    | read_notice_document
plain_text   | PASS                  | PASS                    | -
bad_file     | PASS (reported error) | PASS (reported error)   | read_notice_document
```

Textract mean confidence on the samples: 99.7 (clean PNG), 99.6 (tilted/blurred PNG), 99.9 (PDF). The
low-confidence warning path is covered by unit tests only, not by a live sample.
Without the tool, the baseline sometimes **invents an example notice** (we saw a made-up July 2023
shut-off) instead of just asking for text. Raw output: `evals/results_live.json`. Caveat: the first live run
had 3 false failures caused by my fact-checker (date format, keyword list); I fixed the checker and re-ran.

## Limitations

- OCR only: no tables, forms or handwriting (Textract has other APIs for those).
- Photos with glare or skew lower confidence; the agent is told to warn, not to correct figures.
- PDFs are polled for up to 60 s (`TEXTRACT_TIMEOUT_S`); very long documents need an async design.
- A 5-case eval is a smoke test, not a benchmark.
- Local files are uploaded to S3 for processing (expire after 1 day); don't use for sensitive documents
  without reviewing your data-handling needs.

## License

MIT, see [LICENSE](LICENSE).
