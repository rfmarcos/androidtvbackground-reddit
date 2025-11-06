import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from io import BytesIO
import io
import os
from dotenv import load_dotenv
import shutil
from urllib.request import urlopen
import textwrap
from datetime import datetime, timedelta
import difflib

load_dotenv()

# If TMDB API Read Access Token key is not hardcoded, then load from environment variables
TMDB_TOKEN = os.getenv("TMDB_BEARER_TOKEN")

# Base URL for the API
TMDB_URL = "https://api.themoviedb.org/3/"

# Set your TMDB API Read Access Token key here
TMDB_HEADERS = {"accept": "application/json", "Authorization": f"Bearer {TMDB_TOKEN}"}

# TV Exclusion list - this filter will exclude Tv shows from chosen countries that have a specific genre
TV_EXCLUDED_COUNTRIES = []  # based on ISO 3166-1 alpha-2 codes, enter lowercase like ['cn','kr','jp','fr','us']
TV_EXCLUDED_GENRES = []  # like ['Animation']

# Movie Exclusion list - this filter will exclude movies from chosen countries that have a specific genre
MOVIE_EXCLUDED_COUNTRIES = []  # based on ISO 3166-1 alpha-2 codes, enter lowercase like ['cn','kr','jp','fr','us']
MOVIE_EXCLUDED_GENRES = []  # like ['Animation']

# Keyword exclusion list - this filter will exclude movies or tv shows that contain a specific keyword in their TMDB profile
EXCLUDED_KEYWORDS = ["adult"]  # like ['adult']

# Filter movies by release date and tv shows by last air date
MAX_AIR_DATE = (
    datetime.now() - timedelta(days=365)
)  # specify the number of days since the movie release or the tv show last air date, shows before this date will be excluded

# Allowed networks to show as image instead of tmdb (same name as in tmdb api)
ALLOWED_NETWORKS = {"Netflix", "HBO", "Prime Video", "Disney+"}

# Language
LANGUAGE = "es-ES"
LANGUAGE_SHORT = "es"
NOW_TRENDING_TEXT = "En tendencia en"
SEASON_TEXT = "Temporada"
SEASONS_TEXT = "Temporadas"

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
# Endpoint for trending shows
trending_movies_url = f"{TMDB_URL}trending/movie/week?language={LANGUAGE}"
trending_tvshows_url = f"{TMDB_URL}trending/tv/week?language={LANGUAGE}"

# Endpoint for discover shows
start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
end_date = datetime.now().strftime("%Y-%m-%d")
discover_movies_url = f"{TMDB_URL}discover/movie?sort_by=popularity.desc&language={LANGUAGE}&include_adult=false&page=1&with_release_type=4|5|6&include_video=false&vote_average.gte=1&vote_count.gte=50&with_runtime.gte=15&without_genres=99&release_date.gte={start_date}&release_date.lte={end_date}"
discover_tvshows_url = f"{TMDB_URL}discover/tv?sort_by=popularity.desc&language={LANGUAGE}&include_adult=false&page=1&vote_average.gte=1&vote_count.gte=50&with_runtime.gte=15&without_genres=99|16&first_air_date.gte={start_date}&first_air_date.lte={end_date}"

# Fetching trending movies
trending_movies_response = requests.get(trending_movies_url, headers=TMDB_HEADERS)
trending_movies = trending_movies_response.json()

# Fetching trending TV shows
trending_tvshows_response = requests.get(trending_tvshows_url, headers=TMDB_HEADERS)
trending_tvshows = trending_tvshows_response.json()

# Fetching discover movies
discover_movies_response = requests.get(discover_movies_url, headers=TMDB_HEADERS)
discover_movies = discover_movies_response.json()

# Fetching discover TV shows
discover_tvshows_response = requests.get(discover_tvshows_url, headers=TMDB_HEADERS)
discover_tvshows = discover_tvshows_response.json()

# Fetching genres for movies
genres_url = f"{TMDB_URL}genre/movie/list?language={LANGUAGE}"
genres_response = requests.get(genres_url, headers=TMDB_HEADERS)
genres_data = genres_response.json()
movie_genres = {genre["id"]: genre["name"] for genre in genres_data.get("genres", [])}

# Fetching genres for TV shows
genres_url = f"{TMDB_URL}genre/tv/list?language={LANGUAGE}"
genres_response = requests.get(genres_url, headers=TMDB_HEADERS)
genres_data = genres_response.json()
tv_genres = {genre["id"]: genre["name"] for genre in genres_data.get("genres", [])}


# Fetching TV show details
def get_tv_show_details(tv_id):
    tv_details_url = f"{TMDB_URL}tv/{tv_id}?language={LANGUAGE}"
    tv_details_response = requests.get(tv_details_url, headers=TMDB_HEADERS)
    return tv_details_response.json()


# Fetching movie details
def get_movie_details(movie_id):
    movie_details_url = f"{TMDB_URL}movie/{movie_id}?language={LANGUAGE}"
    movie_details_response = requests.get(movie_details_url, headers=TMDB_HEADERS)
    return movie_details_response.json()


# Function to fetch keywords for a movie
def get_movie_keywords(movie_id):
    keywords_url = f"{TMDB_URL}movie/{movie_id}/keywords"
    response = requests.get(keywords_url, headers=TMDB_HEADERS)
    if response.status_code == 200:
        # Extract and return the names of the keywords
        return [
            keyword["name"].lower() for keyword in response.json().get("keywords", [])
        ]
    return []


# Function to fetch keywords for a TV show
def get_tv_keywords(tv_id):
    keywords_url = f"{TMDB_URL}tv/{tv_id}/keywords"
    response = requests.get(keywords_url, headers=TMDB_HEADERS)
    if response.status_code == 200:
        return [
            keyword["name"].lower() for keyword in response.json().get("results", [])
        ]
    return []


# Create a directory to save the backgrounds and clear its contents if it exists
background_dir = "tmdb_backgrounds"
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


# truncate overview
def truncate_overview(overview, max_chars):
    if len(overview) > max_chars:
        return overview[:max_chars]
    else:
        return overview


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


# Fetch movie or TV show logo
def get_logo_fallback(media_type, media):
    if media_type=="movie":
        name = media["title"]
        original = media["original_title"]
    else:
        name  = media["name"]
        original = media["original_name"]

    if similarity(name, original) > 0.9:
        logo = get_multilogo(media_type, media["id"], original_language=media["original_language"])
    else:
        logo = get_logo(media_type, media["id"], LANGUAGE_SHORT)

    if logo is None and media["original_language"] != "en":
        details_url = f"{TMDB_URL}{media_type}/{media['id']}?language=en-US"
        details_response = requests.get(details_url, headers=TMDB_HEADERS)
        details_data = details_response.json()

        if media_type=="movie":
            english_name = details_data["title"]
        else:
            english_name = details_data["name"]

        if similarity(name, english_name) > 0.9:
            logo = get_logo(media_type, media["id"], "en")

    return logo

def get_logo(media_type, media_id, language):
    logo_url = f"{TMDB_URL}{media_type}/{media_id}/images?language={language}"
    logo_response = requests.get(logo_url, headers=TMDB_HEADERS)
    if logo_response.status_code == 200:
        logos = logo_response.json().get("logos", [])
        for logo in logos:
            if logo["iso_639_1"] == language and logo["file_path"].endswith(
                ".png"
            ):
                return logo["file_path"]
    return None

def get_multilogo(media_type, media_id, original_language):
    logo_url = f"{TMDB_URL}{media_type}/{media_id}/images?include_image_language={LANGUAGE_SHORT},{original_language}"
    logo_response = requests.get(logo_url, headers=TMDB_HEADERS)
    
    logos = logo_response.json().get("logos", [])
    valid_logos = [logo for logo in logos if logo["file_path"].endswith(".png")]
                
    for valid_logo in valid_logos:
        if valid_logo["iso_639_1"] == LANGUAGE_SHORT:
            return valid_logo["file_path"]

    for valid_logo in valid_logos:
        if valid_logo["iso_639_1"] == original_language:
            return valid_logo["file_path"]
    
    return None

def similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

def process_image(
    image_url, title, is_movie, genre, year, rating, duration=None, seasons=None
):
    # Download the background image with a timeout of 10 seconds
    response = requests.get(image_url, timeout=10)
    if response.status_code == 200:
        # Open the image
        image = Image.open(BytesIO(response.content))

        # Resize the image to have a width of 1500 pixels while preserving aspect ratio
        image = resize_image(image, 1500)

        # Open overlay images
        bckg = Image.open(os.path.join(os.path.dirname(__file__), "bckg.png"))
        overlay = Image.open(os.path.join(os.path.dirname(__file__), "overlay.png"))

        try:
            if network_image_url and network_image_url.startswith("http"):
                response = requests.get(network_image_url, timeout=10)
                response.raise_for_status()
                networklogo = resize_image(Image.open(io.BytesIO(response.content)), 41)
                networklogo = networklogo.convert("RGBA")
            else:
                networklogo = Image.open(os.path.join(os.path.dirname(__file__), "tmdblogo.png"))
        except Exception:
            networklogo = Image.open(os.path.join(os.path.dirname(__file__), "tmdblogo.png"))

        # Paste images
        bckg.paste(image, (1175, 0))
        bckg.paste(overlay, (1175, 0), overlay)
        bckg.paste(networklogo, (680, 890), networklogo)

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

        # Text position
        title_position = (200, 420)
        overview_position = (210, 730)
        shadow_offset = 2
        info_position = (210, 650)  # Adjusted position for logo and info
        custom_position = (210, 870)

        # Wrap overview text
        wrapped_overview = "\n".join(textwrap.wrap(overview, width=70, max_lines=2, placeholder=" ..."))

        # Draw Overview for info
        draw.text((overview_position[0] + shadow_offset, overview_position[1] + shadow_offset), wrapped_overview, font=font_overview, fill=shadow_color)
        draw.text(overview_position, wrapped_overview, font=font_overview, fill=metadata_color)

        # Determine genre text and additional info
        if is_movie:
            genre_text = genre
            additional_info = f"{duration}"
        else:
            genre_text = genre
            additional_info = f"{seasons} {SEASON_TEXT if seasons == 1 else SEASONS_TEXT}"

        rating_text = "TMDB: " + str(rating)
        year_text = truncate(str(year), 7)
        info_text = f"{genre_text}  \u2022  {year_text}  \u2022  {additional_info}  \u2022  {rating_text}"

        # Draw metadata
        draw.text(
            (info_position[0] + shadow_offset, info_position[1] + shadow_offset),
            info_text,
            font=font_overview,
            fill=shadow_color,
        )
        draw.text(info_position, info_text, font=font_overview, fill=overview_color)

        # Get logo image URL
        if is_movie:
            logo_path = get_logo_fallback("movie", movie)
        else:
            logo_path = get_logo_fallback("tv", tvshow)

        logo_drawn = False  # Flag to track if logo is drawn

        if logo_path:
            logo_url = f"https://image.tmdb.org/t/p/original{logo_path}"
            logo_response = requests.get(logo_url)
            if logo_response.status_code == 200:
                try:
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
            NOW_TRENDING_TEXT,
            font=font_custom,
            fill=shadow_color,
        )
        draw.text(custom_position, NOW_TRENDING_TEXT, font=font_custom, fill=metadata_color)

        # Save the resized image
        filename = os.path.join(background_dir, f"{clean_filename(title)}.jpg")
        bckg = bckg.convert("RGB")
        bckg.save(filename)
        print(f"Image saved: {filename}")
    else:
        print(f"Failed to download background for {title}")


# Filter criteria
def should_exclude_movie(
    movie,
):
    # Check if the movie's country is in the excluded countries list
    country = movie.get("origin_country", "").lower()

    # Check if any genre in the movie matches the excluded genres list
    genres = [movie_genres.get(genre_id, "") for genre_id in movie.get("genre_ids", [])]

    # Fetch movie keywords
    movie_keywords = get_movie_keywords(movie["id"]) if EXCLUDED_KEYWORDS else []

    # Check release date
    release_date_str = movie.get("release_date")
    release_date = (
        datetime.strptime(release_date_str, "%Y-%m-%d") if release_date_str else None
    )

    # Return True if excluded by country, genre, keywords, or release date
    if (
        country in MOVIE_EXCLUDED_COUNTRIES
        or any(genre in MOVIE_EXCLUDED_GENRES for genre in genres)
        or any(keyword in movie_keywords for keyword in EXCLUDED_KEYWORDS)
        or (release_date and release_date < MAX_AIR_DATE)
    ):
        return True
    return False


def should_exclude_tvshow(
    tvshow,
):
    # Check if the TV show's country is in the excluded countries list
    country = tvshow.get("origin_country", [""])[0].lower()

    # Check if any genre in the TV show matches the excluded genres list
    genres = [tv_genres.get(genre_id, "") for genre_id in tvshow.get("genre_ids", [])]

    # Fetch TV show keywords
    tv_keywords = get_tv_keywords(tvshow["id"]) if EXCLUDED_KEYWORDS else []

    # Check next episode to air date
    last_air_date_str = get_tv_show_details(tvshow["id"]).get("last_air_date")
    last_air_date = (
        datetime.strptime(last_air_date_str, "%Y-%m-%d") if last_air_date_str else None
    )

    # Return True if excluded by country, genre, keywords, or next episode air date
    if (
        country in TV_EXCLUDED_COUNTRIES
        or any(genre in TV_EXCLUDED_GENRES for genre in genres)
        or any(keyword in tv_keywords for keyword in EXCLUDED_KEYWORDS)
        or (last_air_date and last_air_date < MAX_AIR_DATE)
    ):
        return True
    return False


# Process each movie
movies = trending_movies.get("results", []) + discover_movies.get("results", [])
# Sort movies by rating (descending)
movies = sorted(movies, key=lambda m: m.get("vote_average", 0), reverse=True)

# Limit to movies_max
movies = movies[:movies_max]
for movie in movies:
    title = movie["title"]
    if should_exclude_movie(movie):
        continue

    # Extract movie details
    title = movie["title"]
    overview = movie["overview"]
    year = movie["release_date"]
    rating = round(movie["vote_average"], 1)

    genre = ", ".join([movie_genres[genre_id] for genre_id in movie["genre_ids"]])
    print(f"Processing movie: {title} {rating}")
    # Fetch additional movie details
    movie_details = get_movie_details(movie["id"])
    duration = movie_details.get("runtime", 0)

    # Format duration as hours and minutes
    if duration:
        hours = duration // 60
        minutes = duration % 60
        duration = f"{hours}h {minutes}min"
    else:
        duration = "N/A"

    # Check if backdrop image is available
    backdrop_path = movie["backdrop_path"]
    if backdrop_path:
        # Construct image URL
        image_url = f"https://image.tmdb.org/t/p/original{backdrop_path}"
        # Process the image
        process_image(
            image_url,
            title,
            is_movie=True,
            genre=genre,
            year=year,
            rating=rating,
            duration=duration,
        )
    else:
        # Print error message if no backdrop image found
        print(f"No backdrop image found for {title}")


# Process TV shows
tvshows = trending_tvshows.get("results", []) + discover_tvshows.get("results", [])
# Sort TV shows by rating (descending)
tvshows = sorted(tvshows, key=lambda t: t.get("vote_average", 0), reverse=True)

# Limit to tvshows_max
tvshows = tvshows[:tvshows_max]
for tvshow in tvshows:
    if should_exclude_tvshow(tvshow):
        continue

    # Extract TV show details
    title = truncate_overview(tvshow["name"], 58)
    overview = tvshow["overview"]
    year = tvshow["first_air_date"]
    rating = round(tvshow["vote_average"], 1)
    
    genre = ", ".join([tv_genres[genre_id] for genre_id in tvshow["genre_ids"]])
    print(f"Processing TV show: {title} {rating}")
    # Fetch additional TV show details
    tv_details = get_tv_show_details(tvshow["id"])
    seasons = tv_details.get("number_of_seasons", 0)

    # Get network logo URL or fallback
    # TODO query watchmode API, for better results, should also work with movies
    network_image_url = None
    networks = tv_details.get("networks", [])
    for network in networks:
        name = network.get("name")
        logo_path = network.get("logo_path")
        if name in ALLOWED_NETWORKS and logo_path:
            network_image_url = f"https://image.tmdb.org/t/p/original{logo_path}"
            break

    # Check if backdrop image is available
    backdrop_path = tvshow["backdrop_path"]
    if backdrop_path:
        # Construct image URL
        image_url = f"https://image.tmdb.org/t/p/original{backdrop_path}"

        # Process the image
        process_image(
            image_url,
            title,
            is_movie=False,
            genre=genre,
            year=year,
            rating=rating,
            seasons=seasons,
        )
    else:
        # Print error message if no backdrop image found
        print(f"No backdrop image found for {title}")
