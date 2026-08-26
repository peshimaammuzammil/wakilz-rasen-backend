# Agent Variables
# Set these up in: Rasen Dashboard → Agent → Configuration → Variables section
# Add each variable with the exact name and default value below.
# These are injected into the prompt and first message as {{variable_name}}.

---

| Variable Name  | Default Value                                           | Where Used |
|----------------|---------------------------------------------------------|------------|
| `agent_name`   | `Neha Naaz`                                         | First message, Personality tab |
| `company`      | `Wakilz`                                               | Personality tab |
| `city`         | `Hyderabad`                                            | Goals tab, Guardrails tab |
| `areas`        | `Kokapet, Kondapur, Financial District, Gachibowli, Kukatpally` | Goals tab (location step) |
| `budget_range` | `80 lakhs to 2 crores`                                 | Goals tab (budget step) |

---

## Notes

- On outbound campaigns, these can be overridden per-recipient via the CSV upload.
- `agent_name` allows different personas for different clients/campaigns without
  changing the core prompt.
- Currently all variables use these defaults. No per-call override is needed for
  the inbound web call flow.
