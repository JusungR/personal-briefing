#!/usr/bin/env python3
"""
Google OAuth 최초 인증 스크립트 (로컬에서 한 번만 실행)

실행 후 출력된 JSON을 GitHub Secret 'GOOGLE_TOKEN_JSON'에 저장하세요.
"""

import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main():
    print("Google OAuth 인증을 시작합니다.")
    print("Google Cloud Console에서 다운로드한 credentials.json 파일이 필요합니다.\n")

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }

    print("\n" + "=" * 60)
    print("아래 JSON을 복사해서 GitHub Secret 'GOOGLE_TOKEN_JSON'에 저장하세요:")
    print("=" * 60)
    print(json.dumps(token_data, indent=2))


if __name__ == "__main__":
    main()
