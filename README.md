# AndroidTVBackground-Reddit

Automatically generate high-quality **Android TV wallpapers** from **TMDB trending and popular movies/TV shows**, and upload them to a dedicated **Reddit subreddit** — perfect for use as dynamic backgrounds on Android TV launchers such as *Projectivy Launcher*.

![Weapons](https://github.com/user-attachments/assets/d8adb105-2cce-4d2d-aa71-657cecc47333)

---

## 🧠 What It Does

This project automates the creation and sharing of Android TV wallpapers:

1. Fetches **popular** and **trending** movies/series from [TMDB](https://www.themoviedb.org/).
2. Generates wallpaper-style images featuring background, title/logo, and short description.
3. Uploads them automatically to a configured **Reddit subreddit**.

You can use the existing subreddits:

* 🇺🇸 [`r/AndroidTVWallpapers`](https://www.reddit.com/r/AndroidTVWallpapers) *(English)*
* 🇪🇸 [`r/AndroidTVWallpapersES`](https://www.reddit.com/r/AndroidTVWallpapersES) *(Spanish)*

🕒 **Automatic updates:**  
New wallpapers are automatically generated and uploaded **every Monday at 09:00 UTC**.

---
## 🎬 Streaming Providers
The project also supports showing available streaming platforms (e.g. Netflix, Prime Video, Apple TV, etc.) for each movie or TV show.
This data is obtained through TMDB’s “Watch Providers” API, which is powered by JustWatch.

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
   python TMDB.py           # Generates wallpapers
   python upload-wallpaper.py   # Uploads them to Reddit
   ```

---

### 🐳 Docker Setup

You can easily run this project using Docker with your preferred configuration.

#### Example in `docker-compose.yml`

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

### 🤖 Reddit

You’ll need:

* **Client ID**
* **Client Secret**
* **Refresh Token**

Steps:

1. Go to [Reddit Apps](https://www.reddit.com/prefs/apps)
2. Click **“Create App”**
3. Select **“script”**
4. Fill in name, redirect URL and save.
5. Retrieve your tokens (use a [refresh token tool](https://github.com/reddit-archive/reddit/wiki/OAuth2) or similar).
6. Create your own subreddit for uploads.

---

## 🧾 Credits

This project is **based on** [adelatour11/androidtvbackground](https://github.com/adelatour11/androidtvbackground).
Originally designed to fetch Plex/TMDB backgrounds for Android TV, it has been extended to support **multi-language wallpapers**, **automatic generation**, and **Reddit publication**.

---

## 📜 License

MIT License © 2025 [rfmarcos](https://github.com/rfmarcos)
