import os
from dotenv import load_dotenv
import praw
from datetime import datetime, timedelta

load_dotenv()

# Initialize the Reddit instance
reddit = praw.Reddit(
    client_id=os.getenv('CLIENT_ID'),
    client_secret=os.getenv('CLIENT_SECRET'),
    refresh_token=os.getenv('REFRESH_TOKEN'),
    user_agent='Wallpaper Posting Bot v1.0'
)

# Subreddit you want to post to
subreddit = reddit.subreddit(os.getenv('SUBREDDIT'))

# Directories where wallpapers are stored
wallpapers_dirs = ["tmdb_backgrounds"]

# Current UTC time
current_time = datetime.utcnow()

# Delete all existing wallpapers in subreddit
print("[DEBUG] Deleting all existing wallpapers...")
for submission in subreddit.new(limit=None):
    if submission.title.startswith("Wallpaper:"):
        try:
            print(f"Deleting post: {submission.title} (Posted: {submission.created_utc})")
            submission.delete()
            print(f"Deleted post: {submission.title}")
        except Exception as e:
            print(f"Failed to delete post {submission.title}: {e}")

# Upload all wallpapers
print("[DEBUG] Uploading all wallpapers...")
for wallpapers_dir in wallpapers_dirs:
    if os.path.exists(wallpapers_dir):
        for filename in os.listdir(wallpapers_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                file_path = os.path.join(wallpapers_dir, filename)
                title = os.path.splitext(filename)[0]
                title = title.replace('_', ' ')
                title = f"Wallpaper: {title}"
                print(f"Uploading {filename} to subreddit...")
                try:
                    subreddit.submit_image(title=title, image_path=file_path)
                    print(f"Successfully uploaded {title}.")
                except Exception as e:
                    print(f"Failed to upload {filename}: {e}")