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
# uv run https://raw.githubusercontent.com/DoIT-Artifical-Intelligence/youtube-to-docs/refs/heads/main/main.py -- @mga-hgo1740 --model gemini-3-flash-preview  # noqa
# To test locally run one of:
# uv run main.py --model gemini-3-flash-preview
# uv run main.py --model vertex-claude-haiku-4-5@20251001
# uv run main.py --model bedrock-claude-haiku-4-5-20251001-v1
# uv run main.py --model bedrock-nova-2-lite-v1
# uv run main.py --model bedrock-claude-haiku-4-5-20251001
# uv run main.py --model foundry-gpt-5-mini


import argparse
import os
import re
import sys
import time
from typing import Any, List, Optional, Tuple, cast

import google.auth
import isodate
import polars as pl
import requests
from google import genai
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.genai import types
from googleapiclient.discovery import Resource, build
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi

# Global instance for transcript API
ytt_api = YouTubeTranscriptApi()


def get_youtube_service() -> Optional[Resource]:
    """Builds and returns the YouTube Data API service."""
    try:
        api_key = os.environ["YOUTUBE_DATA_API_KEY"]
        return build("youtube", "v3", developerKey=api_key)
    except KeyError:
        print(
            "Warning: YOUTUBE_DATA_API_KEY not found. Playlist and Channel expansion "
            "will fail."
        )
        return None


def resolve_video_ids(
    video_id_input: str, youtube_service: Optional[Resource]
) -> List[str]:
    """
    Resolves the input (video ID, list, playlist, or channel handle)
    into a list of video IDs.
    """
    video_ids: List[str] = []

    # Handle Channel Handles (e.g. @channelname)
    if video_id_input.startswith("@"):
        if not youtube_service:
            print("Error: YOUTUBE_DATA_API_KEY is required to resolve channel handles.")
            sys.exit(1)
        service = cast(Any, youtube_service)
        print(f"Resolving channel handle: {video_id_input}...")
        request = service.channels().list(
            part="contentDetails", forHandle=video_id_input
        )
        response = request.execute()
        if not response["items"]:
            print(f"Error: No channel found for handle {video_id_input}")
            sys.exit(1)
        # Get the 'uploads' playlist ID from the channel details
        video_id_input = response["items"][0]["contentDetails"]["relatedPlaylists"][
            "uploads"
        ]
        print(f"Found uploads playlist: {video_id_input}")

    # Single video (standard ID length is 11)
    if len(video_id_input) == 11 and "," not in video_id_input:
        video_ids = [video_id_input]
    # List of videos
    elif "," in video_id_input:
        video_ids = video_id_input.split(",")
    # Playlist (Standard 'PL' or Uploads 'UU')
    elif video_id_input.startswith("PL") or video_id_input.startswith("UU"):
        if not youtube_service:
            print("Error: YOUTUBE_DATA_API_KEY is required for playlists.")
            sys.exit(1)
        service = cast(Any, youtube_service)
        request = service.playlistItems().list(
            part="contentDetails", playlistId=video_id_input, maxResults=50
        )
        while request:
            response = request.execute()
            for item in response["items"]:
                video_ids.append(item["contentDetails"]["videoId"])
            request = service.playlistItems().list_next(request, response)

    return video_ids


def get_video_details(
    video_id: str, youtube_service: Optional[Resource]
) -> Optional[Tuple[str, str, str, str, str, str, str]]:
    """
    Fetches video metadata from YouTube Data API.
    Returns a tuple of (video_title, description, publishedAt,
    channelTitle, tags, video_duration, url).
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    if not youtube_service:
        return "", "", "", "", "", "", url

    service = cast(Any, youtube_service)
    request = service.videos().list(part="snippet,contentDetails", id=video_id)
    response = request.execute()

    if response["items"]:
        snippet = response["items"][0]["snippet"]
        video_title: str = snippet["title"]
        description: str = snippet["description"]
        publishedAt: str = snippet["publishedAt"]
        channelTitle: str = snippet["channelTitle"]
        tags: str = ", ".join(snippet.get("tags", []))
        iso_duration: str = response["items"][0]["contentDetails"]["duration"]
        video_duration: str = str(isodate.parse_duration(iso_duration))
        return (
            video_title,
            description,
            publishedAt,
            channelTitle,
            tags,
            video_duration,
            url,
        )
    else:
        print(f"Warning: No details found for video ID {video_id}")
        return None


def fetch_transcript(video_id: str) -> Optional[str]:
    """Fetches the transcript for a given video ID."""
    try:
        transcript_obj = ytt_api.fetch(video_id, languages=("en", "en-US"))
        transcript_data = transcript_obj.to_raw_data()
        transcript = " ".join([t["text"] for t in transcript_data])
        return transcript
    except Exception as e:
        print(f"Error fetching transcript for {video_id}: {e}")
        return None


def generate_summary(
    model_name: str, transcript: str, video_title: str, url: str
) -> str:
    """Generates a summary using the specified LLM provider."""
    summary_text = ""
    prompt = (
        f"I have included a transcript for {url} ({video_title})"
        "\n\n"
        "Can you please summarize this?"
        "\n\n"
        f"{transcript}"
    )

    if model_name.startswith("gemini"):
        try:
            GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
            google_genai_client = genai.Client(api_key=GEMINI_API_KEY)
            response = google_genai_client.models.generate_content(
                model=model_name,
                contents=[
                    types.Content(
                        role="user", parts=[types.Part.from_text(text=prompt)]
                    )
                ],
            )
            summary_text = response.text or ""
        except KeyError:
            print("Error: GEMINI_API_KEY not found")
            summary_text = "Error: GEMINI_API_KEY not found"
        except Exception as e:
            print(f"Gemini API Error: {e}")
            summary_text = f"Error: {e}"

    elif model_name.startswith("vertex"):
        try:
            vertex_project_id = os.environ["PROJECT_ID"]
            vertex_credentials, _ = google.auth.default()
            actual_model_name = model_name.replace("vertex-", "")

            if actual_model_name.startswith("claude"):
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
                    content_blocks = response_json.get("content", [])
                    if (
                        content_blocks
                        and isinstance(content_blocks, list)
                        and "text" in content_blocks[0]
                    ):
                        summary_text = content_blocks[0]["text"]
                    else:
                        summary_text = f"Unexpected response format: {response.text}"
                else:
                    summary_text = (
                        f"Vertex API Error {response.status_code}: {response.text}"
                    )
                    print(summary_text)

        except KeyError:
            print(
                "Error: PROJECT_ID environment variable required for GCPVertex models."
            )
            summary_text = "Error: PROJECT_ID required"
        except Exception as e:
            print(f"Vertex Request Error: {e}")
            summary_text = f"Error: {e}"

    elif model_name.startswith("bedrock"):
        try:
            aws_bearer_token_bedrock = os.environ["AWS_BEARER_TOKEN_BEDROCK"]
            actual_model_name = model_name.replace("bedrock-", "")
            if actual_model_name.startswith("claude"):
                actual_model_name = f"us.anthropic.{actual_model_name}:0"
            elif actual_model_name.startswith("nova"):
                actual_model_name = f"us.amazon.{actual_model_name}:0"

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
        except KeyError:
            print(
                "Error: AWS_BEARER_TOKEN_BEDROCK environment variable required for "
                "AWS Bedrock models."
            )
            summary_text = "Error: AWS_BEARER_TOKEN_BEDROCK required"
        except Exception as e:
            print(f"Bedrock Request Error: {e}")
            summary_text = f"Error: {e}"

    elif model_name.startswith("foundry"):
        try:
            AZURE_FOUNDRY_ENDPOINT = os.environ["AZURE_FOUNDRY_ENDPOINT"]
            AZURE_FOUNDRY_API_KEY = os.environ["AZURE_FOUNDRY_API_KEY"]
            actual_model_name = model_name.replace("foundry-", "")
            client = OpenAI(
                base_url=AZURE_FOUNDRY_ENDPOINT, api_key=AZURE_FOUNDRY_API_KEY
            )
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
        except KeyError:
            print(
                "Error: AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY "
                "environment variables required."
            )
            summary_text = "Error: Foundry vars required"
        except Exception as e:
            print(f"Foundry Request Error: {e}")
            summary_text = f"Error: {e}"

    return summary_text


def main() -> None:
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
            "GCP Vertex model (prefixed with 'vertex-'). e.g. "
            "vertex-claude-haiku-4-5@20251001\n"
            "AWS Bedrock model (prefixed with 'bedrock-'). e.g. "
            "bedrock-claude-haiku-4-5-20251001-v1\n"
            "Azure Foundry model (prefix with 'foundry-). e.g. 'foundry-gpt-5-mini'\n"
            "Defaults to None."
        ),
    )

    args = parser.parse_args()
    video_id_input: str = args.video_id
    outfile: str = args.outfile
    model_name: Optional[str] = args.model

    youtube_service = get_youtube_service()

    video_ids = resolve_video_ids(video_id_input, youtube_service)

    # Setup Output Directories
    transcripts_dir: Optional[str] = None
    summaries_dir: Optional[str] = None
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

    data: List[dict] = []
    for video_id in video_ids:
        print(f"Processing Video ID: {video_id}")

        # Get Details
        details = get_video_details(video_id, youtube_service)
        if not details:
            # If explicit None returned, skip
            continue

        (
            video_title,
            description,
            publishedAt,
            channelTitle,
            tags,
            video_duration,
            url,
        ) = details
        print(f"Processing Video URL: {url}")

        # Fetch Transcript
        transcript = fetch_transcript(video_id)
        if not transcript:
            continue

        # Save Transcript
        safe_title = (
            re.sub(r'[\\/*?:"<>|]', "_", video_title)
            .replace("\n", " ")
            .replace("\r", "")
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

        # Summarize
        summary_text = ""
        summary_full_path = ""
        if model_name:
            print(f"Summarizing using model: {model_name}")
            summary_text = generate_summary(model_name, transcript, video_title, url)

            if summaries_dir and summary_text:
                summary_filename = (
                    f"{model_name} - {video_id} - {safe_title} - summary.md"
                )
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
            f"Summary Text {model_name}"
            if model_name
            else "Summary Text": summary_text,
        }
        data.append(row)
        time.sleep(1)

    if data:
        df = pl.DataFrame(data)
        df.write_csv(outfile)
        print(f"Successfully wrote {len(df)} rows to {outfile}")
    else:
        print("No data gathered.")


if __name__ == "__main__":
    main()
