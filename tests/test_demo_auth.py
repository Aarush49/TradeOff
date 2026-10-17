import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from demo_auth import AccountStore, session_cookie, SESSION_SECONDS


class PasswordAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.tmp.name)/'accounts.sqlite3', iterations=1000)
        self.store.set_password('Network_Coordinator', 'Test-password-123!', 'Coordinator')

    def tearDown(self):
        self.tmp.cleanup()

    def test_expiration_and_logout(self):
        with patch('demo_auth.time.time', return_value=1000):
            token, user = self.store.login('Network_Coordinator', 'Test-password-123!')
            self.assertEqual(user['role'], 'coordinator')
            self.assertEqual(self.store.current_user(session_cookie(token))['username'], 'Network_Coordinator')
        with patch('demo_auth.time.time', return_value=1000 + SESSION_SECONDS + 1):
            self.assertIsNone(self.store.current_user(session_cookie(token)))
        token, _ = self.store.login('Network_Coordinator', 'Test-password-123!')
        self.store.logout(session_cookie(token))
        self.assertIsNone(self.store.current_user(session_cookie(token)))
        self.assertIsNone(self.store.current_user('tradeoff_session=forged'))

    def test_wrong_credentials_and_attempt_limit(self):
        for username in ['Network_Coordinator', 'Unknown']:
            with self.assertRaisesRegex(ValueError, 'Invalid username or password'):
                self.store.login(username, 'wrong')
        for _ in range(8):
            with self.assertRaises(ValueError): self.store.login('Unknown', 'wrong')
        with self.assertRaisesRegex(ValueError, 'Too many'):
            self.store.login('Network_Coordinator', 'Test-password-123!')

    def test_reset_revokes_sessions_and_password_survives_restart(self):
        token, _ = self.store.login('Network_Coordinator', 'Test-password-123!')
        other = AccountStore(self.store.path, iterations=1000)
        other.set_password('Network_Coordinator', 'Replacement-123!')
        self.assertIsNone(self.store.current_user(session_cookie(token)))
        with self.assertRaises(ValueError): other.login('Network_Coordinator', 'Test-password-123!')
        self.assertEqual(other.login('Network_Coordinator', 'Replacement-123!')[1]['participant'], 'Coordinator')
        with other.connect() as conn:
            row = dict(conn.execute('SELECT * FROM accounts').fetchone())
        self.assertNotIn('Replacement-123!', str(row))

    def test_initial_credentials_are_private_and_not_regenerated(self):
        store = AccountStore(Path(self.tmp.name)/'fresh.sqlite3', iterations=1000)
        credentials = store.bootstrap()
        self.assertEqual(credentials.stat().st_mode & 0o777, 0o600)
        for line in credentials.read_text().splitlines()[2:]:
            username, password = line.split(': ')
            self.assertEqual(store.login(username, password)[1]['username'], username)
        self.assertIsNone(store.bootstrap())
