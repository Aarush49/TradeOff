"""Provision local accounts or reset a password without putting it in shell history."""
import argparse
import getpass
from pathlib import Path
from demo_auth import AccountStore, WORKSPACES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--auth-db', type=Path, default=Path(__file__).with_name('runtime')/'accounts.sqlite3')
    parser.add_argument('command', choices=['init', 'reset-password', 'create-user'])
    parser.add_argument('username', nargs='?')
    parser.add_argument('--workspace', choices=list(WORKSPACES))
    args = parser.parse_args()
    store = AccountStore(args.auth_db)
    if args.command == 'init':
        path = store.bootstrap()
        print(f'Initial credentials: {path}' if path else 'Accounts already exist; no passwords changed.')
        return
    if not args.username:
        parser.error('A username is required.')
    if args.command == 'create-user':
        if not args.workspace:
            parser.error('--workspace is required when creating a user.')
        with store.connect() as conn:
            if conn.execute('SELECT 1 FROM accounts WHERE username=?', (args.username,)).fetchone():
                parser.error('Account already exists. Use reset-password.')
    password = getpass.getpass('New password (at least 12 characters): ')
    if password != getpass.getpass('Confirm password: '):
        parser.error('Passwords do not match.')
    try:
        store.set_password(args.username, password, args.workspace if args.command == 'create-user' else None)
    except ValueError as exc:
        parser.error(str(exc))
    print(f'Password saved for {args.username}. Previous sessions are invalidated.')


if __name__ == '__main__':
    main()
