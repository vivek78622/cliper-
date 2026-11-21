"""Optional read-only live chat collectors for YouTube and Twitch."""
import json
import os
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime
from urllib.parse import urlparse


CHAT_REACTION = re.compile(
    r"\b(?:lol|lmao|rofl|wtf|omg|no way|clip it|insane|crazy|rip|bruh|"
    r"that was close|what just happened|holy (?:shit|crap))\b|😂|🤣|💀|😱|😮|"
    r"\b(?:lul|kekw|pog|poggers|monkas|omegalul)\b",
    re.IGNORECASE,
)
YOUTUBE_VIDEO_RE = re.compile(r"(?:v=|youtu\.be/|youtube\.com/live/)([A-Za-z0-9_-]{6,})")


def reaction_match(message):
    return bool(CHAT_REACTION.search(str(message or "")))


def score_chat_windows(messages, starts, clip_len):
    """Return robust burst/reaction signals; repeated spam from one chatter is deweighted."""
    windows = []
    for start in starts:
        selected = [m for m in messages if start <= float(m.get("t", -1)) < start + clip_len]
        by_user = {}
        buckets = {}
        for item in selected:
            user = str(item.get("user") or "unknown").casefold()
            text = re.sub(r"\s+", " ", str(item.get("text") or "")).strip().casefold()
            by_user.setdefault(user, set()).add(text)
            bucket = int((float(item.get("t", start)) - start) // 5)
            bucket_users, bucket_reactions = buckets.setdefault(bucket, (set(), set()))
            bucket_users.add(user)
            if reaction_match(text):
                bucket_reactions.add(user)
        unique = len(by_user)
        reactions = sum(
            1 for user, texts in by_user.items()
            if any(reaction_match(text) for text in texts)
        )
        # One user repeating the same line cannot inflate the burst count.
        distinct_lines = sum(len(texts) for texts in by_user.values())
        peak_bucket, peak_data = max(
            buckets.items(), key=lambda pair: len(pair[1][0]) + 2 * len(pair[1][1]), default=(0, (set(), set()))
        )
        windows.append({"start": float(start), "messages": len(selected), "chatters": unique,
                        "reactions": reactions, "distinct_lines": distinct_lines,
                        "peak_t": float(start + peak_bucket * 5 + 2.5),
                        "peak_chatters": len(peak_data[0])})

    counts = [min(row["distinct_lines"], row["chatters"] * 3) for row in windows]
    if not counts:
        return []
    ordered = sorted(counts)
    median = ordered[len(ordered) // 2]
    deviations = sorted(abs(value - median) for value in counts)
    mad = max(1.0, deviations[len(deviations) // 2])
    scored = []
    for row, activity in zip(windows, counts):
        burst = max(0.0, (activity - median) / mad)
        participation = min(row["chatters"], 16) / 16
        reactions = min(row["reactions"], 5) / 5
        # A single spammer has little influence; a diverse reaction burst ranks higher.
        signal = min(2.5, burst * 0.55) + participation * 0.75 + reactions * 1.25
        row["signal"] = round(min(4.0, signal), 2)
        scored.append(row)
    return scored


def summarize_chat_window(messages, start, clip_len):
    selected = [m for m in messages if start <= float(m.get("t", -1)) < start + clip_len]
    by_user = {}
    for item in selected:
        user = str(item.get("user") or "unknown").casefold()
        by_user.setdefault(user, set()).add(re.sub(r"\s+", " ", str(item.get("text") or "")).strip().casefold())
    reaction_users = sum(1 for texts in by_user.values() if any(reaction_match(text) for text in texts))
    return {"message_count": len(selected), "unique_chatters": len(by_user),
            "reaction_chatters": reaction_users}


class LiveChatCollector:
    def __init__(self):
        self._messages = deque(maxlen=50000)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.status = "connecting"
        self.error = None

    def start(self):
        self._thread = threading.Thread(target=self._run_guarded, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def messages_between(self, start_epoch, end_epoch):
        with self._lock:
            return [dict(item) for item in self._messages if start_epoch <= item["epoch"] <= end_epoch]

    def discard_before(self, epoch):
        with self._lock:
            while self._messages and self._messages[0]["epoch"] < epoch:
                self._messages.popleft()

    def _add(self, epoch, user, text, message_id=None):
        with self._lock:
            self._messages.append({"epoch": float(epoch), "user": str(user or "unknown"),
                                   "text": str(text or "")[:500], "id": message_id})

    def _run_guarded(self):
        try:
            self.run()
        except Exception as exc:
            self.error = type(exc).__name__
            self.status = "unavailable"

    def run(self):
        raise NotImplementedError


class YouTubeChatCollector(LiveChatCollector):
    def __init__(self, video_id, api_key):
        super().__init__()
        self.video_id = video_id
        self.api_key = api_key

    def _get_json(self, url):
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)

    def run(self):
        params = urllib.parse.urlencode({
            "part": "liveStreamingDetails", "id": self.video_id, "key": self.api_key,
        })
        details = self._get_json(f"https://www.googleapis.com/youtube/v3/videos?{params}")
        items = details.get("items", [])
        live_chat_id = (items[0].get("liveStreamingDetails") or {}).get("activeLiveChatId") if items else None
        if not live_chat_id:
            self.status = "unavailable"
            self.error = "no active YouTube live chat"
            return

        page_token = None
        self.status = "connected"
        while not self._stop.is_set():
            params = {"part": "snippet,authorDetails", "liveChatId": live_chat_id,
                      "maxResults": 200, "key": self.api_key}
            if page_token:
                params["pageToken"] = page_token
            try:
                data = self._get_json("https://www.googleapis.com/youtube/v3/liveChat/messages?"
                                      + urllib.parse.urlencode(params))
            except urllib.error.HTTPError as exc:
                self.status = "unavailable"
                self.error = f"YouTube API HTTP {exc.code}"
                return
            for item in data.get("items", []):
                snippet = item.get("snippet") or {}
                author = item.get("authorDetails") or {}
                published = snippet.get("publishedAt")
                try:
                    epoch = datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp()
                except (AttributeError, TypeError, ValueError):
                    epoch = time.time()
                text = (snippet.get("textMessageDetails") or {}).get("messageText") or snippet.get("displayMessage", "")
                self._add(epoch, author.get("channelId") or author.get("displayName"), text, item.get("id"))
            page_token = data.get("nextPageToken")
            wait = max(1.0, float(data.get("pollingIntervalMillis", 5000)) / 1000)
            self._stop.wait(wait)


class TwitchChatCollector(LiveChatCollector):
    def __init__(self, channel, username, oauth_token):
        super().__init__()
        self.channel = channel.lower()
        self.username = username.lower()
        self.oauth_token = oauth_token.removeprefix("oauth:").strip()

    def run(self):
        context = ssl.create_default_context()
        with socket.create_connection(("irc.chat.twitch.tv", 6697), timeout=20) as raw:
            with context.wrap_socket(raw, server_hostname="irc.chat.twitch.tv") as connection:
                connection.settimeout(1)
                connection.sendall(f"PASS oauth:{self.oauth_token}\r\n".encode())
                connection.sendall(f"NICK {self.username}\r\n".encode())
                connection.sendall("CAP REQ :twitch.tv/tags\r\n".encode())
                connection.sendall(f"JOIN #{self.channel}\r\n".encode())
                self.status = "connected"
                buffer = b""
                while not self._stop.is_set():
                    try:
                        data = connection.recv(4096)
                        if not data:
                            self.status = "unavailable"
                            self.error = "Twitch chat disconnected"
                            return
                        buffer += data
                    except socket.timeout:
                        continue
                    while b"\r\n" in buffer:
                        raw_line, buffer = buffer.split(b"\r\n", 1)
                        line = raw_line.decode("utf-8", errors="replace")
                        if line.startswith("PING "):
                            connection.sendall(("PONG " + line[5:] + "\r\n").encode())
                            continue
                        self._parse_line(line)

    def _parse_line(self, line):
        tags = {}
        if line.startswith("@"):
            raw_tags, _, line = line.partition(" ")
            tags = dict(part.split("=", 1) if "=" in part else (part, "")
                        for part in raw_tags[1:].split(";"))
        if " PRIVMSG " not in line:
            return
        prefix, _, rest = line.partition(" PRIVMSG ")
        user = prefix.lstrip(":").split("!", 1)[0]
        _, _, text = rest.partition(" :")
        try:
            epoch = float(tags.get("tmi-sent-ts", "")) / 1000
        except ValueError:
            epoch = time.time()
        self._add(epoch, tags.get("user-id") or user, text, tags.get("id"))


def create_live_chat_collector(url, video_id=None, environ=None):
    """Return (collector, source label, fallback reason) without exposing credentials."""
    env = environ if environ is not None else os.environ
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host in {"youtube.com", "m.youtube.com", "youtu.be"}:
        api_key = env.get("YOUTUBE_API_KEY", "").strip()
        if not api_key:
            return None, "unavailable", "YOUTUBE_API_KEY is not set"
        match = YOUTUBE_VIDEO_RE.search(url or "")
        resolved_video_id = video_id or (match.group(1) if match else None)
        if not resolved_video_id:
            return None, "unavailable", "could not read YouTube video ID"
        return YouTubeChatCollector(resolved_video_id, api_key), "youtube-live-chat", None
    if host == "twitch.tv":
        path_parts = [part for part in parsed.path.split("/") if part]
        channel = path_parts[0].lower() if path_parts else ""
        username = env.get("TWITCH_CHAT_USERNAME", "").strip()
        token = env.get("TWITCH_CHAT_TOKEN", "").strip()
        if not username or not token:
            return None, "unavailable", "TWITCH_CHAT_USERNAME and TWITCH_CHAT_TOKEN are not set"
        if not channel:
            return None, "unavailable", "could not read Twitch channel from URL"
        return TwitchChatCollector(channel, username, token), "twitch-chat", None
    return None, "unsupported", "this platform has no live-chat connector"
