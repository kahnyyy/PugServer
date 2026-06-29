"""
pugg_server.py — WebSocket relay server for Pug Lobby multiplayer (N players).
"""

import asyncio, json, random, string, websockets
from websockets.server import WebSocketServerProtocol

# lobby_code → {"clients": {peer_id: {"ws": ws, "name": str}}}
LOBBIES: dict[str, dict] = {}
MAX_LOBBY_SIZE = 8  # ← change this to whatever you want

def _make_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=length))
        if code not in LOBBIES:
            return code

def _make_peer_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

def _lobby_and_id_for(ws) -> tuple:
    for code, lobby in LOBBIES.items():
        for pid, entry in lobby["clients"].items():
            if entry["ws"] is ws:
                return code, lobby, pid
    return None, None, None

async def _send(ws, payload: dict):
    try:
        await ws.send(json.dumps(payload))
    except Exception:
        pass

async def _broadcast(lobby: dict, payload: dict, exclude_ws=None):
    """Send payload to all clients in the lobby except exclude_ws."""
    for entry in lobby["clients"].values():
        if entry["ws"] is not exclude_ws:
            await _send(entry["ws"], payload)

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

            if mtype == "create":
                code = _make_code()
                pid  = _make_peer_id()
                name = msg.get("name", "Unknown")
                LOBBIES[code] = {"clients": {pid: {"ws": ws, "name": name}}}
                await _send(ws, {"type": "created", "code": code, "peer_id": pid})
                print(f"[Lobby] Created {code} by {name}")

            elif mtype == "join":
                code = msg.get("code", "").upper().strip()
                if code not in LOBBIES:
                    await _send(ws, {"type": "error", "msg": "Lobby not found"})
                    continue
                lobby = LOBBIES[code]
                if len(lobby["clients"]) >= MAX_LOBBY_SIZE:
                    await _send(ws, {"type": "error", "msg": f"Lobby is full (max {MAX_LOBBY_SIZE})"})
                    continue
                pid  = _make_peer_id()
                name = msg.get("name", "Unknown")
                # Tell the joiner about everyone already in the lobby
                existing = [{"peer_id": p, "name": e["name"]}
                            for p, e in lobby["clients"].items()]
                await _send(ws, {"type": "joined", "peer_id": pid,
                                 "peers": existing})
                # Tell everyone else a new peer arrived
                await _broadcast(lobby, {"type": "peer_joined",
                                         "peer_id": pid, "peer_name": name})
                lobby["clients"][pid] = {"ws": ws, "name": name}
                print(f"[Lobby] {name} ({pid}) joined {code} "
                      f"({len(lobby['clients'])}/{MAX_LOBBY_SIZE})")

            elif mtype in ("chat", "pos", "say", "state"):
                code, lobby, pid = _lobby_and_id_for(ws)
                if lobby is None:
                    continue
                name = lobby["clients"][pid]["name"]
                # Attach sender's peer_id so receivers know which remote pug to update
                payload = {**msg, "peer_id": pid}
                if mtype == "chat":
                    payload["name"] = name
                await _broadcast(lobby, payload, exclude_ws=ws)

            else:
                await _send(ws, {"type": "error", "msg": f"Unknown type: {mtype}"})

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        code, lobby, pid = _lobby_and_id_for(ws)
        if lobby is not None:
            name = lobby["clients"][pid]["name"]
            del lobby["clients"][pid]
            print(f"[Lobby] {name} left {code}")
            if not lobby["clients"]:
                del LOBBIES[code]
                print(f"[Lobby] {code} empty, removed")
            else:
                await _broadcast(lobby, {"type": "peer_left", "peer_id": pid})
        print(f"[-] Disconnected {ws.remote_address}")

async def main():
    import os
    port = int(os.environ.get("PORT", 8765))
    print(f"[Server] Listening on 0.0.0.0:{port} (max {MAX_LOBBY_SIZE}/lobby)")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
