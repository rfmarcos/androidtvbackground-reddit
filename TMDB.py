import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from io import BytesIO
import os
from dotenv import load_dotenv
import shutil
from datetime import datetime, timedelta
from functools import lru_cache
import difflib
import math

load_dotenv()

TMDB_TOKEN = os.getenv("TMDB_BEARER_TOKEN")

# Language properties
LANGUAGE = os.getenv("LANGUAGE") or "en-US"
# Folder / manifest suffix (e.g. 'en', 'es', 'br')
LANGUAGE_SHORT = os.getenv("LANGUAGE_SHORT") or "en"
# ISO 639-1 language code used to match logos (e.g. 'pt' for 'pt-BR')
LANGUAGE_CODE = LANGUAGE.split("-")[0].lower()
# ISO 3166-1 region used for watch providers (e.g. 'US' for 'en-US')
REGION = (
    os.getenv("REGION")
    or (LANGUAGE.split("-")[1] if "-" in LANGUAGE else LANGUAGE_SHORT)
).upper()
NOW_TRENDING_TEXT = os.getenv("NOW_TRENDING_TEXT") or "Now trending on"
AVAILABLE_ON_TEXT = os.getenv("AVAILABLE_ON_TEXT") or "Available on"
SEASON_TEXT = os.getenv("SEASON_TEXT") or "Season"
SEASONS_TEXT = os.getenv("SEASONS_TEXT") or "Seasons"
OVERVIEW_LINES = int(os.getenv("OVERVIEW_LINES", 4))

# Base URL for the API
TMDB_URL = "https://api.themoviedb.org/3/"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/original"

# Set your TMDB API Read Access Token key here
TMDB_HEADERS = {"accept": "application/json", "Authorization": f"Bearer {TMDB_TOKEN}"}
REQUEST_TIMEOUT = 15

# Shared HTTP session with retries for transient errors and rate limiting
session = requests.Session()
session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=4,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
    ),
)


def tmdb_get(path):
    """GET a TMDB API path and return its JSON, or {} on failure."""
    try:
        response = session.get(
            f"{TMDB_URL}{path}", headers=TMDB_HEADERS, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[WARN] TMDB request failed for {path}: {e}")
        return {}


# TV Exclusion list - this filter will exclude Tv shows from chosen countries that have a specific genre
TV_EXCLUDED_COUNTRIES = []  # based on ISO 3166-1 alpha-2 codes, enter lowercase like ['cn','kr','jp','fr','us']
TV_EXCLUDED_GENRES = []  # like ['Animation']

# Movie Exclusion list - this filter will exclude movies from chosen countries that have a specific genre
MOVIE_EXCLUDED_COUNTRIES = []  # based on ISO 3166-1 alpha-2 codes, enter lowercase like ['cn','kr','jp','fr','us']
MOVIE_EXCLUDED_GENRES = []  # like ['Animation']

# Keyword exclusion list - this filter will exclude movies or tv shows that contain a specific keyword in their TMDB profile
EXCLUDED_KEYWORDS = ["adult"]  # like ['adult']

# Global hits filter - trending is global, so titles whose original language is not in this list
# (e.g. local K-dramas, Indian or Chinese films) only pass when they have enough votes to be a
# worldwide hit (like Squid Game). Set MIN_VOTES_OTHER_LANGUAGES=0 to disable.
MAINSTREAM_LANGUAGES = {
    language.strip().lower()
    for language in (
        os.getenv("MAINSTREAM_LANGUAGES") or "en,es,fr,it,de,pt,ca,nl,sv,da,no,pl"
    ).split(",")
} | {LANGUAGE_CODE}
MIN_VOTES_OTHER_LANGUAGES = int(os.getenv("MIN_VOTES_OTHER_LANGUAGES", 1000))

# Ranking - weighted rating so titles with a handful of votes don't outrank well-known ones
RANKING_MIN_VOTES = 300
RANKING_PRIOR = 6.5

# Filter movies by release date and tv shows by last air date
MAX_AIR_DATE = (
    datetime.now() - timedelta(days=365)
)  # specify the number of days since the movie release or the tv show last air date, shows before this date will be excluded

# Fonts bundled in resources/fonts (Roboto, Apache 2.0)
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "fonts")


def font(weight, size):
    return ImageFont.truetype(os.path.join(FONTS_DIR, f"Roboto-{weight}.ttf"), size=size)

movies_max = 20  # specify the maximum number of movies to fetch
tvshows_max = 20  # specify the maximum number of TV shows to fetch

# Endpoint for discover shows
start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
end_date = datetime.now().strftime("%Y-%m-%d")
discover_movies_path = f"discover/movie?sort_by=popularity.desc&language={LANGUAGE}&include_adult=false&page=1&with_release_type=4|5|6&include_video=false&vote_average.gte=1&vote_count.gte=50&with_runtime.gte=15&without_genres=99&release_date.gte={start_date}&release_date.lte={end_date}"
discover_tvshows_path = f"discover/tv?sort_by=popularity.desc&language={LANGUAGE}&include_adult=false&page=1&vote_average.gte=1&vote_count.gte=50&with_runtime.gte=15&without_genres=99|16&first_air_date.gte={start_date}&first_air_date.lte={end_date}"

# Fetching trending and discover movies / TV shows
trending_movies = tmdb_get(f"trending/movie/week?language={LANGUAGE}")
trending_tvshows = tmdb_get(f"trending/tv/week?language={LANGUAGE}")
discover_movies = tmdb_get(discover_movies_path)
discover_tvshows = tmdb_get(discover_tvshows_path)

# Fetching genres for movies and TV shows
movie_genres = {
    genre["id"]: genre["name"]
    for genre in tmdb_get(f"genre/movie/list?language={LANGUAGE}").get("genres", [])
}
tv_genres = {
    genre["id"]: genre["name"]
    for genre in tmdb_get(f"genre/tv/list?language={LANGUAGE}").get("genres", [])
}


# Fetching TV show details (cached: used by both the filter and the renderer)
@lru_cache(maxsize=None)
def get_tv_show_details(tv_id):
    return tmdb_get(f"tv/{tv_id}?language={LANGUAGE}")


# Fetching movie details
def get_movie_details(movie_id):
    return tmdb_get(f"movie/{movie_id}?language={LANGUAGE}")


# Function to fetch keywords for a movie
def get_movie_keywords(movie_id):
    return [
        keyword["name"].lower()
        for keyword in tmdb_get(f"movie/{movie_id}/keywords").get("keywords", [])
    ]


# Function to fetch keywords for a TV show
def get_tv_keywords(tv_id):
    return [
        keyword["name"].lower()
        for keyword in tmdb_get(f"tv/{tv_id}/keywords").get("results", [])
    ]


# Create a language-specific directory to save the backgrounds and clear its contents if it exists
base_background_dir = "tmdb_backgrounds"
background_dir = os.path.join(base_background_dir, LANGUAGE_SHORT)
os.makedirs(base_background_dir, exist_ok=True)
if os.path.exists(background_dir):
    for file in os.listdir(background_dir):
        file_path = os.path.join(background_dir, file)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"[WARN] Failed to delete {file_path}: {e}")
os.makedirs(background_dir, exist_ok=True)


def cover_resize(image, width, height):
    # Scale the image to fill width x height and crop the overflow (centered)
    scale = max(width / image.width, height / image.height)
    resized = image.resize(
        (max(width, round(image.width * scale)), max(height, round(image.height * scale))),
        Image.LANCZOS,
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def fit_resize(image, max_width, max_height):
    # Scale the image to fit inside max_width x max_height keeping its aspect ratio
    scale = min(max_width / image.width, max_height / image.height)
    return image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.LANCZOS,
    )


def clean_filename(filename):
    # Remove problematic characters from the filename
    cleaned_filename = "".join(
        c if c.isalnum() or c in "._-" else "_" for c in filename
    )
    return cleaned_filename


def unique_path(directory, name, extension):
    # Avoid overwriting a wallpaper when a movie and a TV show share the same title
    path = os.path.join(directory, f"{name}{extension}")
    counter = 2
    while os.path.exists(path):
        path = os.path.join(directory, f"{name}_{counter}{extension}")
        counter += 1
    return path


# Fetch movie or TV show logo
def get_logo_fallback(media_type, media):
    if media_type == "movie":
        name = media["title"]
        original = media["original_title"]
    else:
        name = media["name"]
        original = media["original_name"]

    if similarity(name, original) > 0.9:
        logo = get_multilogo(media_type, media["id"], original_language=media["original_language"])
    else:
        logo = get_logo(media_type, media["id"], LANGUAGE_CODE)

    if logo is None and media["original_language"] != "en":
        details_data = tmdb_get(f"{media_type}/{media['id']}?language=en-US")
        english_name = details_data.get("title" if media_type == "movie" else "name", "")

        if similarity(name, english_name) > 0.9:
            logo = get_logo(media_type, media["id"], "en")

    return logo


def get_logo(media_type, media_id, language):
    logos = tmdb_get(f"{media_type}/{media_id}/images?language={language}").get("logos", [])
    for logo in logos:
        if logo["iso_639_1"] == language and logo["file_path"].endswith(".png"):
            return logo["file_path"]
    return None


def get_multilogo(media_type, media_id, original_language):
    logos = tmdb_get(
        f"{media_type}/{media_id}/images?include_image_language={LANGUAGE_CODE},{original_language}"
    ).get("logos", [])
    valid_logos = [logo for logo in logos if logo["file_path"].endswith(".png")]

    for valid_logo in valid_logos:
        if valid_logo["iso_639_1"] == LANGUAGE_CODE:
            return valid_logo["file_path"]

    for valid_logo in valid_logos:
        if valid_logo["iso_639_1"] == original_language:
            return valid_logo["file_path"]

    return None


def similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


# Wallpaper layout (4K canvas). The info block sits top-left, leaving the lower
# half free for the launcher rows (e.g. Projectivy Launcher).
CANVAS_SIZE = (3840, 2160)
MARGIN_LEFT = 210
CONTENT_WIDTH = 1550
LOGO_MAX_SIZE = (1350, 420)
LOGO_BOTTOM = 640
META_CENTER = 725
PROVIDER_LOGO_HEIGHT = 88
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", 90))

RESOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")

# TMDB returns some TV-only genres untranslated
TV_GENRE_TRANSLATIONS = {
    "es": {
        "Action & Adventure": "Acción y aventura",
        "Sci-Fi & Fantasy": "Ciencia ficción y fantasía",
        "War & Politics": "Bélica y política",
        "Kids": "Infantil",
        "Soap": "Telenovela",
        "Talk": "Entrevistas",
    },
    "pt": {
        "Action & Adventure": "Ação e aventura",
        "Sci-Fi & Fantasy": "Ficção científica e fantasia",
        "War & Politics": "Guerra e política",
        "Kids": "Infantil",
        "Soap": "Novela",
        "Talk": "Entrevistas",
    },
}


def genre_names(genre_ids, genres_map, translations=None, limit=2):
    names = [genres_map.get(genre_id) for genre_id in genre_ids]
    names = [(translations or {}).get(name, name) for name in names if name]
    return ", ".join(names[:limit])


def get_textless_backdrop(media_type, media):
    # Prefer a backdrop without baked-in text, so it doesn't clash with the logo
    textless_paths = [
        backdrop["file_path"]
        for backdrop in tmdb_get(
            f"{media_type}/{media['id']}/images?include_image_language=null"
        ).get("backdrops", [])
        if backdrop.get("iso_639_1") is None and backdrop.get("width", 0) >= 1920
    ]
    if media.get("backdrop_path") in textless_paths or not textless_paths:
        return media.get("backdrop_path")
    return textless_paths[0]


@lru_cache(maxsize=None)
def get_provider_logo(logo_path):
    try:
        response = session.get(f"https://image.tmdb.org/t/p/w154{logo_path}", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception as e:
        print(f"Error getting provider logo {logo_path}: {e}")
        return None


def get_providers_logos(media_type, media_id):
    providers = (
        tmdb_get(f"{media_type}/{media_id}/watch/providers")
        .get("results", {})
        .get(REGION, {})
        .get("flatrate", [])
    )
    providers.sort(key=lambda provider: provider.get("display_priority", 999))

    providers_logos = []
    seen = set()
    for provider in providers:
        logo_path = provider.get("logo_path")
        # Skip variants sharing the same logo (e.g. "Netflix Standard with Ads")
        if not logo_path or logo_path in seen:
            continue
        seen.add(logo_path)
        logo = get_provider_logo(logo_path)
        if logo:
            providers_logos.append(logo)

    if providers_logos:
        return providers_logos, AVAILABLE_ON_TEXT
    return [], NOW_TRENDING_TEXT


def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def gradient_mask(size, horizontal, fn):
    # Build a full-size L mask from fn(t), t in [0, 1] along one axis
    strip = Image.new("L", (256, 1) if horizontal else (1, 256))
    strip.putdata([round(255 * fn(i / 255)) for i in range(256)])
    return strip.resize(size, Image.BILINEAR)


@lru_cache(maxsize=1)
def overlay_mask():
    # Dark on the left (text), at the bottom (launcher rows) and a bit on top (clock)
    left = gradient_mask(CANVAS_SIZE, True, lambda t: 0.96 * (1 - smoothstep((t - 0.28) / 0.45)))
    bottom = gradient_mask(CANVAS_SIZE, False, lambda t: 0.98 * smoothstep((t - 0.42) / 0.46))
    top = gradient_mask(CANVAS_SIZE, False, lambda t: 0.45 * (1 - smoothstep(t / 0.22)))
    visible = ImageChops.multiply(ImageChops.invert(left), ImageChops.invert(bottom))
    return ImageChops.invert(ImageChops.multiply(visible, ImageChops.invert(top)))


@lru_cache(maxsize=1)
def dither_noise():
    # Subtle noise to prevent banding in the dark gradients
    noise = Image.effect_noise(CANVAS_SIZE, 3)
    return Image.merge("RGB", (noise, noise, noise))


def rounded(image, radius):
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius, fill=255)
    result = image.copy()
    result.putalpha(ImageChops.multiply(result.getchannel("A"), mask))
    return result


def wrap_text(text, fnt, max_width, max_lines):
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if fnt.getlength(candidate) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while " " in last and fnt.getlength(last + "…") > max_width:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = last.rstrip(",.;:") + "…"
    return lines


def star_points(cx, cy, outer, inner):
    points = []
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = -math.pi / 2 + i * math.pi / 5
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def draw_title(draw, title):
    # Fallback when there is no logo: biggest size that fits in two lines
    for size in range(170, 89, -10):
        title_font = font("Bold", size)
        lines = wrap_text(title, title_font, CONTENT_WIDTH, 99)
        if len(lines) <= 2 and all(title_font.getlength(line) <= CONTENT_WIDTH for line in lines):
            break
    lines = wrap_text(title, title_font, CONTENT_WIDTH, 2)
    line_height = round(size * 1.08)
    y = LOGO_BOTTOM - line_height * len(lines)
    for line in lines:
        draw.text((MARGIN_LEFT - 6, y), line, font=title_font, fill="white")
        y += line_height


def draw_metadata(draw, rating, details):
    x = MARGIN_LEFT
    if rating:
        # Rating pill: star + score
        rating_font = font("Medium", 46)
        rating_text = f"{rating:.1f}"
        pad, star, gap, height = 24, 22, 14, 72
        width = pad + star * 2 + gap + round(rating_font.getlength(rating_text)) + pad
        top = META_CENTER - height // 2
        draw.rounded_rectangle((x, top, x + width, top + height), height // 2, fill=(255, 255, 255, 46))
        draw.polygon(star_points(x + pad + star, META_CENTER, star, star * 0.45), fill=(245, 197, 24, 255))
        draw.text((x + pad + star * 2 + gap, META_CENTER), rating_text, font=rating_font, fill="white", anchor="lm")
        x += width + 34
    meta_text = "   ·   ".join(part for part in details if part)
    draw.text((x, META_CENTER), meta_text, font=font("Medium", 48), fill=(230, 230, 230, 255), anchor="lm")


def draw_overview(draw, overview):
    overview_font = font("Regular", 48)
    line_height = 66
    y = META_CENTER + 36 + 52
    for line in wrap_text(overview, overview_font, CONTENT_WIDTH, OVERVIEW_LINES):
        draw.text((MARGIN_LEFT, y), line, font=overview_font, fill=(220, 220, 220, 255))
        y += line_height
    return y


def draw_providers(layer, draw, top, providers_logos, provider_text):
    center = top + PROVIDER_LOGO_HEIGHT // 2
    label_font = font("Light", 50)
    draw.text((MARGIN_LEFT, center), provider_text, font=label_font, fill=(205, 205, 205, 255), anchor="lm")
    x = MARGIN_LEFT + round(label_font.getlength(provider_text)) + 32

    if providers_logos:
        logos = [
            rounded(fit_resize(logo, PROVIDER_LOGO_HEIGHT, PROVIDER_LOGO_HEIGHT), 20)
            for logo in providers_logos[:4]
        ]
    else:
        tmdb_logo = Image.open(os.path.join(RESOURCES_DIR, "providers", "tmdblogo.png")).convert("RGBA")
        logos = [fit_resize(tmdb_logo, 400, 46)]

    for logo in logos:
        layer.alpha_composite(logo, (x, center - logo.height // 2))
        x += logo.width + 22


def process_image(
    backdrop_path,
    media,
    media_type,
    title,
    overview,
    genre,
    year,
    rating,
    providers_logos,
    provider_text,
    extra_info,
):
    # Download the background image
    try:
        response = session.get(f"{TMDB_IMAGE_URL}{backdrop_path}", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        backdrop = Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        print(f"Failed to download background for {title}: {e}")
        return

    # Full-bleed backdrop darkened with a gradient tinted by the image's own colour
    backdrop = cover_resize(backdrop, *CANVAS_SIZE)
    average = backdrop.resize((1, 1), Image.BOX).getpixel((0, 0))
    tint = tuple(round(6 + channel * 0.1) for channel in average)
    canvas = Image.composite(Image.new("RGB", CANVAS_SIZE, tint), backdrop, overlay_mask())
    canvas = ImageChops.add(canvas, dither_noise(), 1.0, -128).convert("RGBA")

    # Everything in the info block is drawn on its own layer to cast a soft shadow
    layer = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    logo_drawn = False
    logo_path = get_logo_fallback(media_type, media)
    if logo_path:
        try:
            logo_response = session.get(f"{TMDB_IMAGE_URL}{logo_path}", timeout=REQUEST_TIMEOUT)
            logo_response.raise_for_status()
            logo_image = fit_resize(Image.open(BytesIO(logo_response.content)).convert("RGBA"), *LOGO_MAX_SIZE)
            layer.alpha_composite(logo_image, (MARGIN_LEFT, LOGO_BOTTOM - logo_image.height))
            logo_drawn = True
        except Exception as e:
            print(f"Failed to draw logo for {title}: {e}")
    if not logo_drawn:
        draw_title(draw, title)

    draw_metadata(draw, rating, [str(year)[:4], extra_info, genre])
    overview_bottom = draw_overview(draw, overview)
    draw_providers(layer, draw, overview_bottom + 40, providers_logos, provider_text)

    shadow_alpha = layer.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda a: a * 0.6)
    shadow = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(layer)

    # Save the wallpaper
    filename = unique_path(background_dir, clean_filename(title), ".jpg")
    canvas.convert("RGB").save(
        filename, "JPEG", quality=JPEG_QUALITY, subsampling=0, optimize=True, progressive=True
    )
    print(f"Image saved: {filename}")


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
    except ValueError:
        return None


def get_country(media):
    country = media.get("origin_country") or ""
    if isinstance(country, list):
        country = country[0] if country else ""
    return country.lower()


def is_local_market(media):
    # Not in a mainstream language and without the votes of a worldwide hit
    return (
        media.get("original_language", "").lower() not in MAINSTREAM_LANGUAGES
        and media.get("vote_count", 0) < MIN_VOTES_OTHER_LANGUAGES
    )


# Filter criteria
def should_exclude_movie(movie):
    if is_local_market(movie):
        print(f"Excluding movie (local market): {movie['title']} [{movie.get('original_language')}, {movie.get('vote_count', 0)} votes]")
        return True

    # Check if the movie's country is in the excluded countries list
    country = get_country(movie)

    # Check if any genre in the movie matches the excluded genres list
    genres = [movie_genres.get(genre_id, "") for genre_id in movie.get("genre_ids", [])]

    # Fetch movie keywords
    movie_keywords = get_movie_keywords(movie["id"]) if EXCLUDED_KEYWORDS else []

    # Check release date
    release_date = parse_date(movie.get("release_date"))

    # Return True if excluded by country, genre, keywords, or release date
    if (
        country in MOVIE_EXCLUDED_COUNTRIES
        or any(genre in MOVIE_EXCLUDED_GENRES for genre in genres)
        or any(keyword in movie_keywords for keyword in EXCLUDED_KEYWORDS)
        or (release_date and release_date < MAX_AIR_DATE)
    ):
        print(f"Excluding movie: {movie['title']}")
        return True
    return False


def should_exclude_tvshow(tvshow):
    if is_local_market(tvshow):
        print(f"Excluding tvshow (local market): {tvshow['name']} [{tvshow.get('original_language')}, {tvshow.get('vote_count', 0)} votes]")
        return True

    # Check if the TV show's country is in the excluded countries list
    country = get_country(tvshow)

    # Check if any genre in the TV show matches the excluded genres list
    genres = [tv_genres.get(genre_id, "") for genre_id in tvshow.get("genre_ids", [])]

    # Fetch TV show keywords
    tv_keywords = get_tv_keywords(tvshow["id"]) if EXCLUDED_KEYWORDS else []

    # Check last air date
    last_air_date = parse_date(get_tv_show_details(tvshow["id"]).get("last_air_date"))

    # Return True if excluded by country, genre, keywords, or last air date
    if (
        country in TV_EXCLUDED_COUNTRIES
        or any(genre in TV_EXCLUDED_GENRES for genre in genres)
        or any(keyword in tv_keywords for keyword in EXCLUDED_KEYWORDS)
        or (last_air_date and last_air_date < MAX_AIR_DATE)
    ):
        print(f"Excluding tvshow: {tvshow['name']}")
        return True
    return False


def select_candidates(*result_lists, exclude, limit):
    # Merge lists without duplicates, sort by weighted rating (descending),
    # then apply the exclusion filters until the limit is reached
    unique = {}
    for results in result_lists:
        for item in results.get("results", []):
            unique.setdefault(item["id"], item)

    # Bayesian average: few votes pull the score towards a typical TMDB rating
    def weighted_rating(item):
        votes = item.get("vote_count", 0)
        return (votes * item.get("vote_average", 0) + RANKING_MIN_VOTES * RANKING_PRIOR) / (votes + RANKING_MIN_VOTES)

    ranked = sorted(unique.values(), key=weighted_rating, reverse=True)

    selected = []
    for item in ranked:
        if len(selected) >= limit:
            break
        if not exclude(item):
            selected.append(item)
    return selected


# Process each movie
movies = select_candidates(
    trending_movies, discover_movies, exclude=should_exclude_movie, limit=movies_max
)
for movie in movies:
    # Extract movie details
    title = movie["title"]
    rating = round(movie["vote_average"], 1)
    genre = genre_names(movie.get("genre_ids", []), movie_genres)
    print(f"Processing movie: {title} {rating}")

    # Fetch additional movie details and format duration as hours and minutes
    duration = get_movie_details(movie["id"]).get("runtime") or 0
    duration = f"{duration // 60}h {duration % 60}min" if duration else ""

    # Check if backdrop image is available
    backdrop_path = get_textless_backdrop("movie", movie)
    if not backdrop_path:
        print(f"No backdrop image found for {title}")
        continue

    # Get providers logos thanks to JustWatch
    providers_logos, provider_text = get_providers_logos("movie", movie["id"])

    process_image(
        backdrop_path,
        movie,
        "movie",
        title,
        overview=movie.get("overview", ""),
        genre=genre,
        year=movie.get("release_date", ""),
        rating=rating,
        providers_logos=providers_logos,
        provider_text=provider_text,
        extra_info=duration,
    )


# Process TV shows
tvshows = select_candidates(
    trending_tvshows, discover_tvshows, exclude=should_exclude_tvshow, limit=tvshows_max
)
for tvshow in tvshows:
    # Extract TV show details
    title = tvshow["name"][:58]
    rating = round(tvshow["vote_average"], 1)
    genre = genre_names(
        tvshow.get("genre_ids", []), tv_genres, TV_GENRE_TRANSLATIONS.get(LANGUAGE_CODE)
    )
    print(f"Processing TV show: {title} {rating}")

    # Fetch additional TV show details
    seasons = get_tv_show_details(tvshow["id"]).get("number_of_seasons", 0)
    seasons_text = f"{seasons} {SEASON_TEXT if seasons == 1 else SEASONS_TEXT}" if seasons else ""

    # Check if backdrop image is available
    backdrop_path = get_textless_backdrop("tv", tvshow)
    if not backdrop_path:
        print(f"No backdrop image found for {title}")
        continue

    # Get providers logos thanks to JustWatch
    providers_logos, provider_text = get_providers_logos("tv", tvshow["id"])

    process_image(
        backdrop_path,
        tvshow,
        "tv",
        title,
        overview=tvshow.get("overview", ""),
        genre=genre,
        year=tvshow.get("first_air_date", ""),
        rating=rating,
        providers_logos=providers_logos,
        provider_text=provider_text,
        extra_info=seasons_text,
    )


print("\n[DEBUG] Generating manifest JSON...")

github_user = "rfmarcos"
github_repo = "androidtvbackground-reddit"
branch = "main"

wallpapers_data = []

for filename in os.listdir(background_dir):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        title = os.path.splitext(filename)[0].replace('_', ' ')
        raw_url = f"https://raw.githubusercontent.com/{github_user}/{github_repo}/{branch}/{base_background_dir}/{LANGUAGE_SHORT}/{filename}"

        wallpapers_data.append({
            "title": f"Wallpaper: {title}",
            "url": raw_url
        })

json_path = f"wallpapers_{LANGUAGE_SHORT}.json"
with open(json_path, "w", encoding="utf-8") as json_file:
    json.dump(wallpapers_data, json_file, indent=4)

print(f"[DEBUG] File {json_path} generated correctly with {len(wallpapers_data)} images.")
