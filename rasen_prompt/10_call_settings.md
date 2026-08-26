# Call Settings Reference
# Configure in: Rasen Dashboard → Agent → Call Settings tab

---

## Call Duration

| Setting | Value | Reason |
|---|---|---|
| Maximum duration | **10 minutes** | Enough for full qualification + pitch + close cycle. Prevents runaway calls. |

## Audio & Noise

| Setting | Value | Reason |
|---|---|---|
| Noise suppression | **Medium** | Home/office backgrounds are common. High suppression can clip caller speech. |
| Background audio | **Subtle office ambient, low volume** | Avoids uncanny dead silence during pauses. Humanises the conversation. |

## Endpointing (Response Patience)

| Setting | Value | Reason |
|---|---|---|
| Response patience | **750 ms** | Indian callers often pause mid-thought. Lower values cut them off mid-sentence, which feels rude and kills trust. When in doubt, err patient — being interrupted feels far worse than a brief silence. |

## Voicemail

| Setting | Value | Reason |
|---|---|---|
| Voicemail detection | **On** | Required for future outbound campaigns. No impact on inbound web calls. |
| Retry on voicemail | **Off** (for now) | Enable when outbound campaigns begin. |

## DTMF

| Setting | Value | Reason |
|---|---|---|
| DTMF capturing | **Off** | Not needed in this qualification flow. No OTPs or numeric input expected. |

---

## Notes

- Response Patience is the most critical setting for this use case. If callers report
  being cut off, increase to 1000 ms.
- Background audio file should be a subtle, low-volume office ambience (keyboard clicks,
  distant murmur). Rasen provides presets — pick the quietest one.
- Max duration of 10 minutes covers: ~2 min greeting+qualification + ~2 min pitch +
  ~2 min objections + ~2 min close + buffer.
