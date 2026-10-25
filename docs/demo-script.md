# Demo script (target 2:45, hard limit 3:00)

Setup before recording: terminal font 18pt+, light theme, `cd` into the repo, venv active,
`AWS_PROFILE`, `AWS_REGION`, `NOTICE_BUCKET` exported, `clear`. Hide the prompt path/username and
any account ID (`export PS1='$ '`). Open `samples/water_shutoff.png` in Preview side by side.
No music (or royalty-free/own only); no third-party logos on screen.

| Time | Screen | Say |
|---|---|---|
| 0:00-0:10 | Slide/README title | "Residents get public notices as photos and PDFs. My Strands agent only reads text." |
| 0:10-0:30 | Preview shows the PNG, then terminal: `python -m agent.baseline "Explain this notice: samples/water_shutoff.png"` | "BEFORE: it can't open the image. It asks me to paste the text." Show the reply. |
| 0:30-0:50 | `cat agent/agent_with_tool.py` (highlight `tools=[read_notice_document]`) | "One new tool, one line of wiring: Amazon Textract behind a Strands @tool." |
| 0:50-1:20 | `python -m agent.agent_with_tool "Explain this notice: samples/water_shutoff.png"` | "AFTER: same prompt. The agent decides to call the tool, reads the notice and rewrites it. Date and times are exact." |
| 1:20-1:50 | Same with `samples/clinic_hours.pdf`, then the tilted photo `samples/permit_deadline.png` | "PDF works. The slightly tilted, blurred photo still reads correctly: Textract reports 99.6% confidence." |
| 1:50-2:20 | `python -m agent.agent_with_tool "Explain this notice: <paste plain text>"`; then `python -m evals.run_evals --mode live` | "On plain text it does NOT call the tool. The eval table shows before versus after on the same inputs." |
| 2:20-2:45 | `docs/architecture.md` diagram, then the 15-line pattern in README | "S3 plus Textract plus Bedrock. The docstring is the router, errors are typed JSON, clients are injectable. Reuse it for any document tool." |
| 2:45-3:00 | Repo URL on screen | "Code is open source under MIT. Thanks." |

Fallbacks: pre-record each command; if a live call is slow, speed up (cut, don't fake) the wait.
Do the live eval run once beforehand to confirm it finishes under 30 s of screen time, else show saved output.

## Screen-recording checklist
- [ ] Notifications off, no personal tabs/bookmarks, no account ID, no profile name beyond a neutral one
- [ ] Terminal readable at 1080p; commands pasted from this script
- [ ] BEFORE and AFTER clearly captioned on screen
- [ ] Total < 3:00 including intro/outro; export 1080p
- [ ] No copyrighted music, no third-party trademarks/logos (AWS service names in text are fine; don't show logos)
- [ ] Upload to YouTube/Vimeo as public/unlisted-public; test the link logged out
