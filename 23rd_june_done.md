# PC Link - June 23rd Fixes & Updates

Today, significant improvements were made to the PC Link ecosystem to resolve issues with prompt delivery, live telemetry, and project management. 

## 1. Prompt Injection Reliability
**Problem**: The daemon used `Ctrl+L` to focus the chat panel. In cursor-based IDEs (like Antigravity IDE), `Ctrl+L` expands the selection to the current line if the text editor is focused. This caused prompts to be pasted directly into source files (like `eas.json`) instead of the chat window.
**Fix**: 
- Replaced `Ctrl+L` with the **Command Palette approach**.
- The daemon now presses `Ctrl+Shift+P`, types `"Focus Chat"`, and hits `Enter` before pasting the prompt.
- This guarantees the chat input is safely focused regardless of what editor pane is open.

## 2. Dynamic Project Auto-Detection
**Problem**: The list of available projects was hardcoded in both the mobile app and the daemon's python script. Adding a new project required modifying both codebases and redeploying.
**Fix**:
- Built an **auto-detection system** into the daemon.
- Every 30 seconds, the daemon scans all open windows for the Antigravity IDE (`* - Antigravity IDE - *`).
- It parses the project folder name, finds its path in `C:\Users\Dell\Downloads\`, and automatically registers the project.
- Discovered projects are pushed to Firebase (`systems/<system_id>/projects`).
- The mobile app was updated to listen to this Firebase path, dynamically rendering the exact projects currently open on your PC.

## 3. Live Telemetry Resilience
**Problem**: Telemetry logs (what the agent thinks/edits) only worked for PC Link, and often failed to start because prompt delivery failed.
**Fix**:
- Since prompt delivery is now fixed (Command Palette), telemetry triggers successfully.
- Added immediate status logs: when you hit send, you'll instantly see an "⚙️ Processing: ..." and "💻 Prompt injected into IDE chat" message in the mobile app so you know it worked.
- Improved the transcript-matching logic to prioritize recently modified files, ensuring we tail the correct chat log even across multiple projects.

## 4. Layout & UI Polish
- Disabled `KeyboardAvoidingView` specifically for Android to fix the bug where the terminals/agent navigation bar would get stuck floating in the middle of the screen after dismissing the keyboard.
- Corrected layout margins for the telemetry console.

## 5. Machine State & Setup
- Configured a local `system_config.json` to lock the machine's ID across reboots.
- Placed the correct Firebase Service Account Keys.
- Re-built `daemon.exe` with PyInstaller to bundle all the fixes.

---
*All changes have been successfully committed to GitHub.*
