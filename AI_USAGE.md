# AI usage

Keep all three headings exactly as they are. If this file is missing or any heading is missing, the grader stops and gives 0 ("AI_USAGE.md missing or incomplete"). The content is not scored, but your Track Mentor reads it and the W8 defence can ask about it.

## Tools

- ChatGPT and Gemini API

## What AI got wrong

The AI initially suggested offset pagination for listParcels, which skips or repeats items when status changes. I asked it to switch to cursor-based pagination instead.

## In my own words

1. `listParcels` needs a cursor because offset pagination causes skipped or duplicated items when parcel states change between pages.

2. Renaming a field in `POST /v1/parcels` breaks the courier app because the client app expects exact JSON key names. The backend team and mobile developers must approve this change.