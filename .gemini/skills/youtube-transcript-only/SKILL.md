---
name: youtube-transcript-only
description: Extract only the YouTube transcript for a given video. Use this when the user just wants the raw transcript text.
---

# YouTube Transcript Extractor

1.  **Identify URL**: Find the YouTube video URL in the user's request.
2.  **Execute**: Call `process_video` with the URL.
3.  **Defaults**: The default behavior of `process_video` is to fetch the transcript, which is exactly what is needed here.
