#!/usr/bin/python3
import asyncio
from shared.bot_class import * # pyright: ignore[reportMissingImports]
from shared.auth import * # pyright: ignore[reportMissingImports]
import time
import os
import signal
from collections import Counter
import traceback

password = os.getenv("PASS")
last_crash = 0
open_websockets = []

async def send_live_dm(friendName, content, client):
    ws = await client.session.ws_connect(f"wss://api.maltion.com/wss?friend_username={friendName}", headers={"Cookie": f"session_token={client.token}"})
    open_websockets.append(ws)
    await client.notify_me(f"sent message to {friendName}")
    await ws.send_json({"type": "message", "content": content})
    try:
        await asyncio.wait_for(ws.receive(), timeout=0.5)
    except asyncio.TimeoutError:
        pass
    await ws.close(code=1000, message=b"done")
    open_websockets.remove(ws)

async def pingsomeone(name, sender, client):
    author = sender.lower()
    name = name[1:] if name[0] == "@" else name
    resp = await client.get("/friend-list")
    friendlist = [d["recipient"] for d in resp if d["status"] == "accepted"]
    if name in (author, "me"):
        await send_live_dm(author, "Use \"ping\" by itself to ping yourself.", client)
    elif name not in friendlist:
        await send_live_dm(author, "That user isn't in my friendlist, sorry.", client)
    else:
        try:
            await send_live_dm(name.lower(), f"You got a ping from @{sender}!", client)
            await send_live_dm(author, "Ping successful (i think)", client)
            await client.notify_me(f"Ping from {author} to {name}")
        except Exception as e:
            traceback.print_exc()
            await send_live_dm(author, f"Something went wrong. Please tell @Aveyal.", client)
            await client.notify_me(f"I tried doing a relay but this happened: {e}")

async def welcome(friendName, client):
    payload = {
        "recipient": friendName,
        "content": "Hello, my name is Relay, the first DM bot on MNetwork! I'm still in testing. try pinging. i can take up to 10 seconds to respond"
    }
    await client.post("/send-dm", json=payload, raw=1)

async def checkpings(thedmcounts, client):
    tasks = [client.get(f"/get-dm?user={user}&limit={thedmcounts[user]}") for user in thedmcounts]
    result = await asyncio.gather(*tasks)
    dms = []
    for user_dms in result:
        dms.extend(user_dms)
    reply_tasks = []
    for dm in dms:
        content = dm["content"].strip().lower().split()
        if content[0].lower() == "ping":
            if len(content) == 1:
                reply_tasks.append(send_live_dm(dm["author_name"].lower(), "pong", client))
            elif len(content) == 2:
                reply_tasks.append(pingsomeone(content[1].lower(), dm["author_name"], client))
        elif content[0].lower() == "a,.uhcrs":
            resp = await client.get("/friend-list")
            friendlist = [d["recipient"] for d in resp if d["status"] == "accepted"]
            await client.notify_me(str(friendlist))
    if reply_tasks:
        await asyncio.gather(*reply_tasks)

async def get_notifications(client):
    data = await client.get("/notifications")
    notifs = data["notifications"]
    notifs = [n for n in notifs if not n["is_read"]]
    return notifs

async def poll_notifications(client):
    while True:
        try:
            n = await client.get("/notifications-preview")
            if n["notifications"] > 0:
                print("new notifications!")
                notifs = await get_notifications(client)
                newdms = Counter()
                for notif in notifs:
                    if notif["type"] == "friend_request":
                        await accept_request(notif["content"].split(" ")[0], client)
                    if notif["reference_type"] == "chat":
                        friendname = notif["content"].split(" ")[-1][1:]
                        newdms[friendname] += 1
                await checkpings(newdms, client)
        except LogoutError: # pyright: ignore[reportUndefinedVariable]
            await client.refresh("Relay", password)
        await asyncio.sleep(10)

async def accept_request(username, client):
    payload = {
        "friend_name": username,
        "message": "Relay is accepting a friend request"
    }
    resp = await client.post("/add-friend", json=payload, raw=1)
    print("STATUS OF ACCEPTING FRIEND REQUEST: "+str(resp.status))
    if resp.status == 500:
        print("Bro what")
        what = f"we got the 500 error again with {username}"
        print(what)
        await client.notify_me(what)
        await welcome(username, client)
    elif resp.status != 200:
        print("uh oh")
        body = await resp.text()
        error = f"Failed to accept friend request for {username}: {body}"
        print(error)
        await client.notify_me(error)
    else:
        msg = f"Accepted friend request from {username}"
        print(msg)
        await client.notify_me(msg)
        await welcome(username, client)

async def notify_me2(message):
    async with aiohttp.ClientSession() as s: # type: ignore
        try:
            await s.post("(ntfy server)/relay", data=message)
        except BaseException as e:
            print(e)

async def cleanup(tasks, client):
    if not tasks == 0:
        for task in tasks:
            task.cancel()
    while open_websockets:
        ws = open_websockets.pop()
        try:
            await ws.close(code=1000, message=b"shutdown")
            open_websockets.remove(ws)
        except:
            pass
    try:
        await client.close()
    except:
        pass

async def run_bot():
    with open ("main.pid", "w") as f:
        f.write(str(os.getpid()))
    token = load_session("Relay") # type: ignore

    if token is None or not await validate_session(token, "Relay"): # type: ignore
        token = await login("Relay", password) # type: ignore

    client = BotClient(token, "Relay") # type: ignore

    tasks = [
        asyncio.create_task(poll_notifications(client))
    ]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for task in done:
            exc = task.exception()
            if exc:
                raise exc
    finally:
        await cleanup(tasks, client)

async def main():
    last_crash = 0
    while True:
        try:
            await run_bot()
        except Exception as e:
            traceback.print_exc()
            now = time.time()
            if now - last_crash > 20:
                await notify_me2(f"RelayBot crashed: {e}")
                last_crash = now
            print("RelayBot crashed:", e)
            print("Restarting in 30 seconds...")
            await cleanup(0, "Wait")
            await asyncio.sleep(30)

def handle_sigterm(signum, frame):
    loop = asyncio.get_event_loop()
    loop.create_task(cleanup(0, "ha"))
    raise SystemExit()

signal.signal(signal.SIGTERM, handle_sigterm)

if __name__ == "__main__":
    asyncio.run(main())
else:
    print("what are you doing, this is not how you run this")
