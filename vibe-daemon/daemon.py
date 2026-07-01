import getpass
from auth_client import FirebaseAuthClient, MockDB
import device_verify
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

FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "AIzaSyAmozeBJHWoGOWBfs3hQhfEf07Og-LFzF4")
DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://pc-link-bca30-default-rtdb.firebaseio.com")

auth_client = FirebaseAuthClient(FIREBASE_API_KEY, DATABASE_URL)
db = MockDB(auth_client)


# 2. System Auto-Registration and Auth
CONFIG_FILE = os.path.join(application_path, "system_config.json")
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        sys_config = json.load(f)
        SYSTEM_ID = sys_config.get("id")
        SYSTEM_LABEL = sys_config.get("label")
        refresh_token = sys_config.get("refresh_token")
        
    print("[AUTH] Attempting to refresh login token...")
    success, _ = auth_client.refresh_auth_token(refresh_token)
    if not success:
        print("[AUTH ERROR] Session expired. Please delete system_config.json and login again.")
        sys.exit(1)
else:
    print("
" + "="*50)
    print("🚀 FIRST TIME SETUP: REGISTER THIS MACHINE")
    print("="*50)
    SYSTEM_LABEL = input("Enter a display name for this machine (e.g., Office Rig): ").strip()
    SYSTEM_ID = "".join(c for c in SYSTEM_LABEL if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_').lower()
    if not SYSTEM_ID:
        SYSTEM_ID = "default_system"
        SYSTEM_LABEL = "Default System"
        
    print("
🔐 Firebase Authentication")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    
    print("[AUTH] Logging in...")
    success, _ = auth_client.sign_in_with_email_password(email, password)
    if not success:
        print("[AUTH ERROR] Invalid email or password.")
        sys.exit(1)
        
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"id": SYSTEM_ID, "label": SYSTEM_LABEL, "refresh_token": auth_client.refresh_token}, f, indent=4)
    print(f"
[SAVED] Machine registered as '{SYSTEM_LABEL}' (ID: {SYSTEM_ID}).
")

# 3. Device Verification
print("[SECURITY] Verifying hardware license...")
hw_id = device_verify.get_hardware_uuid()
if not hw_id:
    print("[FATAL] Could not determine hardware UUID.")
    sys.exit(1)
device_id = device_verify.generate_device_hash(hw_id)
# You could enforce a db check here like: db.reference(f'licenses/{device_id}').get()
if not device_verify.verify_device_license(device_id):
    sys.exit(1)

UID = auth_client.uid


# Push presence to cloud so mobile app can discover it
try:
    db.reference(f'users/{UID}/systems/{SYSTEM_ID}').set({
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
        
        raw_prefix = title.split(' - Antigravity IDE')[0].strip()
        parts = raw_prefix.split(' - ')
        folder_name = parts[-1].strip()
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
            db.reference(f'users/{UID}/systems/{SYSTEM_ID}/projects').set(firebase_projects)
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


def _push_log(project_id, text, log_type="response", tool_name=None, file_path_ref=None):
    """Push a single log entry to Firebase, chunking if necessary."""
    MAX_CHUNK = 2000
    base_payload = {
        'type': log_type,
        'timestamp': int(time.time() * 1000)
    }
    if tool_name:
        base_payload['tool'] = tool_name
    if file_path_ref:
        base_payload['file'] = file_path_ref

    if len(text) <= MAX_CHUNK:
        base_payload['text'] = text
        db.reference(f'users/{UID}/live_logs/{SYSTEM_ID}/{project_id}').push(base_payload)
    else:
        # Chunk large messages
        chunk_id = str(uuid.uuid4())[:8]
        chunks = [text[i:i+MAX_CHUNK] for i in range(0, len(text), MAX_CHUNK)]
        for idx, chunk in enumerate(chunks):
            payload = {**base_payload}
            payload['text'] = chunk
            payload['chunk_group'] = chunk_id
            payload['chunk_index'] = idx
            db.reference(f'users/{UID}/live_logs/{SYSTEM_ID}/{project_id}').push(payload)


def _describe_tool_call(name, args):
    """Build a rich description string for any tool call."""
    if name in ('replace_file_content', 'multi_replace_file_content'):
        target = args.get('TargetFile', 'unknown file')
        desc = args.get('Description', args.get('Instruction', ''))
        replacement = args.get('ReplacementContent', '')
        chunks = args.get('ReplacementChunks', [])
        parts = [f"📝 EDIT: {target}"]
        if desc:
            parts.append(f"   Description: {desc}")
        if replacement:
            parts.append(f"   Content:\n{replacement}")
        if chunks:
            for i, ch in enumerate(chunks):
                rc = ch.get('ReplacementContent', '')
                tc = ch.get('TargetContent', '')
                parts.append(f"   --- Chunk {i+1} ---")
                if tc:
                    parts.append(f"   - Target:\n{tc}")
                if rc:
                    parts.append(f"   + Replacement:\n{rc}")
        return '\n'.join(parts), target

    elif name == 'write_to_file':
        target = args.get('TargetFile', 'unknown file')
        desc = args.get('Description', '')
        content = args.get('CodeContent', '')
        parts = [f"📝 CREATE FILE: {target}"]
        if desc:
            parts.append(f"   Description: {desc}")
        if content:
            parts.append(f"   Content:\n{content}")
        return '\n'.join(parts), target

    elif name == 'view_file':
        target = args.get('AbsolutePath', 'unknown file')
        start = args.get('StartLine', '')
        end = args.get('EndLine', '')
        line_info = f" (lines {start}-{end})" if start else ""
        return f"👁️ VIEW FILE: {target}{line_info}", target

    elif name == 'run_command':
        cmd = args.get('CommandLine', 'command')
        cwd = args.get('Cwd', '')
        return f"💻 COMMAND: {cmd}\n   CWD: {cwd}", None

    elif name == 'grep_search':
        query = args.get('Query', '')
        path = args.get('SearchPath', '')
        return f"🔍 SEARCH: \"{query}\" in {path}", None

    elif name == 'search_web':
        query = args.get('query', '')
        return f"🌐 WEB SEARCH: \"{query}\"", None

    elif name == 'list_dir':
        path = args.get('DirectoryPath', '')
        return f"📂 LIST DIR: {path}", None

    elif name == 'browser_subagent':
        task = args.get('TaskSummary', args.get('TaskName', ''))
        return f"🌐 BROWSER: {task}", None

    elif name == 'generate_image':
        prompt = args.get('Prompt', '')
        return f"🎨 GENERATE IMAGE: {prompt}", None

    elif name == 'ask_question':
        questions = args.get('questions', [])
        q_text = questions[0].get('question', '') if questions else ''
        return f"❓ ASKING: {q_text}", None

    elif name == 'manage_task':
        action = args.get('Action', '')
        task_id = args.get('TaskId', '')
        return f"📋 TASK: {action} {task_id}", None

    elif name == 'schedule':
        prompt = args.get('Prompt', '')
        return f"⏱️ SCHEDULE: {prompt}", None

    elif name == 'read_url_content':
        url = args.get('Url', '')
        return f"🔗 READ URL: {url}", None

    else:
        summary = args.get('toolSummary', args.get('toolAction', name))
        return f"⚙️ TOOL [{name}]: {summary}", None


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
                        _push_log(project_id, '[STATUS: DONE]', log_type='status')
                        done_sent = True
                    time.sleep(0.5)
                    continue

                try:
                    data = json.loads(line)
                    t = data.get('type')

                    last_log_time = time.time()
                    if done_sent and t != 'USER_INPUT':
                        done_sent = False

                    # --- USER INPUT ---
                    if t == 'USER_INPUT':
                        content = data.get('content', '')
                        if content:
                            _push_log(project_id, f"👤 You: {content}", log_type='user')

                    # --- MODEL / PLANNER RESPONSE ---
                    elif t in ('MODEL_RESPONSE', 'PLANNER_RESPONSE'):
                        # Thinking (internal reasoning)
                        thinking = data.get('thinking', '')
                        if thinking:
                            _push_log(project_id, f"🧠 {thinking.strip()}", log_type='thinking')

                        # Response body (the actual output)
                        content = data.get('content', '')
                        if content:
                            _push_log(project_id, f"🤖 {content.strip()}", log_type='response')

                        # Tool calls — every single one with rich detail
                        calls = data.get('tool_calls', [])
                        for call in calls:
                            name = call.get('name', '')
                            args = call.get('args', {})
                            if not name and 'function' in call:
                                name = call['function'].get('name', 'unknown_tool')
                                args = call['function'].get('arguments', {})
                                if isinstance(args, str):
                                    try:
                                        args = json.loads(args)
                                    except Exception:
                                        args = {}

                            desc_text, file_ref = _describe_tool_call(name, args)
                            _push_log(project_id, desc_text, log_type='tool_call', tool_name=name, file_path_ref=file_ref)

                    # --- TOOL / SYSTEM RESPONSES (command output, search results, etc.) ---
                    elif t in ('TOOL_RESPONSE', 'SYSTEM_RESPONSE', 'TOOL_OUTPUT'):
                        content = data.get('content', '') or data.get('output', '')
                        if content:
                            tool_name = data.get('tool_name', data.get('name', ''))
                            _push_log(project_id, f"📋 Result:\n{content.strip()}", log_type='result', tool_name=tool_name)

                    # --- Catch-all for any other step types with content ---
                    else:
                        content = data.get('content', '')
                        status = data.get('status', '')
                        if content and t:
                            _push_log(project_id, f"ℹ️ [{t}] {content.strip()}", log_type='status')

                except Exception as e:
                    # Log parse errors for debugging but don't crash
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
    log_text = f'\u2699\ufe0f Processing: "{prompt[:80]}..."' if len(prompt) > 80 else f'\u2699\ufe0f Processing: "{prompt}"'
    _push_log(project_id, log_text, log_type='status')

    # CRITICAL SECTION: We lock the keyboard/mouse so we don't accidentally type into the wrong window
    with gui_lock:
        print(f"[LOCKED] Sending prompt to {ide_window.title.encode('ascii', 'replace').decode()}")
        success = send_prompt_to_ide(ide_window, prompt)

        if success:
            db.reference(db_path).delete()
            print(f"[SUCCESS] Delivered prompt to {project_id}.")
            
            _push_log(project_id, '💻 Prompt injected into IDE chat.', log_type='status')

            # Wait for IDE to log the prompt, then find the correct transcript
            latest_file = None
            search_path = os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript_full.jsonl")
            prompt_json = json.dumps(prompt.strip())
            prompt_snippet = prompt_json[1:-1][:50]
            # Use the project folder name for cross-device matching
            project_folder_name = window_hint.lower()
            
            for _ in range(5):
                time.sleep(1.0)
                files = glob.glob(search_path)
                if not files:
                    continue
                    
                now = time.time()
                recent_files = [f for f in files if (now - os.path.getmtime(f)) < 15]
                for f in sorted(recent_files, key=os.path.getmtime, reverse=True):
                    try:
                        with open(f, 'r', encoding='utf-8') as file:
                            file.seek(0, 2)
                            size = file.tell()
                            file.seek(max(0, size - 16384))
                            tail_content = file.read()
                            # Match ONLY prompt snippet. The project name might not be in the transcript yet!
                            if prompt_snippet in tail_content:
                                latest_file = f
                                break
                    except Exception:
                        pass
                        
                if latest_file:
                    break
                    
            if not latest_file:
                # Fallback: most recently modified transcript that has the prompt (even if older than 15s)
                files = glob.glob(search_path)
                for f in sorted(files, key=os.path.getmtime, reverse=True):
                    try:
                        with open(f, 'r', encoding='utf-8') as file:
                            file.seek(0, 2)
                            size = file.tell()
                            file.seek(max(0, size - 16384))
                            tail_content = file.read()
                            if prompt_snippet in tail_content:
                                latest_file = f
                                print(f"[TAILER] Fallback matched transcript for '{window_hint}': {f}")
                                break
                    except Exception:
                        pass
        else:
            db.reference(db_path).update({"status": "failed_gui"})
            _push_log(project_id, '\u274c Failed to inject prompt into IDE.', log_type='status')
    
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
                    db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/{project_id}/{terminal_id}/logs').push({
                        'text': buffer,
                        'timestamp': int(time.time() * 1000)
                    })
                db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/{project_id}/{terminal_id}/logs').push({
                    'text': "\n[Process Terminated]\n",
                    'timestamp': int(time.time() * 1000)
                })
                break
            buffer += char
        except queue.Empty:
            if buffer:
                db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/{project_id}/{terminal_id}/logs').push({
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
                
                db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'executed', 'terminal_id': term_id})
                print(f"[TERMINAL] Spawned terminal {term_id} for project '{project_id}'")
                
                # Register under the project namespace so app only sees its own terminals
                db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/{project_id}/active/{term_id}').set({
                    'status': 'running',
                    'created_at': int(time.time() * 1000)
                })
            except Exception as e:
                print(f"[TERMINAL ERROR] Failed to spawn: {e}")
                db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'failed'})

        elif action == 'input':
            term_id = data.get('terminal_id')
            cmd_text = data.get('command', '')
            entry = ACTIVE_TERMINALS.get(term_id)
            proc = entry['proc'] if entry else None
            if proc and proc.poll() is None:
                try:
                    proc.stdin.write(cmd_text + "\n")
                    proc.stdin.flush()
                    db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'executed'})
                except Exception as e:
                    print(f"[TERMINAL ERROR] Failed to send input: {e}")
                    db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'failed'})
            else:
                db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'failed_dead'})

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
                db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/{proj}/active/{term_id}').remove()
            db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/control{path_key}').update({'status': 'executed'})

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
ref = db.reference(f'users/{UID}/pending_prompts/{SYSTEM_ID}')
ref.listen(handle_new_prompt)

term_ref = db.reference(f'users/{UID}/remote_terminals/{SYSTEM_ID}/control')
term_ref.listen(handle_terminal_control)

print(f"\n[READY] Vibe Daemon (System ID: {SYSTEM_ID.upper()}) actively listening to Firebase...")
print("[INFO] True concurrency enabled. GUI Lock active.")
print(f"[INFO] Discovered projects: {list(PROJECTS.keys())}")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[SHUTDOWN] Exiting Daemon...")
