import firebase_admin
from firebase_admin import credentials, db
import threading
import time
import os
import sys
import pyautogui
import pyperclip
import pygetwindow as gw
import glob
import json
import subprocess
import uuid
import queue

# Stores the stop_event for each project's active tailer thread
ACTIVE_TAILS = {}
ACTIVE_TERMINALS = {}

# Global lock to ensure pyautogui operations (focusing window, pasting, pressing enter)
# happen sequentially, avoiding physical keyboard collisions across concurrent projects.
gui_lock = threading.Lock()

# Disable pyautogui failsafe (mouse-to-corner abort) for background use
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.3  # Small delay between actions for reliability

# -------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------
# Get the folder where the executable or script is located
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

SERVICE_ACCOUNT_KEY_PATH = os.environ.get("FIREBASE_CREDENTIALS", os.path.join(application_path, "serviceAccountKey.json"))
DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://pc-link-bca30-default-rtdb.firebaseio.com")

# Workspace roots where projects are located
WORKSPACE_ROOTS = [
    r"C:\Users\Dell\Downloads",
]

# Dynamic project registry — populated by scan_projects()
PROJECTS = {}

# 1. Initialize Firebase
try:
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
except Exception as e:
    print(f"[FATAL ERROR] Could not initialize Firebase: {e}")
    print("Please ensure your serviceAccountKey.json is present and valid.")
    sys.exit(1)

# 2. System Auto-Registration
CONFIG_FILE = os.path.join(application_path, "system_config.json")
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        sys_config = json.load(f)
        SYSTEM_ID = sys_config.get("id")
        SYSTEM_LABEL = sys_config.get("label")
else:
    print("\n" + "="*50)
    print("🚀 FIRST TIME SETUP: REGISTER THIS MACHINE")
    print("="*50)
    SYSTEM_LABEL = input("Enter a display name for this machine (e.g., Office Rig): ").strip()
    # Create a simple safe ID from the label
    SYSTEM_ID = "".join(c for c in SYSTEM_LABEL if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_').lower()
    if not SYSTEM_ID:
        SYSTEM_ID = "default_system"
        SYSTEM_LABEL = "Default System"
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"id": SYSTEM_ID, "label": SYSTEM_LABEL}, f, indent=4)
    print(f"\n[SAVED] Machine registered as '{SYSTEM_LABEL}' (ID: {SYSTEM_ID}).\n")

# Push presence to cloud so mobile app can discover it
try:
    db.reference(f'systems/{SYSTEM_ID}').set({
        'label': SYSTEM_LABEL,
        'value': SYSTEM_ID,
        'last_seen': int(time.time() * 1000)
    })
except Exception as e:
    print(f"[WARN] Failed to register system presence in cloud: {e}")


def scan_projects():
    """Auto-detect projects from open Antigravity IDE windows and push to Firebase."""
    global PROJECTS
    all_windows = gw.getAllWindows()
    discovered = {}

    for w in all_windows:
        title = w.title.strip()
        # Antigravity IDE titles look like: "FolderName - Antigravity IDE - filename.ext"
        if ' - Antigravity IDE' not in title:
            continue
        
        folder_name = title.split(' - Antigravity IDE')[0].strip()
        if not folder_name:
            continue

        # Create a safe project ID from the folder name
        project_id = "".join(c for c in folder_name if c.isalnum() or c in ('_', '-')).strip()
        if not project_id:
            continue

        # Skip if already discovered in this scan
        if project_id in discovered:
            continue

        # Find the actual directory on disk
        project_dir = None
        for root in WORKSPACE_ROOTS:
            candidate = os.path.join(root, folder_name)
            if os.path.isdir(candidate):
                project_dir = candidate
                break
        
        if not project_dir:
            # Try case-insensitive search
            for root in WORKSPACE_ROOTS:
                if os.path.isdir(root):
                    for entry in os.listdir(root):
                        if entry.lower() == folder_name.lower() and os.path.isdir(os.path.join(root, entry)):
                            project_dir = os.path.join(root, entry)
                            break
                if project_dir:
                    break

        if not project_dir:
            print(f"[SCAN] Skipping '{folder_name}' — directory not found in workspace roots.")
            continue

        discovered[project_id] = {
            "dir": project_dir,
            "window_hint": folder_name,
            "label": folder_name
        }

    # Update the global registry
    if discovered != PROJECTS:
        PROJECTS = discovered
        # Push to Firebase so the mobile app can see them
        try:
            firebase_projects = {}
            for pid, pconfig in PROJECTS.items():
                firebase_projects[pid] = {
                    "label": pconfig["label"],
                    "value": pid
                }
            db.reference(f'systems/{SYSTEM_ID}/projects').set(firebase_projects)
            print(f"[SCAN] Synced {len(PROJECTS)} projects to Firebase: {list(PROJECTS.keys())}")
        except Exception as e:
            print(f"[SCAN ERROR] Failed to push projects to Firebase: {e}")
    
    return PROJECTS


def project_scanner_loop():
    """Background thread that scans for projects every 30 seconds."""
    while True:
        try:
            scan_projects()
        except Exception as e:
            print(f"[SCAN ERROR] {e}")
        time.sleep(30)


def find_ide_window(window_hint):
    """Find an Antigravity window whose title contains the project folder name."""
    all_windows = gw.getAllWindows()
    hint_lower = window_hint.lower()
    for w in all_windows:
        title = w.title.strip().lower()
        if "antigravity" in title and hint_lower in title:
            return w
    return None


def send_prompt_to_ide(window, prompt):
    """Focus the IDE window, open chat, paste the prompt, and send it."""
    try:
        if window.isMinimized:
            window.restore()
            
        # Aggressive focus stealing (Windows block bypass)
        pyautogui.press('alt')
        window.activate()
        time.sleep(0.8)

        # Escape first to dismiss any open chat panel, menus, or overlays.
        # This ensures Ctrl+L will OPEN the chat (not toggle it closed).
        pyautogui.press('escape')
        time.sleep(0.3)
        pyautogui.press('escape')
        time.sleep(0.5)

        # Now Ctrl+L will reliably open a fresh chat input
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(1.0)

        # Paste the prompt and send
        pyperclip.copy(prompt)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)

        pyautogui.press('enter')
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send prompt: {e}")
        return False


def log_tailer(project_id, file_path, stop_event):
    print(f"[TAILER] Started tailing logs for {project_id} -> {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.seek(0, 2)  # Start at EOF
            last_log_time = time.time()
            done_sent = False

            while not stop_event.is_set():
                line = f.readline()
                if not line:
                    # Idle timeout (15s) -> Assume completion
                    if not done_sent and (time.time() - last_log_time) > 15.0:
                        db.reference(f'live_logs/{SYSTEM_ID}/{project_id}').push({
                            'text': '[STATUS: DONE]',
                            'timestamp': int(time.time() * 1000)
                        })
                        done_sent = True
                    time.sleep(0.5)
                    continue
                
                try:
                    data = json.loads(line)
                    log_msg = None
                    t = data.get('type')
                    
                    last_log_time = time.time()
                    if done_sent and t != 'USER_INPUT':
                        done_sent = False 

                    if t == 'USER_INPUT':
                        log_msg = f"👤 You: {data.get('content', '')}"
                    
                    elif t in ['MODEL_RESPONSE', 'PLANNER_RESPONSE']:
                        text = data.get('content') or data.get('thinking') or ""
                        if text:
                            if len(text) > 400:
                                text = text[:400] + "...\n[Truncated]"
                            log_msg = f"🤖 {text.strip()}"
                            
                        calls = data.get('tool_calls', [])
                        for call in calls:
                            name = call.get('name', '')
                            args = call.get('args', {})
                            
                            if name in ['replace_file_content', 'multi_replace_file_content', 'write_to_file', 'view_file']:
                                target = args.get('TargetFile') or args.get('AbsolutePath') or 'a file'
                                db.reference(f'live_logs/{SYSTEM_ID}/{project_id}').push({
                                    'text': f"📝 Editing/Viewing: {target}",
                                    'timestamp': int(time.time() * 1000)
                                })
                            elif name == 'run_command':
                                cmd = args.get('CommandLine', 'command')
                                db.reference(f'live_logs/{SYSTEM_ID}/{project_id}').push({
                                    'text': f"💻 Running: {cmd}",
                                    'timestamp': int(time.time() * 1000)
                                })
                            elif 'function' in call:
                                func_name = call['function'].get('name', 'tool')
                                db.reference(f'live_logs/{SYSTEM_ID}/{project_id}').push({
                                    'text': f"⚙️ Using tool: {func_name}",
                                    'timestamp': int(time.time() * 1000)
                                })
                    
                    if log_msg:
                        db.reference(f'live_logs/{SYSTEM_ID}/{project_id}').push({
                            'text': log_msg,
                            'timestamp': int(time.time() * 1000)
                        })
                except Exception:
                    pass
    except Exception as e:
        print(f"[TAILER ERROR] {e}")
    finally:
        print(f"[TAILER] Shutting down tailer for {project_id}")


def process_task(task):
    """Executes a single prompt for a project concurrently, safely acquiring GUI lock."""
    project_id = task.get('project')
    prompt = task.get('prompt')
    db_path = task.get('path')

    project_config = PROJECTS.get(project_id)
    if not project_config:
        print(f"[ERROR] Unknown project '{project_id}'. Known: {list(PROJECTS.keys())}")
        db.reference(db_path).update({"status": "failed_unknown_project"})
        return

    target_dir = project_config["dir"]
    window_hint = project_config["window_hint"]

    if not os.path.exists(target_dir):
        print(f"[ERROR] Target dir '{target_dir}' not found.")
        db.reference(db_path).update({"status": "failed_dir_not_found"})
        return

    print(f"\n[QUEUED] Waiting for GUI lock to inject into {project_id}...")
    
    ide_window = find_ide_window(window_hint)
    if not ide_window:
        print(f"[ERROR] No open IDE window found for '{window_hint}'.")
        db.reference(db_path).update({"status": "failed_no_ide_window"})
        return

    latest_file = None

    # Immediately log that we received the prompt
    db.reference(f'live_logs/{SYSTEM_ID}/{project_id}').push({
        'text': f'\u2699\ufe0f Processing: "{prompt[:80]}..."' if len(prompt) > 80 else f'\u2699\ufe0f Processing: "{prompt}"',
        'timestamp': int(time.time() * 1000)
    })

    # CRITICAL SECTION: We lock the keyboard/mouse so we don't accidentally type into the wrong window
    with gui_lock:
        print(f"[LOCKED] Sending prompt to {ide_window.title.encode('ascii', 'replace').decode()}")
        success = send_prompt_to_ide(ide_window, prompt)

        if success:
            db.reference(db_path).delete()
            print(f"[SUCCESS] Delivered prompt to {project_id}.")
            
            db.reference(f'live_logs/{SYSTEM_ID}/{project_id}').push({
                'text': '\U0001f4bb Prompt injected into IDE chat.',
                'timestamp': int(time.time() * 1000)
            })

            # Wait for IDE to log the prompt
            time.sleep(2.0)
            search_path = r"C:\Users\Dell\.gemini\antigravity-ide\brain\*\.system_generated\logs\transcript.jsonl"
            files = glob.glob(search_path)
            
            if files:
                # Strategy 1: Find transcript that was modified very recently (within last 10s)
                now = time.time()
                recent_files = [f for f in files if (now - os.path.getmtime(f)) < 10]
                
                if recent_files:
                    # Among recent files, try to match by prompt content
                    prompt_snippet = prompt.strip()[:50]
                    for f in sorted(recent_files, key=os.path.getmtime, reverse=True):
                        try:
                            with open(f, 'r', encoding='utf-8') as file:
                                file.seek(0, 2)
                                size = file.tell()
                                file.seek(max(0, size - 8192))
                                tail_content = file.read()
                                if prompt_snippet in tail_content:
                                    latest_file = f
                                    break
                        except Exception:
                            pass
                    
                    if not latest_file:
                        latest_file = max(recent_files, key=os.path.getmtime)
                else:
                    # Fallback: most recently modified overall
                    latest_file = max(files, key=os.path.getmtime)
        else:
            db.reference(db_path).update({"status": "failed_gui"})
            db.reference(f'live_logs/{SYSTEM_ID}/{project_id}').push({
                'text': '\u274c Failed to inject prompt into IDE.',
                'timestamp': int(time.time() * 1000)
            })
    
    # End of lock. Other projects can now type.

    # Start tailing the specific log file (completely independent thread)
    if success and latest_file:
        # Kill the old tailer for this project if it's still running
        if project_id in ACTIVE_TAILS:
            print(f"[TAILER] Killing old tailer for {project_id}")
            old_stop_event = ACTIVE_TAILS[project_id]
            old_stop_event.set()
        
        # Start fresh tailer
        stop_event = threading.Event()
        ACTIVE_TAILS[project_id] = stop_event
        
        print(f"[TAILER] Tailing: {latest_file}")
        t = threading.Thread(target=log_tailer, args=(project_id, latest_file, stop_event), daemon=True)
        t.start()


def terminal_stdout_reader(terminal_id, proc, q):
    while True:
        char = proc.stdout.read(1)
        if not char:
            break
        q.put(char)
    q.put(None)

def terminal_queue_processor(terminal_id, project_id, q):
    buffer = ""
    while True:
        try:
            char = q.get(timeout=0.1)
            if char is None:
                if buffer:
                    db.reference(f'remote_terminals/{SYSTEM_ID}/{project_id}/{terminal_id}/logs').push({
                        'text': buffer,
                        'timestamp': int(time.time() * 1000)
                    })
                db.reference(f'remote_terminals/{SYSTEM_ID}/{project_id}/{terminal_id}/logs').push({
                    'text': "\n[Process Terminated]\n",
                    'timestamp': int(time.time() * 1000)
                })
                break
            buffer += char
        except queue.Empty:
            if buffer:
                db.reference(f'remote_terminals/{SYSTEM_ID}/{project_id}/{terminal_id}/logs').push({
                    'text': buffer,
                    'timestamp': int(time.time() * 1000)
                })
                buffer = ""

def handle_terminal_control(event):
    if event.data is None:
        return
        
    data_items = []
    if isinstance(event.data, dict) and 'type' in event.data:
        data_items = [(event.path, event.data)]
    elif isinstance(event.data, dict):
        for key, val in event.data.items():
            if isinstance(val, dict):
                data_items.append((f"/{key}", val))

    for path_key, data in data_items:
        if data.get('status') != 'pending':
            continue

        # --- Read which project this terminal belongs to ---
        project_id = data.get('project', 'default')
            
        action = data.get('type')
        if action == 'spawn':
            term_id = str(uuid.uuid4())[:8]
            try:
                proc = subprocess.Popen(
                    ['cmd.exe'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                # Store terminal keyed by project so outputs are isolated
                ACTIVE_TERMINALS[term_id] = {'proc': proc, 'project_id': project_id}
                
                q = queue.Queue()
                threading.Thread(target=terminal_stdout_reader, args=(term_id, proc, q), daemon=True).start()
                threading.Thread(target=terminal_queue_processor, args=(term_id, project_id, q), daemon=True).start()
                
                db.reference(f'remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'executed', 'terminal_id': term_id})
                print(f"[TERMINAL] Spawned terminal {term_id} for project '{project_id}'")
                
                # Register under the project namespace so app only sees its own terminals
                db.reference(f'remote_terminals/{SYSTEM_ID}/{project_id}/active/{term_id}').set({
                    'status': 'running',
                    'created_at': int(time.time() * 1000)
                })
            except Exception as e:
                print(f"[TERMINAL ERROR] Failed to spawn: {e}")
                db.reference(f'remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'failed'})

        elif action == 'input':
            term_id = data.get('terminal_id')
            cmd_text = data.get('command', '')
            entry = ACTIVE_TERMINALS.get(term_id)
            proc = entry['proc'] if entry else None
            if proc and proc.poll() is None:
                try:
                    proc.stdin.write(cmd_text + "\n")
                    proc.stdin.flush()
                    db.reference(f'remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'executed'})
                except Exception as e:
                    print(f"[TERMINAL ERROR] Failed to send input: {e}")
                    db.reference(f'remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'failed'})
            else:
                db.reference(f'remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'failed_dead'})

        elif action == 'kill':
            term_id = data.get('terminal_id')
            entry = ACTIVE_TERMINALS.get(term_id)
            if entry:
                try:
                    entry['proc'].terminate()
                except:
                    pass
                proj = entry.get('project_id', project_id)
                del ACTIVE_TERMINALS[term_id]
                db.reference(f'remote_terminals/{SYSTEM_ID}/{proj}/active/{term_id}').remove()
            db.reference(f'remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'executed'})

def handle_new_prompt(event):
    """Fires when mobile app pushes to Firebase or on startup for existing nodes."""
    if event.data is None:
        return

    if isinstance(event.data, dict) and 'prompt' in event.data:
        if event.data.get('status') == 'pending':
            task = {
                'project': event.data.get('project'),
                'prompt': event.data.get('prompt'),
                'path': f"pending_prompts/{SYSTEM_ID}{event.path}"
            }
            # Spawn a dedicated worker thread immediately
            threading.Thread(target=process_task, args=(task,), daemon=True).start()
            
    elif isinstance(event.data, dict):
        for key, val in event.data.items():
            if isinstance(val, dict) and val.get('status') == 'pending':
                task = {
                    'project': val.get('project'),
                    'prompt': val.get('prompt'),
                    'path': f"pending_prompts/{SYSTEM_ID}/{key}"
                }
                # Spawn a dedicated worker thread immediately
                threading.Thread(target=process_task, args=(task,), daemon=True).start()


# Run initial project scan before starting listeners
print("[INFO] Running initial project scan...")
scan_projects()

# Clean up any dead terminals from previous daemon runs (per-project namespaces)
try:
    for proj_key in list(PROJECTS.keys()):
        db.reference(f'remote_terminals/{SYSTEM_ID}/{proj_key}/active').delete()
    print("[INFO] Cleaned up dead terminal sessions.")
except Exception as e:
    pass

# Start background project scanner thread (every 30s)
scanner_thread = threading.Thread(target=project_scanner_loop, daemon=True)
scanner_thread.start()
print("[INFO] Project auto-detection scanner started (30s interval).")

# Attach the Firebase listener
ref = db.reference(f'pending_prompts/{SYSTEM_ID}')
ref.listen(handle_new_prompt)

term_ref = db.reference(f'remote_terminals/{SYSTEM_ID}/control')
term_ref.listen(handle_terminal_control)

print(f"\n[READY] Vibe Daemon (System ID: {SYSTEM_ID.upper()}) actively listening to Firebase...")
print("[INFO] True concurrency enabled. GUI Lock active.")
print(f"[INFO] Discovered projects: {list(PROJECTS.keys())}")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[SHUTDOWN] Exiting Daemon...")
