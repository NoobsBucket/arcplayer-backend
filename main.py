from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="ArcPlayer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)


@app.get("/health")
async def health():
    return {"status": "ok", "message": "ArcPlayer API is running!"}


@app.get("/search")
async def search(q: str, limit: int = 20):
    def _search():
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'default_search': 'ytsearch',
        }
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
                'thumbnail': v.get('thumbnail', ''),
                'youtubeId': v['id'],
                'isLocal': False,
            } for v in results.get('entries', []) if v]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _search)

@app.get("/stream/{video_id}")
async def get_stream(video_id: str):
    def _get_stream():
        ydl_opts = {
            'quiet': True,
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://youtube.com/watch?v={video_id}",
                download=False
            )
            formats = info.get('formats', [])
            audio_formats = [
                f for f in formats
                if f.get('acodec') != 'none'
                and f.get('vcodec') == 'none'
            ]
            if audio_formats:
                best = max(
                    audio_formats,
                    key=lambda x: x.get('abr', 0)
                )
                return {
                    'url': best['url'],
                    'title': info.get('title', 'Unknown'),
                    'artist': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                }
            raise HTTPException(
                status_code=404,
                detail="No audio format found"
            )

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_stream)


@app.get("/related/{video_id}")
async def get_related(video_id: str):
    def _get_related():
        ydl_opts = {'quiet': True}
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
                'thumbnail': v.get('thumbnail', ''),
                'youtubeId': v['id'],
                'isLocal': False,
            } for v in related[:15] if v.get('id')]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_related)


@app.get("/playlist/{playlist_id}")
async def get_playlist(playlist_id: str):
    def _get_playlist():
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://youtube.com/playlist?list={playlist_id}",
                download=False
            )
            return {
                'title': info.get('title', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'songs': [{
                    'id': v['id'],
                    'title': v.get('title', 'Unknown'),
                    'artist': v.get('uploader', 'Unknown'),
                    'duration': v.get('duration', 0),
                    'thumbnail': v.get('thumbnail', ''),
                    'youtubeId': v['id'],
                    'isLocal': False,
                } for v in info.get('entries', []) if v]
            }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_playlist)

