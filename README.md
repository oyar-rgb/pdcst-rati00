# pdcst-rati00 — Text-zu-Audio-Podcast-Pipeline

Privater Podcast-Feed: Texte in `episodes/` werden bei jedem Push automatisch per
[edge-tts](https://pypi.org/project/edge-tts/) vertont und als RSS-Feed auf GitHub Pages
veröffentlicht.

## Wie es funktioniert

1. Neue Episode: `.txt`-Datei in `episodes/` ablegen (Format siehe unten), pushen.
2. GitHub Action (`.github/workflows/podcast.yml`) rendert alle Episoden zu MP3,
   baut `feed.xml` und deployed nach GitHub Pages.
3. Apple Podcasts aktualisiert das Abo automatisch.

**Feed-URL:** `https://oyar-rgb.github.io/pdcst-rati00/feed.xml`

## Episodenformat

Dateiname: `JJJJ-MM-TT-kurzer-slug.txt`

```
---
title: Titel der Episode
date: 2026-07-23
voice: de-DE-ConradNeural
description: Kurzbeschreibung für die Podcast-App
---
Der vorzulesende Text ...
```

`voice` ist optional (Standard: `DEFAULT_VOICE` im Workflow, sonst de-DE-ConradNeural).
Verfügbare deutsche Stimmen u. a.: `de-DE-ConradNeural`, `de-DE-KatjaNeural`,
`de-DE-FlorianMultilingualNeural`, `de-DE-SeraphinaMultilingualNeural`, `de-DE-AmalaNeural`.

## Hinweise

- GitHub Pages ist öffentlich; der Feed ist nur durch Nicht-Auffindbarkeit geschützt
  (`robots.txt` + `itunes:block` verhindern Indexierung, nicht den Zugriff).
- Alle Episoden werden bei jedem Lauf neu gerendert (zustandslos, einfach wartbar).
