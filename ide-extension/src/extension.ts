import * as vscode from 'vscode';
import { initializeApp } from 'firebase/app';
import { getDatabase, ref, onChildAdded, remove, update } from 'firebase/database';

const firebaseConfig = {
  apiKey: "AIzaSyAmozeBJHWoGOWBfs3hQhfEf07Og-LFzF4",
  authDomain: "pc-link-bca30.firebaseapp.com",
  databaseURL: "https://pc-link-bca30-default-rtdb.firebaseio.com",
  projectId: "pc-link-bca30",
  storageBucket: "pc-link-bca30.firebasestorage.app",
  messagingSenderId: "265412066500",
  appId: "1:265412066500:web:eb3abd9aa972f10f191d91",
  measurementId: "G-BTGD2SHNW3"
};

const SYSTEM_ID = "office_rig";

export function activate(context: vscode.ExtensionContext) {
    console.log('[PcLink] Extension activated');
    vscode.window.showInformationMessage('Pc Link: Native IDE Listener Started');

    const app = initializeApp(firebaseConfig);
    const db = getDatabase(app);

    // Get current workspace name to match project id
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        console.log('[PcLink] No workspace folder open. Pausing listener.');
        return;
    }
    
    // We match the Python daemon's extraction logic (extracting alpha-numerics)
    const folderName = workspaceFolders[0].name;
    const projectId = folderName.replace(/[^a-zA-Z0-9_-]/g, '');

    console.log(`[PcLink] Listening for prompts for project: ${projectId}`);

    const queueRef = ref(db, `pending_prompts/${SYSTEM_ID}`);

    const unsubscribe = onChildAdded(queueRef, (snapshot) => {
        const data = snapshot.val();
        if (!data || data.status !== 'pending') return;
        
        if (data.project === projectId) {
            console.log(`[PcLink] Received prompt: ${data.prompt}`);
            
            // Mark as processed immediately so other instances don't grab it
            update(snapshot.ref, { status: "processing_native" }).then(() => {
                handlePromptInjection(data.prompt);
                
                // Clean up the queue item just like the python daemon
                remove(snapshot.ref);
            });
        }
    });

    context.subscriptions.push({ dispose: () => unsubscribe() });
}

async function handlePromptInjection(prompt: string) {
    // For Phase 1: We copy the prompt to the clipboard and show a notification
    // to instruct the user. Since Antigravity IDE might not expose a native chat injection
    // API, this is a stable fallback while we research the command ID.
    
    await vscode.env.clipboard.writeText(prompt);
    
    vscode.window.showInformationMessage(
        'Pc Link Prompt Received! It has been copied to your clipboard. Focus the chat window and press Ctrl+V.',
        'Got it'
    );
}

export function deactivate() {
    console.log('[PcLink] Extension deactivated');
}
