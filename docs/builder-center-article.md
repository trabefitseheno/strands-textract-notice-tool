# Teaching a Strands agent to read a photo of a public notice with Amazon Textract

*Weekend Challenge: Give your Agent a Tool.* Code: <REPO URL> · Demo: <VIDEO URL>

## (a) The starting agent

This is a new, original agent built first for this entry (tag `v0-baseline` in the repo, before the tool
was added). It is not derived from any previously published project.

A small agent built with the **Strands Agents SDK** on **Amazon Bedrock** (Amazon Nova Lite). Given
the text of a public notice (a water shut-off, a permit deadline, a clinic day), it rewrites it in
plain language at roughly a 6th-grade reading level, says who it applies to and the deadline, and
copies every date, amount and place exactly. If it lacks the text, it says so instead of inventing
content. It has **no tools**.

Its blind spot: it only understands text. Real notices arrive as phone photos of flyers and scanned
PDFs. Asked about `water_shutoff.png`, it can only reply "please paste the text".

## (b) The one new tool, and why

**`read_notice_document`**: a Strands `@tool` that takes a local path or `s3://` URI of an image or
PDF, uploads it to a private encrypted S3 bucket if needed, runs **Amazon Textract**, and returns typed JSON:
`ok`, `text`, `confidence`, `page_count`, `low_confidence`, `warning`, `error`.

Why this tool: it removes the agent's single biggest input limitation with the smallest possible
surface area, and OCR is a pattern almost every document-facing agent needs. Why Textract and not
asking a multimodal model to read the image: it returns a **per-line confidence**, which lets the agent
be honest about uncertain dates and amounts, and it handles multi-page PDFs through an async API.

The wiring is one line, `Agent(tools=[read_notice_document])`. The agent decides by itself when to
call it, guided by the tool's docstring: call it for file paths and `s3://` URIs ending in image or PDF
extensions, never when the text is already in the message.

## (c) The behaviour it unlocked

| | Before | After |
|---|---|---|
| Photo of a notice | asks for pasted text | reads it, rewrites it, keeps the figures |
| Scanned PDF | asks for pasted text | same, multi-page aware |
| Tilted, blurred photo | n/a | reads it correctly (99.6% mean confidence) |
| Plain text | works | works, tool not called |
| Corrupt / unsupported file | n/a | explains the problem; invents nothing |

Evaluation: the same five inputs run through both agents, checking that the tool is called only
for files, that key dates and amounts survive, and that bad input is reported. Offline (scripted
model + fake Textract) the wiring checks all pass. Live Bedrock + Textract results:
**5/5 pass on the final run** (tool called on all 3 files and the bad file, never on plain text; baseline fails all 3 file cases). Honest caveats: my first live run showed 3 'failures' that were bugs in my checker (it didn't accept `May 12, 2026` for `12 May 2026`, and my error-report keyword list was too narrow), not agent errors; I fixed the checker, then re-ran. n=5, temperature 0, one run each.

## Lessons learned

1. **The docstring is the router.** Spelling out when *not* to call the tool matters as much as when to call it.
2. **Make tools that never raise.** Returning `ok:false` plus a human-readable error stopped the agent
   from guessing at content after a failure.
3. **Surface uncertainty as data.** Confidence in the contract turns "OCR might be wrong" into a behaviour.
4. **Inject your AWS clients.** The tool is tested with mocked boto3 and a fake Textract, so most reliability
   checks run offline in under two seconds.
5. **Dry-run evals catch plumbing bugs, not model bugs.** Mine found a path-with-spaces failure immediately,
   but only live runs say how the real model behaves, so I report them separately.
6. **Lifecycle your uploads.** Notices can be personal; the bucket is private, encrypted and expires objects after a day.

## Reuse it

The pattern (typed result, docstring routing, injectable clients, expiring bucket) is in the README in
about 15 lines. Swap the docstring and file-type checks to read invoices, forms or IDs-of-your-own-choosing.

*All sample notices are synthetic. Built with Strands Agents SDK, Amazon Bedrock, Amazon Textract and Amazon S3.*
