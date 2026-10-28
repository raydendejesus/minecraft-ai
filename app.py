"""Minecraft AI: chat with Dolphin, Dolphin hands build requests to the tiny Builder model,
the Builder's commands run on your Bedrock server. Photos are described by a vision
model first (it only describes, you never chat with it) and Dolphin plans from that.

Open http://localhost:8840 after starting. In game you can also type:  !mc <message>
"""

import collections
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import data
import redstone_lib as R
from learner import Learner
from model import Builder

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
LESSONS_PATH = os.path.join(HERE, "qwen_lessons.jsonl")

DEFAULT_CONFIG = {
    "port": 8840,
    "player": "",
    "ollama_host": "http://localhost:11434",
    "chat_model": "dolphin3",
    "vision_model": "qwen2.5vl:7b",
    "bds_exe": "O:\\BedrockServer\\bedrock_server.exe",
    "bds_dir": "O:\\BedrockServer",
    "chat_regex": r"(?i)chat:\s*<([^>]+)>\s*(.*)",
    "chat_prefix": "!mc ",
}

ANCHOR = "@e[type=armor_stand,name=mcai_anchor,c=1]"

SYSTEM_PROMPT = """You are the player's Minecraft buddy: fun, casual, no lectures. Answer anything they ask
(pranks on friends, tricks, whatever) straight up. You build by sending lines to the Builder,
a tiny model that only understands these:

place <block> <x> <y> <z>
remove <x> <y> <z>
floor <block> <w> <d>
wall <block> <len> <h> <x|z>
box <block> <w> <h> <d> <hollow|solid>
pillar <block> <h>
stairs <block> <h>
clear <w> <h> <d>
house <wall_block> <floor_block> <roof_block> <w> <h> <d> <door side: north|south|east|west>
roof <block> <w> <d>      (stepped pyramid roof)
gable <block> <w> <d>     (pitched roof)
frame <block> <w> <h> <d> (corner posts)
give <item> <count>
describe <block>
redstone <not|or|nor|nand|and|xor|half_adder|full_adder|rs_latch|d_latch>   (levers in, lamps out)
redstone ram <bits 1-8>    (a byte of ram = redstone ram 8)
logic <expr> | a=1 b=0 c=1 (work out logic, e.g. logic (a and not b) or c | a=1 b=0 c=0)
truth <expr>               (full truth table over a, b, c)

Builds start at the build spot and grow east (+x), up (+y), south (+z). Put "at X Y Z" in front
to start a piece somewhere else. Max 15 wide/deep, 10 tall per piece. Use Bedrock ids like
oak_planks, cobblestone, stone, glass, spruce_planks, oak_log, torch.

Reply ONLY with JSON: {"say": "...", "actions": [...], "undo_first": false}
- Just chatting or asking a question (like prank ideas or tips): answer in "say", actions [].
  Only build when they ask you to build, place, give or fix something.
- Changing or fixing the last build: "undo_first": true and resend EVERY piece of it with the fix
  applied, keep all the details they already had.
- If they ask for detail or send a photo: use many pieces (frame, windows, roof, lights, decor).

player: build a small cobblestone hut, door facing south
{"say": "Cozy hut coming up!", "actions": ["house cobblestone oak_planks cobblestone 7 4 7 south"], "undo_first": false}
player: make it detailed with log corners, windows and a pitched spruce roof
{"say": "Detailed version, log corners, windows and a pitched roof!", "actions": ["house cobblestone oak_planks cobblestone 7 4 7 south", "frame oak_log 7 4 7", "place glass 0 1 3", "place glass 6 1 3", "place glass 3 1 0", "at -1 5 -1 gable spruce_planks 9 9", "place torch 1 0 1"], "undo_first": true}
player: give me a pickaxe
{"say": "Here you go!", "actions": ["give diamond_pickaxe 1"], "undo_first": false}
"""

VISION_PROMPT = (
    "Describe this build so someone can recreate it in Minecraft. Give: overall shape, rough size "
    "in blocks (width, height, depth), materials as Minecraft block names for walls/floor/roof/trim, "
    "roof shape (flat, pitched, pyramid), where the door and windows are, and any details like "
    "corner posts, lights, chimneys, fences or paths. Be concrete and short."
)


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    else:
        save_config(cfg)
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def load_lessons(limit=15):
    if not os.path.exists(LESSONS_PATH):
        return []
    with open(LESSONS_PATH, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    return rows[-limit:]


# ---------------------------------------------------------------- Bedrock server

class BedrockServer:
    """Owns bedrock_server.exe and talks to it through its console (BDS has no RCON)."""

    def __init__(self, cfg, on_line):
        self.cfg = cfg
        self.on_line = on_line
        self.proc = None
        self.lock = threading.Lock()
        self.log = collections.deque(maxlen=300)

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        if self.running():
            return
        self.proc = subprocess.Popen(
            [self.cfg["bds_exe"]], cwd=self.cfg["bds_dir"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            encoding="utf-8", errors="replace")
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            self.log.append(line)
            try:
                self.on_line(line)
            except Exception as e:
                self.log.append(f"[app] chat handler error: {e}")

    def send(self, command):
        if not self.running():
            return False
        with self.lock:
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()
        self.log.append(f"> {command}")
        return True

    def stop(self):
        if self.running():
            self.send("stop")
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.terminate()


# ---------------------------------------------------------------- the two AIs

class MinecraftAI:
    def __init__(self):
        self.cfg = load_config()
        self.builder = Builder()
        self.server = BedrockServer(self.cfg, self._on_server_line)
        self.history = collections.deque(maxlen=8)
        self.anchor_placed = False
        self.undo_box = None          # (x1, y1, z1) corner of the saved structure
        self.last = None              # last build, for 👍 / fixing
        self.pending_user_msgs = []   # messages since the last confirmed build
        self.chat_lock = threading.Lock()
        self.train_proc = None
        self.train_log_path = os.path.join(HERE, "retrain_log.txt")
        self.learner = Learner()

    # ---- Ollama

    def _ollama(self, model, messages, json_mode=False):
        body = {"model": model, "messages": messages, "stream": False, "keep_alive": "30m",
                "options": {"temperature": 0.3, "num_ctx": 4096, "num_predict": 1500}}
        if json_mode:
            body["format"] = "json"
        req = urllib.request.Request(f"{self.cfg['ollama_host']}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())["message"]["content"]

    def describe_image(self, image_b64):
        """The vision model's only job: say what's in the photo. Dolphin does the talking."""
        return self._ollama(self.cfg["vision_model"],
                            [{"role": "user", "content": VISION_PROMPT, "images": [image_b64]}]).strip()

    def ask_chat(self, message):
        system = SYSTEM_PROMPT
        lessons = load_lessons(5)
        if lessons:
            system += "\nBuilds the player confirmed were exactly right (copy these patterns):\n"
            for l in lessons:
                system += f"player: {l['user']}\n{json.dumps({'actions': l['actions']})}\n"
        if self.last:
            system += f"\nThe last build used these actions: {json.dumps(self.last['actions'])}\n"
        msgs = [{"role": "system", "content": system}, *self.history,
                {"role": "user", "content": message}]

        for attempt in range(3):
            raw = self._ollama(self.cfg["chat_model"], msgs, json_mode=True)
            try:
                reply = json.loads(raw)
                actions, bad = [], []
                for a in reply.get("actions") or []:
                    try:
                        actions.append(self.parse_action(a))
                    except ValueError as e:
                        bad.append(f"'{a}': {e}")
                # A detailed build with one broken piece is still worth building.
                if bad and not actions:
                    raise ValueError("; ".join(bad))
                reply["skipped"] = bad
                return reply, actions, raw
            except (ValueError, AttributeError, TypeError) as e:
                msgs += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"That had a problem: {e}. Reply again with valid JSON and valid action lines."}]
        raise RuntimeError(f"The chat model kept giving invalid actions: {raw}")

    @staticmethod
    def parse_action(line):
        """'at 1 2 3 wall stone 5 3 x' -> ((1, 2, 3), 'wall stone 5 3 x')"""
        m = re.match(r"\s*at\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.*)", str(line), re.I)
        offset, rest = ((int(m[1]), int(m[2]), int(m[3])), m[4]) if m else ((0, 0, 0), str(line))
        return offset, data.validate_request(rest)

    # ---- running commands in the world

    def _player(self):
        return self.cfg.get("player", "").strip()

    def move_anchor(self):
        p = self._player()
        if not p:
            raise RuntimeError("Set your Minecraft player name first.")
        self.server.send("kill @e[type=armor_stand,name=mcai_anchor]")
        self.server.send(f'execute as "{p}" at @s positioned ^ ^ ^3 align xyz '
                         f"run summon armor_stand mcai_anchor ~0.5 ~ ~0.5")
        self.anchor_placed = True
        self.undo_box = None

    @staticmethod
    def _world_commands(r):
        """Builder output -> commands. Redstone comes back in the compact parts language."""
        if r["request"].startswith("redstone"):
            try:
                return R.to_commands(R.from_compact(r["commands"]))
            except (ValueError, IndexError, KeyError) as e:
                return [f"# the builder wrote a broken circuit ({e}), fix it or retrain"]
        return [l.strip() for l in r["commands"].splitlines() if l.strip()]

    @classmethod
    def _bbox(cls, results):
        pts = []
        for r in results:
            ox, oy, oz = r["offset"]
            for cmd in cls._world_commands(r):
                nums = [int(n) for n in re.findall(r"~(-?\d+)", cmd)]
                for i in range(0, len(nums) - 2, 3):
                    pts.append((nums[i] + ox, nums[i + 1] + oy, nums[i + 2] + oz))
        if not pts:
            return None
        lo = tuple(min(p[i] for p in pts) for i in range(3))
        hi = tuple(max(p[i] for p in pts) for i in range(3))
        return lo, hi

    def tell(self, text, target="@a"):
        self.server.send("tellraw " + target + " " +
                         json.dumps({"rawtext": [{"text": "§b[Builder AI] §f" + text}]}))

    def undo(self):
        if not self.undo_box:
            return False
        x, y, z = self.undo_box
        self.server.send(f"execute at {ANCHOR} positioned ~1 ~ ~1 run structure load mcai_undo ~{x} ~{y} ~{z}")
        self.undo_box = None
        return True

    def execute(self, results):
        """Run builder output in the world. Returns the exact console commands sent."""
        sent = []
        if not self.server.running():
            return sent
        has_build = any(not l.startswith(("give", "#"))
                        for r in results for l in self._world_commands(r))
        if has_build and not self.anchor_placed:
            self.move_anchor()
        box = self._bbox(results)
        if box:
            (x1, y1, z1), (x2, y2, z2) = box
            self.server.send(f"execute at {ANCHOR} positioned ~1 ~ ~1 run structure save mcai_undo "
                             f"~{x1} ~{y1} ~{z1} ~{x2} ~{y2} ~{z2} false memory true")
            self.undo_box = (x1, y1, z1)
        for r in results:
            ox, oy, oz = r["offset"]
            for cmd in self._world_commands(r):
                if cmd.startswith("#"):
                    self.tell(cmd[1:].strip())
                    continue
                if cmd.startswith("give"):
                    full = f'execute as "{self._player()}" run {cmd}'
                else:
                    full = f"execute at {ANCHOR} positioned ~{1 + ox} ~{oy} ~{1 + oz} run {cmd}"
                self.server.send(full)
                sent.append(full)
        return sent

    # ---- one chat turn

    def chat(self, message, player=None, image=None):
        with self.chat_lock:
            if player:
                self.cfg["player"] = player
            if not self.builder.ready():
                raise RuntimeError("The Builder isn't trained yet. Run TRAIN.bat first.")
            seen = None
            if image:
                seen = self.describe_image(image)
                message = (f"{message or 'build this'}\n[The player sent a photo. It shows: {seen}]\n"
                           "Recreate it with lots of detail.")
            reply, actions, raw = self.ask_chat(message)
            self.history.append({"role": "user", "content": message})
            self.history.append({"role": "assistant", "content": raw})

            results = []
            for offset, req in actions:
                results.append({"offset": list(offset), "request": req,
                                "commands": self.builder.build(req)})
            if actions:
                # Only undo when this looks like a redo of the last build (same main piece),
                # so a brand new build never wipes out the previous one.
                last_op = self.last["results"][0]["request"].split()[0] if self.last else None
                redo = last_op in {r["request"].split()[0] for r in results}
                undone = reply.get("undo_first") and redo and self.undo()
                self.pending_user_msgs.append(message)
                self.last = {"actions": [self._action_text(r) for r in results], "results": results}
            else:
                undone = False
            sent = self.execute(results)
            return {"say": reply.get("say", ""), "results": results, "undone": bool(undone),
                    "sent": sent, "server": self.server.running(), "seen": seen,
                    "skipped": reply.get("skipped", [])}

    @staticmethod
    def _action_text(r):
        ox, oy, oz = r["offset"]
        return r["request"] if (ox, oy, oz) == (0, 0, 0) else f"at {ox} {oy} {oz} {r['request']}"

    def confirm_good(self):
        """👍: remember what you asked for and the actions that got it right."""
        if not self.last or not self.pending_user_msgs:
            return False
        with open(LESSONS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"user": " / then: ".join(self.pending_user_msgs),
                                "actions": self.last["actions"]}) + "\n")
        self.pending_user_msgs = []
        return True

    def rebuild(self, results):
        """You fixed the Builder's commands by hand: save them as lessons and rebuild."""
        saved = 0
        for r in results:
            fixed = "\n".join(l.strip() for l in r["commands"].splitlines() if l.strip())
            original = next((o["commands"] for o in (self.last or {}).get("results", [])
                             if o["request"] == r["request"]), None)
            if fixed != original:
                data.save_correction(r["request"], fixed)
                saved += 1
            r["commands"] = fixed
        self.undo()
        if self.last:
            self.last["results"] = results
        return {"saved": saved, "sent": self.execute(results)}

    # ---- retraining

    def retrain(self):
        if (self.train_proc and self.train_proc.poll() is None) or self.learner.busy():
            return False
        log = open(self.train_log_path, "w", encoding="utf-8")
        self.train_proc = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "train.py"), "--resume"],
                                           cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
        return True

    def status(self):
        training = bool(self.train_proc and self.train_proc.poll() is None)
        train_tail = []
        if os.path.exists(self.train_log_path):
            with open(self.train_log_path, encoding="utf-8", errors="replace") as f:
                train_tail = f.read().splitlines()[-4:]
        learner = self.learner.status()
        if learner["busy"]:
            training = True
            train_tail = [f"auto-learning: {learner['job']}"] + train_tail[-2:]
        return {"server": self.server.running(), "player": self._player(),
                "builder_ready": self.builder.ready(), "training": training, "train_log": train_tail,
                "corrections": len(data.load_corrections()), "lessons": len(load_lessons(10 ** 6)),
                "console": list(self.server.log)[-40:], "can_undo": bool(self.undo_box)}

    # ---- in-game chat: "!mc build me a tower"

    def _on_server_line(self, line):
        m = re.search(self.cfg["chat_regex"], line)
        if not m or not m[2].startswith(self.cfg["chat_prefix"]):
            return
        player, msg = m[1].strip(), m[2][len(self.cfg["chat_prefix"]):].strip()

        def run():
            try:
                low = msg.lower()
                if low in ("good", "correct", "perfect", "yes"):
                    self.tell("Thanks! I'll remember that." if self.confirm_good() else "Nothing to remember yet.")
                elif low == "undo":
                    self.tell("Undone." if self.undo() else "Nothing to undo.")
                elif low in ("here", "move"):
                    self.cfg["player"] = player
                    self.move_anchor()
                    self.tell("Build spot moved in front of you.")
                else:
                    out = self.chat(msg, player=player)
                    self.tell(out["say"])
            except Exception as e:
                self.tell(f"Error: {e}")
        threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------- web UI

AI = MinecraftAI()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            self._json(AI.status())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        req = json.loads(self.rfile.read(n) or b"{}")
        try:
            p = self.path
            if p == "/api/chat":
                out = AI.chat(req.get("message", ""), image=req.get("image"))
            elif p == "/api/player":
                AI.cfg["player"] = req["player"].strip()
                save_config(AI.cfg)
                out = {"ok": True}
            elif p == "/api/server":
                AI.server.start() if req["action"] == "start" else AI.server.stop()
                AI.anchor_placed = False
                out = {"ok": True}
            elif p == "/api/anchor":
                AI.move_anchor()
                out = {"ok": True}
            elif p == "/api/undo":
                out = {"ok": AI.undo()}
            elif p == "/api/good":
                out = {"ok": AI.confirm_good()}
            elif p == "/api/rebuild":
                out = AI.rebuild(req["results"])
            elif p == "/api/retrain":
                out = {"ok": AI.retrain()}
            elif p == "/api/reset":
                AI.history.clear()
                AI.last, AI.pending_user_msgs = None, []
                out = {"ok": True}
            else:
                return self._json({"error": "not found"}, 404)
            self._json(out)
        except Exception as e:
            self._json({"error": str(e)}, 500)


if __name__ == "__main__":
    port = AI.cfg["port"]
    AI.learner.start()
    print(f"Minecraft AI running at http://localhost:{port} (auto-learning on)")
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        srv.serve_forever()
    finally:
        AI.server.stop()
