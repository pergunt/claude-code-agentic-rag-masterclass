# Manual checks

Agent-reviewed checks that are not scripted. The `/validate` agent does these after a run and notes the result in its report.

- **Failure screenshots**: skim the images under `validation-report/latest/playwright-artifacts` for any failed e2e test. Look for error banners, blank pages or layout breakage that the assertions don't name.
- **Cancelled turns in LangSmith** (optional): after a run that includes CHAT-03 or RET-06, open the `chat_turn` trace for the stopped turn in the LangSmith UI and check it shows as cancelled, not as an error.
