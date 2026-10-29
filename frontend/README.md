# Media Intelligence Executive Dashboard (Frontend)

Interactive React + Vite frontend for the Autonomous Media Intelligence Analyst Agent.

## Features

- **Executive Document Reader (`ExecutiveBriefingView.jsx`)**:
  - **Executive Reader**: Styled typography, structured threat/opportunity analysis cards, and hyperlinked citation badges.
  - **Analyst Audit View**: Side-by-side evidence inspection highlighting source URLs and verbatim quotation spans.
  - **Raw Markdown View**: Copyable raw briefing text with character-offset syntax.
- **Run History & Session Switcher**:
  - Automatically lists all historical runs stored in the local SQLite database.
  - Switch between past company analyses (e.g. Samsung, Global Logistics NV) with a single click.
  - Preserves selected run across page reloads via `localStorage`.
- **Live Pipeline Tracker**:
  - Visual stage-by-stage progress bar across all 8 pipeline phases.
  - Real-time event log with graceful **Stop Pipeline** capability.
- **Autonomous Cadence Management**:
  - Configure scheduled daily briefings (e.g., 06:00 UTC) or periodic interval runs (every 2–6 hours).
  - One-click manual override ("Trigger Run Now") and live daemon heartbeat status.
- **Citation & Evidence Inspector**:
  - Interactive verbatim evidence explorer validating exact character slices (`body[start:end] == evidence`).
- **Story Clusters & CRM Governance Explorer**:
  - Multilingual semantic clustering view.
  - Policy-gated CRM task audit log (max 5-task cap, idempotency keys, and retry status).

## Development & Build

```bash
# Install dependencies
npm install

# Run Vite dev server with hot reload
npm run dev

# Compile production bundle (served automatically by python run.py via FastAPI)
npm run build
```
