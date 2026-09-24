import json 
import aiohttp
import os

def load_session(username):
    SESSION_FILE = "session.json"
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            return data.get(username)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None

async def validate_session(token, username):
    async with aiohttp.ClientSession(
        cookies={"session_token": token}
    ) as session:
        async with session.get("https://api.maltion.com/get-username") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("username") == username
            else:
                return False

async def login(username, password):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.maltion.com/login",
            json={"username": username, "password": password}
        ) as resp:
            response = await resp.text()
            print(response)
            if resp.status != 200:
                raise Exception(f"Login failed: {response}")

            # Extract the session cookie
            cookies = session.cookie_jar.filter_cookies("https://api.maltion.com")
            token = cookies.get("session_token").value
            data = {}
            if os.path.exists("session.json"):
                with open("session.json", "r") as f:
                    data = json.load(f)
            data[username] = token
            with open("session.json", "w") as f:
                json.dump(data, f, indent=4)
            return token