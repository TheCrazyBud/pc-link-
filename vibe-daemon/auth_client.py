import json
import threading
import time
import requests

class FirebaseEvent:
    def __init__(self, event_type, path, data):
        self.event_type = event_type
        self.path = path
        self.data = data

class DBReference:
    def __init__(self, client, path):
        self.client = client
        self.path = path.strip('/')

    def _get_url(self):
        url = f"{self.client.database_url}/{self.path}.json"
        if self.client.id_token:
            url += f"?auth={self.client.id_token}"
        return url

    def set(self, data):
        url = self._get_url()
        res = requests.put(url, json=data)
        res.raise_for_status()
        return res.json()

    def push(self, data):
        url = self._get_url()
        res = requests.post(url, json=data)
        res.raise_for_status()
        return res.json()

    def update(self, data):
        url = self._get_url()
        res = requests.patch(url, json=data)
        res.raise_for_status()
        return res.json()

    def delete(self):
        url = self._get_url()
        res = requests.delete(url)
        res.raise_for_status()
        return None
        
    def get(self):
        url = self._get_url()
        res = requests.get(url)
        res.raise_for_status()
        return res.json()

    def listen(self, callback):
        """Starts a background thread to listen to Server-Sent Events (SSE)."""
        def _listen_worker():
            url = self._get_url()
            # Firebase SSE headers
            headers = {'Accept': 'text/event-stream'}
            while True:
                try:
                    with requests.get(url, headers=headers, stream=True, timeout=None) as response:
                        response.raise_for_status()
                        event_type = None
                        for line in response.iter_lines():
                            if not line:
                                continue
                            line = line.decode('utf-8')
                            if line.startswith('event: '):
                                event_type = line[7:].strip()
                            elif line.startswith('data: '):
                                data_str = line[6:].strip()
                                if data_str == 'null':
                                    parsed_data = None
                                    path = "/"
                                else:
                                    try:
                                        payload = json.loads(data_str)
                                        parsed_data = payload.get('data')
                                        path = payload.get('path', '/')
                                    except json.JSONDecodeError:
                                        continue
                                
                                if event_type in ('put', 'patch'):
                                    event = FirebaseEvent(event_type, path, parsed_data)
                                    callback(event)
                except Exception as e:
                    print(f"[FIREBASE LISTENER ERROR] Connection lost on /{self.path}. Reconnecting in 5s... ({e})")
                    time.sleep(5)

        t = threading.Thread(target=_listen_worker, daemon=True)
        t.start()
        return t

class FirebaseAuthClient:
    def __init__(self, api_key, database_url):
        self.api_key = api_key
        self.database_url = database_url.rstrip('/')
        self.id_token = None
        self.refresh_token = None
        self.uid = None

    def sign_in_with_email_password(self, email, password):
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            data = res.json()
            self.id_token = data['idToken']
            self.refresh_token = data['refreshToken']
            self.uid = data['localId']
            return True, data
        else:
            return False, res.json()

    def refresh_auth_token(self, refresh_token):
        url = f"https://securetoken.googleapis.com/v1/token?key={self.api_key}"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            data = res.json()
            self.id_token = data['id_token']
            self.refresh_token = data['refresh_token']
            self.uid = data['user_id']
            return True, data
        else:
            return False, res.json()

    def reference(self, path):
        return DBReference(self, path)

# Global Mock equivalent to firebase_admin.db
class MockDB:
    def __init__(self, client):
        self.client = client
    def reference(self, path):
        return self.client.reference(path)
