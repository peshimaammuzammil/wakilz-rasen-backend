# Rasen Prompt — Source of Truth

This folder contains the version-controlled source for the Wakilz voice agent
configured on [app.rasen.ai](https://app.rasen.ai).

**Never edit the prompt directly in the Rasen dashboard without updating these files first.**

---

## Workflow

```
Edit the relevant .md file here
        ↓
Copy-paste content into the correct Rasen dashboard tab
        ↓
Click Publish → note the agent version number in git commit message
        ↓
Make test calls → review transcripts + extractions in Rasen Analytics
        ↓
Iterate: edit .md → paste → publish → repeat
```

---

## Files

| File | Rasen Dashboard Location | What It Controls |
|---|---|---|
| `01_personality.md` | Configuration → System Prompt → Personality tab | Who the agent is, area expertise |
| `02_tone.md` | Configuration → System Prompt → Tone tab | Language rules, sentence style, Hinglish rules |
| `03_goals.md` | Configuration → System Prompt → Goals tab | Full qualification flow + closing sequence |
| `04_guardrails.md` | Configuration → System Prompt → Guardrails tab | Forbidden behaviors, edge cases, redirects |
| `05_tools.md` | Configuration → System Prompt → Tools tab | When to use End Call |
| `06_first_message.md` | Configuration → First Message field | The opening line the agent speaks |
| `07_knowledge_base.md` | Configuration → Knowledge Base → Upload file | All 9 projects (uploaded as a file) |
| `08_extraction_fields.md` | Configuration → Data Extraction | Field definitions to set up manually |
| `09_variables.md` | Configuration → Variables | Variable names + default values |
| `10_call_settings.md` | Agent → Call Settings tab | Duration, patience, audio settings |

---

## Agent Details

- **Agent Name**: Neha Naaz (Wakilz)
- **Workspace**: app.rasen.ai → Wakilz workspace
- **Language**: Hinglish (Latin-script Hindi + English) — default. No Devanagari.
- **Primary Goal**: Book site visit with a specific time slot
- **Secondary Goal**: Capture phone number
- **Post-call**: Rasen Data Extraction (13 fields) — no mid-call webhook tools
- **Escalation**: Log + End Call (no phone transfer)
