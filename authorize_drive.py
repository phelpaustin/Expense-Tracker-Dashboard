#!/usr/bin/env python3
# authorize_drive.py
"""
One-time Google Drive authorization for the Expense Tracker.

WHY: a Google *service account* (credentials.json) has no Drive storage
quota, so it cannot create files in a personal My Drive folder — uploads
fail with ``storageQuotaExceeded``. Logging in as a real Google user (whose
account has 15 GB) fixes receipt uploads and data-file sync.

SETUP (do this once):
  1. In Google Cloud Console → APIs & Services → Credentials, create an
     OAuth client ID of type **Desktop app**. Download the JSON and save it
     next to this script as:  oauth_client.json
     (Make sure the "Google Drive API" is enabled for the project, and add
     your Google account as a Test user on the OAuth consent screen.)
  2. Install the dependency:
        pip install google-auth-oauthlib
  3. Run this script:
        python3 authorize_drive.py
     A browser window opens — log in and grant access. A token.json file is
     written here and the app will use it automatically from then on.

The saved token refreshes itself; you only need to re-run this if you revoke
access or delete token.json.
"""
import os
import sys

from config import GOOGLE_DRIVE_SCOPE

CLIENT_FILE = "oauth_client.json"
TOKEN_FILE = "token.json"
SCOPES = [GOOGLE_DRIVE_SCOPE]


def main() -> int:
    if not os.path.exists(CLIENT_FILE):
        print(
            f"ERROR: '{CLIENT_FILE}' not found.\n"
            "Create an OAuth 'Desktop app' client in Google Cloud Console, "
            f"download it, and save it as '{CLIENT_FILE}' in this folder.\n"
            "See the instructions at the top of authorize_drive.py."
        )
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "ERROR: missing dependency. Install it with:\n"
            "    pip install google-auth-oauthlib"
        )
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())

    print(
        f"\n✅ Success! Saved credentials to '{TOKEN_FILE}'.\n"
        "The Expense Tracker will now upload receipts and sync data files "
        "to your Google Drive. Restart the app to pick up the change."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
