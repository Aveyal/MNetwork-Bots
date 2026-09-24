import aiohttp
from .auth import * # type: ignore

class LogoutError(Exception):
    pass
class BotClient:
    def __init__(self, token, username):
        self.token = token
        self.username = username
        self.session = self.session = aiohttp.ClientSession()
        self.base_url = "https://api.maltion.com"

    async def refresh(self, username, password):
        new_token = await login(username, password) # type: ignore
        self.token = new_token

    def _headers(self):
        return {
            "Cookie": f"session_token={self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def _request(self, method, url, *, raw=False,**kwargs):
        headers = self._headers()
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
        kwargs["headers"] = headers
        resp = await self.session.request(method, url, **kwargs)
        if resp.status == 401:
            try:
                data = await resp.json()
                if data.get("detail") == "You must log in to do this action.":
                    raise LogoutError("Session token expired or invalid")
            except Exception:
                pass
        if raw:
            return resp
        try:
            return await resp.json()
        except Exception:
            return await resp.text()

    
    async def get(self, path, *, raw=False):
        return await self._request("GET", self.base_url + path, raw=raw)

    async def post(self, path, json, *, raw=False):
        return await self._request("POST", self.base_url + path, json=json, raw=raw)

    async def close(self):
        await self.session.close()

    async def notify_me(self, message):
        async with aiohttp.ClientSession() as s: # type: ignore
            try:
                await s.post("(ntfy server)/relay", data=message)
            except BaseException as e:
                print(e)