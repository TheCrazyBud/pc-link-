import firebase_admin
from firebase_admin import credentials, db
import time

if not firebase_admin._apps:
    cred = credentials.Certificate('vibe-daemon/serviceAccountKey.json')
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://pc-link-bca30-default-rtdb.firebaseio.com'})

ref = db.reference('remote_terminals/office_rig/control')
ref.push({
    'type': 'spawn',
    'status': 'pending',
    'timestamp': int(time.time() * 1000)
})
print("Spawn command pushed.")
time.sleep(2)
print("Active terminals:", db.reference('remote_terminals/office_rig/active').get())
