"""
pugg_server.py — WebSocket relay server for Pug Lobby multiplayer.

Deploy this on Railway / Render / any free Python host.
It never stores messages — it just relays them between the two
clients that share the same lobby code.

Protocol (all messages are JSON strings):
  Client → Server:
    {"type": "create"}                         → server replies {"type":"created","code":"ABC123"}
    {"type": "join",   "code": "ABC123"}       → server relays {"type":"peer_joined","name":"Buster"} to host
    {"type": "name",   "name": "Buster"}       → announce your pug name after joining
    {"type": "chat",   "text": "hello!"}       → relayed to the other client in the lobby
    {"type": "pos",    "x": 400, "y": 900}     → relayed to the other client (position sync)
    {"type": "say",    "text": "BORK"}         → relayed to the other client (bubble text)
    {"type": "state",  "state": "sleeping"}    → relayed to the other client (bed/king state)

  Server → Client:
    {"type": "created",     "code": "ABC123"}
    {"type": "joined",      "peer_name": "Buster"}   ← sent to the host when peer connects
    {"type": "peer_name",   "name": "Buster"}         ← sent to the joiner with host's name
    {"type": "chat",        "name": "Buster", "text": "hello!"}
    {"type": "pos",         "x": 400, "y": 900}
    {"type": "say",         "text": "BORK"}
    {"type": "state",       "state": "sleeping"}
    {"type": "peer_left"}                             ← when the other user disconnects
    {"type": "error",       "msg": "..."}
"""

import asyncio
import json
import random
import string
import websockets
from websockets.server import WebSocketServerProtocol

# lobby_code → {"host": ws, "guest": ws|None, "host_name": str, "guest_name": str}
LOBBIES: dict[str, dict] = {}


def _make_code(length: int = 6) -> str:
    """Generate a unique uppercase alphanumeric lobby code."""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=length))
        if code not in LOBBIES:
            return code


def _lobby_for(ws: WebSocketServerProtocol) -> tuple[str, dict] | tuple[None, None]:
    for code, lobby in LOBBIES.items():
        if lobby["host"] is ws or lobby["guest"] is ws:
            return code, lobby
    return None, None


async def _send(ws: WebSocketServerProtocol, payload: dict):
    try:
        await ws.send(json.dumps(payload))
    except Exception:
        pass


async def _relay(sender: WebSocketServerProtocol, payload: dict):
    """Forward payload to the other person in the same lobby."""
    _, lobby = _lobby_for(sender)
    if lobby is None:
        return
    target = lobby["guest"] if lobby["host"] is sender else lobby["host"]
    if target is not None:
        await _send(target, payload)


async def handler(ws: WebSocketServerProtocol):
    print(f"[+] Connection from {ws.remote_address}")
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, {"type": "error", "msg": "Invalid JSON"})
                continue

            mtype = msg.get("type", "")

            # ── CREATE LOBBY ──────────────────────────────────────────────
            if mtype == "create":
                code = _make_code()
                LOBBIES[code] = {
                    "host":       ws,
                    "guest":      None,
                    "host_name":  msg.get("name", "Unknown"),
                    "guest_name": "",
                }
                await _send(ws, {"type": "created", "code": code})
                print(f"[Lobby] Created {code} by {ws.remote_address}")

            # ── JOIN LOBBY ────────────────────────────────────────────────
            elif mtype == "join":
                code = msg.get("code", "").upper().strip()
                if code not in LOBBIES:
                    await _send(ws, {"type": "error", "msg": "Lobby not found"})
                    continue
                lobby = LOBBIES[code]
                if lobby["guest"] is not None:
                    await _send(ws, {"type": "error", "msg": "Lobby is full"})
                    continue
                guest_name = msg.get("name", "Unknown")
                lobby["guest"]      = ws
                lobby["guest_name"] = guest_name
                # Tell the guest the host's name so it can label the remote pug
                await _send(ws, {"type": "joined", "peer_name": lobby["host_name"]})
                # Tell the host a guest arrived
                await _send(lobby["host"], {
                    "type":      "peer_joined",
                    "peer_name": guest_name,
                })
                print(f"[Lobby] {guest_name} joined {code}")

            # ── CHAT MESSAGE ──────────────────────────────────────────────
            elif mtype == "chat":
                _, lobby = _lobby_for(ws)
                if lobby is None:
                    continue
                name = (lobby["host_name"] if lobby["host"] is ws
                        else lobby["guest_name"])
                await _relay(ws, {"type": "chat", "name": name,
                                  "text": msg.get("text", "")})

            # ── POSITION SYNC ─────────────────────────────────────────────
            elif mtype == "pos":
                await _relay(ws, {
                    "type": "pos",
                    "x":    msg.get("x", 0),
                    "y":    msg.get("y", 0),
                    "dx":   msg.get("dx", 0),
                    "dy":   msg.get("dy", 0),
                })

            # ── SAY (speech bubble) ───────────────────────────────────────
            elif mtype == "say":
                await _relay(ws, {"type": "say", "text": msg.get("text", "")})

            # ── STATE (sleeping / king / normal) ──────────────────────────
            elif mtype == "state":
                await _relay(ws, {"type": "state", "state": msg.get("state", "normal")})

            else:
                await _send(ws, {"type": "error", "msg": f"Unknown type: {mtype}"})

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Clean up and notify peer
        code, lobby = _lobby_for(ws)
        if lobby is not None:
            peer = lobby["guest"] if lobby["host"] is ws else lobby["host"]
            if peer is not None:
                await _send(peer, {"type": "peer_left"})
            del LOBBIES[code]
            print(f"[Lobby] {code} closed (disconnect)")
        print(f"[-] Disconnected {ws.remote_address}")


async def main():
    import os
    port = int(os.environ.get("PORT", 8765))
    print(f"[Server] Listening on 0.0.0.0:{port}")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
