# AndroidTVBackground-Reddit

Automatically generate high-quality **Android TV wallpapers** from **TMDB trending and popular movies/TV shows**, and publish them for dedicated **Reddit subreddits** — perfect for use as dynamic backgrounds on Android TV launchers such as *Projectivy Launcher*.

![Weapons](https://github.com/user-attachments/assets/d8adb105-2cce-4d2d-aa71-657cecc47333)

---

## 🧠 What It Does

This project automates the creation and sharing of Android TV wallpapers:

1. Fetches **popular** and **trending** movies/series from [TMDB](https://www.themoviedb.org/).
2. Generates wallpaper-style images featuring background, title/logo, and short description.
3. Commits them to this repository (`tmdb_backgrounds/<lang>/`) together with a manifest (`wallpapers_<lang>.json`) with the raw URL of every image, which is used to publish them to the subreddits.

You can use the existing subreddits:

* 🇺🇸 [`r/AndroidTVWallpapers`](https://www.reddit.com/r/AndroidTVWallpapers) *(English)*
* 🇪🇸 [`r/AndroidTVWallpapersES`](https://www.reddit.com/r/AndroidTVWallpapersES) *(Spanish)*

🕒 **Automatic updates:**  
New wallpapers are automatically generated and uploaded **every Monday at 09:00 UTC**.

---
## 🎬 Streaming Providers
The project also supports showing available streaming platforms (e.g. Netflix, Prime Video, Apple TV, etc.) for each movie or TV show.
This data is obtained through TMDB’s “Watch Providers” API, which is powered by JustWatch.

## 🎯 Global Hits Only

TMDB trending is worldwide, so it often includes titles that are only popular in a local market (K-dramas, Indian or Chinese films...).
Titles whose original language is not in `MAINSTREAM_LANGUAGES` are only included when they have at least `MIN_VOTES_OTHER_LANGUAGES` votes (default 1000),
so worldwide hits like *Squid Game* still make the cut. Candidates are ranked by a weighted rating, so titles with very few votes don't take over the list.

## 🌍 Multi-language Support

One of the main features of this project is **easy language customization**.
All text (titles, labels, descriptions, etc.) can be changed using environment variables — no code editing required.

In your `.env` file, just set:

```bash
LANGUAGE='en-US'
LANGUAGE_SHORT='en'
NOW_TRENDING_TEXT='Now trending on'
SEASON_TEXT='Season'
SEASONS_TEXT='Seasons'
REGION='US'   # optional, country for streaming providers (defaults to the LANGUAGE region)
```

You can switch it to any language simply by updating these parameters.

---

## 🚀 Run Your Own Instance

### 🧰 Manual Setup

1. Install Python 3.10+
2. Clone the repository
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
4. Execute the scripts:

   ```bash
   python TMDB.py           # Generates wallpapers and wallpapers_<lang>.json
   ```

---

### 🐳 Docker Setup

You can easily run this project using Docker with your preferred configuration.

#### Example in `docker-compose.yml`

```yaml
services:
  androidtvbackground:
    image: ghcr.io/rfmarcos/androidtvbackground-reddit:latest
    env_file: .env
    volumes:
      - ./tmdb_backgrounds:/app/tmdb_backgrounds
    command: ["TMDB.py"]
```

---

## ⚙️ Environment Configuration

The project uses a `.env` file for configuration.
See `.env.example` for reference:


> If an optional variable is missing, default values are automatically applied.

---

## 🔑 Getting Your API Keys

### 🎮 TMDB

1. Create a free account at [themoviedb.org](https://www.themoviedb.org/).
2. Go to **Settings → API** and create a “Read Access Token”.

---

## 🧾 Credits

This project is **based on** [adelatour11/androidtvbackground](https://github.com/adelatour11/androidtvbackground).
Originally designed to fetch Plex/TMDB backgrounds for Android TV, it has been extended to support **multi-language wallpapers**, **automatic generation**, and **Reddit publication**.

---

## 📜 License

MIT License © 2025 [rfmarcos](https://github.com/rfmarcos)
