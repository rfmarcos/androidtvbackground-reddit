import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
from dotenv import load_dotenv
import shutil
import textwrap
from datetime import datetime, timedelta
from functools import lru_cache
import difflib

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

# Save font locally
truetype_url = (
    "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Light.ttf"
)
truetype_path = "Roboto-Light.ttf"
if not os.path.exists(truetype_path):
    try:
        response = requests.get(truetype_url, timeout=10)
        if response.status_code == 200:
            with open(truetype_path, "wb") as f:
                f.write(response.content)
            print("Roboto-Light font saved")
        else:
            print(
                f"Failed to download Roboto-Light font. Status code: {response.status_code}"
            )
    except Exception as e:
        print(f"An error occurred while downloading the Roboto-Light font: {e}")

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


# truncate
def truncate(overview, max_chars):
    if len(overview) > max_chars:
        return overview[: max_chars - 3]
    else:
        return overview


# resize image
def resize_image(image, height):
    ratio = height / image.height
    width = int(image.width * ratio)
    return image.resize((width, height))


def resize_logo(image, width, height):
    # Get the aspect ratio of the image
    aspect_ratio = image.width / image.height

    # Calculate new width and height to maintain aspect ratio
    new_width = width
    new_height = int(new_width / aspect_ratio)

    # If the calculated height is greater than the desired height,
    # recalculate the width to fit the desired height
    if new_height > height:
        new_height = height
        new_width = int(new_height * aspect_ratio)

    # Resize the image
    resized_img = image.resize((new_width, new_height))
    return resized_img


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


def get_providers_logos(media_type, media_id):
    providers = (
        tmdb_get(f"{media_type}/{media_id}/watch/providers")
        .get("results", {})
        .get(REGION, {})
        .get("flatrate", [])
    )

    providers.sort(key=lambda provider: provider.get("display_priority", 999))

    providers_logos = []

    for provider in providers:
        name = provider.get("provider_name")
        logo_file = name.lower().replace(' ', '') + '.png'
        try:
            img_path = os.path.join(os.path.dirname(__file__), f"resources/providers/{logo_file}")
            img = Image.open(img_path).convert("RGBA")
            providers_logos.append(img)
        except Exception as e:
            print(f"Error getting provider logo for {name}: {e}")

    if providers_logos:
        provider_text = AVAILABLE_ON_TEXT
    else:
        providers_logos.append(Image.open(os.path.join(os.path.dirname(__file__), "resources/providers/tmdblogo.png")).convert("RGBA"))
        provider_text = NOW_TRENDING_TEXT

    return providers_logos, provider_text


def process_image(
    image_url,
    media,
    media_type,
    title,
    overview,
    genre,
    year,
    rating,
    providers_logos,
    provider_text,
    duration=None,
    seasons=None,
):
    is_movie = media_type == "movie"
    # Download the background image
    try:
        response = session.get(image_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to download background for {title}: {e}")
        return

    # Open the image
    image = Image.open(BytesIO(response.content))

    # Resize the image to have a height of 1500 pixels while preserving aspect ratio
    image = resize_image(image, 1500)

    # Open overlay images
    bckg = Image.open(os.path.join(os.path.dirname(__file__), "bckg.png"))
    overlay = Image.open(os.path.join(os.path.dirname(__file__), "overlay.png"))

    # Paste images
    bckg.paste(image, (1175, 0))
    bckg.paste(overlay, (1175, 0), overlay)

    # Add title text with shadow
    draw = ImageDraw.Draw(bckg)

    # Text font
    font_title = ImageFont.truetype(truetype_path, size=190)
    font_overview = ImageFont.truetype(truetype_path, size=50)
    font_custom = ImageFont.truetype(truetype_path, size=60)

    # Text color
    shadow_color = "black"
    main_color = "white"
    overview_color = (150, 150, 150)  # Grey color for the summary
    metadata_color = "white"

    # Wrap overview text
    wrapped_overview = "\n".join(textwrap.wrap(overview, width=70, max_lines=OVERVIEW_LINES, placeholder="..."))
    line_height = font_overview.getbbox("A")[3]
    overview_height = (wrapped_overview.count("\n") + 1) * line_height

    # Text position
    title_position = (200, 420)
    overview_position = (210, 730)
    shadow_offset = 2
    info_position = (210, 650)  # Adjusted position for logo and info
    custom_position = (210, overview_position[1] + overview_height + 30)

    bbox = font_custom.getbbox(provider_text)
    provider_x_position = 210 + bbox[2] - bbox[0] + 20
    for provider_logo in providers_logos[:3]:
        bckg.paste(provider_logo, (provider_x_position, overview_position[1] + overview_height + 55), provider_logo)
        provider_x_position += provider_logo.width + 30

    # Draw Overview for info
    draw.text((overview_position[0] + shadow_offset, overview_position[1] + shadow_offset), wrapped_overview, font=font_overview, fill=shadow_color)
    draw.text(overview_position, wrapped_overview, font=font_overview, fill=metadata_color)

    # Determine genre text and additional info
    if is_movie:
        additional_info = f"{duration}"
    else:
        additional_info = f"{seasons} {SEASON_TEXT if seasons == 1 else SEASONS_TEXT}"

    rating_text = "TMDB: " + str(rating)
    year_text = truncate(str(year), 7)
    info_text = f"{genre}  •  {year_text}  •  {additional_info}  •  {rating_text}"

    # Draw metadata
    draw.text(
        (info_position[0] + shadow_offset, info_position[1] + shadow_offset),
        info_text,
        font=font_overview,
        fill=shadow_color,
    )
    draw.text(info_position, info_text, font=font_overview, fill=overview_color)

    # Get logo image URL
    logo_path = get_logo_fallback(media_type, media)

    logo_drawn = False  # Flag to track if logo is drawn

    if logo_path:
        try:
            logo_response = session.get(f"{TMDB_IMAGE_URL}{logo_path}", timeout=REQUEST_TIMEOUT)
            logo_response.raise_for_status()
            logo_image = Image.open(BytesIO(logo_response.content))
            # Resize the logo image to fit within a box while maintaining aspect ratio
            logo_image = resize_logo(logo_image, 1000, 500)
            logo_position = (
                210,
                info_position[1] - logo_image.height - 25,
            )  # Position for logo
            logo_image = logo_image.convert("RGBA")

            # Paste the logo onto the image
            bckg.paste(logo_image, logo_position, logo_image)
            logo_drawn = True  # Logo was successfully drawn
        except Exception as e:
            print(f"Failed to draw logo for {title}: {e}")

    if not logo_drawn:
        # Draw title text if logo is not available or failed to draw
        draw.text(
            (title_position[0] + shadow_offset, title_position[1] + shadow_offset),
            title,
            font=font_title,
            fill=shadow_color,
        )
        draw.text(title_position, title, font=font_title, fill=main_color)

    # Draw custom text
    draw.text(
        (custom_position[0] + shadow_offset, custom_position[1] + shadow_offset),
        provider_text,
        font=font_custom,
        fill=shadow_color,
    )
    draw.text(custom_position, provider_text, font=font_custom, fill=metadata_color)

    # Save the resized image
    filename = unique_path(background_dir, clean_filename(title), ".jpg")
    bckg = bckg.convert("RGB")
    bckg.save(filename)
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
    genre = ", ".join(movie_genres.get(genre_id, "") for genre_id in movie.get("genre_ids", []))
    print(f"Processing movie: {title} {rating}")

    # Fetch additional movie details
    duration = get_movie_details(movie["id"]).get("runtime") or 0

    # Format duration as hours and minutes
    if duration:
        duration = f"{duration // 60}h {duration % 60}min"
    else:
        duration = "N/A"

    # Check if backdrop image is available
    backdrop_path = movie.get("backdrop_path")
    if not backdrop_path:
        print(f"No backdrop image found for {title}")
        continue

    # Get providers logos thanks to JustWatch
    providers_logos, provider_text = get_providers_logos("movie", movie["id"])

    process_image(
        f"{TMDB_IMAGE_URL}{backdrop_path}",
        movie,
        "movie",
        title,
        overview=movie.get("overview", ""),
        genre=genre,
        year=movie.get("release_date", ""),
        rating=rating,
        providers_logos=providers_logos,
        provider_text=provider_text,
        duration=duration,
    )


# Process TV shows
tvshows = select_candidates(
    trending_tvshows, discover_tvshows, exclude=should_exclude_tvshow, limit=tvshows_max
)
for tvshow in tvshows:
    # Extract TV show details
    title = tvshow["name"][:58]
    rating = round(tvshow["vote_average"], 1)
    genre = ", ".join(tv_genres.get(genre_id, "") for genre_id in tvshow.get("genre_ids", []))
    print(f"Processing TV show: {title} {rating}")

    # Fetch additional TV show details
    seasons = get_tv_show_details(tvshow["id"]).get("number_of_seasons", 0)

    # Check if backdrop image is available
    backdrop_path = tvshow.get("backdrop_path")
    if not backdrop_path:
        print(f"No backdrop image found for {title}")
        continue

    # Get providers logos thanks to JustWatch
    providers_logos, provider_text = get_providers_logos("tv", tvshow["id"])

    process_image(
        f"{TMDB_IMAGE_URL}{backdrop_path}",
        tvshow,
        "tv",
        title,
        overview=tvshow.get("overview", ""),
        genre=genre,
        year=tvshow.get("first_air_date", ""),
        rating=rating,
        providers_logos=providers_logos,
        provider_text=provider_text,
        seasons=seasons,
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
