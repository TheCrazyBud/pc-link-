# Full-Fidelity Live Telemetry

## Overview
The Pc Link system now features full-fidelity, real-time live telemetry. This allows the mobile application to display the complete, untruncated internal thought process and actions of the AI agent running in the Antigravity IDE.

## Architecture

### 1. Daemon (`vibe-daemon/daemon.py`)
- **Full Transcripts:** The daemon monitors the `transcript_full.jsonl` file instead of the truncated version. This ensures that massive file outputs and deeply detailed AI reasoning are captured without being cut off.
- **Payload Categorization:** Incoming logs are categorized into types:
  - `thinking`: The AI's internal reasoning process.
  - `response`: The final conversational response to the user.
  - `tool_call`: When the AI invokes a tool (e.g., viewing a file, running a command).
  - `result`: The output resulting from a tool call or system response.
  - `status`: High-level system state notifications.
- **Message Chunking:** Firebase Realtime Database limits the size of individual push payloads. The daemon automatically segments large payloads (like 10,000-line command outputs) into smaller chunks with a shared `chunk_group` ID, pushing them sequentially.

### 2. Mobile App (`capture-app-54/App.js`)
- **Chunk Reassembly:** The React Native app listens to the last 200 logs via Firebase. When it detects chunks belonging to the same `chunk_group`, it seamlessly stitches them back together into a single block of text before rendering.
- **Collapsible UI:** To prevent the screen from being overwhelmed by massive logs, "Thinking" blocks and long "Result" blocks are rendered in a collapsed state (e.g., `🧠 [Thinking... tap to expand]`). Tapping the block expands it to reveal the full content.
- **Color-Coded Styling:** The logs are visually distinct:
  - **Thinking:** Italic purple
  - **Tools:** Cyan
  - **Results:** Terminal green
  - **Commands/Files:** Distinct emojis and colors

## Multi-Project Stability
A critical part of the telemetry upgrade was stabilizing multi-project detection. 
- The daemon strictly extracts the parent workspace folder name by splitting the IDE window title from right-to-left. This prevents the daemon from creating a new "project" every time the user switches tabs within the IDE.
- Log tracking completely bypasses folder-name matching in the transcript file, relying solely on matching the injected prompt snippet to ensure logs never bleed across different projects.
