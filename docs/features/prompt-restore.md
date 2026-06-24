# Prompt Restore

## Overview
The Prompt Restore feature allows users to quickly recover the last prompt they sent via the mobile application. This is particularly useful if a dictated prompt had typos, or if the user wants to tweak an instruction and resend it without re-typing or re-dictating the whole phrase.

## Architecture

### Mobile App (`capture-app-54/App.js`)
- **Storage:** The feature utilizes `@react-native-async-storage/async-storage` for persistent, on-device caching.
- **Project Isolation:** Prompts are saved with keys specific to the project they were sent to (`lastPrompt_{projectId}`). This ensures that if you switch from a React frontend project to a Python backend project, the restore button will fetch the correct prompt for the active project.
- **Auto-Loading:** The `useEffect` hook listens for changes to the `selectedProject` state. When the user switches projects in the navigation menu, the component automatically pulls the correct cached prompt from memory.
- **One-Tap Restore:** Tapping the purple "Restore" button immediately populates the text input field with the cached prompt, ready to be edited and sent.
