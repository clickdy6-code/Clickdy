
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from starlette.background import BackgroundTask

app = FastAPI(title="Clickdy Video Downloader")

# Development/testing only. Restrict this to your real website before deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class DownloadRequest(BaseModel):
    url: HttpUrl


@app.get("/")
def home():
    return {"status": "Clickdy downloader backend is running"}


@app.post("/api/download")
def download_video(request: DownloadRequest):
    url = str(request.url)
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Please enter a valid public video URL.")

    # Block local/private hostnames and IP addresses to reduce SSRF risk.
    host = parsed.hostname.lower()
    if (
        host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
        or host.endswith((".local", ".internal"))
    ):
        raise HTTPException(status_code=400, detail="Private or local URLs are not supported.")

    temp_dir = tempfile.mkdtemp(prefix="clickdy_")

    try:
        output_template = str(Path(temp_dir) / "video.%(ext)s")
        options = {
            "format": "bestvideo*+bestaudio/best",
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "max_filesize": 1024 * 1024 * 1024,  # 1 GB limit
            "socket_timeout": 20,
            "retries": 2,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail="This video could not be retrieved. It may be private, "
                           "unsupported, restricted, or unavailable. Details: "
                           + str(exc)[:250],
                )

        files = [
            p for p in Path(temp_dir).iterdir()
            if p.is_file() and p.suffix.lower() in {
                ".mp4", ".mkv", ".webm", ".mov", ".m4v"
            }
        ]

        if not files:
            raise HTTPException(
                status_code=500,
                detail="No video file was produced. Check that FFmpeg is installed."
            )

        video_file = max(files, key=lambda p: p.stat().st_size)
        title = re.sub(r"[^A-Za-z0-9._ -]", "", info.get("title") or "clickdy-video")
        title = title.strip(" ._-")[:100] or "clickdy-video"
        filename = f"{title}{video_file.suffix.lower()}"

        return FileResponse(
            path=str(video_file),
            media_type="application/octet-stream",
            filename=filename,
            background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
        )

    except HTTPException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail="Download failed: " + str(exc)[:250],
        )
