# Native IDE Extension (Phase 1)

## Overview
The Native IDE Extension (`ide-extension`) was created to replace the brittle OS-level window hacking performed by the Python `vibe-daemon`. Instead of using `pyautogui` to physically manipulate the user's keyboard and mouse, the extension securely hooks directly into the IDE.

## Architecture

### `ide-extension/`
- **Standalone Build:** Built as a standard VS Code extension using TypeScript and Webpack. It is completely isolated from the Python daemon.
- **Firebase Connection:** The extension acts as a native listener, connecting to the user's Firebase RTDB.
- **Stable Workspace Context:** The extension inherently knows exactly which workspace it is running in using `vscode.workspace.workspaceFolders`. This completely bypasses the bug-prone window-title scraping method previously used.

### Prompt Injection Flow
1. The extension listens to `pending_prompts/office_rig`.
2. When a prompt arrives with a `project` ID matching the current IDE workspace, the extension immediately flags the prompt in Firebase as `processing_native`. This prevents race conditions where the Python daemon might also attempt to process the same prompt.
3. **Fallback Injection:** Because the Antigravity IDE hides the exact command ID for native chat injection, the Phase 1 extension utilizes a seamless fallback: it securely writes the incoming prompt directly to the system clipboard (`vscode.env.clipboard.writeText`) and triggers a native IDE notification in the bottom right corner alerting the user to paste it (`Ctrl+V`).

## Future Development (Phase 2)
The extension currently handles prompt reception. The next architectural step is to migrate the log-tailing functionality from `vibe-daemon/daemon.py` directly into the extension, allowing us to deprecate the Python daemon entirely for a 100% native VS Code experience.
