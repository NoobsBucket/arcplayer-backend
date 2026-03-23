import express from 'express';
import cors from 'cors';
import { Innertube } from 'youtubei.js';
import fs from 'fs';

const app = express();
app.use(cors());
app.use(express.json());

const COOKIES_FILE = '/app/cookies.txt';

// ─────────────────────────────────
// INIT INNERTUBE (once, reused)
// ─────────────────────────────────
let yt;

async function getInnertube() {
  if (yt) return yt;

  const opts = {
    generate_session_locally: true, // faster startup
  };

  // pass cookies if available (same as your yt-dlp setup)
  if (fs.existsSync(COOKIES_FILE)) {
    const raw = fs.readFileSync(COOKIES_FILE, 'utf-8');
    // cookies.txt is Netscape format — extract Cookie header string
    const cookieHeader = raw
      .split('\n')
      .filter(l => l && !l.startsWith('#'))
      .map(l => {
        const parts = l.split('\t');
        return parts.length >= 7 ? `${parts[5]}=${parts[6]}` : null;
      })
      .filter(Boolean)
      .join('; ');

    if (cookieHeader) opts.cookie = cookieHeader;
  }

  yt = await Innertube.create(opts);
  return yt;
}

// helper to safely get thumbnail
const thumb = (id) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;

// normalize a video object from various youtubei.js response shapes
function normalizeVideo(v) {
  const id = v?.id || v?.video_id;
  if (!id) return null;
  return {
    id,
    title: v?.title?.text ?? v?.title ?? 'Unknown',
    artist: v?.author?.name ?? v?.short_byline_text?.text ?? 'Unknown',
    duration: v?.duration?.seconds ?? 0,
    thumbnail: thumb(id),
    youtubeId: id,
    isLocal: false,
  };
}


// ─────────────────────────────────
// HEALTH CHECK
// ─────────────────────────────────
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    message: 'ArcPlayer API is running!',
    cookies: fs.existsSync(COOKIES_FILE),
    engine: 'youtubei.js',
  });
});


// ─────────────────────────────────
// SEARCH
// ─────────────────────────────────
app.get('/search', async (req, res) => {
  try {
    const { q, limit = 20 } = req.query;
    if (!q) return res.status(400).json({ error: 'q is required' });

    const innertube = await getInnertube();
    const results = await innertube.search(q, { type: 'video' });

    const videos = (results.videos || [])
      .slice(0, Number(limit))
      .map(normalizeVideo)
      .filter(Boolean);

    res.json(videos);
  } catch (e) {
    console.error('/search error:', e.message);
    res.status(500).json({ error: e.message });
  }
});


// ─────────────────────────────────
// GET STREAM URL  🔥 fast now
// ─────────────────────────────────
app.get('/stream/:video_id', async (req, res) => {
  try {
    const { video_id } = req.params;
    const innertube = await getInnertube();

    const info = await innertube.getBasicInfo(video_id);

    // pick best audio-only format
    const format = info.chooseFormat({ type: 'audio', quality: 'best' });

    if (!format) {
      return res.status(404).json({ error: 'No audio format found' });
    }

    const url = format.decipher(innertube.session.player);

    res.json({
      url,
      title: info.basic_info?.title ?? 'Unknown',
      artist: info.basic_info?.author ?? 'Unknown',
      duration: info.basic_info?.duration ?? 0,
      thumbnail: thumb(video_id),
    });
  } catch (e) {
    console.error('/stream error:', e.message);
    res.status(500).json({ error: e.message });
  }
});


// ─────────────────────────────────
// GET RELATED  (next song suggestions)
// ─────────────────────────────────
app.get('/related/:video_id', async (req, res) => {
  try {
    const { video_id } = req.params;
    const innertube = await getInnertube();

    // getInfo gives richer data including watch_next panel
    const info = await innertube.getInfo(video_id);

    const related = info.watch_next_feed
      ?.filter(v => v?.type === 'CompactVideo')
      ?.slice(0, 15)
      ?.map(normalizeVideo)
      ?.filter(Boolean) ?? [];

    res.json(related);
  } catch (e) {
    console.error('/related error:', e.message);
    res.status(500).json({ error: e.message });
  }
});


// ─────────────────────────────────
// GET PLAYLIST
// ─────────────────────────────────
app.get('/playlist/:playlist_id', async (req, res) => {
  try {
    const { playlist_id } = req.params;
    const innertube = await getInnertube();

    const playlist = await innertube.getPlaylist(playlist_id);
    const entries = playlist.videos || [];
    const firstId = entries[0]?.id ?? '';

    res.json({
      title: playlist.info?.title ?? 'Unknown',
      thumbnail: thumb(firstId),
      songs: entries.map(normalizeVideo).filter(Boolean),
    });
  } catch (e) {
    console.error('/playlist error:', e.message);
    res.status(500).json({ error: e.message });
  }
});


// ─────────────────────────────────
// GET TRENDING
// ─────────────────────────────────
app.get('/trending', async (req, res) => {
  try {
    const innertube = await getInnertube();
    const trending = await innertube.getTrending();

    // Music tab is more relevant for a music app
    const musicTab = trending.tabs?.find(t =>
      t?.title?.toLowerCase().includes('music')
    );

    const feed = musicTab
      ? await musicTab.endpoint.call(innertube.actions)
      : trending;

    const videos = (feed.videos ?? feed.contents ?? [])
      .slice(0, 20)
      .map(normalizeVideo)
      .filter(Boolean);

    res.json(videos);
  } catch (e) {
    console.error('/trending error:', e.message);
    res.status(500).json({ error: e.message });
  }
});


// ─────────────────────────────────
// START
// ─────────────────────────────────
const PORT = process.env.PORT || 8000;

// warm up innertube on boot so first request is fast
getInnertube()
  .then(() => console.log('✅ Innertube ready'))
  .catch(e => console.error('Innertube init failed:', e.message));

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🎵 ArcPlayer API running on port ${PORT}`);
});