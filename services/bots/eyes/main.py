#!/usr/bin/python3
from shared.bot_class import * # type: ignore
from shared.auth import * # type: ignore
import os
import asyncio
import time
import aiohttp
import json

password = os.getenv("PASS")

data = None

with open("bots/eyes/ids.json", "r") as f:
    data = json.load(f)

def save():
    global data
    with open("bots/eyes/ids.json", "w") as f:
        json.dump(data, f)

async def newCommunity(resp, client):
    global data
    com = resp["community"]
    name = com["name"]
    author = com["author_name"]
    desc = com["description"]
    await client.notify_me(
        f"New community #{data['community']}: {name}\n"
        f"By: {author}\n"
        f"Description: {desc}"
    )
    await client.post("/mnetwork/follow-community", {"id": data["community"]})
    data["community"] = data["community"] + 1
    save()

async def newUser(resp, client):
    global data
    name = resp["username"]
    await client.notify_me(
        f"New user #{data['user']}: {name}"
    )
    um = await client.post("/mnetwork/follow-user", {"user": name})
    print(str(um))
    data["user"] = data["user"] + 1
    save()

async def poll_ids(client):
    global data
    while True:
        try:
            m = await client.get(f"/mnetwork/get-community?community={data['community']}", raw=1)
            n = await client.get(f"/mnetwork/get-community?community={data['community']}")
            if m.status != 404:
                await newCommunity(n, client)
            o = await client.get(f"/get-user-by-id?id={data['user']}")
            if o.get("username", "") != "":
                await newUser(o, client)
        except LogoutError: # pyright: ignore[reportUndefinedVariable]
            await client.refresh("eyes", password)
        await asyncio.sleep(10)

async def notify_me2(message):
    async with aiohttp.ClientSession() as s: # type: ignore
        try:
            await s.post("(ntfy server)/relay", data=message)
        except BaseException as e:
            print(e)

async def run_bot():
    with open ("main.pid", "w") as f:
        f.write(str(os.getpid()))
    token = load_session("eyes") # type: ignore

    if token is None or not await validate_session(token, "eyes"): # type: ignore
        token = await login("eyes", password) # type: ignore

    client = BotClient(token, "eyes") # type: ignore
    try:
        await asyncio.gather(
            poll_ids(client)
        )
    finally:
        await client.close()

async def main():
    last_crash = 0
    while True:
        try:
            await run_bot()
        except Exception as e:
            now = time.time()
            if now - last_crash > 20:
                await notify_me2(f"eyes crashed: {e}")
            print("eyes crashed:", e)
            last_crash = now
            print("Restarting in 30 seconds...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
else:
    print("wth are you doing")