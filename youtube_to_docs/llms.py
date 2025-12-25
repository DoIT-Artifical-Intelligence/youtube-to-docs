import os

import google.auth
import requests
from google import genai
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.genai import types
from openai import OpenAI


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
