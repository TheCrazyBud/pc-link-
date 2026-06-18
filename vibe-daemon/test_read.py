import firebase_admin
from firebase_admin import credentials, db

if not firebase_admin._apps:
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://pc-link-bca30-default-rtdb.firebaseio.com'})

ref = db.reference('pending_prompts/office_rig')
print(ref.get())
