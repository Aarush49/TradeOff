"""Password authentication and expiring local sessions (standard library only)."""
from contextlib import contextmanager
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from http.cookies import SimpleCookie, CookieError

WORKSPACES = {
    'Coordinator': dict(role='coordinator', organization='TradeOff Network'),
    'Factory A': dict(role='factory', organization='Medical devices'),
    'Factory B': dict(role='factory', organization='Consumer electronics'),
    'Supplier S': dict(role='supplier', organization='Primary chip supplier'),
    'Supplier T': dict(role='supplier', organization='Alternative chip supplier'),
}
USERNAMES = {'Coordinator': 'Network_Coordinator', **{p: p.replace(' ', '_') for p in WORKSPACES if p != 'Coordinator'}}
SESSION_SECONDS = 8 * 60 * 60


def session_cookie(token, max_age=SESSION_SECONDS):
    return f'tradeoff_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}'


def token_from_cookie(header):
    try:
        cookie = SimpleCookie()
        cookie.load(header or '')
        return cookie['tradeoff_session'].value if 'tradeoff_session' in cookie else None
    except CookieError:
        return None


class AccountStore:
    def __init__(self, path, iterations=600_000):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.iterations = iterations
        self.sessions = {}
        self.failures = {}
        self.lock = threading.RLock()
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS accounts (username TEXT PRIMARY KEY, participant TEXT NOT NULL, salt TEXT NOT NULL, digest TEXT NOT NULL, iterations INTEGER NOT NULL, version TEXT NOT NULL)')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def set_password(self, username, password, participant=None):
        import re
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,63}', username):
            raise ValueError('Username must contain 3–64 letters, digits or underscores, starting with a letter.')
        if not isinstance(password, str) or not 12 <= len(password) <= 1024:
            raise ValueError('Password must contain 12–1024 characters.')
        with self.connect() as conn:
            previous = conn.execute('SELECT participant FROM accounts WHERE username=?', (username,)).fetchone()
            participant = participant if participant is not None else (previous['participant'] if previous else None)
            if participant not in WORKSPACES:
                raise ValueError('Choose a valid assigned workspace.')
            salt = secrets.token_hex(16)
            digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), self.iterations).hex()
            conn.execute('INSERT OR REPLACE INTO accounts VALUES (?,?,?,?,?,?)',
                         (username, participant, salt, digest, self.iterations, secrets.token_hex(16)))
        with self.lock:
            self.failures.clear()

    def bootstrap(self):
        """Create initial accounts once; never reset an existing installation."""
        import os
        credentials = self.path.with_name(self.path.stem + '-initial-credentials.txt')
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]:
                return None
            rows, lines = [], []
            for participant, username in USERNAMES.items():
                password = secrets.token_urlsafe(18)
                salt = secrets.token_hex(16)
                digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), self.iterations).hex()
                rows.append((username, participant, salt, digest, self.iterations, secrets.token_hex(16)))
                lines.append(f'{username}: {password}\n')
            # Exclusive creation prevents overwriting previously issued credentials.
            fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, 'w') as out:
                    out.write('TradeOff initial credentials. Keep private; delete after saving passwords securely.\n\n')
                    out.writelines(lines)
                    out.flush()
                    os.fsync(out.fileno())
                conn.executemany('INSERT INTO accounts VALUES (?,?,?,?,?,?)', rows)
                conn.commit()
            except Exception:
                credentials.unlink()
                raise
        return credentials

    def login(self, username, password, address='local'):
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 64 or len(password) > 1024:
            raise ValueError('Invalid username or password.')
        with self.lock:
            now = time.time()
            self.failures = {key: value for key, value in self.failures.items() if now - value[1] < 300}
            if self.failures.get(address, (0, 0))[0] >= 10:
                raise ValueError('Too many sign-in attempts. Try again in five minutes.')
            with self.connect() as conn:
                row = conn.execute('SELECT * FROM accounts WHERE username=?', (username,)).fetchone()
            salt = bytes.fromhex(row['salt']) if row else bytes(16)
            rounds = row['iterations'] if row else self.iterations
            digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, rounds).hex()
            if not hmac.compare_digest(digest, row['digest'] if row else '0' * 64) or row is None:
                count = self.failures.get(address, (0, now))[0]
                self.failures[address] = (count + 1, now)
                raise ValueError('Invalid username or password.')
            self.failures.pop(address, None)
            user = dict(username=username, participant=row['participant'], provider='password',
                        **WORKSPACES[row['participant']], expires_at=now + SESSION_SECONDS)
            token = secrets.token_urlsafe(32)
            self.sessions = {k: v for k, v in self.sessions.items() if v[0]['expires_at'] > now}
            if len(self.sessions) >= 256:
                del self.sessions[min(self.sessions, key=lambda k: self.sessions[k][0]['expires_at'])]
            self.sessions[token] = (user, row['version'])
            return token, user.copy()

    def current_user(self, header):
        token = token_from_cookie(header)
        with self.lock:
            entry = self.sessions.get(token)
            if entry and entry[0]['expires_at'] > time.time():
                with self.connect() as conn:
                    row = conn.execute('SELECT version FROM accounts WHERE username=?', (entry[0]['username'],)).fetchone()
                if row and row['version'] == entry[1]:
                    return entry[0].copy()
            self.sessions.pop(token, None)
        return None

    def logout(self, header):
        with self.lock:
            self.sessions.pop(token_from_cookie(header), None)
