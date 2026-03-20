from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="ArcPlayer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)
COOKIES_FILE = '/app/cookies.txt'

def get_ydl_opts(extra: dict = {}):
    opts = {
        'quiet': True,
        **extra,
    }
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
    return opts

# ─────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "message": "ArcPlayer API is running!",
        "cookies": os.path.exists(COOKIES_FILE)
    }

# ─────────────────────────────────
# SEARCH
# ─────────────────────────────────
@app.get("/search")
async def search(q: str, limit: int = 20):
    def _search():
        ydl_opts = get_ydl_opts({
            'extract_flat': True,
            'default_search': 'ytsearch',
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(
                f"ytsearch{limit}:{q}",
                download=False
            )
            return [{
                'id': v['id'],
                'title': v.get('title', 'Unknown'),
                'artist': v.get('uploader', 'Unknown'),
                'duration': v.get('duration', 0),
                'thumbnail': f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
                'youtubeId': v['id'],
                'isLocal': False,
            } for v in results.get('entries', []) if v and v.get('id')]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _search)

# ─────────────────────────────────
# GET STREAM URL
# ─────────────────────────────────
@app.get("/stream/{video_id}")
async def get_stream(video_id: str):
    def _get_stream():
        ydl_opts = get_ydl_opts({
            'format': 'bestaudio/best',
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://youtube.com/watch?v={video_id}",
                download=False
            )

            # Try direct URL first
            if info.get('url'):
                return {
                    'url': info['url'],
                    'title': info.get('title', 'Unknown'),
                    'artist': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                }

            formats = info.get('formats', [])

            # Try audio only formats first
            audio_formats = [
                f for f in formats
                if f.get('acodec') != 'none'
                and f.get('vcodec') == 'none'
                and f.get('url')
            ]

            # Fallback to any format with url
            if not audio_formats:
                audio_formats = [
                    f for f in formats
                    if f.get('url')
                ]

            if not audio_formats:
                raise HTTPException(
                    status_code=404,
                    detail="No playable format found"
                )

            # Get best quality
            best = max(
                audio_formats,
                key=lambda x: x.get('abr') or x.get('tbr') or x.get('quality') or 0
            )

            return {
                'url': best['url'],
                'title': info.get('title', 'Unknown'),
                'artist': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_stream)

# ─────────────────────────────────
# GET RELATED SONGS
# ─────────────────────────────────
@app.get("/related/{video_id}")
async def get_related(video_id: str):
    def _get_related():
        ydl_opts = get_ydl_opts()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://youtube.com/watch?v={video_id}",
                download=False
            )
            related = info.get('related_videos', [])
            return [{
                'id': v['id'],
                'title': v.get('title', 'Unknown'),
                'artist': v.get('uploader', 'Unknown'),
                'duration': v.get('duration', 0),
                'thumbnail': f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
                'youtubeId': v['id'],
                'isLocal': False,
            } for v in related[:15] if v and v.get('id')]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_related)

# ─────────────────────────────────
# GET PLAYLIST
# ─────────────────────────────────
@app.get("/playlist/{playlist_id}")
async def get_playlist(playlist_id: str):
    def _get_playlist():
        ydl_opts = get_ydl_opts({
            'extract_flat': True,
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://youtube.com/playlist?list={playlist_id}",
                download=False
            )
            entries = info.get('entries', [])
            first_id = entries[0].get('id', '') if entries else ''
            return {
                'title': info.get('title', 'Unknown'),
                'thumbnail': f"https://i.ytimg.com/vi/{first_id}/hqdefault.jpg",
                'songs': [{
                    'id': v['id'],
                    'title': v.get('title', 'Unknown'),
                    'artist': v.get('uploader', 'Unknown'),
                    'duration': v.get('duration', 0),
                    'thumbnail': f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
                    'youtubeId': v['id'],
                    'isLocal': False,
                } for v in entries if v and v.get('id')]
            }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_playlist)

# ─────────────────────────────────
# GET TRENDING
# ─────────────────────────────────
@app.get("/trending")
async def get_trending():
    def _get_trending():
        ydl_opts = get_ydl_opts({
            'extract_flat': True,
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(
                "https://www.youtube.com/feed/trending?bp=4gINGgt5dG1hX2NoYXJ0cw%3D%3D",
                download=False
            )
            return [{
                'id': v['id'],
                'title': v.get('title', 'Unknown'),
                'artist': v.get('uploader', 'Unknown'),
                'duration': v.get('duration', 0),
                'thumbnail': f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
                'youtubeId': v['id'],
                'isLocal': False,
            } for v in results.get('entries', [])[:20] if v and v.get('id')]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_trending)