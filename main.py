# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "google-auth>=2.45.0",
#     "google-genai>=1.56.0",
#     "google-api-python-client>=2.187.0",
#     "isodate>=0.7.2",
#     "openai>=1.56.0",
#     "polars>=1.36.1",
#     "requests>=2.32.5",
#     "youtube-transcript-api>=1.2.3"
# ]
# ///
#
# Run as:
# uv run https://raw.githubusercontent.com/DoIT-Artifical-Intelligence/youtube-to-docs/refs/heads/main/main.py -- @mga-hgo1740 --model gemini-2.0-flash-exp
# To test locally run one of:
# uv run main.py --model gemini-3-flash-preview
# uv run main.py --model vertex-claude-haiku-4-5@20251001
# uv run main.py --model bedrock-claude-haiku-4-5-20251001-v1
# uv run main.py --model bedrock-nova-2-lite-v1
# uv run main.py --model bedrock-claude-haiku-4-5-20251001
# uv run main.py --model foundry-gpt-5-mini


import os
import argparse
import sys
import time
import re
import requests
import isodate
import polars as pl
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi

ytt_api = YouTubeTranscriptApi()

try:
    YOUTUBE_DATA_API_KEY = os.environ["YOUTUBE_DATA_API_KEY"]
    youtube_service = build("youtube", "v3", developerKey=YOUTUBE_DATA_API_KEY)
except KeyError:
    YOUTUBE_DATA_API_KEY = None
    youtube_service = None
    print(
        "Warning: YOUTUBE_DATA_API_KEY not found. Playlist and Channel expansion will fail."
    )

parser = argparse.ArgumentParser()
parser.add_argument(
    "video_id",
    nargs="?",
    default="KuPc06JgI_A",
    help=(
        "Can be one of: \n"
        "A Video ID e.g. 'KuPc06JgI_A'\n"
        "Playlist ID (starts with PL e.g. 'PL8ZxoInteClyHaiReuOHpv6Z4SPrXtYtW')\n"
        "Channel Handle (starts with @ e.g. '@mga-hgo1740')\n"
        "Comma-separated list of Video IDs. (e.g. 'KuPc06JgI_A,GalhDyf3F8g')"
    ),
)
parser.add_argument(
    "-o",
    "--outfile",
    default="youtube-docs.csv",
    help=("Can be one of: \nLocal file path to save the output CSV file."),
)
parser.add_argument(
    "-m",
    "--model",
    default=None,
    help=(
        "The LLM to use for summarization. Can be one of: \n"
        "Gemini model (e.g., 'gemini-3-flash-preview')\n"
        "GCP Vertex model (prefixed with 'vertex-'). e.g. 'vertex-claude-haiku-4-5@20251001'\n"
        "AWS Bedrock model (prefixed with 'bedrock-'). e.g. 'bedrock-claude-haiku-4-5-20251001-v1'\n"
        "Azure Foundry model (prefix with 'foundry-). e.g. 'foundry-gpt-5-mini'\n"
        "Defaults to None."
    ),
)

args = parser.parse_args()
video_id = args.video_id
outfile = args.outfile
model_name = args.model

if model_name:
    if model_name.startswith("gemini"):
        try:
            GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
            google_genai_client = genai.Client(api_key=GEMINI_API_KEY)
        except KeyError:
            print("Error: GEMINI_API_KEY not found")
            sys.exit(1)
    elif model_name.startswith("vertex"):
        # Setup for Raw Requests to Vertex
        try:
            vertex_project_id = os.environ["PROJECT_ID"]
            # Get default Google credentials (e.g. from gcloud auth application-default login)
            vertex_credentials, _ = google.auth.default()
        except KeyError:
            print(
                "Error: PROJECT_ID environment variable required for GCPVertex models."
            )
            sys.exit(1)
        except Exception as e:
            print(f"Error getting Google Credentials: {e}")
            sys.exit(1)
    elif model_name.startswith("bedrock"):
        try:
            aws_bearer_token_bedrock = os.environ["AWS_BEARER_TOKEN_BEDROCK"]
        except KeyError:
            print(
                "Error: AWS_BEARER_TOKEN_BEDROCK environment variable required for AWS Bedrock models."
            )
            sys.exit(1)
    elif model_name.startswith("foundry"):
        try:
            AZURE_FOUNDRY_ENDPOINT = os.environ["AZURE_FOUNDRY_ENDPOINT"]
            AZURE_FOUNDRY_API_KEY = os.environ["AZURE_FOUNDRY_API_KEY"]
        except KeyError:
            print(
                "Error: AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY environment variables required for Azure Foundry models."
            )
            sys.exit(1)

# Handle Channel Handles (e.g. @channelname)
if video_id.startswith("@"):
    if not youtube_service:
        print("Error: YOUTUBE_DATA_API_KEY is required to resolve channel handles.")
        sys.exit(1)
    print(f"Resolving channel handle: {video_id}...")
    request = youtube_service.channels().list(part="contentDetails", forHandle=video_id)
    response = request.execute()
    if not response["items"]:
        print(f"Error: No channel found for handle {video_id}")
        sys.exit(1)
    # Get the 'uploads' playlist ID from the channel details
    # This playlist usually starts with 'UU' and contains all channel videos
    video_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"Found uploads playlist: {video_id}")
video_ids = []
# Single video (standard ID length is 11)
if len(video_id) == 11 and "," not in video_id:
    video_ids = [video_id]
# List of videos
elif "," in video_id:
    video_ids = video_id.split(",")
# Playlist (Standard 'PL' or Uploads 'UU')
elif video_id.startswith("PL") or video_id.startswith("UU"):
    if not youtube_service:
        print("Error: YOUTUBE_DATA_API_KEY is required for playlists.")
        sys.exit(1)
    request = youtube_service.playlistItems().list(
        part="contentDetails", playlistId=video_id, maxResults=50
    )
    while request:
        response = request.execute()
        for item in response["items"]:
            video_ids.append(item["contentDetails"]["videoId"])
        request = youtube_service.playlistItems().list_next(request, response)

# Setup Output Directories
transcripts_dir = None
summaries_dir = None
if outfile.endswith(".csv"):
    output_dir = os.path.dirname(outfile)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    base_dir = output_dir if output_dir else "."
    transcripts_dir = os.path.join(base_dir, "transcript-files")
    summaries_dir = os.path.join(base_dir, "summary-files")
    os.makedirs(transcripts_dir, exist_ok=True)
    os.makedirs(summaries_dir, exist_ok=True)

print(f"Processing {len(video_ids)} videos.")
print(f"Processing Videos: {video_ids}")

print(f"Saving to: {outfile}")
if model_name:
    print(f"Summarizing using model: {model_name}")

data = []
for video_id in video_ids:
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Processing Video URL: {url}")
    if youtube_service:
        request = youtube_service.videos().list(
            part="snippet,contentDetails", id=video_id
        )
        response = request.execute()
        if response["items"]:
            snippet = response["items"][0]["snippet"]
            video_title = snippet["title"]
            description = snippet["description"]
            publishedAt = snippet["publishedAt"]
            channelTitle = snippet["channelTitle"]
            tags = ", ".join(snippet.get("tags", []))
            iso_duration = response["items"][0]["contentDetails"]["duration"]
            video_duration = str(isodate.parse_duration(iso_duration))
        else:
            # Handle case where video ID might be invalid or deleted
            print(f"Warning: No details found for video ID {video_id}")
            continue
    else:
        video_title, description, publishedAt, channelTitle, tags, video_duration = (
            "" for _ in range(6)
        )

    # Fetch Transcript
    try:
        transcript_obj = ytt_api.fetch(video_id, languages=("en", "en-US"))
        transcript_data = transcript_obj.to_raw_data()
        transcript = " ".join([t["text"] for t in transcript_data])
    except Exception as e:
        print(f"Error fetching transcript for {video_id}: {e}")
        continue

    # Save Transcript
    safe_title = (
        re.sub(r'[\\/*?:"<>|]', "_", video_title).replace("\n", " ").replace("\r", "")
    )
    transcript_full_path = ""
    if transcripts_dir:
        transcript_filename = f"{video_id} - {safe_title}.txt"
        transcript_full_path = os.path.abspath(
            os.path.join(transcripts_dir, transcript_filename)
        )
        try:
            with open(transcript_full_path, "w", encoding="utf-8") as f:
                f.write(transcript)
            print(f"Saved transcript: {transcript_filename}")
        except OSError as e:
            print(f"Error writing transcript: {e}")

    # Summarize using AI
    summary_text = ""
    if model_name:
        print(f"Summarizing using model: {model_name}")
        prompt = (
            f"I have included a transcript for {url} ({video_title})"
            "\n\n"
            "Can you please summarize this?"
            "\n\n"
            f"{transcript}"
        )
        # Gemini
        if model_name.startswith("gemini"):
            try:
                response = google_genai_client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Content(
                            role="user", parts=[types.Part.from_text(text=prompt)]
                        )
                    ],
                )
                summary_text = response.text
            except Exception as e:
                print(f"Gemini API Error: {e}")
                summary_text = f"Error: {e}"
        # GCP Vertex
        elif model_name.startswith("vertex"):
            actual_model_name = model_name.replace("vertex-", "")
            if actual_model_name.startswith("claude"):
                try:
                    if vertex_credentials.expired:
                        vertex_credentials.refresh(GoogleAuthRequest())
                    access_token = vertex_credentials.token
                    endpoint = (
                        "https://us-east5-aiplatform.googleapis.com/v1/"
                        f"projects/{vertex_project_id}/locations/us-east5/"
                        f"publishers/anthropic/models/{actual_model_name}:rawPredict"
                    )
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json; charset=utf-8",
                    }
                    payload = {
                        "anthropic_version": "vertex-2023-10-16",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 64_000,
                        "stream": False,
                    }
                    response = requests.post(endpoint, headers=headers, json=payload)
                    if response.status_code == 200:
                        response_json = response.json()
                        # Parse Claude Response
                        content_blocks = response_json.get("content", [])
                        if (
                            content_blocks
                            and isinstance(content_blocks, list)
                            and "text" in content_blocks[0]
                        ):
                            summary_text = content_blocks[0]["text"]
                        else:
                            summary_text = (
                                f"Unexpected response format: {response.text}"
                            )
                    else:
                        summary_text = (
                            f"Vertex API Error {response.status_code}: {response.text}"
                        )
                        print(summary_text)
                except Exception as e:
                    print(f"Vertex Request Error: {e}")
                    summary_text = f"Error: {e}"
        # AWS Bedrock
        elif model_name.startswith("bedrock"):
            actual_model_name = model_name.replace("bedrock-", "")
            if actual_model_name.startswith("claude"):
                actual_model_name = f"us.anthropic.{actual_model_name}:0"
            elif actual_model_name.startswith("nova"):
                actual_model_name = f"us.amazon.{actual_model_name}:0"
            try:
                endpoint = (
                    f"https://bedrock-runtime.us-east-1.amazonaws.com/model/"
                    f"{actual_model_name}/converse"
                )
                response = requests.post(
                    endpoint,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {aws_bearer_token_bedrock}",
                    },
                    json={
                        "messages": [
                            {
                                "role": "user",
                                "content": [{"text": prompt}],
                            }
                        ],
                        "max_tokens": 64_000,
                    },
                )
                if response.status_code == 200:
                    response_json = response.json()
                    print(response_json)
                    try:
                        content_blocks = response_json["output"]["message"]["content"]
                        if (
                            content_blocks
                            and isinstance(content_blocks, list)
                            and "text" in content_blocks[0]
                        ):
                            summary_text = content_blocks[0]["text"]
                        else:
                            summary_text = f"Unexpected content format: {response_json}"
                    except KeyError:
                        summary_text = f"Unexpected response structure: {response_json}"
                else:
                    summary_text = (
                        f"Bedrock API Error {response.status_code}: {response.text}"
                    )
                    print(summary_text)
            except Exception as e:
                print(f"Bedrock Request Error: {e}")
                summary_text = f"Error: {e}"
        # Azure Foundry
        elif model_name.startswith("foundry"):
            actual_model_name = model_name.replace("foundry-", "")
            client = OpenAI(
                base_url=AZURE_FOUNDRY_ENDPOINT, api_key=AZURE_FOUNDRY_API_KEY
            )
            try:
                completion = client.chat.completions.create(
                    model=actual_model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )
                summary_text = completion.choices[0].message.content
            except Exception as e:
                print(f"Foundry Request Error: {e}")
                summary_text = f"Error: {e}"

    summary_full_path = ""
    if summaries_dir and summary_text:
        summary_filename = f"{model_name} - {video_id} - {safe_title} - summary.md"
        summary_full_path = os.path.abspath(
            os.path.join(summaries_dir, summary_filename)
        )
        try:
            with open(summary_full_path, "w", encoding="utf-8") as f:
                f.write(summary_text)
            print(f"Saved summary: {summary_filename}")
        except OSError as e:
            print(f"Error writing summary: {e}")

    print(f"Video Title: {video_title}")
    print(f"Description: {description}")
    print(f"Published At: {publishedAt}")
    print(f"Channel Title: {channelTitle}")
    print(f"Tags: {tags}")
    print(f"Video Duration: {video_duration}")
    print(f"Number of Transcript characters: {len(transcript)}")

    row = {
        "URL": url,
        "Title": video_title,
        "Description": description,
        "Data Published": publishedAt,
        "Channel": channelTitle,
        "Tags": tags,
        "Duration": video_duration,
        "Transcript characters": len(transcript),
        "Transcript File": transcript_full_path,
        "Summary File": summary_full_path,
        f"Summary Text {model_name}" if model_name else "Summary Text": summary_text,
    }
    data.append(row)
    time.sleep(1)

df = pl.DataFrame(data)
df.write_csv(outfile)
print(f"Successfully wrote {len(df)} rows to {outfile}")
