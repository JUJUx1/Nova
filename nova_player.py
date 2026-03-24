#!/usr/bin/env python3
"""
███╗   ██╗ ██████╗ ██╗   ██╗ █████╗     ██████╗ ██╗      █████╗ ██╗   ██╗███████╗██████╗
████╗  ██║██╔═══██╗██║   ██║██╔══██╗    ██╔══██╗██║     ██╔══██╗╚██╗ ██╔╝██╔════╝██╔══██╗
██╔██╗ ██║██║   ██║██║   ██║███████║    ██████╔╝██║     ███████║ ╚████╔╝ █████╗  ██████╔╝
██║╚██╗██║██║   ██║╚██╗ ██╔╝██╔══██║    ██╔═══╝ ██║     ██╔══██║  ╚██╔╝  ██╔══╝  ██╔══██╗
██║ ╚████║╚██████╔╝ ╚████╔╝ ██║  ██║    ██║     ███████╗██║  ██║   ██║   ███████╗██║  ██║
╚═╝  ╚═══╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝    ╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
                         ♫  Termux Music CLI  ♫
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SETUP & INSTALL CHECKER
#  Run:  pip install mutagen requests   (curses is stdlib)
#        pkg install mpv                (Termux audio backend)
# ─────────────────────────────────────────────────────────────────────────────

import os, sys, time, json, math, random, curses, socket, threading
import subprocess, urllib.request, urllib.parse, urllib.error
from pathlib import Path

# ── optional libs ──────────────────────────────────────────────────────────
try:
    from mutagen import File as MFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

try:
    import requests as _req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import yt_dlp as _ytdlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    HAS_SPOTIPY = True
except ImportError:
    HAS_SPOTIPY = False

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
VERSION      = "2.0"
MPV_SOCKET   = os.path.join(os.environ.get("TMPDIR", "/tmp"), "nova_mpv.sock")
AUDIO_EXTS   = {".mp3", ".flac", ".ogg", ".m4a", ".wav", ".aac", ".opus", ".wma"}
LYRICS_API        = "https://lrclib.net/api/get"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL   = "claude-haiku-4-5-20251001"
SPOTIFY_CREDS_FILE = Path.home() / ".nova_spotify.json"

# Output dir for recordings
REC_DIRS = [
    Path.home() / "storage" / "downloads",
    Path("/sdcard/Download"),
    Path.home(),
]

# Possible song directories (Termux storage)
SONG_DIRS = [
    Path.home() / "storage" / "downloads" / "songs",
    Path.home() / "Downloads" / "songs",
    Path("/sdcard/Download/songs"),
    Path("/sdcard/Music"),
    Path.home() / "songs",
]

# ─────────────────────────────────────────────────────────────────────────────
#  COLOUR PALETTE  (256-colour)
# ─────────────────────────────────────────────────────────────────────────────
C_BLACK    = 0
C_CYAN     = 51
C_MAGENTA  = 201
C_YELLOW   = 226
C_GREEN    = 46
C_ORANGE   = 214
C_RED      = 196
C_BLUE     = 27
C_WHITE    = 231
C_GRAY     = 240
C_DGRAY    = 235
C_PINK     = 213
C_TEAL     = 87

# curses pair indices
P_TITLE    = 1   # cyan on black
P_ARTIST   = 2   # magenta on black
P_NORMAL   = 3   # white on black
P_SELECTED = 4   # black on cyan
P_PROGRESS = 5   # green
P_BORDER   = 6   # blue
P_LYRICS   = 7   # yellow
P_LYRHI    = 8   # black on yellow  (active lyric)
P_HEADER   = 9   # orange
P_GRAY     = 10  # gray
P_KEY      = 11  # pink
P_EQ1      = 12  # cyan bar
P_EQ2      = 13  # magenta bar
P_EQ3      = 14  # yellow bar
P_PAUSED   = 15  # red
P_TEAL     = 16  # teal
P_STATUS   = 17  # green on black
P_CYAN     = 18  # bright cyan on black

# ─────────────────────────────────────────────────────────────────────────────
#  EQUALIZER SIMULATOR
# ─────────────────────────────────────────────────────────────────────────────
class EQSimulator:
    """
    Smooth musical EQ simulator.
    Uses overlapping sine layers + per-band randomness to mimic
    a real frequency spectrum — bass heavy low end, rolling mids,
    sparkly highs.
    """
    def __init__(self, bands: int = 32):
        self.bands   = bands
        self.vals    = [0.0] * bands
        self.smooth  = [0.0] * bands   # extra smoothed copy for display
        self.peaks   = [0.0] * bands
        self.pdecay  = [0.0] * bands
        self.phase   = [random.uniform(0, 2 * math.pi) for _ in range(bands)]
        self.phase2  = [random.uniform(0, 2 * math.pi) for _ in range(bands)]
        self.phase3  = [random.uniform(0, 2 * math.pi) for _ in range(bands)]
        self.speed   = [random.uniform(0.3, 1.2) for _ in range(bands)]
        self.speed2  = [random.uniform(1.5, 4.0) for _ in range(bands)]
        self.active  = False
        self.t       = 0.0
        # Per-band base energy — bass bands have more energy
        self.base    = [max(0.05, 0.55 * math.exp(-((i - 2)**2) / (2 * 4**2))
                        + 0.35 * math.exp(-((i - bands*0.3)**2) / (2 * (bands*0.15)**2))
                        + 0.15 * math.exp(-((i - bands*0.65)**2) / (2 * (bands*0.2)**2)))
                        for i in range(bands)]

    def tick(self, dt: float = 0.04):
        if not self.active:
            self.vals   = [max(0, v * 0.78) for v in self.vals]
            self.smooth = [max(0, v * 0.82) for v in self.smooth]
            self.peaks  = [max(0, p * 0.93) for p in self.peaks]
            return
        self.t += dt
        for i in range(self.bands):
            b = self.base[i]
            # Three overlapping sine layers for organic movement
            w1 = math.sin(self.t * self.speed[i]  + self.phase[i])
            w2 = math.sin(self.t * self.speed2[i] + self.phase2[i]) * 0.4
            w3 = math.sin(self.t * self.speed[i] * 0.3 + self.phase3[i]) * 0.25
            noise = random.gauss(0, 0.06)
            raw = b * (0.5 + 0.5 * w1) + b * 0.3 * w2 + b * 0.2 * w3 + noise * b
            raw = max(0.0, min(1.0, raw))
            # Fast attack, slow release (like a VU meter)
            if raw > self.vals[i]:
                self.vals[i] = self.vals[i] * 0.3 + raw * 0.7   # fast attack
            else:
                self.vals[i] = self.vals[i] * 0.82 + raw * 0.18  # slow release
            # Extra smoothing layer for silky display
            self.smooth[i] = self.smooth[i] * 0.65 + self.vals[i] * 0.35
            # Peak hold + slow fall
            if self.smooth[i] >= self.peaks[i]:
                self.peaks[i]  = self.smooth[i]
                self.pdecay[i] = 0.0
            else:
                self.pdecay[i] += dt
                if self.pdecay[i] > 0.55:
                    self.peaks[i] = max(self.smooth[i],
                                        self.peaks[i] - dt * 0.45)

# ─────────────────────────────────────────────────────────────────────────────
#  MPV IPC WRAPPER
# ─────────────────────────────────────────────────────────────────────────────
class MPVClient:
    def __init__(self, sock_path: str):
        self.sock_path = sock_path
        self._lock = threading.Lock()
        self._proc = None

    def launch(self, path: str) -> bool:
        """Start mpv and wait until IPC socket is ready."""
        self.kill()
        try:
            os.unlink(self.sock_path)
        except OSError:
            pass
        cmd = [
            "mpv", "--no-video",
            f"--input-ipc-server={self.sock_path}",
            "--idle=yes",
            "--keep-open=yes",
            str(path),
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return False
        # Poll until socket file appears (up to 6 s)
        deadline = time.time() + 6.0
        while time.time() < deadline:
            if os.path.exists(self.sock_path):
                time.sleep(0.2)   # let mpv finish binding
                return True
            time.sleep(0.1)
        return False

    def _send(self, cmd: dict):
        if not os.path.exists(self.sock_path):
            return None
        try:
            with self._lock:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect(self.sock_path)
                s.sendall((json.dumps(cmd) + "\n").encode())
                resp = b""
                try:
                    while True:
                        chunk = s.recv(4096)
                        if not chunk:
                            break
                        resp += chunk
                        if b"\n" in resp:
                            break
                except socket.timeout:
                    pass
                s.close()
                for line in resp.split(b"\n"):
                    line = line.strip()
                    if line:
                        try:
                            return json.loads(line)
                        except:
                            pass
        except Exception:
            pass
        return None

    def _prop(self, name: str):
        r = self._send({"command": ["get_property", name]})
        if r and r.get("error") == "success":
            return r.get("data")
        return None

    def play(self):
        # Retry a few times in case mpv isn't quite ready
        for _ in range(5):
            self._send({"command": ["set_property", "pause", False]})
            time.sleep(0.1)
            if not self.is_paused():
                return

    def pause(self):
        self._send({"command": ["set_property", "pause", True]})

    def is_paused(self) -> bool:
        r = self._prop("pause")
        return bool(r) if r is not None else True

    def position(self) -> float:
        p = self._prop("time-pos")
        return float(p) if p is not None else 0.0

    def duration(self) -> float:
        d = self._prop("duration")
        return float(d) if d is not None else 0.0

    def seek(self, secs: float):
        self._send({"command": ["seek", secs, "relative"]})

    def seek_abs(self, secs: float):
        self._send({"command": ["seek", secs, "absolute"]})

    def load(self, path: str):
        """Load file and wait until mpv is ready to play."""
        self._send({"command": ["loadfile", str(path), "replace"]})
        # Wait for duration to become available
        deadline = time.time() + 5.0
        while time.time() < deadline:
            d = self._prop("duration")
            if d is not None and float(d) > 0:
                return
            time.sleep(0.15)

    def volume(self, v: int):
        self._send({"command": ["set_property", "volume", v]})

    def get_volume(self) -> int:
        v = self._prop("volume")
        return int(v) if v is not None else 100

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def eof(self) -> bool:
        r = self._prop("eof-reached")
        return bool(r) if r is not None else False

    def kill(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except:
                pass
            self._proc = None
        try:
            os.unlink(self.sock_path)
        except OSError:
            pass

# ─────────────────────────────────────────────────────────────────────────────
#  LYRICS FETCHER
# ─────────────────────────────────────────────────────────────────────────────
def _http_get(url: str, timeout: int = 8) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NovaPlayer/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return ""

import re as _re

def _clean_title(t: str) -> str:
    """Strip noise from filenames/tags before searching."""
    t = _re.sub(r"\(feat\.?[^)]*\)", "", t, flags=_re.I)
    t = _re.sub(r"\[.*?\]", "", t)
    t = _re.sub(r"\(.*?(remix|edit|version|remaster|live|acoustic|radio|official|lyric|video|audio|hd|hq)[^)]*\)", "", t, flags=_re.I)
    t = _re.sub(r"\s*[-_|]\s*", " ", t)
    t = _re.sub(r"\s+", " ", t).strip()
    return t

def _extract_artist_from_filename(filename: str) -> tuple[str, str]:
    """
    Try to pull artist + title from common filename patterns:
      "Artist - Title"
      "Title (Artist)"      ← e.g. "Aaoge Tum Kabhi (The Local Train)"
      "Artist_Title"
    Returns (artist, title) or ("", original)
    """
    name = _re.sub(r"\.(mp3|flac|m4a|ogg|wav|aac|opus|wma)$", "", filename, flags=_re.I)

    # Pattern: "Title (Band Name)"  — parenthesised artist at end
    m = _re.match(r"^(.+?)\s*\(([^)]{3,40})\)\s*$", name.strip())
    if m:
        title_part  = m.group(1).strip()
        artist_part = m.group(2).strip()
        # Only treat as artist if it doesn't look like a year or quality tag
        if not _re.match(r"^\d{4}$", artist_part) and not _re.match(r"^(hd|hq|\d+p|official)$", artist_part, _re.I):
            return artist_part, title_part

    # Pattern: "Artist - Title" or "Artist – Title"
    m = _re.match(r"^(.+?)\s*[-–]\s*(.+)$", name.strip())
    if m:
        a, t = m.group(1).strip(), m.group(2).strip()
        if 2 <= len(a) <= 50 and 2 <= len(t) <= 100:
            return a, t

    return "", _clean_title(name)

def _lrclib_try(params: dict) -> dict | None:
    raw = _http_get(f"{LYRICS_API}?" + urllib.parse.urlencode(params))
    if not raw:
        return None
    try:
        d = json.loads(raw)
        if isinstance(d, dict) and (d.get("syncedLyrics") or d.get("plainLyrics")):
            return d
    except:
        pass
    return None

def _lrclib_search(query: str, artist: str = "") -> tuple[list, bool]:
    """lrclib /api/search — fuzzy search, returns best result."""
    params = {"q": query}
    if artist:
        params["artist_name"] = artist
    raw = _http_get("https://lrclib.net/api/search?" + urllib.parse.urlencode(params))
    if not raw:
        return [], False
    try:
        results = json.loads(raw)
        if not isinstance(results, list) or not results:
            return [], False
        # Prefer synced, then plain
        for prefer_synced in (True, False):
            for r in results[:8]:
                has = r.get("syncedLyrics") if prefer_synced else r.get("plainLyrics")
                if has:
                    if prefer_synced:
                        return _parse_lrc(r["syncedLyrics"]), True
                    else:
                        return [(-1.0, l) for l in r["plainLyrics"].splitlines() if l.strip()], False
    except:
        pass
    return [], False

def _extract_result(data: dict) -> tuple[list, bool]:
    synced = data.get("syncedLyrics") or ""
    plain  = data.get("plainLyrics")  or ""
    if synced:
        return _parse_lrc(synced), True
    if plain:
        return [(-1.0, l) for l in plain.splitlines() if l.strip()], False
    return [], False

def fetch_lyrics(artist: str, title: str, duration: float = 0,
                 filename: str = "") -> tuple[list, bool]:
    """
    Aggressive multi-strategy lyrics fetch. Works even with Unknown Artist tags.

    Strategies tried in order:
      1. Known artist + title (if artist tag looks valid)
      2. Title-only GET
      3. Cleaned title GET
      4. Artist extracted from filename + cleaned title
      5. Fuzzy search with cleaned title
      6. Fuzzy search with raw title
    """
    if not title and not filename:
        return [], False

    BAD_ARTISTS = {"unknown artist", "unknown", "", "va", "various artists", "various"}
    known_artist = artist.strip() if artist.strip().lower() not in BAD_ARTISTS else ""

    raw_title    = (title or "").strip()
    clean_ttl    = _clean_title(raw_title)

    # Try to extract artist+title from the filename
    fn_artist, fn_title = "", ""
    if filename:
        fn_artist, fn_title = _extract_artist_from_filename(filename)
        fn_title = _clean_title(fn_title) if fn_title else ""

    tried = set()

    def _try_get(art, ttl):
        key = (art.lower(), ttl.lower())
        if key in tried or not ttl:
            return None
        tried.add(key)
        params = {"track_name": ttl}
        if art:
            params["artist_name"] = art
        return _lrclib_try(params)

    # 1. Known tag artist + raw title
    d = _try_get(known_artist, raw_title)
    if d: return _extract_result(d)

    # 2. Title only (no artist)
    d = _try_get("", raw_title)
    if d: return _extract_result(d)

    # 3. Cleaned title only
    d = _try_get("", clean_ttl)
    if d: return _extract_result(d)

    # 4. Filename-extracted artist + filename-extracted title
    if fn_artist or fn_title:
        d = _try_get(fn_artist, fn_title or clean_ttl)
        if d: return _extract_result(d)
        # also try with no artist
        d = _try_get("", fn_title or clean_ttl)
        if d: return _extract_result(d)

    # 5. Known artist + cleaned title
    if known_artist:
        d = _try_get(known_artist, clean_ttl)
        if d: return _extract_result(d)

    # 6. Fuzzy search — broadest net
    search_q = fn_title or clean_ttl or raw_title
    lines, synced = _lrclib_search(search_q, artist=fn_artist or known_artist)
    if lines:
        return lines, synced

    # 7. Fuzzy search title only, no artist hint
    if fn_artist or known_artist:
        lines, synced = _lrclib_search(search_q)
        if lines:
            return lines, synced

    return [], False

def _parse_lrc(lrc: str) -> list:
    lines = []
    for line in lrc.splitlines():
        line = line.strip()
        if line.startswith("[") and "]" in line:
            tag_end = line.index("]")
            tag  = line[1:tag_end]
            text = line[tag_end+1:].strip()
            try:
                parts = tag.split(":")
                mins  = float(parts[0])
                secs  = float(parts[1])
                lines.append((mins * 60 + secs, text))
            except:
                pass
    return sorted(lines, key=lambda x: x[0])

# ─────────────────────────────────────────────────────────────────────────────
#  ROMANIZER  — 100% FREE, zero-dependency, works fully offline
#  Built-in char maps for Devanagari/Hindi, Bengali, Gujarati, Punjabi,
#  Tamil, Telugu, Kannada, Malayalam, Arabic/Urdu
#  + optional indic-transliteration (pip install indic-transliteration)
#  + aksharamukha web API as bonus fallback
# ─────────────────────────────────────────────────────────────────────────────

try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate as _indic_trans
    HAS_INDIC = True
except ImportError:
    HAS_INDIC = False

# ── Built-in Devanagari → Roman map (covers Hindi, Marathi, Sanskrit) ────────
_DEVA = {
    # Vowels
    'अ':'a','आ':'aa','इ':'i','ई':'ee','उ':'u','ऊ':'oo','ऋ':'ri',
    'ए':'e','ऐ':'ai','ओ':'o','औ':'au','अं':'an','अः':'ah',
    # Vowel matras
    'ा':'aa','ि':'i','ी':'ee','ु':'u','ू':'oo','ृ':'ri',
    'े':'e','ै':'ai','ो':'o','ौ':'au','ं':'n','ः':'h','्':'',
    # Consonants
    'क':'k','ख':'kh','ग':'g','घ':'gh','ङ':'ng',
    'च':'ch','छ':'chh','ज':'j','झ':'jh','ञ':'ny',
    'ट':'t','ठ':'th','ड':'d','ढ':'dh','ण':'n',
    'त':'t','थ':'th','द':'d','ध':'dh','न':'n',
    'प':'p','फ':'ph','ब':'b','भ':'bh','म':'m',
    'य':'y','र':'r','ल':'l','व':'v','श':'sh',
    'ष':'sh','स':'s','ह':'h','ळ':'l','क्ष':'ksh','ज्ञ':'gya',
    # Common conjuncts
    'क्':'k','ग्':'g','ज्':'j','त्':'t','द्':'d','न्':'n',
    'प्':'p','म्':'m','र्':'r','ल्':'l','स्':'s','ह्':'h',
    # Numerals
    '०':'0','१':'1','२':'2','३':'3','४':'4',
    '५':'5','६':'6','७':'7','८':'8','९':'9',
    # Punctuation
    '।':'.','॥':'..','ऽ':"'",
}

# ── Bengali → Roman ───────────────────────────────────────────────────────────
_BENG = {
    'অ':'a','আ':'aa','ই':'i','ঈ':'ee','উ':'u','ঊ':'oo','এ':'e','ঐ':'oi','ও':'o','ঔ':'ou',
    'া':'aa','ি':'i','ী':'ee','ু':'u','ূ':'oo','ে':'e','ৈ':'oi','ো':'o','ৌ':'ou','ং':'ng','ঃ':'h','্':'',
    'ক':'k','খ':'kh','গ':'g','ঘ':'gh','ঙ':'ng',
    'চ':'ch','ছ':'chh','জ':'j','ঝ':'jh','ঞ':'ny',
    'ট':'t','ঠ':'th','ড':'d','ঢ':'dh','ণ':'n',
    'ত':'t','থ':'th','দ':'d','ধ':'dh','ন':'n',
    'প':'p','ফ':'ph','ব':'b','ভ':'bh','ম':'m',
    'য':'y','র':'r','ল':'l','শ':'sh','ষ':'sh','স':'s','হ':'h','ড়':'r','ঢ়':'rh','য়':'y',
    '০':'0','১':'1','২':'2','৩':'3','৪':'4','৫':'5','৬':'6','৭':'7','৮':'8','৯':'9',
}

# ── Gujarati → Roman ──────────────────────────────────────────────────────────
_GUJA = {
    'અ':'a','આ':'aa','ઇ':'i','ઈ':'ee','ઉ':'u','ઊ':'oo','એ':'e','ઐ':'ai','ઓ':'o','ઔ':'au',
    'ા':'aa','િ':'i','ી':'ee','ુ':'u','ૂ':'oo','ે':'e','ૈ':'ai','ો':'o','ૌ':'au','ં':'n','ઃ':'h','્':'',
    'ક':'k','ખ':'kh','ગ':'g','ઘ':'gh','ચ':'ch','છ':'chh','જ':'j','ઝ':'jh',
    'ટ':'t','ઠ':'th','ડ':'d','ઢ':'dh','ણ':'n','ત':'t','થ':'th','દ':'d','ધ':'dh','ન':'n',
    'પ':'p','ફ':'ph','બ':'b','ભ':'bh','મ':'m','ય':'y','ર':'r','લ':'l','વ':'v','શ':'sh','સ':'s','હ':'h',
}

# ── Gurmukhi/Punjabi → Roman ──────────────────────────────────────────────────
_GURU = {
    'ਅ':'a','ਆ':'aa','ਇ':'i','ਈ':'ee','ਉ':'u','ਊ':'oo','ਏ':'e','ਐ':'ai','ਓ':'o','ਔ':'au',
    'ਾ':'aa','ਿ':'i','ੀ':'ee','ੁ':'u','ੂ':'oo','ੇ':'e','ੈ':'ai','ੋ':'o','ੌ':'au','ੰ':'n','ਃ':'h','੍':'',
    'ਕ':'k','ਖ':'kh','ਗ':'g','ਘ':'gh','ਙ':'ng','ਚ':'ch','ਛ':'chh','ਜ':'j','ਝ':'jh',
    'ਟ':'t','ਠ':'th','ਡ':'d','ਢ':'dh','ਣ':'n','ਤ':'t','ਥ':'th','ਦ':'d','ਧ':'dh','ਨ':'n',
    'ਪ':'p','ਫ':'ph','ਬ':'b','ਭ':'bh','ਮ':'m','ਯ':'y','ਰ':'r','ਲ':'l','ਵ':'v','ਸ਼':'sh','ਸ':'s','ਹ':'h',
    '੦':'0','੧':'1','੨':'2','੩':'3','੪':'4','੫':'5','੬':'6','੭':'7','੮':'8','੯':'9',
}

# ── Arabic/Urdu → Roman (common phonetic mapping) ────────────────────────────
_ARAB = {
    'ا':'a','ب':'b','پ':'p','ت':'t','ٹ':'t','ث':'s','ج':'j','چ':'ch','ح':'h','خ':'kh',
    'د':'d','ڈ':'d','ذ':'z','ر':'r','ڑ':'r','ز':'z','ژ':'zh','س':'s','ش':'sh','ص':'s',
    'ض':'z','ط':'t','ظ':'z','ع':"'a",'غ':'gh','ف':'f','ق':'q','ک':'k','گ':'g','ل':'l',
    'م':'m','ن':'n','و':'w','ہ':'h','ھ':'h','ی':'y','ے':'e','ئ':'y','ء':"'",'آ':'aa',
    'اَ':'a','اِ':'i','اُ':'u','ان':'an','وں':'on','یں':'en',
    'َ':'a','ُ':'u','ِ':'i','ّ':'','ْ':'',  # harakat
    '۰':'0','۱':'1','۲':'2','۳':'3','۴':'4','۵':'5','۶':'6','۷':'7','۸':'8','۹':'9',
}

# ── Tamil → Roman ─────────────────────────────────────────────────────────────
_TAML = {
    'அ':'a','ஆ':'aa','இ':'i','ஈ':'ee','உ':'u','ஊ':'oo','எ':'e','ஏ':'ae','ஐ':'ai','ஒ':'o','ஓ':'oo','ஔ':'au',
    'ா':'aa','ி':'i','ீ':'ee','ு':'u','ூ':'oo','ெ':'e','ே':'ae','ை':'ai','ொ':'o','ோ':'oo','ௌ':'au','்':'',
    'க':'k','ங':'ng','ச':'ch','ஞ':'ny','ட':'t','ண':'n','த':'th','ந':'n','ப':'p','ம':'m',
    'ய':'y','ர':'r','ல':'l','வ':'v','ழ':'zh','ள':'l','ற':'tr','ன':'n','ஜ':'j','ஷ':'sh','ஸ':'s','ஹ':'h',
}

# ── Telugu → Roman ────────────────────────────────────────────────────────────
_TELU = {
    'అ':'a','ఆ':'aa','ఇ':'i','ఈ':'ee','ఉ':'u','ఊ':'oo','ఎ':'e','ఏ':'ae','ఐ':'ai','ఒ':'o','ఓ':'oo','ఔ':'au',
    'ా':'aa','ి':'i','ీ':'ee','ు':'u','ూ':'oo','ె':'e','ే':'ae','ై':'ai','ొ':'o','ో':'oo','ౌ':'au','్':'',
    'క':'k','ఖ':'kh','గ':'g','ఘ':'gh','ఙ':'ng','చ':'ch','ఛ':'chh','జ':'j','ఝ':'jh','ఞ':'ny',
    'ట':'t','ఠ':'th','డ':'d','ఢ':'dh','ణ':'n','త':'t','థ':'th','ద':'d','ధ':'dh','న':'n',
    'ప':'p','ఫ':'ph','బ':'b','భ':'bh','మ':'m','య':'y','ర':'r','ల':'l','వ':'v','శ':'sh','ష':'sh','స':'s','హ':'h',
}

# ── Kannada → Roman ───────────────────────────────────────────────────────────
_KANN = {
    'ಅ':'a','ಆ':'aa','ಇ':'i','ಈ':'ee','ಉ':'u','ಊ':'oo','ಎ':'e','ಏ':'ae','ಐ':'ai','ಒ':'o','ಓ':'oo','ಔ':'au',
    'ಾ':'aa','ಿ':'i','ೀ':'ee','ು':'u','ೂ':'oo','ೆ':'e','ೇ':'ae','ೈ':'ai','ೊ':'o','ೋ':'oo','ೌ':'au','್':'',
    'ಕ':'k','ಖ':'kh','ಗ':'g','ಘ':'gh','ಙ':'ng','ಚ':'ch','ಛ':'chh','ಜ':'j','ಝ':'jh','ಞ':'ny',
    'ಟ':'t','ಠ':'th','ಡ':'d','ಢ':'dh','ಣ':'n','ತ':'t','ಥ':'th','ದ':'d','ಧ':'dh','ನ':'n',
    'ಪ':'p','ಫ':'ph','ಬ':'b','ಭ':'bh','ಮ':'m','ಯ':'y','ರ':'r','ಲ':'l','ವ':'v','ಶ':'sh','ಷ':'sh','ಸ':'s','ಹ':'h',
}

# ── Malayalam → Roman ─────────────────────────────────────────────────────────
_MALY = {
    'അ':'a','ആ':'aa','ഇ':'i','ഈ':'ee','ഉ':'u','ഊ':'oo','എ':'e','ഏ':'ae','ഐ':'ai','ഒ':'o','ഓ':'oo','ഔ':'au',
    'ാ':'aa','ി':'i','ീ':'ee','ു':'u','ൂ':'oo','െ':'e','േ':'ae','ൈ':'ai','ൊ':'o','ോ':'oo','ൌ':'au','്':'',
    'ക':'k','ഖ':'kh','ഗ':'g','ഘ':'gh','ങ':'ng','ച':'ch','ഛ':'chh','ജ':'j','ഝ':'jh','ഞ':'ny',
    'ട':'t','ഠ':'th','ഡ':'d','ഢ':'dh','ണ':'n','ത':'t','ഥ':'th','ദ':'d','ധ':'dh','ന':'n',
    'പ':'p','ഫ':'ph','ബ':'b','ഭ':'bh','മ':'m','യ':'y','ര':'r','ല':'l','വ':'v','ശ':'sh','ഷ':'sh','സ':'s','ഹ':'h',
}

_SCRIPT_MAP = {
    "DEVANAGARI": _DEVA,
    "BENGALI":    _BENG,
    "GUJARATI":   _GUJA,
    "GURMUKHI":   _GURU,
    "ARABIC":     _ARAB,
    "TAMIL":      _TAML,
    "TELUGU":     _TELU,
    "KANNADA":    _KANN,
    "MALAYALAM":  _MALY,
}

def _is_non_latin(text):
    if not text:
        return False
    non_latin = sum(1 for c in text if ord(c) > 0x024F and not c.isspace())
    total     = sum(1 for c in text if not c.isspace())
    return total > 0 and (non_latin / total) > 0.25

def _detect_script(text):
    counts = {}
    for c in text:
        cp = ord(c)
        if   0x0900 <= cp <= 0x097F: counts["DEVANAGARI"] = counts.get("DEVANAGARI",0)+1
        elif 0x0980 <= cp <= 0x09FF: counts["BENGALI"]    = counts.get("BENGALI",0)+1
        elif 0x0A80 <= cp <= 0x0AFF: counts["GUJARATI"]   = counts.get("GUJARATI",0)+1
        elif 0x0A00 <= cp <= 0x0A7F: counts["GURMUKHI"]   = counts.get("GURMUKHI",0)+1
        elif 0x0B80 <= cp <= 0x0BFF: counts["TAMIL"]      = counts.get("TAMIL",0)+1
        elif 0x0C00 <= cp <= 0x0C7F: counts["TELUGU"]     = counts.get("TELUGU",0)+1
        elif 0x0C80 <= cp <= 0x0CFF: counts["KANNADA"]    = counts.get("KANNADA",0)+1
        elif 0x0D00 <= cp <= 0x0D7F: counts["MALAYALAM"]  = counts.get("MALAYALAM",0)+1
        elif 0x0600 <= cp <= 0x06FF: counts["ARABIC"]     = counts.get("ARABIC",0)+1
    return max(counts, key=counts.get) if counts else None

def _apply_charmap(text, cmap):
    """Apply a character substitution map to text, longest match first."""
    result = []
    i = 0
    while i < len(text):
        # Try 3-char, 2-char, 1-char matches (for conjuncts etc.)
        matched = False
        for length in (3, 2, 1):
            chunk = text[i:i+length]
            if chunk in cmap:
                result.append(cmap[chunk])
                i += length
                matched = True
                break
        if not matched:
            result.append(text[i])  # keep unknown char as-is
            i += 1
    # Clean up: collapse repeated vowels (aaa→aa), fix spacing
    out = "".join(result)
    # Add implicit 'a' after consonants not followed by vowel marker
    # (simplified — just clean up double spaces)
    import re
    out = re.sub(r"  +", " ", out).strip()
    return out

def _romanize_line_builtin(text, script):
    """Pure Python built-in romanization — works fully offline, no deps."""
    cmap = _SCRIPT_MAP.get(script)
    if not cmap:
        return None
    result = _apply_charmap(text, cmap)
    # Post-process: if Devanagari, add implicit 'a' after bare consonants
    # (virama handles this already via '' mapping, so we just clean up)
    return result if result.strip() else None

def _romanize_line_indic(text, script):
    """indic_transliteration library (if installed)."""
    if not HAS_INDIC:
        return None
    _SCHEME = {
        "DEVANAGARI":"DEVANAGARI","GUJARATI":"GUJARATI","GURMUKHI":"GURMUKHI",
        "BENGALI":"BENGALI","TAMIL":"TAMIL","TELUGU":"TELUGU",
        "KANNADA":"KANNADA","MALAYALAM":"MALAYALAM",
    }
    scheme = _SCHEME.get(script)
    if not scheme:
        return None
    try:
        return _indic_trans(text, getattr(sanscript, scheme), sanscript.IAST)
    except Exception:
        return None

def _romanize_line_aksharamukha(text, script):
    """aksharamukha free web API — fallback when offline methods insufficient."""
    _AK = {
        "DEVANAGARI":"Devanagari","GUJARATI":"Gujarati","GURMUKHI":"Gurmukhi",
        "BENGALI":"Bengali","TAMIL":"Tamil","TELUGU":"Telugu",
        "KANNADA":"Kannada","MALAYALAM":"Malayalam","ARABIC":"Arabic",
    }
    src = _AK.get(script)
    if not src:
        return None
    try:
        params = urllib.parse.urlencode({"from":src,"to":"IASTPlusTrans","text":text,"strict":"false"})
        raw = _http_get(f"https://aksharamukha-plugin.appspot.com/api/public?{params}", timeout=6)
        return raw.strip() if raw and raw.strip() else None
    except Exception:
        return None

def _romanize_single(text):
    if not _is_non_latin(text):
        return text
    script = _detect_script(text)
    if not script:
        return text
    # 1. indic_transliteration (best quality, if installed)
    r = _romanize_line_indic(text, script)
    if r and r.strip() and _is_non_latin(r) is False:
        return r
    # 2. Built-in char map (always works, offline)
    r = _romanize_line_builtin(text, script)
    if r and r.strip():
        return r
    # 3. aksharamukha web API (bonus quality boost if online)
    r = _romanize_line_aksharamukha(text, script)
    if r and r.strip():
        return r
    return text   # give up, show original

def romanize_lyrics(lines):
    if not lines:
        return lines
    sample = " ".join(t for (_, t) in lines[:10] if t.strip())
    if not _is_non_latin(sample):
        return lines
    result = []
    changed = False
    for ts, text in lines:
        if text.strip() and _is_non_latin(text):
            roman = _romanize_single(text)
            result.append((ts, roman))
            if roman != text:
                changed = True
        else:
            result.append((ts, text))
    return result if changed else lines
# ─────────────────────────────────────────────────────────────────────────────
#  METADATA READER
# ─────────────────────────────────────────────────────────────────────────────
def read_meta(path: Path) -> dict:
    meta = {"title": path.stem, "artist": "Unknown Artist", "album": ""}
    if not HAS_MUTAGEN:
        return meta
    try:
        f = MFile(path)
        if f is None:
            return meta
        tags = f.tags
        if tags is None:
            return meta
        def g(keys):
            for k in keys:
                v = tags.get(k)
                if v:
                    val = str(v[0]) if hasattr(v, '__iter__') and not isinstance(v, str) else str(v)
                    if val.strip():
                        return val.strip()
            return None
        meta["title"]  = g(["TIT2","©nam","TITLE","title"]) or meta["title"]
        meta["artist"] = g(["TPE1","©ART","ARTIST","artist"]) or meta["artist"]
        meta["album"]  = g(["TALB","©alb","ALBUM","album"]) or ""
    except Exception:
        pass
    return meta

# ─────────────────────────────────────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
def fmt_time(secs: float) -> str:
    secs = max(0, int(secs))
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def trunc(s: str, w: int) -> str:
    if len(s) > w:
        return s[:w-1] + "…"
    return s

# ─────────────────────────────────────────────────────────────────────────────
#  PLAYER STATE
# ─────────────────────────────────────────────────────────────────────────────
class PlayerState:
    def __init__(self, songs_dir: Path):
        self.songs_dir   = songs_dir
        self.songs       : list[Path] = []
        self.current_idx : int = 0
        self.list_offset : int = 0          # scroll offset in song list
        self.volume      : int = 80
        self.shuffle     : bool = False
        self.repeat      : bool = False
        self.meta        : dict = {}
        self.lyrics      : list[tuple[float,str]] = []
        self.lyrics_sync : bool = False
        self.lyrics_off  : int  = 0         # scroll offset in lyrics
        self.lyrics_auto : bool = True      # auto-scroll lyrics
        self.lyrics_fetching   : bool = False
        self.lyrics_romanizing : bool = False
        self.lyrics_romanized  : list = []
        self.lyrics_show_roman : bool = True
        self.lyrics_sync_offset: float = 0.0  # seconds: +later -earlier
        self.sync_offsets : dict = {}         # per-song offset cache
        self.lyrics_msg  : str = ""
        self.status_msg  : str = ""
        self.status_ts   : float = 0
        self.focus       : str = "list"     # list | lyrics
        self.mpv_started : bool = False
        self.eq             : EQSimulator = EQSimulator(28)
        self.shuffle_queue  : list[int] = []
        self.search_mode    : bool = False
        self.search_query   : str  = ''
        self.search_results : list = []   # indices into self.songs
        self.search_cursor  : int  = 0    # selected result index
        self.recording      : bool  = False
        self.rec_path       : str   = ''
        self.dl_mode        : bool  = False
        self.dl_query       : str   = ''
        self.dl_results     : list  = []
        self.dl_cursor      : int   = 0
        self.dl_status      : str   = ''
        self.dl_searching   : bool  = False
        self.dl_downloading : bool  = False
        self.dl_progress    : str   = ''

    def refresh_songs(self):
        self.songs = sorted(
            [p for p in self.songs_dir.iterdir() if p.suffix.lower() in AUDIO_EXTS],
            key=lambda p: p.name.lower(),
        )

    def status(self, msg: str, dur: float = 3.0):
        self.status_msg = msg
        self.status_ts  = time.time() + dur

    def get_status(self) -> str:
        if time.time() < self.status_ts:
            return self.status_msg
        return ""

    def next_track(self) -> int | None:
        if not self.songs:
            return None
        if self.shuffle:
            if not self.shuffle_queue:
                self.shuffle_queue = list(range(len(self.songs)))
                random.shuffle(self.shuffle_queue)
            nxt = self.shuffle_queue.pop(0)
            self.current_idx = nxt
        else:
            self.current_idx = (self.current_idx + 1) % len(self.songs)
        return self.current_idx

    def prev_track(self) -> int | None:
        if not self.songs:
            return None
        self.current_idx = (self.current_idx - 1) % len(self.songs)
        return self.current_idx

    def run_search(self):
        q = self.search_query.lower().strip()
        if not q:
            self.search_results = list(range(len(self.songs)))
        else:
            self.search_results = [
                i for i, s in enumerate(self.songs)
                if q in s.stem.lower()
            ]
        self.search_cursor = 0

# ─────────────────────────────────────────────────────────────────────────────
#  DRAWING  ENGINE
# ─────────────────────────────────────────────────────────────────────────────
LOGO_LINES = [
    "  ███╗  ██╗ ██████╗ ██╗   ██╗ █████╗ ",
    "  ████╗ ██║██╔═══██╗██║   ██║██╔══██╗",
    "  ██╔██╗██║██║   ██║╚██╗ ██╔╝███████║",
    "  ██║╚████║╚██████╔╝  ╚███╔╝ ██║  ██║",
    "  ╚═╝ ╚═══╝ ╚═════╝    ╚══╝  ╚═╝  ╚═╝",
]

EQ_CHARS  = " ▁▂▃▄▅▆▇█"
PEAK_CHAR = "▲"

def draw_box(win, y, x, h, w, pair, title: str = ""):
    try:
        # Corners
        win.addstr(y,       x,       "╔", curses.color_pair(pair))
        win.addstr(y,       x+w-1,   "╗", curses.color_pair(pair))
        win.addstr(y+h-1,   x,       "╚", curses.color_pair(pair))
        win.addstr(y+h-1,   x+w-1,   "╝", curses.color_pair(pair))
        # Sides
        for i in range(1, w-1):
            win.addstr(y,     x+i, "═", curses.color_pair(pair))
            win.addstr(y+h-1, x+i, "═", curses.color_pair(pair))
        for i in range(1, h-1):
            win.addstr(y+i, x,     "║", curses.color_pair(pair))
            win.addstr(y+i, x+w-1, "║", curses.color_pair(pair))
        if title:
            t = f"[ {title} ]"
            tx = x + max(1, (w - len(t)) // 2)
            win.addstr(y, tx, t, curses.color_pair(P_HEADER) | curses.A_BOLD)
    except curses.error:
        pass

def draw_progress(win, y, x, w, pos, dur, pair_fill, pair_empty):
    if dur <= 0:
        return
    filled = int((pos / dur) * w)
    filled = clamp(filled, 0, w)
    bar_fill  = "━" * filled
    bar_empty = "─" * (w - filled)
    try:
        win.addstr(y, x, bar_fill,  curses.color_pair(pair_fill)  | curses.A_BOLD)
        win.addstr(y, x + filled, bar_empty, curses.color_pair(pair_empty))
    except curses.error:
        pass

# Sub-character vertical resolution blocks (bottom → top)
_EIGHTH_BLOCKS = " ▁▂▃▄▅▆▇█"

def draw_eq(win, y, x, w, h, eq: EQSimulator):
    """
    Soul-touching spectrum visualizer.
    - Sub-character top block for silky smooth heights
    - Per-ROW colour gradient: deep teal → cyan → magenta → fire orange
    - Slim ─ peak line that floats and falls
    - Dim reflection glow below each bar
    """
    bands = eq.bands
    # Each bar = 1 char wide, 1 char gap → fits 2*bands chars ideally
    # Fill the full width by spacing evenly
    if bands * 2 <= w:
        bar_w    = 1
        spacing  = max(1, (w) // bands)   # chars per band slot (bar+gap)
    else:
        spacing  = max(1, w // bands)
        bar_w    = 1

    # Row-level colour gradient palette (index 0=bottom, h-1=top)
    def row_pair(row_from_bottom: int, total: int) -> int:
        ratio = row_from_bottom / max(1, total - 1)
        if ratio < 0.35:
            return P_EQ1          # deep cyan / teal  (bass floor)
        elif ratio < 0.65:
            return P_TEAL         # bright teal / green (mids)
        elif ratio < 0.82:
            return P_EQ2          # magenta / purple (upper mids)
        else:
            return P_EQ3          # yellow / orange / fire (peaks)

    for i in range(bands):
        bx = x + i * spacing
        if bx >= x + w:
            break

        val  = eq.smooth[i]
        peak = eq.peaks[i]

        # Full-character bar height + fractional remainder
        full_h   = int(val * h)
        frac     = (val * h) - full_h          # 0.0–1.0 remainder
        frac_idx = int(frac * 8)               # index into _EIGHTH_BLOCKS

        full_h = clamp(full_h, 0, h)
        peak_y = int((1.0 - peak) * (h - 1))
        peak_y = clamp(peak_y, 0, h - 1)

        for row in range(h):
            bar_row_from_bottom = (h - 1) - row   # 0 = bottom row
            pair = row_pair(bar_row_from_bottom, h)
            bx2 = bx
            try:
                if bar_row_from_bottom < full_h:
                    # Solid filled block
                    win.addstr(y + row, bx2, "█", curses.color_pair(pair) | curses.A_BOLD)
                elif bar_row_from_bottom == full_h and frac_idx > 0:
                    # Sub-character fractional top
                    ch = _EIGHTH_BLOCKS[frac_idx]
                    win.addstr(y + row, bx2, ch, curses.color_pair(pair) | curses.A_BOLD)
                else:
                    # Empty — tiny dot every 4 rows for depth grid
                    if bar_row_from_bottom % 4 == 0 and bar_row_from_bottom > 0:
                        win.addstr(y + row, bx2, "·", curses.color_pair(P_GRAY) | curses.A_DIM)
                    else:
                        win.addstr(y + row, bx2, " ", curses.color_pair(P_GRAY))
            except curses.error:
                pass

        # Floating peak line — elegant ─ character
        try:
            pk_pair = P_EQ3 if peak > 0.75 else (P_EQ2 if peak > 0.45 else P_EQ1)
            win.addstr(y + peak_y, bx, "─", curses.color_pair(pk_pair) | curses.A_BOLD)
        except curses.error:
            pass

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN TUI  (curses entry)
# ─────────────────────────────────────────────────────────────────────────────
def init_colors():
    curses.start_color()
    curses.use_default_colors()
    def p(n, fg, bg=-1):
        try:
            curses.init_pair(n, fg, bg)
        except:
            pass

    # Check 256-colour support
    if curses.COLORS >= 256:
        p(P_TITLE,    C_CYAN,    -1)
        p(P_ARTIST,   C_MAGENTA, -1)
        p(P_NORMAL,   C_WHITE,   -1)
        p(P_SELECTED, C_BLACK,   C_CYAN)
        p(P_PROGRESS, C_GREEN,   -1)
        p(P_BORDER,   C_BLUE,    -1)
        p(P_LYRICS,   C_YELLOW,  -1)
        p(P_LYRHI,    C_BLACK,   C_YELLOW)
        p(P_HEADER,   C_ORANGE,  -1)
        p(P_GRAY,     C_GRAY,    -1)
        p(P_KEY,      C_PINK,    -1)
        p(P_EQ1,      C_CYAN,    -1)
        p(P_EQ2,      C_MAGENTA, -1)
        p(P_EQ3,      C_YELLOW,  -1)
        p(P_PAUSED,   C_RED,     -1)
        p(P_TEAL,     C_TEAL,    -1)
        p(P_STATUS,   C_GREEN,   -1)
        p(P_CYAN,     C_CYAN,    -1)
    else:
        # Fallback 8-colour
        p(P_TITLE,    curses.COLOR_CYAN,    -1)
        p(P_ARTIST,   curses.COLOR_MAGENTA, -1)
        p(P_NORMAL,   curses.COLOR_WHITE,   -1)
        p(P_SELECTED, curses.COLOR_BLACK,   curses.COLOR_CYAN)
        p(P_PROGRESS, curses.COLOR_GREEN,   -1)
        p(P_BORDER,   curses.COLOR_BLUE,    -1)
        p(P_LYRICS,   curses.COLOR_YELLOW,  -1)
        p(P_LYRHI,    curses.COLOR_BLACK,   curses.COLOR_YELLOW)
        p(P_HEADER,   curses.COLOR_YELLOW,  -1)
        p(P_GRAY,     curses.COLOR_WHITE,   -1)
        p(P_KEY,      curses.COLOR_MAGENTA, -1)
        p(P_EQ1,      curses.COLOR_CYAN,    -1)
        p(P_EQ2,      curses.COLOR_MAGENTA, -1)
        p(P_EQ3,      curses.COLOR_YELLOW,  -1)
        p(P_PAUSED,   curses.COLOR_RED,     -1)
        p(P_TEAL,     curses.COLOR_CYAN,    -1)
        p(P_STATUS,   curses.COLOR_GREEN,   -1)
        p(P_CYAN,     curses.COLOR_CYAN,    -1)


# ─────────────────────────────────────────────────────────────────────────────
#  VIDEO RECORDER  -- aesthetic 9:16 MP4, Pillow only, no numpy
# ─────────────────────────────────────────────────────────────────────────────

REC_LOG = os.path.join(os.environ.get("TMPDIR", "/tmp"), "nova_rec.log")

def _rec_log(msg):
    try:
        with open(REC_LOG, "a") as f:
            f.write(time.strftime("%H:%M:%S") + "  " + str(msg) + "\n")
    except Exception:
        pass

def _find_rec_dir():
    for d in REC_DIRS:
        if d.exists():
            return d
    return Path.home()

def _find_font(size):
    import glob as _g
    candidates = [
        "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/system/fonts/Roboto-Regular.ttf",
        "/system/fonts/DroidSansMono.ttf",
        "/system/fonts/NotoSansMono-Regular.ttf",
        "/system/fonts/DroidSans.ttf",
        "/system/fonts/NotoSans-Regular.ttf",
    ]
    candidates += _g.glob("/system/fonts/*.ttf")[:6]
    candidates += _g.glob("/data/data/com.termux/files/usr/share/fonts/**/*.ttf",
                          recursive=True)[:8]
    for p in candidates:
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _rec_log(f"font {size}px -> {p}")
                return f
            except Exception:
                pass
    _rec_log(f"font {size}px -> PIL default")
    try:    return ImageFont.load_default(size=size)
    except: return ImageFont.load_default()

def _tw(draw, text, font):
    try:    return int(draw.textlength(text, font=font))
    except: pass
    try:
        bb = draw.textbbox((0,0), text, font=font)
        return bb[2]-bb[0]
    except: pass
    return len(text) * max(6, getattr(font,"size",12)//2)

def _t(draw, xy, text, font, fill):
    try:    draw.text(xy, text, font=font, fill=fill)
    except Exception as e: _rec_log("text:"+str(e))

def _fit(draw, text, font, max_w):
    while text and _tw(draw, text, font) > max_w:
        text = text[:-1]
    return text

def _lerp_color(c1, c2, t):
    return (int(c1[0]+(c2[0]-c1[0])*t),
            int(c1[1]+(c2[1]-c1[1])*t),
            int(c1[2]+(c2[2]-c1[2])*t))


# ─────────────────────────────────────────────────────────────────────────────
#  VIDEO RECORDER
#  540x960, 15fps, smooth EQ interpolation, pixel-perfect terminal layout
# ─────────────────────────────────────────────────────────────────────────────
class VideoRecorder:
    # ── Canvas ──────────────────────────────────────────────────────────────
    W, H = 540, 960
    FPS  = 15       # 15fps: smooth enough, ~66ms/frame budget on ARM

    # ── Palette ─────────────────────────────────────────────────────────────
    BG       = (0,   0,   0)
    C_BCYAN  = (50,  245, 245)
    C_MAG    = (200, 70,  255)
    C_YELLOW = (255, 228, 30)
    C_GREEN  = (45,  215, 65)
    C_WHITE  = (220, 220, 225)
    C_GRAY   = (90,  90,  105)
    C_DGRAY  = (35,  35,  48)
    C_ORANGE = (255, 155, 15)
    C_BLUE   = (50,  70,  235)
    C_RED    = (210, 40,  40)
    C_TEAL   = (0,   185, 165)
    SEL_BG   = (0,   165, 185)
    SEL_FG   = (0,   0,   0)
    LYR_A_BG = (185, 165, 0)
    LYR_A_FG = (0,   0,   0)

    # EQ gradient stops (bottom→top): teal, cyan, magenta, red/fire
    EQ_GRAD = [
        (0.00, (0,   190, 190)),
        (0.40, (0,   230, 255)),
        (0.70, (180, 60,  255)),
        (1.00, (255, 50,  0  )),
    ]

    def __init__(self):
        self._active      = False
        self._thread      = None
        self._ffmpeg      = None
        self.out_path     = ""
        self._start_pos   = 0.0
        self._song_path   = ""
        self._start_time  = 0.0
        self._fonts       = {}
        # Smooth EQ state for interpolation between frames
        self._eq_disp     = None   # displayed (interpolated) values
        self._eq_peak_disp= None
        # Fixed layout (computed in start())
        self._CH = 20   # char cell height
        self._CW = 12   # char cell width
        self._PAD = 8   # inner padding

    def _font(self, sz):
        if sz not in self._fonts:
            self._fonts[sz] = _find_font(sz)
        return self._fonts[sz]

    def _eq_color(self, ratio):
        """Per-pixel gradient color for EQ bar (ratio = 0 bottom, 1 top)."""
        g = self.EQ_GRAD
        for i in range(len(g)-1):
            r0, c0 = g[i]
            r1, c1 = g[i+1]
            if ratio <= r1:
                t = (ratio - r0) / max(0.001, r1 - r0)
                return _lerp_color(c0, c1, t)
        return g[-1][1]

    def _box(self, draw, x0, y0, x1, y1, col, title="", tf=None, title_h=0):
        """Box with title centered on top border, safely inside canvas."""
        lw = 2
        # Borders
        draw.rectangle([x0,    y0,    x1,    y0+lw], fill=col)
        draw.rectangle([x0,    y1-lw, x1,    y1   ], fill=col)
        draw.rectangle([x0,    y0,    x0+lw, y1   ], fill=col)
        draw.rectangle([x1-lw, y0,    x1,    y1   ], fill=col)
        # Title — punched into top border
        if title and tf and title_h > 0:
            t   = "[ " + title + " ]"
            tw2 = _tw(draw, t, tf)
            tx  = x0 + max(4, (x1-x0-tw2)//2)
            # Clear a slot in the top border for the text
            draw.rectangle([tx-3, y0-1, tx+tw2+3, y0+title_h+2], fill=self.BG)
            _t(draw, (tx, y0), t, tf, self.C_ORANGE)

    def _render(self, state, pos, dur, eq_s, eq_p):
        W, H   = self.W, self.H
        img    = Image.new("RGB", (W, H), self.BG)
        draw   = ImageDraw.Draw(img)

        CH     = self._CH
        PAD    = self._PAD
        MF_SZ  = CH - 2          # main font size
        SF_SZ  = max(11, CH - 7) # small font size
        mf     = self._font(MF_SZ)
        sf     = self._font(SF_SZ)

        # ── Fixed section heights (must sum to H exactly) ─────────────────
        # Title row height for box headers
        TH    = SF_SZ + 4   # title text height
        INNER = lambda rows: rows * CH + PAD * 2  # inner content height

        EQ_ROWS   = 5
        INFO_ROWS = 4
        LIST_ROWS = 7
        # Lyrics gets whatever remains
        EQ_H   = TH + INNER(EQ_ROWS)
        INFO_H = TH + INNER(INFO_ROWS)
        LIST_H = TH + INNER(LIST_ROWS)
        LYR_H  = H - EQ_H - INFO_H - LIST_H
        # Safety clamp
        LYR_H  = max(TH + INNER(3), LYR_H)

        # ══ 1. EQ ════════════════════════════════════════════════════════
        y0, y1 = 0, EQ_H
        self._box(draw, 0, y0, W-1, y1, self.C_BLUE,
                  "SPECTRUM ANALYZER", sf, TH)

        bands  = len(eq_s)
        eb_top = y0 + TH + PAD
        eb_bot = y1 - PAD
        eb_h   = max(1, eb_bot - eb_top)
        slot   = (W - PAD*2) / max(1, bands)
        bw     = max(3, int(slot * 0.74))

        for i in range(bands):
            v   = max(0.0, min(1.0, eq_s[i]))
            pk  = max(0.0, min(1.0, eq_p[i]))
            bx  = int(PAD + i * slot + (slot - bw) / 2)
            bh  = int(v * eb_h)
            if bh < 1:
                continue
            bt  = eb_bot - bh
            # Per-row gradient (every 2px for speed)
            step = 2
            for sy in range(bt, eb_bot, step):
                ratio = (eb_bot - sy) / eb_h   # 0=bottom,1=top
                c = self._eq_color(ratio)
                draw.rectangle([bx, sy, bx+bw, min(sy+step, eb_bot)], fill=c)
            # Peak dot
            if pk > 0.02:
                pky = max(eb_top, eb_bot - int(pk*eb_h) - 2)
                draw.rectangle([bx-1, pky, bx+bw+1, pky+3], fill=self.C_YELLOW)

        # ══ 2. NOW PLAYING ════════════════════════════════════════════════
        y0 = EQ_H
        y1 = y0 + INFO_H
        self._box(draw, 0, y0, W-1, y1, self.C_BLUE, "NOW PLAYING", sf, TH)

        iy = y0 + TH + PAD

        title  = (state.meta.get("title")  or "No track").strip()
        artist = (state.meta.get("artist") or "").strip()
        BAD    = {"unknown artist", "unknown", ""}

        td  = _fit(draw, title, mf, W - PAD*4)
        _t(draw, ((W - _tw(draw,td,mf))//2, iy), td, mf, self.C_BCYAN)
        iy += CH

        if artist.lower() not in BAD:
            ad = _fit(draw, artist, sf, W - PAD*4)
            _t(draw, ((W - _tw(draw,ad,sf))//2, iy), ad, sf, self.C_MAG)
        iy += CH

        # Progress bar
        px0, px1 = PAD*3, W-PAD*3
        pw  = px1 - px0
        pby = iy + CH//2 - 3
        draw.rectangle([px0, pby,   px1,       pby+6], fill=self.C_DGRAY)
        if dur > 0:
            filled = max(0, min(pw, int((pos/dur)*pw)))
            if filled > 2:
                draw.rectangle([px0, pby, px0+filled, pby+6], fill=self.C_GREEN)
                hx = px0 + filled
                draw.ellipse([hx-6, pby-3, hx+6, pby+9], fill=self.C_GREEN)
        _t(draw, (PAD*2, iy), fmt_time(pos), sf, self.C_GRAY)
        ds = fmt_time(dur)
        _t(draw, (W-PAD*2-_tw(draw,ds,sf), iy), ds, sf, self.C_GRAY)
        iy += CH

        # Controls + REC
        ctrl = "> PLAY  << PREV  >> NEXT  VOL:" + "|"*(state.volume//13)
        _t(draw, (PAD*2, iy), _fit(draw, ctrl, sf, W//2), sf, self.C_WHITE)
        badge = " REC "
        bw3 = _tw(draw, badge, sf)
        bx3 = W - PAD*2 - bw3
        draw.rectangle([bx3-2, iy-1, bx3+bw3+2, iy+SF_SZ+2], fill=self.C_RED)
        _t(draw, (bx3, iy), badge, sf, (255,255,255))

        # ══ 3. LIBRARY ════════════════════════════════════════════════════
        y0 = EQ_H + INFO_H
        y1 = y0 + LIST_H
        lbl = f"LIBRARY  [{len(state.songs)} tracks]"
        self._box(draw, 0, y0, W-1, y1, self.C_BLUE, lbl, sf, TH)

        vis = (LIST_H - TH - PAD*2) // CH
        off = max(0, min(state.current_idx - vis//2,
                         max(0, len(state.songs)-vis)))
        for ri in range(vis):
            si   = off + ri
            if si >= len(state.songs):
                break
            is_cur = si == state.current_idx
            pfx    = "> " if is_cur else "  "
            label  = _fit(draw, pfx + state.songs[si].stem, mf, W - PAD*4)
            lx2    = PAD*2
            ly2    = y0 + TH + PAD + ri*CH
            if is_cur:
                draw.rectangle([lx2-2, ly2, W-PAD*2, ly2+CH-1], fill=self.SEL_BG)
                _t(draw, (lx2, ly2), label, mf, self.SEL_FG)
            else:
                _t(draw, (lx2, ly2), label, mf, self.C_WHITE)

        # ══ 4. LYRICS ════════════════════════════════════════════════════
        y0 = EQ_H + INFO_H + LIST_H
        y1 = y0 + LYR_H
        rtag = " [ROM]" if (state.lyrics_romanized and state.lyrics_show_roman) else ""
        stag = f" {state.lyrics_sync_offset:+.1f}s" if state.lyrics_sync_offset else ""
        self._box(draw, 0, y0, W-1, y1, self.C_BLUE,
                  f"LYRICS{rtag}{stag}", sf, TH)

        _dl = (state.lyrics_romanized
               if state.lyrics_show_roman and state.lyrics_romanized
               else state.lyrics)

        lyr_vis = max(1, (LYR_H - TH - PAD*2) // CH)

        if _dl:
            adj = pos - state.lyrics_sync_offset
            cur = -1
            if state.lyrics_sync:
                for li, (ts, _) in enumerate(_dl):
                    if ts <= adj:
                        cur = li
            sl = max(0, cur - lyr_vis//2) if cur >= 0 else 0

            for ri in range(lyr_vis):
                li = sl + ri
                if li >= len(_dl):
                    break
                _, lt = _dl[li]
                if not lt.strip():
                    orn = "· · ·"
                    _t(draw, ((W-_tw(draw,orn,sf))//2,
                               y0+TH+PAD+ri*CH), orn, sf, self.C_DGRAY)
                    continue
                act  = (li == cur)
                dist = abs(li-cur) if cur >= 0 else 99
                ltd  = _fit(draw, lt.strip(), mf, W-PAD*4)
                lx4  = (W - _tw(draw,ltd,mf))//2
                ly4  = y0 + TH + PAD + ri*CH
                if act:
                    draw.rectangle([PAD, ly4, W-PAD, ly4+CH-1], fill=self.LYR_A_BG)
                    _t(draw, (lx4, ly4), ltd, mf, self.LYR_A_FG)
                elif dist == 1:
                    _t(draw, (lx4, ly4), ltd, mf, self.C_YELLOW)
                elif dist <= 3:
                    _t(draw, (lx4, ly4), ltd, mf, self.C_WHITE)
                else:
                    _t(draw, (lx4, ly4), ltd, mf, self.C_GRAY)
        else:
            msg = state.lyrics_msg or "Press L to fetch lyrics"
            _t(draw, (PAD*2, y0+TH+PAD), _fit(draw,msg,sf,W-PAD*4), sf, self.C_GRAY)

        return img

    def start(self, state, mpv):
        if not HAS_PIL:
            return False, "pip install Pillow first"
        try:
            subprocess.run(["ffmpeg","-version"], capture_output=True, check=True)
        except Exception:
            return False, "pkg install ffmpeg first"

        try: open(REC_LOG,"w").close()
        except: pass

        rec_dir = _find_rec_dir()
        ts      = time.strftime("%Y%m%d_%H%M%S")
        self.out_path    = str(rec_dir / f"nova_{ts}.mp4")
        self._start_pos  = mpv.position() if state.mpv_started else 0.0
        self._song_path  = str(state.songs[state.current_idx]) if state.songs else ""
        self._start_time = time.time()
        self._eq_disp    = list(state.eq.smooth)
        self._eq_peak_disp = list(state.eq.peaks)

        _rec_log(f"Start pos={round(self._start_pos,2)}s")
        _rec_log(f"Song: {self._song_path}")
        _rec_log(f"Out:  {self.out_path}")

        # Warm fonts
        mf_sz = self._CH - 2
        sf_sz = max(11, self._CH - 7)
        for sz in (sf_sz, mf_sz):
            self._font(sz)
        _rec_log("Fonts warmed")

        # Test render
        try:
            tf = self._render(state, self._start_pos,
                              mpv.duration() if state.mpv_started else 180.0,
                              [0.5]*len(state.eq.smooth),
                              [0.7]*len(state.eq.peaks))
            _rec_log(f"Test render OK {tf.size}")
        except Exception as ex:
            import traceback
            _rec_log("TEST RENDER FAILED: "+str(ex))
            _rec_log(traceback.format_exc())
            return False, "Render failed: "+str(ex)

        fflog = REC_LOG.replace(".log","_ff.log")
        cmd = [
            "ffmpeg", "-y",
            "-f","rawvideo", "-vcodec","rawvideo",
            "-s",f"{self.W}x{self.H}",
            "-pix_fmt","rgb24",
            "-r",str(self.FPS),
            "-i","pipe:0",
            "-ss",str(round(self._start_pos,3)),
            "-i",self._song_path,
            "-map","0:v:0", "-map","1:a:0",
            "-c:v","libx264", "-preset","ultrafast", "-crf","22",
            "-pix_fmt","yuv420p",
            "-c:a","aac", "-b:a","192k",
            "-shortest", "-movflags","+faststart",
            self.out_path,
        ]
        _rec_log("ffmpeg: "+" ".join(cmd))
        try:
            self._ffmpeg = subprocess.Popen(
                cmd, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=open(fflog,"w"),
            )
        except Exception as ex:
            _rec_log("Popen: "+str(ex))
            return False, str(ex)

        self._active = True
        self._thread = threading.Thread(
            target=self._loop, args=(state, mpv), daemon=True)
        self._thread.start()
        _rec_log("Thread started")
        return True, self.out_path

    def stop(self, state, mpv):
        _rec_log("Stop called")
        self._active = False
        if self._thread:
            self._thread.join(timeout=10)
        if self._ffmpeg:
            try:
                self._ffmpeg.stdin.flush()
                self._ffmpeg.stdin.close()
            except: pass
            try:    self._ffmpeg.wait(timeout=30)
            except: self._ffmpeg.kill()
            _rec_log("ffmpeg exit="+str(getattr(self._ffmpeg,"returncode","?")))
            self._ffmpeg = None
        if os.path.exists(self.out_path):
            sz = os.path.getsize(self.out_path)
            _rec_log(f"Done {self.out_path} ({sz//1024}KB)")
            return True, self.out_path
        return False, "Output file not found"

    def _loop(self, state, mpv):
        interval = 1.0 / self.FPS
        n = 0
        _rec_log("Loop start")

        while self._active:
            t0 = time.time()
            try:
                pos  = mpv.position() if state.mpv_started else 0.0
                dur  = mpv.duration() if state.mpv_started else 0.0

                # ── Smooth EQ interpolation ─────────────────────────────
                # Blend displayed values toward live values each frame
                # Fast attack (0.55), slow release (0.35) → fluid motion
                live_s = list(state.eq.smooth)
                live_p = list(state.eq.peaks)
                if self._eq_disp is None:
                    self._eq_disp      = live_s[:]
                    self._eq_peak_disp = live_p[:]
                else:
                    for i in range(len(live_s)):
                        cur_v  = self._eq_disp[i]
                        tgt_v  = live_s[i]
                        # Attack faster than decay for snappy feel
                        alpha  = 0.60 if tgt_v > cur_v else 0.35
                        self._eq_disp[i] = cur_v + (tgt_v - cur_v) * alpha
                        # Peaks: fast rise, slow fall
                        cur_p  = self._eq_peak_disp[i]
                        tgt_p  = live_p[i]
                        palpha = 0.80 if tgt_p > cur_p else 0.20
                        self._eq_peak_disp[i] = cur_p + (tgt_p - cur_p) * palpha

                fr  = self._render(state, pos, dur,
                                   self._eq_disp, self._eq_peak_disp)
                self._ffmpeg.stdin.write(fr.tobytes())
                self._ffmpeg.stdin.flush()
                n += 1
                if n % 30 == 0:
                    elapsed = time.time() - self._start_time
                    _rec_log(f"frame={n} pos={round(pos,1)}s elapsed={round(elapsed,1)}s")
            except BrokenPipeError:
                _rec_log("pipe broken at frame "+str(n)); break
            except Exception as ex:
                import traceback
                _rec_log(f"frame {n} err: {ex}")
                _rec_log(traceback.format_exc()); break

            time.sleep(max(0, interval-(time.time()-t0)))

        self._active = False
        _rec_log(f"Loop done frames={n}")

    @property
    def is_recording(self):
        return self._active

ScreenRecorder = VideoRecorder


# ─────────────────────────────────────────────────────────────────────────────
#  DOWNLOADER — YouTube Music, best-quality audio, yt-dlp
# ─────────────────────────────────────────────────────────────────────────────

def _auto_update_ytdlp():
    """Silently update yt-dlp in the background on every launch."""
    try:
        result = subprocess.run(
            ["pip", "install", "-U", "yt-dlp",
             "--quiet", "--break-system-packages"],
            capture_output=True, timeout=60
        )
        if result.returncode == 0:
            import importlib
            import yt_dlp as _ytdlp_mod
            importlib.reload(_ytdlp_mod)
    except Exception:
        pass  # never crash the player over an update


# Piped API instances — used as fallback when yt-dlp search is blocked
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://piped-api.garudalinux.org",
    "https://api.piped.projectsegfau.lt",
]

def piped_search(query, max_results=8):
    """Search via Piped API — no auth needed, works when yt-dlp is blocked."""
    for instance in PIPED_INSTANCES:
        try:
            url = f"{instance}/search?q={urllib.parse.quote(query)}&filter=all"
            raw = _http_get(url, timeout=6)
            if not raw:
                continue
            data = json.loads(raw)
            results = []
            for item in (data.get("items") or [])[:max_results]:
                vid_id = item.get("url", "").replace("/watch?v=", "")
                results.append({
                    "title":  item.get("title", "Unknown").strip(),
                    "artist": item.get("uploaderName", "").strip(),
                    "url":    f"https://youtube.com/watch?v={vid_id}",
                    "id":     vid_id,
                    "dur":    int(item.get("duration") or 0),
                    "source": "youtube",
                })
            if results:
                return results
        except Exception:
            continue
    return []

def ytm_search(query, max_results=8):
    if not HAS_YTDLP:
        return []
    opts = {
        "quiet": True, "no_warnings": True,
        "extract_flat": True,
        "ignoreerrors": True,
    }
    try:
        with _ytdlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        results = []
        for e in (info.get("entries") or []):
            if not e: continue
            results.append({
                "title":  (e.get("title")    or "Unknown").strip(),
                "artist": (e.get("uploader") or e.get("channel") or "").strip(),
                "url":    e.get("url") or e.get("webpage_url") or "",
                "id":     e.get("id") or "",
                "dur":    int(e.get("duration") or 0),
                "source": "youtube",
            })
        return results
    except Exception:
        return []

def ytm_search_with_fallback(query, max_results=8):
    """Try yt-dlp first, fall back to Piped API if blocked or empty."""
    results = ytm_search(query, max_results)
    if not results:
        results = piped_search(query, max_results)
    return results

def ytm_download(url, out_dir, progress_cb=None):
    if not HAS_YTDLP:
        return False, "pip install yt-dlp"
    tmpl = str(out_dir / "%(title)s.%(ext)s")
    def _hook(d):
        if not progress_cb: return
        if d.get("status") == "downloading":
            progress_cb("  ⬇  " + d.get("_percent_str","").strip()
                        + "  " + d.get("_speed_str","").strip()
                        + "  ETA " + d.get("_eta_str","").strip())
        elif d.get("status") == "finished":
            progress_cb("  ✓  Converting…")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": tmpl,
        "quiet": True, "no_warnings": True,
        "ignoreerrors": True,
        "progress_hooks": [_hook],
        "postprocessors": [
            {"key": "FFmpegExtractAudio",
             "preferredcodec": "m4a", "preferredquality": "0"},
            {"key": "FFmpegMetadata", "add_metadata": True},
        ],
    }
    try:
        with _ytdlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
        candidates = sorted(out_dir.glob("*.m4a"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            return True, str(candidates[0])
        return True, "downloaded"
    except Exception as ex:
        err = str(ex).lower()
        if "sign in" in err or "bot" in err or "confirm" in err:
            return False, "YouTube blocked download. yt-dlp auto-updated — try again in a moment."
        elif "network" in err or "connection" in err:
            return False, "No internet connection."
        elif "unavailable" in err or "private" in err:
            return False, "This video is unavailable or private."
        else:
            return False, f"Download failed: {str(ex)[:60]}"


# ─────────────────────────────────────────────────────────────────────────────
#  SPOTIFY INTEGRATION  (optional — pip install spotipy)
#  Credentials stored in ~/.nova_spotify.json:
#    {"client_id": "...", "client_secret": "..."}
#  Get free credentials at: https://developer.spotify.com/dashboard
# ─────────────────────────────────────────────────────────────────────────────
def _get_spotify_client():
    if not HAS_SPOTIPY:
        return None
    try:
        if SPOTIFY_CREDS_FILE.exists():
            creds = json.loads(SPOTIFY_CREDS_FILE.read_text())
        else:
            return None
        cid = creds.get("client_id", "").strip()
        csec = creds.get("client_secret", "").strip()
        if not cid or not csec:
            return None
        auth = SpotifyClientCredentials(client_id=cid, client_secret=csec)
        return spotipy.Spotify(auth_manager=auth)
    except Exception:
        return None

def spotify_search(query, max_results=5):
    sp = _get_spotify_client()
    if not sp:
        return []
    try:
        res = sp.search(q=query, type="track", limit=max_results)
        results = []
        for item in (res.get("tracks", {}).get("items") or []):
            artist = item["artists"][0]["name"] if item.get("artists") else ""
            results.append({
                "title":  item.get("name", "Unknown").strip(),
                "artist": artist.strip(),
                "url":    item.get("external_urls", {}).get("spotify", ""),
                "id":     item.get("id", ""),
                "dur":    int(item.get("duration_ms", 0)) // 1000,
                "source": "spotify",
            })
        return results
    except Exception:
        return []

def spotify_download(title, artist, out_dir, progress_cb=None):
    """Find best YouTube match for a Spotify track and download it."""
    query = f"{artist} - {title}" if artist else title
    if progress_cb:
        progress_cb("  ⟳  Finding YouTube match…")
    yt_results = ytm_search_with_fallback(query, max_results=3)
    if not yt_results:
        return False, "No YouTube match found for this track"
    best = yt_results[0]
    vid_url = (f"https://www.youtube.com/watch?v={best['id']}"
               if best.get("id") else best["url"])
    # Download with the Spotify track name instead of YouTube title
    tmpl = str(out_dir / f"{title}.%(ext)s")
    def _hook(d):
        if not progress_cb: return
        if d.get("status") == "downloading":
            progress_cb("  ⬇  " + d.get("_percent_str", "").strip()
                        + "  " + d.get("_speed_str", "").strip()
                        + "  ETA " + d.get("_eta_str", "").strip())
        elif d.get("status") == "finished":
            progress_cb("  ✓  Converting…")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": tmpl,
        "quiet": True, "no_warnings": True,
        "ignoreerrors": True,
        "progress_hooks": [_hook],
        "postprocessors": [
            {"key": "FFmpegExtractAudio",
             "preferredcodec": "m4a", "preferredquality": "0"},
            {"key": "FFmpegMetadata", "add_metadata": True},
        ],
    }
    try:
        with _ytdlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(vid_url, download=True)
        candidates = sorted(out_dir.glob("*.m4a"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            return True, str(candidates[0])
        return True, "downloaded"
    except Exception as ex:
        return False, str(ex)


def run_ui(stdscr, state: PlayerState, mpv: MPVClient):
    curses.curs_set(0)
    stdscr.timeout(33)       # 33 ms → ~30 fps
    init_colors()

    recorder = VideoRecorder()
    lyric_fetch_thread = None

    # Auto-fetch lyrics for the first track (loaded before curses started)
    _first_fetch_done = [False]

    def start_lyrics_fetch():
        if state.lyrics_fetching:
            return
        state.lyrics_fetching = True
        state.lyrics = []
        state.lyrics_msg = "  ⟳  Fetching lyrics…"
        def worker():
            try:
                a = state.meta.get("artist","")
                t = state.meta.get("title","")
                dur = mpv.duration()
                lines, synced = fetch_lyrics(a, t, dur, filename=state.songs[state.current_idx].name if state.songs else "")
                state.lyrics      = lines
                state.lyrics_sync = synced
                state.lyrics_off  = 0
                if lines:
                    state.lyrics_msg = f"  ✓  {'Synced' if synced else 'Plain'} lyrics loaded  ({len(lines)} lines)"
                    def _romanize(cl=lines):
                        try:
                            state.lyrics_romanizing = True
                            state.lyrics_msg += "  ⟳ romanizing…"
                            roman = romanize_lyrics(cl)
                            state.lyrics_romanized = roman
                            state.lyrics_msg = state.lyrics_msg.replace("  ⟳ romanizing…",
                                "  ✓ romanized" if roman is not cl else "")
                        except Exception:
                            pass
                        finally:
                            state.lyrics_romanizing = False
                    threading.Thread(target=_romanize, daemon=True).start()
                else:
                    state.lyrics_msg = "  ✗  No lyrics found"
            except Exception as e:
                state.lyrics_msg = f"  ✗  Error: {e}"
            finally:
                state.lyrics_fetching = False
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return t

    def load_and_play(idx: int):
        if not state.songs:
            return
        state.current_idx = idx
        song = state.songs[idx]
        state.meta = read_meta(song)
        state.lyrics           = []
        state.lyrics_romanized  = []
        state.lyrics_off        = 0
        # Restore per-song sync offset
        song_key = state.songs[idx].name if state.songs else ''
        state.lyrics_sync_offset = state.sync_offsets.get(song_key, 0.0)
        if not mpv.is_alive():
            mpv.launch(song)
            mpv.volume(state.volume)
            mpv.play()
        else:
            mpv.load(song)
            time.sleep(0.15)
            mpv.play()
        state.eq.active = True
        state.mpv_started = True
        state.status(f"♫  {state.meta['title']}", 3)
        start_lyrics_fetch()

    last_tick = time.time()
    frame     = 0

    # Kick off lyrics fetch for whatever is already playing at startup
    if state.mpv_started and state.meta and not _first_fetch_done[0]:
        _first_fetch_done[0] = True
        start_lyrics_fetch()

    while True:
        now = time.time()
        dt  = now - last_tick
        last_tick = now
        frame += 1

        # ── EQ tick ──────────────────────────────────────────────────────────
        state.eq.active = state.mpv_started and not mpv.is_paused()
        state.eq.tick(dt)

        # ── auto-advance ─────────────────────────────────────────────────────
        if state.mpv_started and mpv.is_alive() and mpv.eof():
            if state.repeat:
                mpv.seek_abs(0)
                mpv.play()
            else:
                nxt = state.next_track()
                if nxt is not None:
                    load_and_play(nxt)

        # ── layout ───────────────────────────────────────────────────────────
        H, W = stdscr.getmaxyx()
        stdscr.erase()

        # ─ Header band ───────────────────────────────────────────────────────
        HEADER_H  = 3
        EQ_H      = 8
        INFO_H    = 6
        CTRL_H    = 2
        FOOTER_H  = 1
        TOP_AREA  = HEADER_H + EQ_H + INFO_H + CTRL_H + FOOTER_H
        use_split = W >= 88        # wide: list + lyrics side by side
        if use_split:
            LIST_W  = W // 2 - 1
            LYRIC_W = W - LIST_W - 3
        else:
            LIST_W  = W - 2
            LYRIC_W = W - 2
        remaining = max(10, H - TOP_AREA - 2)
        if use_split:
            LIST_H  = remaining
            LYRIC_H = remaining
        else:
            LIST_H  = max(4, remaining // 2)
            LYRIC_H = max(4, remaining - LIST_H - 2)

        # ── Draw header ───────────────────────────────────────────────────────
        logo_y = 0
        logo_colors = [P_TEAL, P_CYAN, P_TITLE, P_ARTIST, P_EQ2]
        for li, line in enumerate(LOGO_LINES):
            lx = max(0, (W - len(line)) // 2)
            try:
                stdscr.addstr(logo_y + li, lx, trunc(line, W-1),
                              curses.color_pair(logo_colors[li % len(logo_colors)]) | curses.A_BOLD)
            except curses.error:
                pass
        # Version tag
        vtag = f"v{VERSION}  ♪"
        try:
            stdscr.addstr(0, W - len(vtag) - 1, vtag, curses.color_pair(P_GRAY))
        except curses.error:
            pass

        # ── EQ visualizer ─────────────────────────────────────────────────────
        eq_y = HEADER_H
        eq_bx = 1
        eq_bw = W - 2
        draw_box(stdscr, eq_y, 0, EQ_H + 2, W, P_BORDER,
                 "SPECTRUM ANALYZER")
        draw_eq(stdscr, eq_y + 1, eq_bx, eq_bw, EQ_H, state.eq)

        # ── Now-playing info ──────────────────────────────────────────────────
        info_y = eq_y + EQ_H + 2
        draw_box(stdscr, info_y, 0, INFO_H, W, P_BORDER, "NOW PLAYING")

        pos = mpv.position() if state.mpv_started else 0.0
        dur = mpv.duration() if state.mpv_started else 0.0
        paused = mpv.is_paused() if state.mpv_started else True

        title  = state.meta.get("title",  "─  No track loaded  ─")
        artist = state.meta.get("artist", "")
        album  = state.meta.get("album",  "")

        play_icon  = "⏸" if paused else "▶"
        rec_icon   = "  ⏺ REC" if state.recording else ""
        shuf_icon  = "🔀" if state.shuffle else " ─ "
        rep_icon   = "🔁" if state.repeat  else " ─ "
        vol_bar    = "▮" * (state.volume // 10) + "▯" * (10 - state.volume // 10)

        try:
            # Title
            tx = max(1, (W - len(title)) // 2)
            attr = curses.color_pair(P_PAUSED if paused else P_TITLE) | curses.A_BOLD
            stdscr.addstr(info_y + 1, tx, trunc(title, W - 2), attr)
            # Artist / Album
            sub = f"{artist}  {'·  ' + album if album else ''}"
            sx = max(1, (W - len(sub)) // 2)
            stdscr.addstr(info_y + 2, sx, trunc(sub, W - 2),
                          curses.color_pair(P_ARTIST))
            # Progress bar
            pb_w = W - 20
            pb_x = 10
            stdscr.addstr(info_y + 3, 2, fmt_time(pos), curses.color_pair(P_GRAY))
            draw_progress(stdscr, info_y + 3, pb_x, pb_w, pos, dur,
                          P_PROGRESS, P_GRAY)
            stdscr.addstr(info_y + 3, pb_x + pb_w + 1, fmt_time(dur),
                          curses.color_pair(P_GRAY))
            # Controls row
            ctrl = (f"  {play_icon}  "
                    f"[◀◀ PREV]  [▶▶ NEXT]  "
                    f"SHF:{shuf_icon}  REP:{rep_icon}  "
                    f"VOL: {vol_bar}  {state.volume:3d}%{rec_icon}")
            stdscr.addstr(info_y + 4, 2, trunc(ctrl, W - 3),
                          curses.color_pair(P_PAUSED if state.recording else P_NORMAL))
        except curses.error:
            pass

        # ── Song List ─────────────────────────────────────────────────────────
        list_y = info_y + INFO_H
        if state.search_mode:
            list_border_title = f"SEARCH: {state.search_query}█  [{len(state.search_results)} found]"
        else:
            list_border_title = f"LIBRARY  [{len(state.songs)} tracks]  [ / ] to search"
        draw_box(stdscr, list_y, 0, LIST_H + 2, LIST_W + 2, P_BORDER,
                 list_border_title)

        # Which song list to display
        if state.search_mode and state.search_results is not None:
            _vis_list  = state.search_results   # list of indices
            _sel_pos   = state.search_cursor
        else:
            _vis_list  = list(range(len(state.songs)))
            _sel_pos   = state.current_idx

        vis_songs = LIST_H
        # Scroll offset
        if _sel_pos < state.list_offset:
            state.list_offset = _sel_pos
        if _sel_pos >= state.list_offset + vis_songs:
            state.list_offset = _sel_pos - vis_songs + 1
        state.list_offset = clamp(state.list_offset, 0, max(0, len(_vis_list) - vis_songs))

        for ri in range(vis_songs):
            vi = state.list_offset + ri
            if vi >= len(_vis_list):
                break
            si   = _vis_list[vi]
            song = state.songs[si]
            is_current  = si == state.current_idx
            is_selected = vi == _sel_pos and state.search_mode
            label = f"  {chr(9654)+chr(32) if is_current else '  '}{song.stem}"
            label = trunc(label, LIST_W - 2).ljust(LIST_W)
            # Highlight matched query chars
            try:
                if is_current and is_selected:
                    attr = curses.color_pair(P_LYRHI) | curses.A_BOLD
                elif is_current:
                    attr = curses.color_pair(P_SELECTED) | curses.A_BOLD
                elif is_selected:
                    attr = curses.color_pair(P_SELECTED)
                else:
                    attr = curses.color_pair(P_NORMAL)
                stdscr.addstr(list_y + 1 + ri, 1, label[:LIST_W], attr)
            except curses.error:
                pass

        # ── Lyrics Panel ─────────────────────────────────────────────────────
        # Always shown: side-by-side on wide, stacked below list on narrow
        if use_split:
            lyr_y  = list_y
            lyr_bx = LIST_W + 2
            lyr_bw = LYRIC_W + 1
        else:
            lyr_y  = list_y + LIST_H + 2
            lyr_bx = 0
            lyr_bw = W

        _rtag = (" ⟳ROM" if state.lyrics_romanizing
                 else " [ROM]" if (state.lyrics_romanized and state.lyrics_show_roman)
                 else " [ORI]" if state.lyrics_romanized
                 else "")
        _stag = (f" {state.lyrics_sync_offset:+.1f}s"
                 if state.lyrics_sync_offset != 0.0 else "")
        draw_box(stdscr, lyr_y, lyr_bx, LYRIC_H + 2, lyr_bw, P_BORDER,
                 f"♪  LYRICS{_rtag}{_stag}  ♪")
        inner_w = lyr_bw - 2

        # Find current lyric line (apply sync offset)
        cur_lyr = -1
        adj_pos = pos - state.lyrics_sync_offset   # offset-corrected position
        if state.lyrics and state.lyrics_sync:
            for li2, (ts2, _) in enumerate(state.lyrics):
                if ts2 <= adj_pos:
                    cur_lyr = li2
            if state.lyrics_auto and cur_lyr >= 0:
                mid = LYRIC_H // 2
                state.lyrics_off = max(0, cur_lyr - mid)

        if state.lyrics:
            _dlyr = (state.lyrics_romanized
                     if state.lyrics_show_roman and state.lyrics_romanized
                     else state.lyrics)
            lyr_vis = LYRIC_H
            state.lyrics_off = clamp(state.lyrics_off, 0,
                                     max(0, len(_dlyr) - lyr_vis))
            for ri in range(lyr_vis):
                li2 = state.lyrics_off + ri
                if li2 >= len(_dlyr):
                    break
                _, ltxt = _dlyr[li2]
                if not ltxt.strip():
                    # Empty lyric line — draw a small ornament
                    try:
                        ornament = "· · ·"
                        ox = lyr_bx + 1 + max(0, (inner_w - len(ornament)) // 2)
                        stdscr.addstr(lyr_y + 1 + ri, ox, ornament,
                                      curses.color_pair(P_GRAY) | curses.A_DIM)
                    except curses.error:
                        pass
                    continue
                is_active = li2 == cur_lyr
                dist = abs(li2 - cur_lyr) if cur_lyr >= 0 else 99
                # Center the lyric text
                raw = ltxt.strip()
                if is_active:
                    raw = f"♪  {raw}  ♪"
                raw = trunc(raw, inner_w - 2)
                cx  = lyr_bx + 1 + max(0, (inner_w - len(raw)) // 2)
                try:
                    if is_active:
                        stdscr.addstr(lyr_y + 1 + ri, cx, raw,
                                      curses.color_pair(P_LYRHI) | curses.A_BOLD)
                    elif dist == 1:
                        stdscr.addstr(lyr_y + 1 + ri, cx, raw,
                                      curses.color_pair(P_LYRICS) | curses.A_BOLD)
                    elif dist == 2:
                        stdscr.addstr(lyr_y + 1 + ri, cx, raw,
                                      curses.color_pair(P_LYRICS))
                    elif dist <= 4:
                        stdscr.addstr(lyr_y + 1 + ri, cx, raw,
                                      curses.color_pair(P_NORMAL))
                    else:
                        stdscr.addstr(lyr_y + 1 + ri, cx, raw,
                                      curses.color_pair(P_GRAY) | curses.A_DIM)
                except curses.error:
                    pass
        else:
            # No lyrics yet — show status / hint
            msg  = state.lyrics_msg if state.lyrics_msg else "  ♪  Press  L  to fetch lyrics"
            hint = "  Auto-fetches on each new track"
            try:
                my = lyr_y + LYRIC_H // 2 - 1
                mx = lyr_bx + 1 + max(0, (inner_w - len(msg)) // 2)
                stdscr.addstr(my,     mx, trunc(msg,  inner_w), curses.color_pair(P_GRAY))
                hx = lyr_bx + 1 + max(0, (inner_w - len(hint)) // 2)
                stdscr.addstr(my + 1, hx, trunc(hint, inner_w),
                              curses.color_pair(P_GRAY) | curses.A_DIM)
            except curses.error:
                pass

        # ── Download Panel overlay ────────────────────────────────────────────
        if state.dl_mode:
            DW = min(W - 2, 72)
            DH = min(H - 4, 22)
            DX = max(0, (W - DW) // 2)
            DY = 3
            for dy2 in range(DH):
                try:
                    stdscr.addstr(DY+dy2, DX, ' '*DW, curses.color_pair(P_NORMAL))
                except curses.error:
                    pass
            draw_box(stdscr, DY, DX, DH, DW, P_HEADER, "DOWNLOAD  ♫  YouTube Music")
            qline = "  Search: " + state.dl_query + ("█" if not state.dl_searching and not state.dl_downloading else "")
            try:
                stdscr.addstr(DY+1, DX+1, trunc(qline, DW-2).ljust(DW-2),
                              curses.color_pair(P_TITLE) | curses.A_BOLD)
            except curses.error:
                pass
            try:
                stdscr.addstr(DY+2, DX+1, "─"*(DW-2), curses.color_pair(P_BORDER))
            except curses.error:
                pass
            if state.dl_status:
                try:
                    stdscr.addstr(DY+3, DX+1, trunc(state.dl_status, DW-2),
                                  curses.color_pair(P_STATUS))
                except curses.error:
                    pass
            if state.dl_progress:
                try:
                    stdscr.addstr(DY+4, DX+1, trunc(state.dl_progress, DW-2),
                                  curses.color_pair(P_TEAL) | curses.A_BOLD)
                except curses.error:
                    pass
            res_y0  = DY + 5
            res_vis = DH - 7
            if state.dl_results:
                dl_off = max(0, min(state.dl_cursor - res_vis//2,
                                    max(0, len(state.dl_results)-res_vis)))
                for ri in range(res_vis):
                    idx2 = dl_off + ri
                    if idx2 >= len(state.dl_results):
                        break
                    r2   = state.dl_results[idx2]
                    dm   = r2['dur'] // 60; ds2 = r2['dur'] % 60
                    dur2 = f"{dm}:{ds2:02d}" if r2['dur'] else ''
                    src_tag = " (Spotify)" if r2.get("source") == "spotify" else " (YouTube)"
                    pfx2 = "▶ " if idx2 == state.dl_cursor else "  "
                    line = pfx2 + trunc(r2['title'], DW-20) + src_tag + "  " + dur2
                    line = line.ljust(DW-2)
                    try:
                        attr2 = (curses.color_pair(P_SELECTED)|curses.A_BOLD
                                 if idx2 == state.dl_cursor
                                 else curses.color_pair(P_NORMAL))
                        stdscr.addstr(res_y0+ri, DX+1, line[:DW-2], attr2)
                    except curses.error:
                        pass
            elif not state.dl_searching:
                hint2 = "  Type a song name and press ENTER to search"
                try:
                    stdscr.addstr(res_y0+1, DX+1, trunc(hint2, DW-2),
                                  curses.color_pair(P_GRAY))
                except curses.error:
                    pass
            dl_foot = " [ENTER]Search/Download  [↑↓]Move  [ESC]Close "
            try:
                stdscr.addstr(DY+DH-1, DX+1, trunc(dl_foot, DW-2),
                              curses.color_pair(P_KEY))
            except curses.error:
                pass

        # ── Footer key hints ──────────────────────────────────────────────────
        footer_y = H - 1
        if state.search_mode:
            keys = [("Type", "Filter"), ("↑↓", "Move"), ("ENTER", "Play"), ("ESC", "Close")]
        elif state.dl_mode:
            keys = [("Type", "Query"), ("ENTER", "Search/DL"), ("↑↓", "Move"), ("ESC", "Close")]
        else:
            rec_hint = ("^R", "⏹ Stop REC") if state.recording else ("^R", "⏺ Record")
            keys = [
                ("↑↓", "Nav"), ("ENTER", "Play"), ("SPC", "Pause"),
                ("←→", "Seek"), ("-+", "Vol"), ("N/P", "Skip"),
                ("/", "Search"), ("D", "Download"), ("L", "Lyrics"),
                ("T", "Roman"), rec_hint, ("Q", "Quit"),
            ]
        kstr = ""
        for k, v in keys:
            kstr += f" [{k}]:{v} "
        try:
            stdscr.addstr(footer_y, 0,
                          trunc(kstr, W - 1).center(W - 1),
                          curses.color_pair(P_KEY))
        except curses.error:
            pass

        # ── Status message ────────────────────────────────────────────────────
        smsg = state.get_status()
        if smsg:
            sx = max(0, (W - len(smsg)) // 2)
            try:
                stdscr.addstr(footer_y - 1, sx, trunc(smsg, W - 1),
                              curses.color_pair(P_STATUS) | curses.A_BOLD)
            except curses.error:
                pass

        stdscr.refresh()

        # ── Input ─────────────────────────────────────────────────────────────
        key = stdscr.getch()
        if key == -1:
            continue

        # ── Download panel intercepts ALL keys while open ─────────────────────
        if state.dl_mode:
            if key == 27:   # ESC — close
                state.dl_mode = False
                curses.curs_set(0)
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                state.dl_query = state.dl_query[:-1]
                if not state.dl_query:
                    state.dl_results = []
                    state.dl_status  = "  ♫  Type a song name, press ENTER to search"
            elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                if not state.dl_results and state.dl_query.strip() and not state.dl_searching:
                    q3 = state.dl_query.strip()
                    state.dl_searching = True
                    state.dl_status    = "  ⟳  Searching \"" + q3 + "\"…"
                    state.dl_results   = []
                    def _do_search(query=q3):
                        yt_res, sp_res = [], []
                        t1 = threading.Thread(target=lambda: yt_res.extend(ytm_search_with_fallback(query)), daemon=True)
                        t2 = threading.Thread(target=lambda: sp_res.extend(spotify_search(query)), daemon=True)
                        t1.start(); t2.start()
                        t1.join(); t2.join()
                        # Interleave: YouTube first, then Spotify, paired by rank
                        merged = []
                        for i in range(max(len(yt_res), len(sp_res))):
                            if i < len(yt_res): merged.append(yt_res[i])
                            if i < len(sp_res): merged.append(sp_res[i])
                        state.dl_results, state.dl_cursor = merged, 0
                        state.dl_searching = False
                        sp_note = " + Spotify" if sp_res else (" (no Spotify — see ~/.nova_spotify.json)" if HAS_SPOTIPY else "")
                        state.dl_status = (
                            f"  ✓  {len(merged)} results{sp_note} — ↑↓ select, ENTER download"
                            if merged else
                            "  ✗  No results — try different search"
                        )
                    threading.Thread(target=_do_search, daemon=True).start()
                elif state.dl_results and not state.dl_downloading:
                    sel3 = state.dl_results[state.dl_cursor]
                    state.dl_downloading = True
                    state.dl_status   = "  ⬇  Downloading: " + trunc(sel3['title'], 40)
                    state.dl_progress = "  ⟳  Starting…"
                    def _do_dl(item=sel3):
                        def _prog(m): state.dl_progress = m
                        if item.get("source") == "spotify":
                            ok3, res3 = spotify_download(item['title'], item['artist'], state.songs_dir, _prog)
                        else:
                            vid_url = (f"https://www.youtube.com/watch?v={item['id']}"
                                       if item.get("id") else item["url"])
                            ok3, res3 = ytm_download(vid_url, state.songs_dir, _prog)
                        state.dl_downloading = False
                        if ok3:
                            state.refresh_songs()
                            fn3 = Path(res3).name if res3 != "downloaded" else "file"
                            state.dl_status   = "  ✓  Saved: " + fn3
                            state.dl_progress = "  Search another or ESC to close"
                            state.dl_results, state.dl_query = [], ''
                            state.status("✓  Downloaded: " + trunc(fn3, 35), 6)
                        else:
                            state.dl_status   = "  ✗  Failed: " + trunc(res3, 50)
                            state.dl_progress = ''
                    threading.Thread(target=_do_dl, daemon=True).start()
            elif key == curses.KEY_UP:
                state.dl_cursor = max(0, state.dl_cursor - 1)
            elif key == curses.KEY_DOWN:
                state.dl_cursor = min(max(0, len(state.dl_results)-1), state.dl_cursor+1)
            elif 32 <= key <= 126 and not state.dl_searching and not state.dl_downloading:
                state.dl_query  += chr(key)
                state.dl_results = []
                state.dl_status  = "  Press ENTER to search"
            continue   # ← swallow ALL keys, nothing reaches player handlers

        # ── Search mode intercepts ALL keys while active ──────────────────────
        if state.search_mode:
            if key == 27:   # ESC — close search
                state.search_mode  = False
                state.search_query = ''
                curses.curs_set(0)
            elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                if state.search_results:
                    real_idx = state.search_results[state.search_cursor]
                    state.search_mode  = False
                    state.search_query = ''
                    curses.curs_set(0)
                    load_and_play(real_idx)
            elif key == curses.KEY_UP:
                state.search_cursor = max(0, state.search_cursor - 1)
            elif key == curses.KEY_DOWN:
                state.search_cursor = min(len(state.search_results) - 1,
                                          state.search_cursor + 1)
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                state.search_query = state.search_query[:-1]
                state.run_search()
            elif 32 <= key <= 126:
                state.search_query += chr(key)
                state.run_search()
            continue   # ← swallow ALL keys, nothing reaches player handlers

        # ── Player keys (only when search panel is closed) ────────────────────
        if key in (ord('q'), ord('Q')):
            if state.recording:
                recorder.stop()
                state.recording = False
            break

        # Navigation
        elif key == curses.KEY_UP:
            if state.songs:
                state.current_idx = max(0, state.current_idx - 1)
        elif key == curses.KEY_DOWN:
            if state.songs:
                state.current_idx = min(len(state.songs) - 1, state.current_idx + 1)
        elif key == curses.KEY_PPAGE:
            state.current_idx = max(0, state.current_idx - 10)
        elif key == curses.KEY_NPAGE:
            state.current_idx = min(len(state.songs) - 1, state.current_idx + 10)

        # Play selected
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r'), ord(' ') if not state.mpv_started else -99):
            if key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                load_and_play(state.current_idx)

        # Pause / Play
        elif key == ord(' '):
            if state.mpv_started:
                if mpv.is_paused():
                    mpv.play()
                    state.status("▶  Playing")
                else:
                    mpv.pause()
                    state.status("⏸  Paused")

        # Seek
        elif key == curses.KEY_LEFT:
            mpv.seek(-5); state.status("◀◀  -5s")
        elif key == curses.KEY_RIGHT:
            mpv.seek(5);  state.status("▶▶  +5s")

        # Volume
        elif key in (ord('-'), ord('_')):
            state.volume = max(0, state.volume - 5)
            mpv.volume(state.volume)
            state.status(f"🔉  Volume: {state.volume}%")
        elif key in (ord('+'), ord('=')):
            state.volume = min(130, state.volume + 5)
            mpv.volume(state.volume)
            state.status(f"🔊  Volume: {state.volume}%")

        # Next / Prev
        elif key in (ord('n'), ord('N')):
            nxt = state.next_track()
            if nxt is not None:
                load_and_play(nxt)
        elif key in (ord('p'), ord('P')):
            prv = state.prev_track()
            if prv is not None:
                load_and_play(prv)

        # Shuffle
        elif key in (ord('s'), ord('S')):
            state.shuffle = not state.shuffle
            state.shuffle_queue = []
            state.status(f"🔀  Shuffle {'ON' if state.shuffle else 'OFF'}")

        # Repeat
        elif key in (ord('r'), ord('R')):
            state.repeat = not state.repeat
            state.status(f"🔁  Repeat {'ON' if state.repeat else 'OFF'}")

        # Fetch lyrics manually
        elif key in (ord('l'), ord('L')):
            if state.meta:
                start_lyrics_fetch()
                state.status("⟳  Fetching lyrics…")

        # Toggle romanized / original lyrics
        elif key in (ord('t'), ord('T')):
            if state.lyrics_romanized:
                state.lyrics_show_roman = not state.lyrics_show_roman
                mode = 'Romanized' if state.lyrics_show_roman else 'Original'
                state.status(f"♪  {mode} lyrics")
            else:
                state.status("⟳  Romanization pending or unavailable")

        # ── Record video  Ctrl+R ─────────────────────────────────────────
        elif key == 18:   # Ctrl+R
            if not state.recording:
                ok, info = recorder.start(state, mpv)
                if ok:
                    state.recording = True
                    state.rec_path  = info
                    state.status(f"⏺  Recording started — Ctrl+R to stop", 5)
                else:
                    state.status(f"✗  Recorder: {info}", 5)
            else:
                ok2, info2 = recorder.stop(state, mpv)
                state.recording = False
                fname = Path(info2).name if ok2 else info2
                state.status((f"✓  Saved: {fname}" if ok2 else f"✗  {info2}"), 6)

        # Reload song list
        elif key in (ord('u'), ord('U')):
            state.refresh_songs()
            state.status(f"↺  Library refreshed  ({len(state.songs)} songs)")

        # Lyrics sync offset — [ earlier, ] later
        elif key == ord('['):
            state.lyrics_sync_offset -= 0.5
            sk = state.songs[state.current_idx].name if state.songs else ''
            state.sync_offsets[sk] = state.lyrics_sync_offset
            state.status(f"♪  Lyrics sync {state.lyrics_sync_offset:+.1f}s  ([ earlier  ] later)")
        elif key == ord(']'):
            state.lyrics_sync_offset += 0.5
            sk = state.songs[state.current_idx].name if state.songs else ''
            state.sync_offsets[sk] = state.lyrics_sync_offset
            state.status(f"♪  Lyrics sync {state.lyrics_sync_offset:+.1f}s  ([ earlier  ] later)")
        elif key == ord('\\'):   # \ to reset sync
            state.lyrics_sync_offset = 0.0
            sk = state.songs[state.current_idx].name if state.songs else ''
            state.sync_offsets.pop(sk, None)
            state.status("♪  Lyrics sync reset to 0")

        # Search mode — press / to open, ESC to close
        elif key == ord('/') and not state.search_mode:
            state.search_mode  = True
            state.search_query = ''
            state.run_search()
            curses.curs_set(1)

        # ── Download panel opener  (D key) ─────────────────────────────────
        elif key in (ord('d'), ord('D')) and not state.search_mode:
            if not HAS_YTDLP:
                state.status("✗  pip install yt-dlp  first", 5)
            else:
                state.dl_mode, state.dl_query  = True, ''
                state.dl_results, state.dl_cursor = [], 0
                state.dl_status   = "  ♫  Type a song name, press ENTER to search"
                state.dl_progress = ''
                curses.curs_set(1)

        # Scroll lyrics manually
        elif key == ord('j') or (use_split and key == curses.KEY_DOWN):
            state.lyrics_off += 1
            state.lyrics_auto = False
        elif key == ord('k') or (use_split and key == curses.KEY_UP):
            state.lyrics_off = max(0, state.lyrics_off - 1)
            state.lyrics_auto = False
        elif key in (ord('a'), ord('A')):
            state.lyrics_auto = not state.lyrics_auto
            state.status(f"♫  Lyrics auto-scroll {'ON' if state.lyrics_auto else 'OFF'}")

    mpv.kill()

# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def check_deps():
    ok = True
    if not HAS_MUTAGEN:
        print("  ⚠  mutagen not found  →  pip install mutagen")
        ok = False
    if not HAS_INDIC:
        print("  ℹ  For Indic romanization: pip install indic-transliteration  (optional)")
    if not HAS_PIL:
        print("  ℹ  For video recording: pip install Pillow   pkg install ffmpeg  (optional, no numpy needed)")
    if not HAS_YTDLP:
        print("  ℹ  For downloading: pip install yt-dlp  (optional)")
    try:
        subprocess.run(["mpv", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  ✗  mpv not found  →  pkg install mpv")
        ok = False
    return ok

def main():
    # ── Banner ────────────────────────────────────────────────────────────────
    print("\033[96m")
    for line in LOGO_LINES:
        print(" " * 4 + line)
    print("\033[0m")
    print(f"  \033[93mNova Player v{VERSION}\033[0m  —  Termux Music CLI\n")

    if not check_deps():
        print("\n  Install missing deps then rerun.  ")
        print("  \033[90mpkg install mpv && pip install mutagen requests\033[0m\n")

    # ── Find / create songs dir ───────────────────────────────────────────────
    songs_dir = None
    for d in SONG_DIRS:
        if d.exists():
            songs_dir = d
            break
    if songs_dir is None:
        songs_dir = SONG_DIRS[0]
        songs_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓  Created songs folder:  \033[92m{songs_dir}\033[0m")
    else:
        print(f"  ♫  Songs folder:  \033[92m{songs_dir}\033[0m")

    state = PlayerState(songs_dir)
    state.refresh_songs()
    print(f"  ♬  Found \033[96m{len(state.songs)}\033[0m audio files.")

    if not state.songs:
        print(f"\n  Drop audio files into:\n  {songs_dir}\n  Then press U inside the player to refresh.\n")

    mpv = MPVClient(MPV_SOCKET)

    # ── Auto-play first track ─────────────────────────────────────────────────
    autoplay_idx = None
    if state.songs:
        autoplay_idx = 0

    # ── Silent yt-dlp auto-update (background, max 15s wait) ─────────────────
    print("  ⟳  Checking for yt-dlp updates…")
    _update_thread = threading.Thread(target=_auto_update_ytdlp, daemon=True)
    _update_thread.start()
    _update_thread.join(timeout=15)
    print("  ✓  Ready")

    time.sleep(0.3)
    print("  Launching UI…\n")

    # Launch mpv and start playing BEFORE entering curses
    if autoplay_idx is not None:
        song = state.songs[autoplay_idx]
        state.meta = read_meta(song)
        print(f"  ▶  Starting mpv…  ({song.name})")
        if mpv.launch(song):
            mpv.volume(state.volume)
            mpv.play()
            state.eq.active = True
            state.mpv_started = True
            print("  ✓  Playback started")
            print("  ⟳  Lyrics will auto-load in the player…")
        else:
            print("  ✗  mpv failed to start — is it installed? (pkg install mpv)")
            time.sleep(2)

    def _main(stdscr):
        run_ui(stdscr, state, mpv)

    try:
        curses.wrapper(_main)
    except KeyboardInterrupt:
        pass
    finally:
        mpv.kill()
        print("\n  \033[93mNova Player exited. Stay groovy ♫\033[0m\n")

if __name__ == "__main__":
    main()
