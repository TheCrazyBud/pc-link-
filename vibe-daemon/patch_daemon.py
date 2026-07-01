import re

with open('daemon.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
content = re.sub(
    r'import firebase_admin\nfrom firebase_admin import credentials, db',
    r'import getpass\nfrom auth_client import FirebaseAuthClient, MockDB\nimport device_verify',
    content
)

# 2. Config & Firebase Init
config_regex = r'SERVICE_ACCOUNT_KEY_PATH =.*?sys\.exit\(1\)'
new_config = '''FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "AIzaSyAmozeBJHWoGOWBfs3hQhfEf07Og-LFzF4")
DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://pc-link-bca30-default-rtdb.firebaseio.com")

auth_client = FirebaseAuthClient(FIREBASE_API_KEY, DATABASE_URL)
db = MockDB(auth_client)
'''
content = re.sub(config_regex, new_config, content, flags=re.DOTALL)

# 3. Auto-Registration
sys_regex = r'# 2\. System Auto-Registration.*?CONFIG_FILE.*?\[SAVED\] Machine registered.*?\\n"\)'
new_sys_reg = '''# 2. System Auto-Registration and Auth
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
    print("\\n" + "="*50)
    print("🚀 FIRST TIME SETUP: REGISTER THIS MACHINE")
    print("="*50)
    SYSTEM_LABEL = input("Enter a display name for this machine (e.g., Office Rig): ").strip()
    SYSTEM_ID = "".join(c for c in SYSTEM_LABEL if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_').lower()
    if not SYSTEM_ID:
        SYSTEM_ID = "default_system"
        SYSTEM_LABEL = "Default System"
        
    print("\\n🔐 Firebase Authentication")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    
    print("[AUTH] Logging in...")
    success, _ = auth_client.sign_in_with_email_password(email, password)
    if not success:
        print("[AUTH ERROR] Invalid email or password.")
        sys.exit(1)
        
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"id": SYSTEM_ID, "label": SYSTEM_LABEL, "refresh_token": auth_client.refresh_token}, f, indent=4)
    print(f"\\n[SAVED] Machine registered as '{SYSTEM_LABEL}' (ID: {SYSTEM_ID}).\\n")

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
'''
content = re.sub(sys_regex, new_sys_reg, content, flags=re.DOTALL)

# 4. Scope Database Paths
path_replacements = [
    (r"f'systems/\{SYSTEM_ID\}'", r"f'users/{UID}/systems/{SYSTEM_ID}'"),
    (r"f'systems/\{SYSTEM_ID\}/projects'", r"f'users/{UID}/systems/{SYSTEM_ID}/projects'"),
    (r"f'live_logs/\{SYSTEM_ID\}/\{project_id\}'", r"f'users/{UID}/live_logs/{SYSTEM_ID}/{project_id}'"),
    (r"f'remote_terminals/\{SYSTEM_ID\}/\{project_id\}/\{terminal_id\}/logs'", r"f'users/{UID}/remote_terminals/{SYSTEM_ID}/{project_id}/{terminal_id}/logs'"),
    (r"f'remote_terminals/\{SYSTEM_ID\}/control\{path_key\}'", r"f'users/{UID}/remote_terminals/{SYSTEM_ID}/control{path_key}'"),
    (r"f'remote_terminals/\{SYSTEM_ID\}/\{project_id\}/active/\{term_id\}'", r"f'users/{UID}/remote_terminals/{SYSTEM_ID}/{project_id}/active/{term_id}'"),
    (r"f'remote_terminals/\{SYSTEM_ID\}/\{proj\}/active/\{term_id\}'", r"f'users/{UID}/remote_terminals/{SYSTEM_ID}/{proj}/active/{term_id}'"),
    (r"f'remote_terminals/\{SYSTEM_ID\}/\{proj\}/active'", r"f'users/{UID}/remote_terminals/{SYSTEM_ID}/{proj}/active'"),
    (r"f'pending_prompts/\{SYSTEM_ID\}'", r"f'users/{UID}/pending_prompts/{SYSTEM_ID}'"),
    (r"f'remote_terminals/\{SYSTEM_ID\}/control'", r"f'users/{UID}/remote_terminals/{SYSTEM_ID}/control'"),
    (r"f'pending_prompts/\{SYSTEM_ID\}\{event\.path\}'", r"f'users/{UID}/pending_prompts/{SYSTEM_ID}{event.path}'"),
    (r"f'pending_prompts/\{SYSTEM_ID\}/\{key\}'", r"f'users/{UID}/pending_prompts/{SYSTEM_ID}/{key}'")
]

for old, new in path_replacements:
    content = re.sub(old, new, content)

with open('daemon.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("daemon.py successfully patched.")
