import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk
import imageio.v2 as imageio
import threading
import queue
import random
import pyttsx3
import sys
import ctypes
import ctypes.wintypes
import numpy as np
import time

# --- DEPENDENCIES FOR NEW CHAOTIC FEATURES ---
try:
    import pygetwindow as gw
    import pyautogui
except ImportError:
    gw = None
    pyautogui = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

LOCKED_VOLUME_PCT = 0.05

class VolumeLock:
    def __init__(self, target: float = LOCKED_VOLUME_PCT):
        self._target = target
        self._active = False
        self._volume = None
        self._callback = None
        try:
            self._setup()
        except Exception as e:
            print(f"[VolumeLock] Could not initialise (pycaw installed?): {e}")

    def _setup(self):
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from pycaw.callbacks import AudioEndpointVolumeCallback
        import comtypes

        comtypes.CoInitialize()

        speaker = AudioUtilities.GetSpeakers()
        if hasattr(speaker, 'Activate'):
            interface = speaker.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        elif hasattr(speaker, '_dev'):
            interface = speaker._dev.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        else:
            from pycaw.pycaw import IMMDeviceEnumerator, EDataFlow, ERole, CLSID_MMDeviceEnumerator
            enumerator = comtypes.CoCreateInstance(
                CLSID_MMDeviceEnumerator,
                IMMDeviceEnumerator,
                comtypes.CLSCTX_ALL,
            )
            endpoint = enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
            interface = endpoint.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        self._volume = interface.QueryInterface(IAudioEndpointVolume)

        self._apply()

        apply_fn = self._apply

        class _Callback(AudioEndpointVolumeCallback):
            _suppress = False

            def OnNotify(self, pNotify):
                if self._suppress:
                    return
                self._suppress = True
                try:
                    apply_fn()
                finally:
                    self._suppress = False

        self._callback = _Callback()
        self._volume.RegisterControlChangeNotify(self._callback)
        self._active = True
        print(f"[VolumeLock] Volume locked to {int(self._target * 100)}%")

    def _apply(self):
        if self._volume is not None:
            try:
                self._volume.SetMasterVolumeLevelScalar(self._target, None)
                self._volume.SetMute(False, None)
            except Exception:
                pass

    def change_target(self, delta: float) -> float:
        """Adjusts the lock target dynamically. Keeps volume bound above 5%. Returns new level."""
        self._target = max(0.05, min(1.0, self._target + delta))
        self._apply()
        print(f"[VolumeLock] Target updated to: {int(self._target * 100)}%")
        return self._target

    def release(self):
        if self._active and self._volume is not None and self._callback is not None:
            try:
                self._volume.UnregisterControlChangeNotify(self._callback)
            except Exception:
                pass
        self._active = False
        try:
            import comtypes
            comtypes.CoUninitialize()
        except Exception:
            pass


# =========================
# CONFIG
# =========================
VIDEO_PATH        = r"J:\mr potato head\dog.mp4"
KING_VIDEO_PATH   = r"J:\mr potato head\king pug.mp4"
LICK_SOUND_PATH   = r"J:\mr potato head\slurpBASEBOOSTED.wav"
BED_PNG_PATH      = r"J:\mr potato head\bed bg.png"
SLEEP_SOUND_PATH  = r"J:\mr potato head\sleepy.mp3"
THRONE_PNG_PATH   = r"J:\mr potato head\throne.png"
POOP_PNG_PATH     = r"J:\mr potato head\poop.png"
DIRT_PNG_PATH     = r"J:\mr potato head\dirt.png"
BALL_PNG_PATH     = r"J:\mr potato head\Ball.png"
POOP_SOUND_PATH   = r"J:\mr potato head\poopSound.mp3"
BOUNCE_SOUND_PATH = r"J:\mr potato head\bounce.mp3"
SHREDDER_PNG_PATH = r"J:\mr potato head\Shredder.png"
SHRED_SOUND_PATH  = r"J:\mr potato head\ShredSound.mp3"
SAD_SOUND_PATH    = r"J:\mr potato head\SadSong.wav"
GUN_PNG_PATH      = r"J:\mr potato head\gun.png"
GUNSHOT_SFX_PATH  = r"J:\mr potato head\gunshooy.mp3"

SPRITE_SIZE          = (250, 150)
SPRITE_FLOOR_OFFSET  = 0

# Physics constants
GRAVITY           = 0.18
BOUNCE_DAMPING    = 0.72   
MIN_BOUNCE_SPEED  = 1.2    
WANDER_SPEED      = 4
JUMP_SPEED_X      = 7
JUMP_SPEED_Y      = -14

# State monitoring flags
POWERSHELL_TRIGGERED = False

IDLE_MESSAGES = [
    "im watching u",
    "hello human",
    "hi",
    "meow detected",
    "roman hubbard",
    "lick lick lick",
    "zooming around!",
    "where did everyone come from?",
]

DRAG_MESSAGES = [
    "UNHAND ME!",
    "Where are we going?",
    "Put me down, human!",
    "AEEIIIHHH!",
]

FRIEND_NAMES = [
    "TuffGuy", "Buster", "Spike", "Waffles", "Chonker", "Nugget", "Scrappy",
    "Aturo JR", "Logan", "Ms Allen", "The Hounde", "dog", "Chomper", "Ripper",
    "Killer", "Destroyer of Worlds", "Sunshine && Rainbows", "Caleb Clancey",
    "😊😊😊", "Aturo", "Hunter", "Finn"
]

CACHED_PIL_FRAMES: list[Image.Image] = []
CACHED_KING_FRAMES: list[Image.Image] = []

PUG_PERSONALITY: dict[str, dict] = {
    "TuffGuy": {
        "idle":  ["I fear nothing", "back off", "DO NOT TEST ME", "yeah thats right", "im built different"],
        "drag":  ["BIG MISTAKE", "YOU WILL REGRET THIS", "put me down or else"],
        "chat":  ["I don't talk to strangers", "...", "what do you want", "leave me alone"],
    },
    "Buster": {
        "idle":  ["bork bork", "i am speed", "sniff sniff", "wanna play?", "BUSTER MODE ACTIVATED"],
        "drag":  ["BORK!", "not again!!", "wheeeee??"],
        "chat":  ["BORK", "wanna throw the ball?", "bork bork bork", "im a good boy"],
    },
    "Spike": {
        "idle":  ["spiiiike", "too cool for this", "yeah whatever", "dont look at me"],
        "drag":  ["watch the spikes bro", "RUDE", "ugh seriously"],
        "chat":  ["cool story", "meh", "whatever human", "spike dont care"],
    },
    "Waffles": {
        "idle":  ["syrup?", "i am waffle", "crispy on the outside", "square shaped thoughts", "waffle time"],
        "drag":  ["my syrup!!", "WAFFLE EMERGENCY", "nooo the waffle"],
        "chat":  ["do you like waffles?", "waffle waffle waffle", "im delicious", "square life"],
    },
    "Chonker": {
        "idle":  ["need food", "very chonk", "more food pls", "i am big", "chonk chonk chonk"],
        "drag":  ["TOO MUCH EXERCISE", "put me near food", "i am heavy"],
        "chat":  ["feed me", "food?", "i am merely big boned", "chonk"],
    },
    "Nugget": {
        "idle":  ["tiny but mighty", "nugget power", "small dog big dreams", "i am nugget"],
        "drag":  ["PUT DOWN THE NUGGET", "unhand the nugget!!", "nugget distress!!"],
        "chat":  ["nugget", "tiny and proud", "do not underestimate nugget", "nugget says hi"],
    },
    "Scrappy": {
        "idle":  ["lets fight", "come at me", "i scrappy", "who wants it", "SCRAPPY MODE"],
        "drag":  ["FIGHT ME", "you asked for this", "SCRAPPY WILL REMEMBER THIS"],
        "chat":  ["lets go", "i will fight you", "scrappy dont back down", "bring it"],
    },
    "Aturo JR": {
        "idle":  ["i am small but mighty", "mini pug comin thru", "tiny aturo", "jr reporting for duty", "smol boi"],
        "drag":  ["TINY DOG BIG SCREAMS", "put down the junior!!", "jr does not consent"],
        "chat":  ["i am aturo jr", "small but deadly", "junior is here", "dont let the size fool u"],
    },
    "Logan": {
        "idle":  ["logan here", "whats good", "just vibing", "its giving pug energy", "lowkey iconic", "for the boys"],
        "drag":  ["NOT COOL BRO", "logan out", "bruh"],
        "chat":  ["bruh", "lowkey dont care", "vibes", "what do you want logan says"],
    },
    "Ms Allen": {
        "idle":  ["CDT assignments due", "sit down class", "no running in the halls", "eyes on me", "detention incoming"],
        "drag":  ["THIS IS INAPPROPRIATE", "see me after class", "WRITE THIS DOWN"],
        "chat":  ["do your homework", "that will be an essay", "eyes forward", "participation grade: zero"],
    },
    "The Hounde": {
        "idle":  ["THE HOUNDE APPROACHES", "none shall pass", "i am ancient", "the hounde watches"],
        "drag":  ["THE HOUNDE IS DISPLEASED", "RELEASE THE HOUNDE", "thou shalt not"],
        "chat":  ["the hounde speaks", "bow before the hounde", "i have been here forever", "the hounde knows all"],
    },
    "dog": {
        "idle":  ["dog", "woof", "dog dog dog", "i am dog"],
        "drag":  ["dog", "woof", "DOG"],
        "chat":  ["dog", "woof", "dog."],
    },
    "Chomper": {
        "idle":  ["*chomp*", "everything looks tasty", "nom nom nom", "do not put fingers near"],
        "drag":  ["I WILL BITE", "CHOMPER CHOMPS", "you asked for it"],
        "chat":  ["nom", "i will eat that", "chomp chomp", "tasty"],
    },
    "Ripper": {
        "idle":  ["RIP AND TEAR", "nothing survives", "ripper is here", "destruction imminent"],
        "drag":  ["YOU DARE LIFT RIPPER", "RIPPER WILL RIP", "TEAR TEAR TEAR"],
        "chat":  ["rip", "tear", "ripper tears everything", "destruction is beauty"],
    },
    "Killer": {
        "idle":  ["dont let the name fool u", "im actually very gentle", "killer of hearts", "lethal cuteness"],
        "drag":  ["unhand killer", "killler does not enjoy this", "KILLER STRIKES BACK"],
        "chat":  ["i am killer", "despite the name im friendly", "deadly cute", "killer approves"],
    },
    "Destroyer of Worlds": {
        "idle":  ["world #1 destroyed", "currently destroying world #2", "annihilation in progress", "your world is next"],
        "drag":  ["THE DESTROYER CANNOT BE CONTAINED", "RELEASE THE DESTROYER", "WORLDS WILL PAY"],
        "chat":  ["which world would you like destroyed", "destruction is my passion", "i have already destroyed 7 worlds today", "tuesday is a good day to destroy worlds"],
    },
    "Sunshine && Rainbows": {
        "idle":  ["everything is wonderful 🌈", "so happy!!", "love u all", "spreading joy", "🌟✨💖"],
        "drag":  ["oh no!! but i still love u!!", "sunshine does not judge 🌈", "this is fine!! 💕"],
        "chat":  ["love and light!!", "you are wonderful", "rainbows for everyone", "happiness intensifies 🌈"],
    },
    "Caleb Clancey": {
        "idle":  ["caleb clancey in the building", "clancey reporting", "i sure do like carrots", "caleb knows whats up", "silksong silksong", "hollow knight love"],
        "drag":  ["CALEB CLANCEY DOES NOT APPRECIATE THIS", "unhand clancey", "clancey is not impressed", "i cant beat grandmaster lobby"],
        "chat":  ["caleb clancey here", "the clancey has spoken", "clancey approves", "ask clancey", "celeste is too hard"],
    },
    "😊😊😊": {
        "idle":  ["😊", "😊😊", "😊😊😊", "😊😊😊😊", "😊😊😊😊😊"],
        "drag":  ["😊", "😊😊😊", "😊😊😊😊😊😊"],
        "chat":  ["😊", "😊😊😊", "😊😊😊😊😊😊😊😊😊"],
    },
    "Aturo": {
        "idle":  ["I love spelling be", "lwokeu kinda hungry", "cdt results soon right guys", "happy happy aturo", "aturo aturo aturo"],
        "drag":  ["where is aturo juinor", "aturo atur", "let go of me"],
        "chat":  ["i am art ro", "lick pug lick", "are u talk bout me"],
    },
    "Hunter": {
        "idle":  ["straight execelle", "not chat gpt", "this is excellence level", "uhhhhh shit", "uhhhhhhhhhh"],
        "drag":  ["uhhhhhh fuck", "neh neh neh neh", "im just a babebe"],
        "chat":  ["i am hunter the mendoza", "i grab u hand", "hunter is that you"],
    },
}

def pre_load_video(path, target_list):
    try:
        reader = imageio.get_reader(path)
        for frame in reader:
            frame = frame.copy()
            black_pixels = (frame[:, :, 0] == 0) & (frame[:, :, 1] == 0) & (frame[:, :, 2] == 0)
            frame[black_pixels] = [1, 1, 1]
            image = Image.fromarray(frame).convert("RGB")
            image.thumbnail(SPRITE_SIZE)
            target_list.append(image)
        print(f"Cached {len(target_list)} animation frames for {path}.")
    except Exception as e:
        print(f"Failed to cache animation {path}: {e}")

# =========================
# SPEECH ENGINE
# =========================
class SpeechEngine:
    def __init__(self):
        self._queue: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def say(self, text: str):
        self._queue.put(text)

    def _worker(self):
        engine = pyttsx3.init()
        while True:
            text = self._queue.get()
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass

_speech = SpeechEngine()

# =========================
# AUDIO HELPERS
# =========================
def play_lick():
    def _play():
        try:
            import winsound
            winsound.PlaySound(LICK_SOUND_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            pass
    threading.Thread(target=_play, daemon=True).start()

def play_lick_loop(stop_event: threading.Event):
    def _loop():
        try:
            import winsound
            while not stop_event.is_set():
                winsound.PlaySound(LICK_SOUND_PATH, winsound.SND_FILENAME)
        except Exception:
            pass
    threading.Thread(target=_loop, daemon=True).start()

def play_mp3(file_path):
    def _play():
        try:
            winmm = ctypes.windll.winmm
            alias = f"mp3_{random.randint(0, 100000)}"
            winmm.mciSendStringW(f'open "{file_path}" type mpegvideo alias {alias}', None, 0, 0)
            winmm.mciSendStringW(f'play {alias}', None, 0, 0)
        except Exception as e:
            print(f"MCI Playback failed: {e}")
    threading.Thread(target=_play, daemon=True).start()

def play_bounce():
    play_mp3(BOUNCE_SOUND_PATH)

def play_poop_sound():
    play_mp3(POOP_SOUND_PATH)

def play_shred_sound():
    play_mp3(SHRED_SOUND_PATH)

def play_sad_sound():
    def _play():
        try:
            import winsound
            winsound.PlaySound(SAD_SOUND_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            play_mp3(SAD_SOUND_PATH)
    threading.Thread(target=_play, daemon=True).start()

def play_gunshot():
    play_mp3(GUNSHOT_SFX_PATH)


def _show_volume_toast(level: float):
    """Show a brief on-screen indicator of the current locked volume level."""
    if not manager.main_root:
        return
    try:
        pct = int(round(level * 100))
        bar_filled = int(pct / 5)           # 20 blocks max
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        msg = f"🔊 Volume: {pct}%\n{bar}"

        toast = tk.Toplevel(manager.main_root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg="#111111")
        toast.attributes("-alpha", 0.88)

        lbl = tk.Label(
            toast, text=msg,
            font=("Consolas", 13, "bold"),
            fg="#00ff88", bg="#111111",
            padx=18, pady=10,
            justify="left"
        )
        lbl.pack()

        toast.update_idletasks()
        sw = toast.winfo_screenwidth()
        sh = toast.winfo_screenheight()
        w  = toast.winfo_reqwidth()
        h  = toast.winfo_reqheight()
        # Bottom-right corner, above taskbar
        try:
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
            floor_y = rect.bottom
        except Exception:
            floor_y = sh
        toast.geometry(f"+{sw - w - 20}+{floor_y - h - 10}")

        # Auto-dismiss after 2 seconds
        toast.after(2000, toast.destroy)
    except Exception as e:
        print(f"[VolumeToast] Failed: {e}")



# =========================
# BULLET
# =========================
class DesktopBullet:
    SIZE = 14

    def __init__(self, root_parent: tk.Misc, x: float, y: float, direction: int, owner_gun: "DesktopGun"):
        self._owner_gun = owner_gun
        self.x   = x
        self.y   = y
        self.dx  = direction * 28
        self._destroyed = False

        self.win = tk.Toplevel(root_parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black")
        self.win.wm_attributes("-transparentcolor", "black")

        self._lbl = tk.Label(self.win, text="•", font=("Arial Black", 16, "bold"),
                             fg="yellow", bg="black", bd=0)
        self._lbl.pack()
        self.win.geometry(f"{self.SIZE}x{self.SIZE}+{int(self.x)}+{int(self.y)}")
        self._after_id = None
        self._move()

    def _move(self):
        if self._destroyed:
            return
        try:
            if not self.win.winfo_exists():
                self._cleanup()
                return
        except Exception:
            self._cleanup()
            return

        self.x += self.dx
        sw = self.win.winfo_screenwidth()

        if self.x < -40 or self.x > sw + 40:
            self._cleanup()
            return

        for buddy in list(manager.active_buddies):
            if buddy is self._owner_gun.attached_to:
                continue
            if (buddy.current_x <= self.x <= buddy.current_x + buddy.width and
                    buddy.current_y <= self.y <= buddy.current_y + buddy.height):
                self._cleanup()
                manager.unregister(buddy)
                try:
                    buddy.bubble_win.destroy()
                except Exception:
                    pass
                try:
                    buddy.root.destroy()
                except Exception:
                    pass
                if not manager.active_buddies:
                    manager.clear_throne()
                    if manager.active_shredder:
                        manager.active_shredder.destroy()
                    if manager.scratch_canvas:
                        manager.scratch_canvas.wash_clean()
                    for ball in list(manager.active_toys):
                        ball.destroy()
                    for gun in list(manager.active_guns):
                        gun.destroy()
                    if manager.main_root:
                        try:
                            manager.main_root.destroy()
                        except Exception:
                            pass
                return

        try:
            self.win.geometry(f"{self.SIZE}x{self.SIZE}+{int(self.x)}+{int(self.y)}")
        except Exception:
            self._cleanup()
            return
        self._after_id = self.win.after(16, self._move)

    def _cleanup(self):
        if self._destroyed:
            return
        self._destroyed = True
        try:
            self._owner_gun.active_bullets.discard(self)
        except Exception:
            pass
        if self._after_id:
            try:
                self.win.after_cancel(self._after_id)
            except Exception:
                pass
        try:
            self.win.destroy()
        except Exception:
            pass


# =========================
# GUN
# =========================
class DesktopGun:
    GUN_SIZE = (80, 50)
    MAX_BULLETS = 2
    FIRE_INTERVAL_MS = 3000

    def __init__(self, root_parent: tk.Misc):
        self._root_parent = root_parent
        self.attached_to: "DesktopBuddy | None" = None
        self.active_bullets: set = set()
        self._fire_after_id = None
        self._destroyed = False

        self.win = tk.Toplevel(root_parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black")
        self.win.wm_attributes("-transparentcolor", "black")

        try:
            img = Image.open(GUN_PNG_PATH).convert("RGBA")
            img.thumbnail(self.GUN_SIZE)
            self._tk_img = ImageTk.PhotoImage(img)
            self.width, self.height = img.size
            self._lbl = tk.Label(self.win, image=self._tk_img, bg="black", bd=0)
        except Exception as e:
            print(f"[Gun] Could not load gun PNG: {e}")
            self._tk_img = None
            self.width, self.height = 60, 30
            self._lbl = tk.Label(self.win, text="🔫", font=("Arial", 24), bg="black", bd=0)
        self._lbl.pack()

        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.x = float(sw // 2)
        self.y = float(sh // 2)
        self.win.geometry(f"{self.width}x{self.height}+{int(self.x)}+{int(self.y)}")

        self._drag_ox = 0
        self._drag_oy = 0
        self._lbl.bind("<Button-1>",        self._start_drag)
        self._lbl.bind("<B1-Motion>",       self._on_drag)
        self._lbl.bind("<ButtonRelease-1>", self._stop_drag)
        self._lbl.bind("<Button-3>",        self._on_right_click)

        manager.active_guns.append(self)

    def _start_drag(self, event):
        if self.attached_to is not None:
            return
        self._drag_ox = event.x
        self._drag_oy = event.y

    def _on_drag(self, event):
        if self.attached_to is not None:
            return
        self.x = float(self.win.winfo_x() + event.x - self._drag_ox)
        self.y = float(self.win.winfo_y() + event.y - self._drag_oy)
        self.win.geometry(f"{self.width}x{self.height}+{int(self.x)}+{int(self.y)}")

    def _stop_drag(self, event):
        if self.attached_to is not None:
            return
        for buddy in manager.active_buddies:
            if (buddy.current_x <= self.x <= buddy.current_x + buddy.width and
                    buddy.current_y <= self.y <= buddy.current_y + buddy.height):
                self._attach(buddy)
                return

    def _attach(self, buddy):
        self.attached_to = buddy
        buddy.has_gun = self
        buddy.say("ARMED AND DANGEROUS 🔫")
        self._schedule_fire()

    def _schedule_fire(self):
        if self._destroyed or self.attached_to is None:
            return
        self._fire_after_id = self.win.after(self.FIRE_INTERVAL_MS, self._fire)

    def _fire(self):
        if self._destroyed or self.attached_to is None:
            return
        buddy = self.attached_to
        try:
            if not buddy.root.winfo_exists():
                self._detach()
                return
        except Exception:
            self._detach()
            return

        if len(self.active_bullets) < self.MAX_BULLETS:
            direction = 1 if buddy.dx >= 0 else -1
            bx = buddy.current_x + (buddy.width if direction == 1 else 0)
            by = buddy.current_y + buddy.height // 2
            bullet = DesktopBullet(self._root_parent, bx, by, direction, self)
            self.active_bullets.add(bullet)
            play_gunshot()

        self._schedule_fire()

    def _detach(self):
        if self.attached_to is not None:
            try:
                self.attached_to.has_gun = None
            except Exception:
                pass
            self.attached_to = None
        if self._fire_after_id:
            try:
                self.win.after_cancel(self._fire_after_id)
            except Exception:
                pass
            self._fire_after_id = None

    def update_position(self):
        if self.attached_to is None or self._destroyed:
            return
        buddy = self.attached_to
        try:
            if not buddy.root.winfo_exists():
                self._detach()
                return
        except Exception:
            self._detach()
            return
        gx = int(buddy.current_x + buddy.width - 5)
        gy = int(buddy.current_y + buddy.height // 2 - self.height // 2)
        self.x = float(gx)
        self.y = float(gy)
        try:
            self.win.geometry(f"{self.width}x{self.height}+{gx}+{gy}")
        except Exception:
            pass

    def _on_right_click(self, event):
        menu = tk.Menu(self.win, tearoff=0)
        if self.attached_to is not None:
            menu.add_command(label="🔫 detach gun", command=self._detach)
            menu.add_separator()
        menu.add_command(label="🗑️ remove gun", command=self.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        self._detach()
        for bullet in list(self.active_bullets):
            bullet._cleanup()
        self.active_bullets.clear()
        try:
            manager.active_guns.remove(self)
        except ValueError:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass


# ===================================================
# CANVAS LAYER
# ===================================================
class DesktopScratchCanvas:
    """
    Windowless manager for poop/dirt PNG overlays.
    The fullscreen black Toplevel has been removed entirely — it caused the
    screen to go black. Poop and dirt are individual small Toplevels with
    transparent backgrounds, which work fine on their own.
    add_scratch() and add_dig_hole() are kept as no-ops so call sites don't break.
    """
    def __init__(self, root_parent: tk.Misc):
        self._root_parent = root_parent
        self._poop_windows: list = []
        self._dirt_windows: list = []

    def add_scratch(self, start_x, start_y):
        pass  # required the fullscreen canvas — removed to fix black screen

    def add_dig_hole(self, cx, cy):
        pass  # same as above

    def _make_png_window(self, png_path, cx, cy, size):
        try:
            img = Image.open(png_path).convert("RGBA")
            img.thumbnail((size, size))
            win = tk.Toplevel(self._root_parent)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg="black")
            win.wm_attributes("-transparentcolor", "black")
            tk_img = ImageTk.PhotoImage(img)
            lbl = tk.Label(win, image=tk_img, bg="black", bd=0)
            lbl.image = tk_img
            lbl.pack()
            w, h = img.size
            win.geometry(f"{w}x{h}+{cx - w // 2}+{cy - h // 2}")
            return win
        except Exception as e:
            print(f"[Canvas] Failed to spawn PNG window ({png_path}): {e}")
            return None

    def add_poop(self, cx, cy):
        win = self._make_png_window(POOP_PNG_PATH, cx, cy, 60)
        if win:
            self._poop_windows.append(win)

    def add_dirt(self, cx, cy):
        size = random.randint(40, 80)
        win = self._make_png_window(DIRT_PNG_PATH, cx, cy, size)
        if win:
            self._dirt_windows.append(win)

    def wash_clean(self):
        for w in self._poop_windows + self._dirt_windows:
            try:
                w.destroy()
            except Exception:
                pass
        self._poop_windows = []
        self._dirt_windows = []

# ===================================================
class DesktopToyBall:
    def __init__(self, root_parent: tk.Misc, start_x: int, start_y: int):
        self.win = tk.Toplevel(root_parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black")
        self.win.wm_attributes("-transparentcolor", "black")

        try:
            img = Image.open(BALL_PNG_PATH).convert("RGBA")
            img.thumbnail((55, 55))
            self._tk_img = ImageTk.PhotoImage(img)
            self.width, self.height = img.size
            self.label = tk.Label(self.win, image=self._tk_img, bg="black", bd=0)
        except Exception as e:
            print(f"[Ball] Could not load ball PNG, using emoji fallback: {e}")
            self._tk_img = None
            self.width, self.height = 45, 45
            self.label = tk.Label(self.win, text="🎾", font=("Arial", 26), bg="black", bd=0)
        self.label.pack()

        self.x = float(start_x)
        self.y = float(start_y)
        self.dx = float(random.choice([-14, -10, 10, 14]))
        self.dy = float(-16)

        self.screen_width  = self.win.winfo_screenwidth()
        self.screen_height = self.win.winfo_screenheight()
        self.floor         = self._get_ball_floor()

        self._was_airborne = True
        self._after_id = None

        self.win.geometry(f"{self.width}x{self.height}+{int(self.x)}+{int(self.y)}")
        self.label.bind("<Button-3>", self._on_right_click)

        MAX_BALLS = 5
        while len(manager.active_toys) >= MAX_BALLS:
            manager.active_toys[0].destroy()

        manager.active_toys.append(self)

        for buddy in manager.active_buddies:
            buddy.start_chasing_ball(self)

        self._physics_loop()

    def _get_ball_floor(self) -> int:
        try:
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
            return rect.bottom - self.height
        except Exception:
            return self.screen_height - self.height

    def _physics_loop(self):
        try:
            if not self.win.winfo_exists():
                return
        except Exception:
            return

        self.dy += GRAVITY
        self.x  += self.dx
        self.y  += self.dy

        bounced_this_tick = False

        if self.x < 0:
            self.x  = 0
            self.dx = abs(self.dx) * BOUNCE_DAMPING
            bounced_this_tick = True
        elif self.x > self.screen_width - self.width:
            self.x  = self.screen_width - self.width
            self.dx = -abs(self.dx) * BOUNCE_DAMPING
            bounced_this_tick = True

        if self.y < 0:
            self.y  = 0
            self.dy = abs(self.dy) * BOUNCE_DAMPING
            bounced_this_tick = True

        if self.y >= self.floor:
            self.y = self.floor
            impact_speed = abs(self.dy)
            if self._was_airborne and impact_speed > 1.5:
                bounced_this_tick = True
            self.dy = -impact_speed * BOUNCE_DAMPING
            if impact_speed <= 1.5:
                self.dy = 0.0
            self.dx *= 0.92
            if abs(self.dy) < 1.5:
                self.dy = 0.0
            self._was_airborne = False
        else:
            self._was_airborne = True

        if bounced_this_tick:
            play_bounce()

        try:
            self.win.geometry(f"{self.width}x{self.height}+{int(self.x)}+{int(self.y)}")
            self._after_id = self.win.after(16, self._physics_loop)
        except Exception:
            pass

    def kick(self, force_x, force_y):
        self.dx = force_x
        self.dy = force_y

    def _on_right_click(self, event):
        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label="🗑️ remove ball", command=self.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def destroy(self):
        try:
            manager.active_toys.remove(self)
        except ValueError:
            pass
        for buddy in manager.active_buddies:
            if buddy.chasing_ball is self:
                buddy.chasing_ball = None
        if self._after_id is not None:
            try:
                self.win.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        try:
            self.win.destroy()
        except Exception:
            pass


# =========================
# WORLD ENTITIES
# =========================
class DesktopBed:
    def __init__(self, root_parent: tk.Misc, ground_level: int, screen_width: int):
        self.win = tk.Toplevel(root_parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black")
        self.win.wm_attributes("-transparentcolor", "black")

        try:
            img = Image.open(BED_PNG_PATH).convert("RGBA")
            img.thumbnail((400, 200))
            self.tk_img = ImageTk.PhotoImage(img)
            self.width, self.height = img.size
        except Exception as e:
            print(f"Failed to load bed image: {e}")
            self.width, self.height = 300, 100
            self.tk_img = None

        self.label = tk.Label(self.win, image=self.tk_img, bg="black", bd=0)
        if not self.tk_img:
            self.label.config(text="🛋️ THE PACK BED 🛋️", fg="white", bg="brown", font=("Arial", 16))
        self.label.pack()

        self.x = (screen_width // 2) - (self.width // 2)
        self.y = ground_level + 40
        self.win.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
        self._force_topmost()

    def _force_topmost(self):
        try:
            hwnd = ctypes.wintypes.HWND(self.win.winfo_id())
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        except Exception:
            pass

    def destroy(self):
        self.win.destroy()


class DesktopThrone:
    def __init__(self, root_parent: tk.Misc, ground_level: int, screen_width: int):
        self._root_parent = root_parent
        self.win = tk.Toplevel(root_parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black")
        self.win.wm_attributes("-transparentcolor", "black")

        try:
            img = Image.open(THRONE_PNG_PATH).convert("RGBA")
            img.thumbnail((300, 300))
            self.tk_img = ImageTk.PhotoImage(img)
            self.width, self.height = img.size
        except Exception as e:
            print(f"Failed to load throne image: {e}")
            self.width, self.height = 200, 200
            self.tk_img = None

        self.label = tk.Label(self.win, image=self.tk_img, bg="black", bd=0)
        if not self.tk_img:
            self.label.config(text="👑 PUG THRONE 👑", fg="gold", bg="darkred", font=("Arial", 18, "bold"))
        self.label.pack()

        screen_height = self.win.winfo_screenheight()
        self.x = (screen_width // 2) - (self.width // 2)
        self.y = (screen_height // 2) - (self.height // 2)
        self.win.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        self.label.bind("<Button-3>", self._on_right_click)
        self._force_topmost()

    def _force_topmost(self):
        try:
            hwnd = ctypes.wintypes.HWND(self.win.winfo_id())
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        except Exception:
            pass

    def _on_right_click(self, event):
        menu = tk.Menu(self.win, tearoff=0)

        # Promote submenu — only non-king pugs are listed
        candidates = [b for b in manager.active_buddies if not b.is_king]
        if candidates:
            promote_menu = tk.Menu(menu, tearoff=0)
            for buddy in candidates:
                promote_menu.add_command(
                    label=f"👑 {buddy.name}",
                    command=lambda b=buddy: manager.promote_pug(b),
                )
            menu.add_cascade(label="👑 promote to king ▶", menu=promote_menu)
        else:
            menu.add_command(label="👑 promote to king (no pugs)", state="disabled")

        menu.add_separator()
        menu.add_command(label="🗑️ remove throne", command=manager.clear_throne)
        menu.tk_popup(event.x_root, event.y_root)

    def destroy(self):
        self.win.destroy()


# =========================
# THE SHREDDER
# =========================
class DesktopShredder:
    SHREDDER_SIZE = (200, 300)

    def __init__(self, root_parent: tk.Misc):
        self._root_parent = root_parent
        self.win = tk.Toplevel(root_parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black")
        self.win.wm_attributes("-transparentcolor", "black")

        try:
            img = Image.open(SHREDDER_PNG_PATH).convert("RGBA")
            img.thumbnail(self.SHREDDER_SIZE)
            self._tk_img = ImageTk.PhotoImage(img)
            self.width, self.height = img.size
            self._label = tk.Label(self.win, image=self._tk_img, bg="black", bd=0)
        except Exception as e:
            print(f"[Shredder] Could not load shredder PNG: {e}")
            self._tk_img = None
            self.width, self.height = 160, 220
            self._label = tk.Label(
                self.win, text="🗂️\nSHREDDER", font=("Arial Black", 18, "bold"),
                fg="red", bg="black", justify="center"
            )
        self._label.pack()

        sh = self.win.winfo_screenheight()
        self.x = 30
        self.y = (sh // 2) - (self.height // 2)
        self.win.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        self._label.bind("<Button-3>", self._on_right_click)
        self._force_topmost()

    def _force_topmost(self):
        try:
            hwnd = ctypes.wintypes.HWND(self.win.winfo_id())
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        except Exception:
            pass

    def check_pug_overlap(self, buddy: "DesktopBuddy") -> bool:
        pug_cx = buddy.current_x + buddy.width  // 2
        pug_cy = buddy.current_y + buddy.height // 2
        return (self.x <= pug_cx <= self.x + self.width and
                self.y <= pug_cy <= self.y + self.height)

    def _on_right_click(self, event):
        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label="💀 view shredded pugs", command=self._show_obituary)
        menu.add_separator()
        menu.add_command(label="🗑️ remove shredder",    command=self.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def _show_obituary(self):
        win = tk.Toplevel(self._root_parent)
        win.title("💀 Shredded Pugs")
        win.configure(bg="#1a1a1a")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        tk.Label(win, text="R.I.P. 🪦", font=("Arial Black", 14, "bold"), fg="red", bg="#1a1a1a").pack(pady=(12, 4))

        if manager.shredded_pugs:
            for i, name in enumerate(manager.shredded_pugs, 1):
                tk.Label(win, text=f"{i}. {name}", font=("Arial", 11), fg="white", bg="#1a1a1a").pack(anchor="w", padx=20, pady=1)
        else:
            tk.Label(win, text="No pugs have been shredded... yet.", font=("Arial", 10, "italic"), fg="#888888", bg="#1a1a1a").pack(padx=20, pady=6)

        tk.Button(win, text="Close", command=win.destroy, bg="#333333", fg="white", bd=0, font=("Arial", 9), padx=12, pady=4).pack(pady=10)

        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w  = win.winfo_reqwidth()
        h  = win.winfo_reqheight()
        win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def destroy(self):
        manager.active_shredder = None
        try:
            self.win.destroy()
        except Exception:
            pass


# ========================================
# DIALOGUE INPUT BOX
# ========================================
class CustomPugDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#222222", bd=2, relief="solid")

        self.result = None

        lbl_title = tk.Label(self, text=title, bg="#333333", fg="white", font=("Arial", 10, "bold"), anchor="w", padx=5)
        lbl_title.pack(fill="x", side="top")

        body = tk.Frame(self, bg="#222222", padx=15, pady=10)
        body.pack(fill="both", expand=True)

        lbl_prompt = tk.Label(body, text=prompt, bg="#222222", fg="white", font=("Arial", 10))
        lbl_prompt.pack(anchor="w", pady=(0, 5))

        self.entry = tk.Entry(body, font=("Arial", 11), bg="#444444", fg="white", insertbackground="white", relief="flat")
        self.entry.pack(fill="x", pady=5)
        self.entry.focus_set()

        btn_frame = tk.Frame(body, bg="#222222")
        btn_frame.pack(anchor="e", pady=(10, 0))

        btn_ok = tk.Button(btn_frame, text="OK", width=8, font=("Arial", 9, "bold"), bg="#444444", fg="white", bd=0, command=self._validate)
        btn_ok.pack(side="left", padx=5)

        btn_cancel = tk.Button(btn_frame, text="Cancel", width=8, font=("Arial", 9), bg="#333333", fg="white", bd=0, command=self.destroy)
        btn_cancel.pack(side="left")

        self.bind("<Return>", lambda e: self._validate())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 320, 140
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self.grab_set()
        self.wait_window()

    def _validate(self):
        self.result = self.entry.get()
        self.destroy()

    @staticmethod
    def askstring(parent, title, prompt):
        dialog = CustomPugDialog(parent, title, prompt)
        return dialog.result


# =========================
# BUDDY MANAGER
# =========================
class BuddyManager:
    def __init__(self):
        self.active_buddies: list["DesktopBuddy"] = []
        self.active_toys: list[DesktopToyBall]    = []
        self.active_bed: "DesktopBed | None"       = None
        self.active_throne: "DesktopThrone | None" = None
        self.active_shredder: "DesktopShredder | None" = None
        self.scratch_canvas: "DesktopScratchCanvas | None" = None
        self.main_root: "tk.Tk | None"             = None
        self.shredded_pugs: list[str]              = []
        self.active_guns: list                     = []   

    def register(self, buddy: "DesktopBuddy"):
        self.active_buddies.append(buddy)
        if self.scratch_canvas is None and self.main_root is not None:
            self.scratch_canvas = DesktopScratchCanvas(self.main_root)

        if self.active_toys:
            buddy.start_chasing_ball(self.active_toys[0])

    def unregister(self, buddy: "DesktopBuddy"):
        try:
            self.active_buddies.remove(buddy)
        except ValueError:
            pass

    def talk_to_all(self):
        if not self.active_buddies:
            return
        ref = self.active_buddies[0]
        user_msg = CustomPugDialog.askstring(ref.root, "The Pack", "Broadcast message to ALL pugs:")
        if user_msg:
            cleaned = user_msg.strip().lower()
            if cleaned == "pug away":
                self.purge_all_buddies()
                return
            if cleaned == "wake up":
                self.trigger_wake_sequence()
                return
            for buddy in self.active_buddies:
                buddy.say(f"{buddy.name}: {user_msg}")

    def trigger_sleep_sequence(self):
        if self.active_bed is not None or not self.active_buddies:
            return
        ref = self.active_buddies[0]
        self.active_bed = DesktopBed(self.main_root, ref.ground_level, ref.screen_width)
        for buddy in self.active_buddies:
            buddy.start_bed_routine(self.active_bed)

    def trigger_wake_sequence(self):
        self.clear_bed()
        for buddy in self.active_buddies:
            buddy.wake_up_routine()

    def spawn_king_pug(self):
        if not self.active_buddies:
            return
        ref = self.active_buddies[0]
        if self.active_throne is None:
            self.active_throne = DesktopThrone(self.main_root, ref.ground_level, ref.screen_width)
        DesktopBuddy(is_king=True)

    def spawn_shredder(self):
        if self.active_shredder is not None:
            return
        self.active_shredder = DesktopShredder(self.main_root)

    def promote_pug(self, buddy: "DesktopBuddy"):
        """Remove any existing king, then promote buddy to king."""
        # Dismiss the current king if there is one
        for existing in list(self.active_buddies):
            if existing.is_king:
                self.unregister(existing)
                try:
                    existing.bubble_win.destroy()
                except Exception:
                    pass
                try:
                    existing.root.destroy()
                except Exception:
                    pass
                break
        # Promote the chosen pug in-place
        buddy.promote_to_king()

    def shred_pug(self, buddy: "DesktopBuddy"):
        name = buddy.name
        self.shredded_pugs.append(name)
        play_shred_sound()
        play_sad_sound()
        self.unregister(buddy)
        try:
            buddy.bubble_win.destroy()
        except Exception:
            pass
        try:
            buddy.root.destroy()
        except Exception:
            pass
        print(f"[Shredder] RIP {name}. Total shredded: {len(self.shredded_pugs)}")
        # If no pugs remain, clean up everything and exit
        if not self.active_buddies:
            self.clear_throne()
            if self.active_shredder is not None:
                self.active_shredder.destroy()
            if self.scratch_canvas:
                self.scratch_canvas.wash_clean()
            for ball in list(self.active_toys):
                ball.destroy()
            if self.main_root:
                try:
                    self.main_root.destroy()
                except Exception:
                    pass

    def clear_bed(self):
        if self.active_bed:
            self.active_bed.destroy()
            self.active_bed = None

    def clear_throne(self):
        if self.active_throne:
            self.active_throne.destroy()
            self.active_throne = None

    def purge_all_buddies(self):
        self.clear_bed()
        self.clear_throne()
        if self.scratch_canvas:
            self.scratch_canvas.wash_clean()
        for ball in list(self.active_toys):
            ball.destroy()
        for gun in list(self.active_guns):
            gun.destroy()
        for buddy in list(self.active_buddies):
            try:
                buddy.root.destroy()
            except Exception:
                pass
        if self.main_root:
            try:
                self.main_root.destroy()
            except Exception:
                pass

manager = BuddyManager()


# ========================================
# MAXIMUM LICK OVERLAY
# ========================================
class MaximumLickOverlay:
    def __init__(self, parent_root: tk.Misc):
        self._stop_sound = threading.Event()
        play_lick_loop(self._stop_sound)

        self._win = tk.Toplevel(parent_root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg="black")

        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        self._win.geometry(f"{sw}x{sh}+0+0")

        try:
            hwnd = ctypes.windll.user32.GetParent(self._win.winfo_id())
            if not hwnd:
                hwnd = self._win.winfo_id()
            GWL_EXSTYLE      = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED     = 0x00080000
            current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)
        except Exception as e:
            print(f"[Overlay] Click-through initialization failure: {e}")

        big_size = min(sw, sh)
        self._big_frames = []
        if CACHED_PIL_FRAMES:
            for frame in CACHED_PIL_FRAMES:
                f = frame.copy().resize((big_size, big_size), Image.Resampling.LANCZOS)
                self._big_frames.append(ImageTk.PhotoImage(f))

        self._label = tk.Label(self._win, bg="black", bd=0)
        self._label.place(relx=0.5, rely=0.5, anchor="center")

        self._banner = tk.Label(self._win, text="L I C K I N G   I N T E N S I F I E S", font=("Arial Black", 36, "bold"), fg="white", bg="black")
        self._banner.place(relx=0.5, rely=0.08, anchor="center")

        hint = tk.Label(self._win, text="Press Esc key to exit chaos safely", font=("Arial", 14), fg="#888888", bg="black")
        hint.place(relx=0.5, rely=0.95, anchor="center")

        self._win.bind_all("<Escape>", self._close)

        self._frame_index = 0
        self._animate()

    def _animate(self):
        if not self._win.winfo_exists():
            return
        if not self._big_frames:
            if CACHED_PIL_FRAMES:
                sw = self._win.winfo_screenwidth()
                sh = self._win.winfo_screenheight()
                big_size = min(sw, sh)
                for frame in CACHED_PIL_FRAMES:
                    f = frame.copy().resize((big_size, big_size), Image.Resampling.LANCZOS)
                    self._big_frames.append(ImageTk.PhotoImage(f))
            else:
                self._win.after(20, self._animate)
                return

        colours = ["#ff4444", "#ff8800", "#ffff00", "#00ff88", "#00ccff", "#cc44ff"]
        self._banner.config(fg=random.choice(colours))
        self._label.config(image=self._big_frames[self._frame_index])
        self._frame_index = (self._frame_index + 1) % len(self._big_frames)

        if manager.scratch_canvas and random.random() < 0.1:
            sw = self._win.winfo_screenwidth()
            sh = self._win.winfo_screenheight()
            rx = random.randint(30, sw - 30)
            ry = random.randint(30, sh - 30)
            manager.scratch_canvas.add_dirt(rx, ry)

        self._win.after(20, self._animate)

    def _close(self, _event=None):
        self._stop_sound.set()
        self._win.destroy()


# =========================
# INDIVIDUAL BUDDY WINDOW
# =========================
class DesktopBuddy:
    def __init__(self, is_king: bool = False, name: str = None):
        self.is_king  = is_king
        
        # All pugs use Toplevel connected to a hidden core layout frame. No more chain destruction!
        self.root = tk.Toplevel(manager.main_root)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.wm_attributes("-transparentcolor", "black")

        if self.is_king:
            self.name = "King Pug VII"
        elif name is not None:
            self.name = name
        else:
            used_names = {b.name for b in manager.active_buddies}
            available  = [n for n in FRIEND_NAMES if n not in used_names]
            self.name  = random.choice(available) if available else random.choice(FRIEND_NAMES)

        if self.name == "Aturo JR":
            self.width  = SPRITE_SIZE[0] // 2
            self.height = SPRITE_SIZE[1] // 2
        else:
            self.width, self.height = SPRITE_SIZE
        self.extra_height = 0

        self.bubble_win = tk.Toplevel(self.root)
        self.bubble_win.overrideredirect(True)
        self.bubble_win.attributes("-topmost", True)
        self.bubble_win.configure(bg="#FF00FF")
        self.bubble_win.wm_attributes("-transparentcolor", "#FF00FF")

        self.bubble = tk.Label(
            self.bubble_win, text="", font=("Arial", 10, "bold"),
            bg="white", fg="black", padx=10, pady=5, wraplength=200, bd=1, relief="solid"
        )
        self.bubble.pack()
        self.bubble_win.withdraw()

        self.label = tk.Label(self.root, bg="black", bd=0)
        self.label.pack(side="bottom")

        self.is_dragging = False
        self.dx = random.choice([-WANDER_SPEED, WANDER_SPEED])
        self.dy = 0.0  
        self._bubble_cancel_id: str | None = None

        self._drag_history = []

        self.bed_state      = "normal"
        self.target_bed_x   = 0
        self.target_bed_y   = 0
        self.bed_timer_count = 0

        self.idle_stay_still_ticks  = 0
        self.captured_window_title  = None
        self.frenzy_chase_active    = False
        self._last_ball_hit_time    = time.time()
        self._last_poop_time        = time.time()   
        self._ground_cache_tick     = 0
        self.chasing_ball: "DesktopToyBall | None" = None
        self.laxative_mode          = False
        self._being_shredded        = False
        self.has_gun                = None         

        self.screen_width  = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.ground_level  = self._get_ground_level()
        self.ceiling       = 0

        self.current_x = float(random.randint(100, max(200, self.screen_width - 300)))
        self.current_y = float(self.ground_level)
        self.root.geometry(f"+{int(self.current_x)}+{int(self.current_y)}")

        self.root.update_idletasks()
        self._force_topmost()

        self._frame_index = 0
        self._tk_frames   = []

        self.label.bind("<Button-1>",        self._start_drag)
        self.label.bind("<B1-Motion>",       self._drag)
        self.label.bind("<ButtonRelease-1>", self._stop_drag)
        self.label.bind("<Button-3>",        self._popup_menu)

        manager.register(self)

        self._animate()
        self._physics_loop()
        self._idle_chat_loop()

    def _get_ground_level(self) -> int:
        try:
            if sys.platform == "win32":
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
                return rect.bottom - self.height + SPRITE_FLOOR_OFFSET
        except Exception:
            pass
        return self.screen_height - self.height

    def _force_topmost(self):
        try:
            hwnd = ctypes.wintypes.HWND(self.root.winfo_id())
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        except Exception:
            pass

    def start_bed_routine(self, bed: DesktopBed):
        span_x = random.randint(0, max(1, bed.width - 180))
        self.target_bed_x = bed.x + span_x
        self.target_bed_y = bed.y - 120
        self.bed_state    = "moving_to_bed"
        self.say("BED TIME!")

    def wake_up_routine(self):
        if self.bed_state in ("moving_to_bed", "trampoline", "sleeping"):
            self.bed_state = "normal"
            self.dy = JUMP_SPEED_Y * 0.6   
            self.dx = random.choice([-WANDER_SPEED, WANDER_SPEED])
            self.say("I'M AWAKE!!")
            play_lick()

    def promote_to_king(self):
        """Flip this pug to king mode: rename, switch to king video, reset frames."""
        old_name   = self.name
        self.is_king = True
        self.name    = f"King {old_name}"
        # Clear the cached frames so _animate picks up CACHED_KING_FRAMES fresh
        self._tk_frames  = []
        self._frame_index = 0
        self.bed_state   = "normal"
        self.say(f"ALL HAIL KING {old_name.upper()}! 👑")
        play_lick()
        print(f"[Throne] {old_name} promoted to {self.name}")

    def go_frenzy_mode(self):
        self.frenzy_chase_active = True
        self.bed_state = "normal"
        self.say("MEOW SIGHTED!! TARGET ENGAGED!!")
        play_lick()

    def _update_bed_mechanics(self):
        if self.bed_state == "moving_to_bed":
            dist_x = self.target_bed_x - self.current_x
            dist_y = self.target_bed_y - self.current_y
            self.current_x += max(-12.0, min(12.0, dist_x))
            self.current_y += max(-12.0, min(12.0, dist_y))
            if abs(dist_x) < 15 and abs(dist_y) < 15:
                self.bed_state      = "trampoline"
                self.bed_timer_count = 0
                self.dy = -12.0

        elif self.bed_state == "trampoline":
            self.dy += GRAVITY
            self.current_y += self.dy
            self.current_x += max(-3.0, min(3.0, self.target_bed_x - self.current_x))
            if self.current_y >= self.target_bed_y:
                self.current_y = float(self.target_bed_y)
                self.dy = self.dy * -0.75
                play_lick()
            self.bed_timer_count += 1
            if self.bed_timer_count >= 180:
                self.bed_state      = "sleeping"
                self.current_y      = float(self.target_bed_y)
                self.dy = 0.0
                self.dx = 0.0
                self.say("Zzz...")
                play_mp3(SLEEP_SOUND_PATH)

        elif self.bed_state == "sleeping":
            self.current_x = float(self.target_bed_x)
            self.current_y = float(self.target_bed_y)

    def _animate(self):
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        raw_source = CACHED_KING_FRAMES if self.is_king else CACHED_PIL_FRAMES
        target_size = (self.width, self.height)
        if len(self._tk_frames) < len(raw_source):
            for i in range(len(self._tk_frames), len(raw_source)):
                frame = raw_source[i]
                if frame.size != target_size:
                    frame = frame.copy().resize(target_size, Image.Resampling.LANCZOS)
                self._tk_frames.append(ImageTk.PhotoImage(frame))

        if self._tk_frames:
            self._frame_index = self._frame_index % len(self._tk_frames)
            try:
                self.label.config(image=self._tk_frames[self._frame_index])
            except Exception:
                return
            self._frame_index = (self._frame_index + 1) % len(self._tk_frames)

        self.root.after(25, self._animate)

    def _start_drag(self, event):
        self.is_dragging = True
        self._drag_history = [(time.time(), self.root.winfo_x(), self.root.winfo_y())]
        if self.bed_state != "normal":
            self.bed_state = "normal"
            manager.clear_bed()
        self._drag_x = event.x
        self._drag_y = event.y
        personality = PUG_PERSONALITY.get(self.name, {})
        pool = personality.get("drag", DRAG_MESSAGES)
        self.say(random.choice(pool))

    def _drag(self, event):
        self.current_x = float(self.root.winfo_x() + event.x - self._drag_x)
        self.current_y = float(self.root.winfo_y() + event.y - self._drag_y)
        self.root.geometry(f"+{int(self.current_x)}+{int(self.current_y)}")
        now = time.time()
        self._drag_history.append((now, self.current_x, self.current_y))
        if len(self._drag_history) > 6:
            self._drag_history.pop(0)

    def _stop_drag(self, _event):
        self.is_dragging = False

        if (not self._being_shredded and manager.active_shredder is not None and manager.active_shredder.check_pug_overlap(self)):
            self._being_shredded = True
            self.say("NOOOOO!! 😱")
            self.root.after(600, lambda: manager.shred_pug(self))
            return

        if self.is_king and manager.active_throne is not None:
            t     = manager.active_throne
            self_cx = self.current_x + (self.width  // 2)
            self_cy = self.current_y + (self.height // 2)
            if (t.x <= self_cx <= t.x + t.width) and (t.y <= self_cy <= t.y + t.height):
                self.bed_state = "throned"
                self.current_x = float(t.x + (t.width  // 2) - (self.width  // 2))
                self.current_y = float(t.y + (t.height // 2) - (self.height // 2) - 15)
                self.dx = 0.0
                self.dy = 0.0
                self.say("BOW BEFORE ME!")
                return

        if len(self._drag_history) >= 2:
            first_pt = self._drag_history[0]
            last_pt  = self._drag_history[-1]
            dt = last_pt[0] - first_pt[0]
            if dt > 0.01:
                thrown_dx = (last_pt[1] - first_pt[1]) / dt * 0.016
                thrown_dy = (last_pt[2] - first_pt[2]) / dt * 0.016
                self.dx = max(-45.0, min(45.0, thrown_dx))
                self.dy = max(-45.0, min(45.0, thrown_dy))
                if abs(self.dx) > 12 or abs(self.dy) > 12:
                    self.say("WEEEEE!!!")
                    play_lick()
                    return

        self.dy = 0.0  
        self.dx = random.choice([-WANDER_SPEED, WANDER_SPEED])

    def _physics_loop(self):
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        self._ground_cache_tick += 1
        if self._ground_cache_tick >= 30:
            self._ground_cache_tick = 0
            self.ground_level = self._get_ground_level()
        adjusted_ground = self.ground_level

        if self.is_dragging:
            self._check_buddy_collisions()
            self.idle_stay_still_ticks = 0
        else:
            if self.frenzy_chase_active and pyautogui is not None:
                cursor_x, cursor_y = pyautogui.position()
                t_x = cursor_x - (self.width  // 2)
                t_y = cursor_y - (self.height // 2)
                self.current_x += (t_x - self.current_x) * 0.14
                self.current_y += (t_y - self.current_y) * 0.14
                if abs(self.current_x - t_x) < 25 and abs(self.current_y - t_y) < 25:
                    self.frenzy_chase_active = False
                    self.say("I LICKED YOUR HAND!")
                    play_lick()

            elif self.bed_state == "throned":
                if manager.active_throne:
                    t = manager.active_throne
                    self.current_x = float(t.x + (t.width  // 2) - (self.width  // 2))
                    self.current_y = float(t.y + (t.height // 2) - (self.height // 2) - 15)

            elif self.bed_state != "normal":
                self._update_bed_mechanics()

            else:
                if self.chasing_ball is None:
                    self._check_buddy_collisions()
                self._check_toy_ball_collisions()

                if self.chasing_ball is not None:
                    ball = self.chasing_ball
                    if not ball.win.winfo_exists() or ball not in manager.active_toys:
                        self.chasing_ball = None
                    else:
                        target_x = int(ball.x) - (self.width  // 2)
                        target_y = int(ball.y) - (self.height // 2)
                        diff_x   = target_x - self.current_x
                        diff_y   = target_y - self.current_y
                        chase_speed = 7
                        dist = max(1, abs(diff_x) + abs(diff_y))
                        self.dx = (diff_x / dist) * chase_speed * min(1.0, dist / 80)
                        on_or_near_floor = self.current_y >= adjusted_ground - 20
                        if diff_y < -80 and on_or_near_floor and abs(self.dy) < 3:
                            self.dy = JUMP_SPEED_Y * 0.8

                self.dy += GRAVITY
                self.current_x += self.dx
                self.current_y += self.dy

                if self.current_x < 0:
                    self.current_x = 0.0
                    self.dx = abs(self.dx) * BOUNCE_DAMPING
                    if abs(self.dx) > 2:
                        play_lick()
                elif self.current_x > self.screen_width - self.width:
                    self.current_x = float(self.screen_width - self.width)
                    self.dx = -abs(self.dx) * BOUNCE_DAMPING
                    if abs(self.dx) > 2:
                        play_lick()

                if self.current_y < self.ceiling:
                    self.current_y = float(self.ceiling)
                    self.dy = abs(self.dy) * BOUNCE_DAMPING   

                if self.current_y >= adjusted_ground:
                    now = time.time()
                    if abs(self.dy) < 4.0 and random.random() < 0.012:
                        if now - self._last_poop_time > 60.0:
                            self._last_poop_time = now
                            self._trigger_digging_behavior()
                    self.current_y = float(adjusted_ground)
                    impact_speed = abs(self.dy)
                    self.dy = -impact_speed * BOUNCE_DAMPING
                    if impact_speed > 1.0 and abs(self.dy) < MIN_BOUNCE_SPEED:
                        self.dy = -MIN_BOUNCE_SPEED
                    elif impact_speed <= 1.0:
                        self.dy = 0.0  
                    self.dx *= 0.95
                    if abs(self.dx) < 1.0:
                        self.dx = float(random.choice([-WANDER_SPEED, WANDER_SPEED]))
                    if impact_speed > 2.0:
                        play_bounce()

                if abs(self.dx) < 1.5 and abs(self.dy) < 1.5:
                    self.idle_stay_still_ticks += 1
                    if self.idle_stay_still_ticks > 240:
                        if manager.scratch_canvas and random.random() < 0.08:
                            manager.scratch_canvas.add_scratch(
                                int(self.current_x) + (self.width  // 2),
                                int(self.current_y) +  self.height - 15
                            )
                        if random.random() < 0.005:
                            self._execute_window_theft()
                else:
                    self.idle_stay_still_ticks = 0

            try:
                self.root.geometry(f"+{int(self.current_x)}+{int(self.current_y)}")
            except Exception:
                return

            if self.has_gun is not None:
                self.has_gun.update_position()

            if self.bubble_win.winfo_viewable():
                bubble_w = self.bubble_win.winfo_reqwidth()
                bubble_h = self.bubble_win.winfo_reqheight()
                bx = int(self.current_x) + (self.width  // 2) - (bubble_w // 2)
                by = int(self.current_y) - bubble_h - 5
                try:
                    self.bubble_win.geometry(f"+{bx}+{by}")
                except Exception:
                    pass

        try:
            self.root.after(16, self._physics_loop)
        except Exception:
            pass

    def _check_toy_ball_collisions(self):
        my_cx = self.current_x + (self.width  // 2)
        my_cy = self.current_y + (self.height // 2)
        now   = time.time()
        if now - self._last_ball_hit_time < 1.0:
            return
        for ball in list(manager.active_toys):
            ball_cx = ball.x + (ball.width  // 2)
            ball_cy = ball.y + (ball.height // 2)
            distance = np.hypot(my_cx - ball_cx, my_cy - ball_cy)
            if distance < 115:
                out_dx = (ball_cx - my_cx) * 0.25 + self.dx * 1.2
                out_dy = -abs(self.dy) * 1.1 - random.randint(6, 11)
                ball.kick(out_dx, out_dy)
                self._last_ball_hit_time = now
                self.say("MINE!!! 🎾")
                play_lick()
                break

    def _execute_window_theft(self):
        if self.captured_window_title is None and gw is not None:
            try:
                front_window = gw.getActiveWindow()
                if front_window and front_window.title and "Pug" not in front_window.title:
                    if front_window.title not in FRIEND_NAMES:
                        self.captured_window_title = front_window.title[:18] + "..."
                        self.say(f"GIMME THIS! Stole [{self.captured_window_title}]!")
                        front_window.minimize()
                        play_lick()
            except Exception:
                pass

    def _trigger_digging_behavior(self):
        self.say("💩")
        play_poop_sound()
        if manager.scratch_canvas:
            center_x = int(self.current_x) + (self.width  // 2)
            base_y   = int(self.current_y) +  self.height - 20
            manager.scratch_canvas.add_poop(center_x, base_y)

    def _check_buddy_collisions(self):
        for other in manager.active_buddies:
            if other is self or other.bed_state != "normal":
                continue
            dist_x = other.current_x - self.current_x
            dist_y = other.current_y - self.current_y
            if abs(dist_x) < 160 and abs(dist_y) < 160:
                if self.is_dragging:
                    if not other.is_dragging:
                        if len(self._drag_history) >= 2:
                            dt = self._drag_history[-1][0] - self._drag_history[0][0]
                            bat_dx = (self._drag_history[-1][1] - self._drag_history[0][1]) / dt * 0.016 if dt > 0 else 0
                            bat_dy = (self._drag_history[-1][2] - self._drag_history[0][2]) / dt * 0.016 if dt > 0 else 0
                        else:
                            bat_dx, bat_dy = 0, 0
                        base_force_x = 22.0 if bat_dx == 0 else (np.sign(bat_dx) * max(15.0, abs(bat_dx) * 2.2))
                        base_force_y = -18.0 if bat_dy == 0 else (np.sign(bat_dy) * max(12.0, abs(bat_dy) * 1.8))
                        other.dx = base_force_x + random.uniform(-4, 4)
                        other.dy = base_force_y - random.uniform(5, 10)
                        other.say("OOF!!")
                        play_lick()
                elif not other.is_dragging:
                    self.dx = abs(self.dx) * (1 if self.current_x >= other.current_x else -1)
                    self.dy = -abs(self.dy) * 0.7
                    break

    def _popup_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"💬 talk to {self.name}",    command=self._chat)
        menu.add_command(label="🗣️ talk to all pugs",        command=manager.talk_to_all)
        menu.add_command(label="🎾 throw tennis ball",        command=self._throw_ball_toy)
        menu.add_command(label="🗑️ remove all balls",         command=self._remove_all_balls)
        menu.add_command(label="🧼 bath (clean screen)",      command=self._give_cleaning_bath)

        # Spawn submenu — lists every available pug name, plus a random option
        spawn_menu = tk.Menu(menu, tearoff=0)
        spawn_menu.add_command(label="🎲 random", command=self._spawn_friend)
        spawn_menu.add_separator()
        used_names = {b.name for b in manager.active_buddies}
        for pug_name in FRIEND_NAMES:
            already_alive = pug_name in used_names
            label = f"{'✓ ' if already_alive else ''}{pug_name}"
            spawn_menu.add_command(
                label=label,
                command=lambda n=pug_name: DesktopBuddy(name=n),
            )
        menu.add_cascade(label="🐶 call sir pugsalot ▶", menu=spawn_menu)

        menu.add_command(label="🚀 boom",                     command=self._force_jump)
        menu.add_command(label="👅 slurp",                    command=self._maximum_lick)
        menu.add_command(label="💊 feed laxatives",           command=self._feed_laxatives)
        menu.add_separator()
        menu.add_command(label="👋 dismiss this pug",        command=self._dismiss)
        menu.add_command(label="❌ destroy entire pack",     command=manager.purge_all_buddies)
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _throw_ball_toy(self):
        DesktopToyBall(manager.main_root, int(self.current_x), int(self.current_y) - 60)

    def _remove_all_balls(self):
        for ball in list(manager.active_toys):
            ball.destroy()
        self.say("no more balls 😔")

    def _give_cleaning_bath(self):
        if manager.scratch_canvas:
            manager.scratch_canvas.wash_clean()
        if self.captured_window_title:
            self.say("Dropped the stolen items!")
            self.captured_window_title = None
        else:
            self.say("Clean and shiny!")
        play_lick()

    def _spawn_friend(self):
        DesktopBuddy()  # random pug

    def start_chasing_ball(self, ball: "DesktopToyBall"):
        self.chasing_ball = ball
        self.say("BALL!! 🎾")

    def _force_jump(self):
        if self.bed_state != "normal":
            return
        self.dy = JUMP_SPEED_Y * 1.6
        self.dx = random.choice([-JUMP_SPEED_X, JUMP_SPEED_X])
        self.say("UP WE GO!")
        play_lick()

    def _maximum_lick(self):
        self.say("COME TO PAPA")
        self.root.after(300, lambda: MaximumLickOverlay(manager.main_root))

    def _feed_laxatives(self):
        if self.laxative_mode:
            return
        self.laxative_mode = True
        self.say("oh no... 💩💩💩")
        self._laxative_loop()

    def _laxative_loop(self):
        if not self.laxative_mode or not self.root.winfo_exists():
            return
        self._trigger_digging_behavior()
        self.root.after(2000, self._laxative_loop)

    def _dismiss(self):
        if self.has_gun is not None:
            self.has_gun.destroy()
        manager.unregister(self)
        try:
            self.bubble_win.destroy()
            self.root.destroy()
        except Exception:
            pass

    def _chat(self):
        user = CustomPugDialog.askstring(self.root, self.name, f"Message for {self.name}:")
        if user:
            cleaned_msg = user.strip().lower()
            if cleaned_msg == "pug away":
                manager.purge_all_buddies()
                return
            if cleaned_msg == "sleep":
                manager.trigger_sleep_sequence()
                return
            if cleaned_msg == "wake up":
                manager.trigger_wake_sequence()
                return
            if cleaned_msg == "king pug":
                manager.spawn_king_pug()
                return
            if cleaned_msg == "shredder":
                manager.spawn_shredder()
                self.say("THE SHREDDER APPROACHES... 😨")
                return
            if cleaned_msg == "gun":
                DesktopGun(manager.main_root)
                self.say("HERE COMES THE HEAT 🔫")
                return
            self.say(self._generate_response(user))
            play_lick()

    def _generate_response(self, text: str) -> str:
        text = text.lower()
        if self.is_king:
            return "Kneel before your majestic ruler!"
        personality = PUG_PERSONALITY.get(self.name, {})
        chat_pool = personality.get("chat", [])
        if any(w in text for w in ("hello", "hi", "hey")):
            return random.choice(chat_pool) if chat_pool else "hello human"
        if "potato" in text:
            return "POTATO SPOTTED!"
        if "name" in text:
            return f"i am {self.name}"
        if "lick" in text:
            play_lick()
            return "lick lick lick"
        if "maximum" in text:
            self._maximum_lick()
            return "oh no"
        return random.choice(chat_pool) if chat_pool else random.choice(["hmmm?", "feed me", "lick lick", "i trust nothing"])

    def _clear_bubble_height(self):
        self.extra_height = 0
        self.bubble_win.withdraw()

    def say(self, text: str):
        if self._bubble_cancel_id:
            self.root.after_cancel(self._bubble_cancel_id)
        self.bubble.config(text=text)
        self.bubble_win.deiconify()
        self.bubble_win.update_idletasks()
        bubble_w = self.bubble_win.winfo_reqwidth()
        bubble_h = self.bubble_win.winfo_reqheight()
        bx = int(self.current_x) + (self.width  // 2) - (bubble_w // 2)
        by = int(self.current_y) - bubble_h - 5
        self.bubble_win.geometry(f"+{bx}+{by}")
        self._bubble_cancel_id = self.root.after(4000, self._clear_bubble_height)
        _speech.say(text)

    def _idle_chat_loop(self):
        if not self.is_dragging and self.bed_state == "normal" and random.random() < 0.75:
            personality = PUG_PERSONALITY.get(self.name, {})
            pool = personality.get("idle", IDLE_MESSAGES)
            self.say(f"{self.name}: {random.choice(pool)}")
            play_lick()
        self.root.after(random.randint(6000, 14000), self._idle_chat_loop)


# ========================================
# CENTRAL MONITOR & VOICE LOOPS
# ========================================
def central_powershell_monitor():
    global POWERSHELL_TRIGGERED
    target_hwnd = ctypes.windll.user32.FindWindowW(None, "Windows PowerShell")
    if not target_hwnd:
        target_hwnd = ctypes.windll.user32.FindWindowW(None, "PowerShell")

    if target_hwnd:
        if not POWERSHELL_TRIGGERED:
            POWERSHELL_TRIGGERED = True
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(target_hwnd, ctypes.byref(pid))
            PROCESS_TERMINATE = 0x0001
            h_process = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid.value)
            if h_process:
                ctypes.windll.kernel32.TerminateProcess(h_process, 1)
                ctypes.windll.kernel32.CloseHandle(h_process)
            if manager.active_buddies:
                manager.active_buddies[0]._maximum_lick()
    else:
        POWERSHELL_TRIGGERED = False

    if manager.main_root:
        manager.main_root.after(400, central_powershell_monitor)


def voice_listener_loop():
    if sr is None:
        print("[Voice Engine] SpeechRecognition module is missing.")
        return
    
    recognizer = sr.Recognizer()
    try:
        mic = sr.Microphone()
    except Exception as e:
        print(f"[Voice Engine] Microphone interface missing: {e}")
        return

    print("[Voice Engine] Active and listening for phrases...")
    while True:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            try:
                audio = recognizer.listen(source, timeout=2, phrase_time_limit=4)
            except sr.WaitTimeoutError:
                continue
            except Exception:
                continue

        try:
            text = recognizer.recognize_google(audio).lower().strip()
            print(f"[Voice Recognized]: {text}")

            # Dynamic Volume Operations — show on-screen toast after adjusting
            if "volume down" in text:
                new_level = volume_lock.change_target(-0.05)
                if manager.main_root:
                    manager.main_root.after(0, lambda lvl=new_level: _show_volume_toast(lvl))
            elif "volume up" in text:
                new_level = volume_lock.change_target(0.05)
                if manager.main_root:
                    manager.main_root.after(0, lambda lvl=new_level: _show_volume_toast(lvl))

        except (sr.UnknownValueError, sr.RequestError):
            pass
        except Exception as e:
            print(f"[Voice Error]: {e}")


# =========================
# Entry point
# =========================
if __name__ == "__main__":
    # Standardised window manager core sequence
    root = tk.Tk()
    root.withdraw() # Hide the master window frame completely from view.
    manager.main_root = root

    volume_lock = VolumeLock(LOCKED_VOLUME_PCT)
    
    try:
        threading.Thread(target=pre_load_video, args=(VIDEO_PATH, CACHED_PIL_FRAMES), daemon=True).start()
        threading.Thread(target=pre_load_video, args=(KING_VIDEO_PATH, CACHED_KING_FRAMES), daemon=True).start()
        threading.Thread(target=voice_listener_loop, daemon=True).start()

        # Instantiate our central loop and seed the initial visible pet window
        root.after(400, central_powershell_monitor)
        first_pug = DesktopBuddy()
        
        root.mainloop()
    finally:
        volume_lock.release()