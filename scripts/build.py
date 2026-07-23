#!/usr/bin/env python3
"""Podcast-Builder: rendert episodes/*.txt via edge-tts zu MP3 und erzeugt RSS-Feed + Site.

Episodenformat (Front Matter zwischen --- Zeilen, danach der vorzulesende Text):

    ---
    title: Mein Titel
    date: 2026-07-23
    voice: de-DE-ConradNeural
    description: Kurzbeschreibung fuer die Podcast-App
    ---
    Der eigentliche Text ...

Ausgabe: _site/ (audio/*.mp3, feed.xml, index.html, robots.txt)
"""
import asyncio
import html
import os
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import edge_tts
from mutagen.mp3 import MP3

BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
if not BASE_URL:
    sys.exit("FEHLER: Umgebungsvariable BASE_URL fehlt")

FEED_TITLE = os.environ.get("FEED_TITLE", "Rayos Audio-Feed")
FEED_DESCRIPTION = "Privater Text-zu-Audio-Feed (automatisch generiert)"
DEFAULT_VOICE = os.environ.get("DEFAULT_VOICE", "de-DE-ConradNeural")

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "episodes"
SITE = ROOT / "_site"
AUDIO = SITE / "audio"
COVER = ROOT / "cover.jpg"  # optional: quadratisch, 1400-3000 px, RGB


def parse_episode(path: Path):
    raw = path.read_text(encoding="utf-8")
    meta, body = {}, raw
    if raw.lstrip().startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
            body = parts[2].strip()
    meta.setdefault("title", path.stem)
    meta.setdefault("voice", DEFAULT_VOICE)
    meta.setdefault("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    meta.setdefault("description", "")
    return meta, body


async def render(text: str, voice: str, out: Path):
    await edge_tts.Communicate(text, voice=voice).save(str(out))


def pub_date(txt: Path, meta: dict) -> datetime:
    """Veröffentlichungszeitpunkt: erster Git-Commit der Episodendatei.

    Stabil über Rebuilds hinweg (Feed-Reader sehen keine wandernden Daten) und
    minutengenau, damit "gerade eben" auch als solches angezeigt wird. Fallback:
    Front-Matter-Datum um 6 Uhr UTC (z. B. bei fehlender Git-Historie).
    """
    try:
        iso = subprocess.run(
            ["git", "log", "--follow", "--format=%aI", "--reverse", "--", str(txt)],
            capture_output=True, text=True, cwd=ROOT, check=True,
        ).stdout.strip().splitlines()[0]
        return datetime.fromisoformat(iso).astimezone(timezone.utc)
    except (subprocess.CalledProcessError, IndexError, ValueError):
        return datetime.strptime(meta["date"], "%Y-%m-%d").replace(
            hour=6, tzinfo=timezone.utc
        )


def build():
    AUDIO.mkdir(parents=True, exist_ok=True)
    items = []
    for txt in sorted(EPISODES_DIR.glob("*.txt")):
        meta, body = parse_episode(txt)
        slug = txt.stem
        mp3 = AUDIO / f"{slug}.mp3"
        print(f"Rendere {slug} mit {meta['voice']} ...", flush=True)
        asyncio.run(render(body, meta["voice"], mp3))
        info = MP3(mp3).info
        pub = pub_date(txt, meta)
        items.append(
            {
                "title": meta["title"],
                "description": meta["description"],
                "url": f"{BASE_URL}/audio/{slug}.mp3",
                "bytes": mp3.stat().st_size,
                "seconds": int(info.length),
                "pub": pub,
                "slug": slug,
            }
        )
    items.sort(key=lambda i: (i["pub"], i["slug"]), reverse=True)
    if COVER.exists():
        (SITE / "cover.jpg").write_bytes(COVER.read_bytes())
    write_feed(items)
    write_index(items)
    (SITE / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    print(f"Fertig: {len(items)} Episoden.")


def write_feed(items):
    e = html.escape
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">',
        "<channel>",
        f"<title>{e(FEED_TITLE)}</title>",
        f"<link>{e(BASE_URL)}/</link>",
        f"<description>{e(FEED_DESCRIPTION)}</description>",
        "<language>de-DE</language>",
        "<itunes:block>Yes</itunes:block>",
        f"<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>",
    ]
    if COVER.exists():
        parts += [
            f'<itunes:image href="{e(BASE_URL)}/cover.jpg"/>',
            f"<image><url>{e(BASE_URL)}/cover.jpg</url>"
            f"<title>{e(FEED_TITLE)}</title><link>{e(BASE_URL)}/</link></image>",
        ]
    for i in items:
        h, rem = divmod(i["seconds"], 3600)
        m, s = divmod(rem, 60)
        parts += [
            "<item>",
            f"<title>{e(i['title'])}</title>",
            f"<description>{e(i['description'])}</description>",
            f"<enclosure url=\"{e(i['url'])}\" length=\"{i['bytes']}\" type=\"audio/mpeg\"/>",
            f"<guid isPermaLink=\"false\">{e(i['slug'])}</guid>",
            f"<pubDate>{format_datetime(i['pub'])}</pubDate>",
            f"<itunes:duration>{h:02d}:{m:02d}:{s:02d}</itunes:duration>",
            "</item>",
        ]
    parts += ["</channel>", "</rss>"]
    (SITE / "feed.xml").write_text("\n".join(parts), encoding="utf-8")


def write_index(items):
    e = html.escape
    rows = "\n".join(
        f'<li><a href="audio/{e(i["slug"])}.mp3">{e(i["title"])}</a> '
        f'({i["seconds"] // 60}:{i["seconds"] % 60:02d} min)</li>'
        for i in items
    )
    (SITE / "index.html").write_text(
        f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow"><title>{e(FEED_TITLE)}</title></head>
<body><h1>{e(FEED_TITLE)}</h1>
<p>Feed-URL zum Abonnieren: <a href="feed.xml">feed.xml</a></p>
<ul>{rows}</ul></body></html>""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
