# Pipeline

`
input/song.mp3  ──prep──▶  assets/audio/song_mono22k.wav   (22k mono, header waveform)
input/lyrics.lrc ─lyrics──▶ assets/audio/lyrics_synced.lrc + data/word_timing/word_timeline.json
data/h3_takes.json ─dancer─▶ dancer/pv_cache/* + continuity/cache/h3_full_v1/*   (stand-in takes)
dsh/batches/*.py ─pages──▶  dsh/*_frames.json ─screenshot.mjs(Playwright)──▶ dsh_frames/
dsh/compose.py  ─render──▶  build/film_master.mp4 ─ffmpeg──▶ build/film.mp4
archive ───────▶  output/YYYY-MM-DD-NN/film.mp4 + RESULT.md
`

Entry points: python -m world_execute_replica all, un.bat, or
world-execute after pip install -e ..
