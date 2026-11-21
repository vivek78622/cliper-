"""Find current YouTube live streams for a query, ranked by YouTube view count.

Set YOUTUBE_API_KEY in the environment. The YouTube API does not provide this
search as a dependable live concurrent-viewer leaderboard.
"""
import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/youtube/v3/search"


def find_streams(query, api_key, limit=25):
    params = urllib.parse.urlencode({
        "part": "snippet", "eventType": "live", "type": "video", "q": query,
        "maxResults": min(max(limit, 1), 50), "order": "viewCount", "key": api_key,
    })
    request = urllib.request.Request(f"{API}?{params}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    streams = []
    for item in payload.get("items", []):
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            continue
        streams.append({
            "title": html.unescape(snippet.get("title", "")),
            "channel": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "published_at": snippet.get("publishedAt"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "rank_signal": "YouTube search order=viewCount; not current live viewers",
        })
    return streams


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="GTA 6")
    parser.add_argument("--max", type=int, default=25, help="candidate count (maximum 50)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        sys.exit("Set YOUTUBE_API_KEY in your environment before searching.")
    try:
        streams = find_streams(args.query, api_key, args.max)
    except urllib.error.HTTPError as error:
        sys.exit(f"YouTube API returned HTTP {error.code}; check the API key and quota.")
    except Exception as error:
        sys.exit(f"Stream search failed ({type(error).__name__}). Check the network and API key.")
    if args.json:
        print(json.dumps(streams, ensure_ascii=False, indent=2))
    else:
        for rank, stream in enumerate(streams, 1):
            print(f"[{rank}] {stream['channel']} — {stream['title']}\n    {stream['url']}")
            print("    Rank signal: YouTube view-count ordering; not current concurrent viewers.")
        if not streams:
            print("No live results found. Try another search phrase.")


if __name__ == "__main__":
    main()
