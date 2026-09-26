"""Small shared-workspace gate for invited online demo users, not a full user system."""
import base64
import binascii
import hmac
import time
from collections import deque
from app import config

attempts = {}
global_calls = deque()

def authorized(header):
    if not config.PUBLIC_DEPLOYMENT:
        return True
    try:
        scheme, value = header.split(' ', 1)
        if scheme.lower() != 'basic':
            return False
        username, password = base64.b64decode(value, validate=True).decode('utf-8').split(':', 1)
        return hmac.compare_digest(username.encode(), b'bolorder') and hmac.compare_digest(password.encode(), config.APP_ACCESS_PASSWORD.encode())
    except (ValueError, UnicodeError, binascii.Error):
        return False

def allow_request(identity, bucket, limit, window=60):
    now = time.monotonic()
    key = (identity, bucket)
    entries = attempts.setdefault(key, deque())
    while entries and entries[0] < now-window:
        entries.popleft()
    if len(entries) >= limit:
        return False
    entries.append(now)
    if len(attempts) > 2000:
        stale = [k for k, v in attempts.items() if not v or v[-1] < now-window]
        for k in stale:
            attempts.pop(k, None)
    return True

def allow_ai_call(identity):
    if not allow_request(identity, 'ai', 15):
        return False
    now = time.monotonic()
    while global_calls and global_calls[0] < now-60:
        global_calls.popleft()
    if len(global_calls) >= 40:
        return False
    global_calls.append(now)
    return True
