# Submission checklist (deadline Mon 26 Oct 2026, 1:00 PM PT = 11:00 PM Madagascar)

| # | Rule | Evidence | Status |
|---|---|---|---|
| 1 | Start from an existing AWS agent; add exactly ONE new tool | `agent/baseline.py` (before) vs `agent/agent_with_tool.py` (after: only `tools=[read_notice_document]` differs); article section (a). Starting agent is built first in this repo and tagged `v0-baseline`; the tool lands in a later commit. Previously published projects are not used | Done |
| 2 | Uses a named AWS service | Bedrock (`agent/common.py`), Textract + S3 (`tools/read_notice_document.py`), CloudFormation (`infra/template.yaml`) | Done in code; live run pending |
| 3 | Builder Center write-up: (a) starting agent (b) tool and why (c) new behaviour | `docs/builder-center-article.md` | Drafted; fill live results + URLs, then publish |
| 4 | Public demo video < 3 min, BEFORE and AFTER, no trademarks/music | `docs/demo-script.md` (timed, with recording checklist) | TODO: record Mon morning, upload, test logged out |
| 5 | Original, not previously published, NEW repo | New repo `strands-textract-notice-tool`; no code or history from earlier projects; baseline written fresh | Local only; push after you confirm visibility |

Reliability evidence: `pytest` (13 pass: mocked boto3 unit tests + dry eval), `python -m evals.run_evals --mode dry`,
live: `python -m evals.run_evals --mode live` and `pytest -m integration` (done: 5/5, 2 integration tests pass; see README).

Safety/hygiene
- [x] Secrets scan before first commit (re-run before push; also scan for 12-digit account IDs)
- [x] LICENSE (MIT, check the copyright holder name), `.gitignore`
- [x] Synthetic samples only; nothing from work (Pulse/Axian)
- [x] Live eval table pasted into README + article
- [ ] Tear-down run after recording (README "Tear-down")
- [ ] Repo made public; links tested logged out
