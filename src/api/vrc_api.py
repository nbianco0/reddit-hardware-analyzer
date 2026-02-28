import os
import json
import requests
from dotenv import load_dotenv
from vrchatapi.configuration import Configuration
from vrchatapi.api_client import ApiClient

load_dotenv()

class VRChatClient:
    def __init__(self):
        self.username = os.getenv("VRC_USERNAME")
        self.password = os.getenv("VRC_PASSWORD")
        self.user_agent = os.getenv("VRC_USER_AGENT")
        self.cookie_file = "vrc_cookies.json"
        
        if not all([self.username, self.password, self.user_agent]):
            raise ValueError("Missing credentials in .env")

        # VRChat official SDK client
        self.config = Configuration()
        self.api_client = ApiClient(self.config)
        self.api_client.user_agent = self.user_agent

        # Session requests from VRCX
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self.api_base = "https://api.vrchat.cloud/api/1"

    def _load_cookies(self):
        if not os.path.exists(self.cookie_file):
            return False
        with open(self.cookie_file, "r") as f:
            cookies_dict = json.load(f)
        self.session.cookies.update(cookies_dict)
        return True

    def _save_cookies(self):
        with open(self.cookie_file, "w") as f:
            json.dump(
                requests.utils.dict_from_cookiejar(self.session.cookies),
                f
            )

    def _sync_cookies_to_api_client(self):
        cookie_string = "; ".join([
            f"{k}={v}" for k, v in self.session.cookies.items()
        ])
        self.api_client.cookie = cookie_string

    def authenticate(self):
        # Try cookie-based login
        if self._load_cookies():
            print("Trying saved cookies...")
            res = self.session.get(f"{self.api_base}/auth/user")
            data = res.json()

            if res.status_code == 200 and not data.get("requiresTwoFactorAuth"):
                print("✔ Logged in using saved cookies!")
                self._sync_cookies_to_api_client()
                return data
            
            print("✘ Cookies invalid or expired. Falling back to password.")
            self.session.cookies.clear()

        # Full login with BasicAuth (first-time only)
        print("Logging in with username and password...")
        res = self.session.get(
            f"{self.api_base}/auth/user",
            auth=(self.username, self.password),
            allow_redirects=False
        )

        if res.status_code == 401:
            raise ValueError("Invalid username or password.")

        data = res.json()

        # Handle 2FA
        requires_2fa = data.get("requiresTwoFactorAuth", [])

        if requires_2fa:
            if "emailOtp" in requires_2fa:
                code = input("Enter VRChat EMAIL 2FA code: ")
                url = f"{self.api_base}/auth/twofactorauth/emailotp/verify"
            else:
                code = input("Enter VRChat TOTP code: ")
                url = f"{self.api_base}/auth/twofactorauth/totp/verify"

            verify = self.session.post(url, json={"code": code}, allow_redirects=False)

            if verify.status_code != 200:
                raise ValueError(f"2FA failed: {verify.text}")

            # Sync cookies from verification
            self._sync_cookies_to_api_client()

            # Finalize login
            res = self.session.get(f"{self.api_base}/auth/user")

        print("✔ Logged in successfully!")
        self._save_cookies()
        self._sync_cookies_to_api_client()

        return res.json()

if __name__ == "__main__":
    client = VRChatClient()
    user_data = client.authenticate()
    print(f"Authenticated as: {user_data.get('displayName')}")

    from vrchatapi.api import users_api
    u_api = users_api.UsersApi(client.api_client)
    print("SDK test:", u_api.get_user(user_data["id"]).bio)