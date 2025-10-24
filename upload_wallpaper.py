import os
import praw
from datetime import datetime, timedelta

# Metadata file to track uploaded images
metadata_file = "uploaded_wallpapers.txt"

# Load previously uploaded image filenames
if os.path.exists(metadata_file):
    with open(metadata_file, "r") as f:
        uploaded_images = set(f.read().splitlines())
    print(f"[DEBUG] Loaded {len(uploaded_images)} previously uploaded images.")  # <-- log
else:
    uploaded_images = set()
    print("[DEBUG] No metadata file found. Starting fresh.")  # <-- log

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
wallpapers_dirs = ["plex_backgrounds", "tmdb_backgrounds"]

# Time limit for deleting old posts (2 weeks)
time_limit = timedelta(weeks=2)
current_time = datetime.utcnow()

# Delete old posts
print("[DEBUG] Checking old posts for deletion...")  # <-- log
for submission in subreddit.new(limit=None):
    print(f"[DEBUG] Deleting post: {submission.title} (Posted: {submission.created_utc})")  # <-- log
    # Calculate the age of the submission
    post_age = current_time - datetime.utcfromtimestamp(submission.created_utc)
    
    # Skip if the post is not an image or doesn't match your tracking criteria
    if post_age > time_limit and submission.title.startswith("Wallpaper:") and "PLEX" not in submission.title.upper():
        # Try to delete the post
        try:
            # Remove "Wallpaper: " prefix to get the original filename
            filename = submission.title.replace("Wallpaper: ", "").strip()
            
            if filename in uploaded_images:
                print(f"Deleting post: {submission.title} (Posted on: {submission.created_utc})")
                submission.delete()
                print(f"Deleted post: {submission.title}")
                
                # Remove the entry from the uploaded images set and the metadata file
                uploaded_images.remove(filename)
        except Exception as e:
            print(f"Failed to delete post {submission.title}: {e}")

# Write back the updated uploaded images to the metadata file
with open(metadata_file, "w") as f:
    for img in uploaded_images:
        f.write(f"{img}\n")

# Upload new wallpapers
print("[DEBUG] Starting upload of new wallpapers...")  # <-- log
for wallpapers_dir in wallpapers_dirs:
    if os.path.exists(wallpapers_dir):
        for filename in os.listdir(wallpapers_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                # Check if the image has already been uploaded
                if filename in uploaded_images:
                    print(f"Skipping {filename}, already uploaded.")
                    continue

                file_path = os.path.join(wallpapers_dir, filename)
                print(f"Uploading {filename} to subreddit...")

                # Submit the image to the subreddit
                try:
                    subreddit.submit_image(title=f"Wallpaper: {filename}", image_path=file_path)
                    print(f"Successfully uploaded {filename}.")
                    
                    # Add the image name to the metadata file
                    with open(metadata_file, "a") as f:
                        f.write(f"{filename}\n")

                    # Add to uploaded set to prevent processing during the current run
                    uploaded_images.add(filename)
                except Exception as e:
                    print(f"Failed to upload {filename}: {e}")
