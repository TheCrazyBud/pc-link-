# Dynamic System Registration Tasks

- `[x]` Update `daemon.py` Backend
  - `[x]` Add startup logic to check for `system_config.json`.
  - `[x]` If missing, prompt user for `SYSTEM_NAME` and `SYSTEM_ID` via terminal input.
  - `[x]` Save input to `system_config.json`.
  - `[x]` On startup, push `{ label: SYSTEM_NAME, value: SYSTEM_ID }` to `systems/<SYSTEM_ID>` in Firebase.
- `[x]` Update `App.js` Mobile App
  - `[x]` Remove hardcoded `SYSTEMS` array.
  - `[x]` Add `systems` state array.
  - `[x]` Implement `useEffect` to listen to `systems/` Firebase node.
  - `[x]` Update Modal UI to map over dynamic `systems` state.
