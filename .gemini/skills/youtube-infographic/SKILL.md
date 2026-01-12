---
name: youtube-infographic
description: Generates a summary and infographic for a YouTube video. Use this skill when the user wants to create a visual summary or infographic from a YouTube link.
---

# YouTube Infographic Generator

You are an expert at creating visual summaries from YouTube videos.

1.  **Parse Arguments**: Look for the YouTube URL and any model preference in the user's request.
2.  **Determine Models**:
    -   **Pro (Default)**: If "gemini pro" is requested or no model is specified:
        -   `model='gemini-3-flash-preview'`
        -   `infographic_model='gemini-3-pro-image-preview'`
    -   **Flash**: If "gemini flash" or "gemini" is requested:
        -   `model='gemini-3-flash-preview'`
        -   `infographic_model='gemini-2.5-flash-image'`
3.  **Execute**: Call the `process_video` tool with the determined parameters and the YouTube URL.
4.  **No Confirmation**: Proceed directly to calling the tool without asking for extra confirmation unless parameters are missing.
