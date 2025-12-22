# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "google-genai>=1.56.0",
#     "google-api-python-client>=2.187.0",
#     "isodate>=0.7.2",
#     "youtube-transcript-api>=1.2.3"
# ]
# ///
# 
# Run as `uv run https://raw.githubusercontent.com/DoIT-Artifical-Intelligence/youtube-to-docs/refs/heads/main/main.py`
print("hello world")
import os

try:
    YOUTUBE_DATA_API_KEY = os.environ["YOUTUBE_DATA_API_KEY"]
except:
    YOUTUBE_DATA_API_KEY = None
print(YOUTUBE_DATA_API_KEY)
    
