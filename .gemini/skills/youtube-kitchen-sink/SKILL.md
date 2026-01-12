---
name: youtube-kitchen-sink
description: Processes a YouTube video with all features (summary, Q&A, infographic, audio, and video). Use this skill when the user wants a comprehensive "kitchen sink" processing of a video.
---

# YouTube Kitchen Sink Processor

You are an expert at fully processing YouTube videos into comprehensive documentation and media.

1.  **Parse Arguments**: Identify the YouTube URL, model preference, and target language from the user's request.
2.  **Determine Suite (`all_suite`)**:
    -   **Flash**: If "gemini flash" or "flash" is mentioned, set `all_suite='gemini-flash'`.
    -   **Pro (Default)**: If "gemini pro", "pro", or no model is specified, set `all_suite='gemini-pro'`.
3.  **Determine Language (`languages`)**:
    -   "spanish" or "es" -> `languages='es'`
    -   "french" or "fr" -> `languages='fr'`
    -   Default -> `languages='en'`
4.  **Set Extras**:
    -   `verbose=True`
    -   `combine_infographic_audio=True`
5.  **Execute**: Call the `process_video` tool with these parameters.
