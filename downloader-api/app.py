import os
import re
import glob
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


app = FastAPI(
    title="Clickdy Downloader API",
    description="Clickdy public media extraction service",
    version="1.0.0"
)

origins = [
    item.strip()
    for item in os.getenv(
        "FRONTEND_ORIGIN",
        "https://clickdy.vercel.app,http://localhost:5500"
    ).split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


ALLOWED_DOMAINS = {
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "fb.watch",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "pinterest.com",
    "www.pinterest.com",
    "pin.it",
}


class URLRequest(BaseModel):
    url: HttpUrl


class DownloadRequest(BaseModel):
    url: HttpUrl
    quality: str = "best"


def validate_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)

    if parsed.scheme != "https":
        raise HTTPException(
            status_code=400,
            detail="Only HTTPS links are supported."
        )

    hostname = (parsed.hostname or "").lower()

    if hostname not in ALLOWED_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail="This platform is not currently supported."
        )

    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL."
        )

    return raw_url


def make_options(download=False, quality="best", folder=None):
    formats = {
        "best": "best[ext=mp4]/best",
        "720": "best[height<=720][ext=mp4]/best[height<=720]/best",
        "480": "best[height<=480][ext=mp4]/best[height<=480]/best",
        "360": "best[height<=360][ext=mp4]/best[height<=360]/best",
    }

    if quality not in formats:
        raise HTTPException(
            status_code=400,
            detail="Invalid video quality."
        )

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 1,
        "ignoreerrors": False,
        "format": formats[quality],
        "max_filesize": 300 * 1024 * 1024,
        "restrictfilenames": True,
    }

    if download:
        options.update({
            "outtmpl": os.path.join(folder, "%(title).80s.%(ext)s"),
            "merge_output_format": "mp4",
        })

    return options


def extract_info(url: str):
    try:
        with yt_dlp.YoutubeDL(make_options()) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise ValueError("No video information returned.")

        return info

    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Could not retrieve this video. It may be unavailable, restricted, or unsupported."
        ) from exc


@app.get("/")
def home():
    return {
        "service": "Clickdy Downloader API",
        "status": "running"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/info")
def get_video_info(request: URLRequest):
    url = validate_url(str(request.url))
    info = extract_info(url)

    return {
        "success": True,
        "title": info.get("title") or "Untitled video",
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "platform": info.get("extractor_key"),
        "formats": [
            {"quality": "Best available", "value": "best"},
            {"quality": "720p maximum", "value": "720"},
            {"quality": "480p maximum", "value": "480"},
            {"quality": "360p maximum", "value": "360"},
        ]
    }


@app.post("/api/download")
def download_video(request: DownloadRequest):
    url = validate_url(str(request.url))

    if request.quality not in {"best", "720", "480", "360"}:
        raise HTTPException(
            status_code=400,
            detail="Selected quality is not supported."
        )

    temp_folder = tempfile.mkdtemp(prefix="clickdy_")

    try:
        options = make_options(
            download=True,
            quality=request.quality,
            folder=temp_folder
        )

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        files = [
            file for file in glob.glob(os.path.join(temp_folder, "*"))
            if os.path.isfile(file)
        ]

        if not files:
            raise ValueError("Download file was not created.")

        output_file = max(files, key=os.path.getsize)

        if os.path.getsize(output_file) > 300 * 1024 * 1024:
            raise ValueError("Video exceeds the 300 MB limit.")

        title = info.get("title") or "clickdy-video"
        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:70]
        filename = f"{safe_title}.mp4"

        extension = Path(output_file).suffix.lower()

        if extension not in {".mp4", ".webm", ".mkv", ".mov"}:
            filename = f"{safe_title}{extension}"

        return FileResponse(
            output_file,
            filename=filename,
            media_type="application/octet-stream",
            background=BackgroundTask(shutil.rmtree, temp_folder, True)
        )

    except HTTPException:
        shutil.rmtree(temp_folder, ignore_errors=True)
        raise

    except Exception as exc:
        shutil.rmtree(temp_folder, ignore_errors=True)

        raise HTTPException(
            status_code=422,
            detail="Download failed. The video may be restricted, unavailable, or unsupported."
        ) from exc