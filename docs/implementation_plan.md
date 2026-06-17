# Dynamic System Registration Plan

## Goal
Replace the hardcoded system list (India, Peru, NYC) with a fully dynamic "plug-and-play" architecture. When a new physical machine runs the backend daemon, it will automatically register itself to the cloud, and the mobile app will instantly detect it and add it to the UI.

## Proposed Changes

### 1. `daemon.py` (Backend Auto-Registration)
- **One-Time Naming:** On its very first run, `daemon.py` will ask you in the terminal: *"Enter a name for this machine (e.g., Office Desktop, Home Rig):"*. It will save this to a local `vibe_config.json` file so it never asks again.
- **Cloud Presence:** Whenever `daemon.py` starts, it will push its registered name to a new Firebase node: `systems/<system_id>`. This acts as a persistent directory of all your available machines.

### 2. `App.js` (Mobile App Discovery)
- **Dynamic System List:** The hardcoded `SYSTEMS` array will be completely removed.
- **Live Discovery:** The app will establish a real-time listener on the `systems/` Firebase node.
- **Auto-Population:** The moment you spin up a new daemon on a new laptop anywhere in the world, the mobile app will instantly detect it and populate it into your frosted glass System Selection modal.

## User Review Required
> [!IMPORTANT]  
> Are you okay with the daemon asking you for the machine name directly in the terminal on its first launch, and saving it to a local config file? This is the easiest way to give a custom name without modifying code.

## Verification
- We will update the app to listen for live systems.
- We will update `daemon.py` with the registration logic.
- We will run the daemon, type "Windows Rig" as the name, and verify it instantly appears on the mobile app's selection menu.
