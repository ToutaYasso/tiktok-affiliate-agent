"""
ffmpeg-worker — WF04 Video Assembly Service
POST /generate-video : télécharge audio Azure, génère image 1080x1920, assemble MP4, upload Azure
"""
import os
import subprocess
import tempfile
import hashlib
import hmac
import base64
import logging
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
from azure.storage.blob import BlobServiceClient, ContentSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ffmpeg-worker", version="1.0.0")

# ── Config Azure ──────────────────────────────────────────────────────────────
AZURE_ACCOUNT   = os.getenv("AZURE_STORAGE_ACCOUNT", "tiktokaffiliate2026")
AZURE_KEY       = os.getenv("AZURE_STORAGE_KEY", "")
AZURE_CONTAINER = os.getenv("AZURE_CONTAINER", "tiktok-videos")
AZURE_CONN_STR  = os.getenv("AZURE_CONNECTION_STRING", "")

# ── Amazon PA API v5 ──────────────────────────────────────────────────────────
AMAZON_ACCESS_KEY    = os.getenv("AMAZON_ACCESS_KEY", "")
AMAZON_SECRET_KEY    = os.getenv("AMAZON_SECRET_KEY", "")
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "affiliatefres-21")
AMAZON_HOST          = "webservices.amazon.fr"
AMAZON_REGION        = "eu-west-1"
AMAZON_SERVICE       = "ProductAdvertisingAPI"

# ── Dimensions TikTok / Instagram Reels 9:16 ─────────────────────────────────
WIDTH, HEIGHT = 1080, 1920
BG_COLOR   = (15, 15, 25)      # fond sombre
ACCENT     = (255, 48, 108)    # rose TikTok
TEXT_WHITE = (255, 255, 255)
TEXT_GREY  = (180, 180, 180)

# ── Instagram Reels specs ─────────────────────────────────────────────────────
# Résolution : 1080×1920 (9:16)
# Frame rate : 30 fps
# Codec vidéo : H.264 High profile level 4.0
# Bitrate vidéo : 3500k (recommandé Instagram)
# Codec audio : AAC 192k 44100Hz
REELS_FPS        = "30"
REELS_VIDEO_BR   = "3500k"
REELS_VIDEO_MAX  = "4000k"
REELS_VIDEO_BUF  = "8000k"
REELS_AUDIO_BR   = "192k"
REELS_AUDIO_RATE = "44100"

# ── Fonts (inclus dans le container via fonts-liberation) ─────────────────────
FONT_PATH_BOLD   = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_PATH_REGULAR= "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


class VideoRequest(BaseModel):
    video_id:      int
    product_id:    int
    product_title: str
    audio_blob_name: str          # ex: "audio/52_produit_cool.mp3"
    image_url:     Optional[str] = None
    affiliate_link: Optional[str] = ""
    hashtags:      Optional[str] = ""
    script_hook:   Optional[str] = ""


class VideoResponse(BaseModel):
    video_id:   int
    video_url:  str
    blob_path:  str
    status:     str = "video_ready"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers Azure
# ─────────────────────────────────────────────────────────────────────────────

def get_blob_service() -> BlobServiceClient:
    if AZURE_CONN_STR:
        return BlobServiceClient.from_connection_string(AZURE_CONN_STR)
    account_url = f"https://{AZURE_ACCOUNT}.blob.core.windows.net"
    from azure.storage.blob import StorageSharedKeyCredential
    cred = StorageSharedKeyCredential(AZURE_ACCOUNT, AZURE_KEY)
    return BlobServiceClient(account_url=account_url, credential=cred)


def download_blob(blob_name: str, dest_path: str) -> None:
    """Télécharge un blob Azure vers un fichier local."""
    client = get_blob_service()
    container = client.get_container_client(AZURE_CONTAINER)
    with open(dest_path, "wb") as f:
        data = container.download_blob(blob_name)
        data.readinto(f)
    logger.info(f"Downloaded blob {blob_name} → {dest_path}")


def upload_blob(local_path: str, blob_name: str) -> str:
    """Upload un fichier vers Azure Blob et retourne l'URL publique."""
    client = get_blob_service()
    container = client.get_container_client(AZURE_CONTAINER)
    with open(local_path, "rb") as f:
        container.upload_blob(
            name=blob_name,
            data=f,
            overwrite=True,
            content_settings=ContentSettings(content_type="video/mp4")
        )
    url = f"https://{AZURE_ACCOUNT}.blob.core.windows.net/{AZURE_CONTAINER}/{blob_name}"
    logger.info(f"Uploaded {local_path} → {url}")
    return url


# ─────────────────────────────────────────────────────────────────────────────
# Génération image 1080×1920
# ─────────────────────────────────────────────────────────────────────────────

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Coupe le texte pour qu'il rentre dans max_width pixels."""
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = f"{line} {word}".strip()
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def download_product_image(image_url: str, dest_path: str) -> bool:
    """Télécharge l'image produit. Retourne False si échec (on utilisera placeholder)."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.amazon.com/",
        }
        r = requests.get(image_url, timeout=15, headers=headers)
        if r.status_code == 200:
            content_type = r.headers.get("Content-Type", "")
            if "image" in content_type or len(r.content) > 5000:
                with open(dest_path, "wb") as f:
                    f.write(r.content)
                # Verify it's a valid image
                try:
                    from PIL import Image as PILImg
                    with PILImg.open(dest_path) as test_img:
                        test_img.verify()
                    return True
                except Exception:
                    logger.warning(f"Downloaded file is not a valid image: {image_url}")
                    return False
    except Exception as e:
        logger.warning(f"Image download failed: {e}")
    return False


def generate_frame(
    product_title: str,
    script_hook: str,
    affiliate_link: str,
    hashtags: str,
    image_url: Optional[str],
    output_path: str
) -> None:
    """Génère une image 1080×1920 au format TikTok / Instagram Reels."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # ── Dégradé fond (simulation) ──────────────────────────────────────────
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(15 + 20 * ratio)
        g = int(15 + 5 * ratio)
        b = int(25 + 30 * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # ── Image produit (zone centrale) ─────────────────────────────────────
    prod_img_path = output_path.replace(".png", "_prod.jpg")
    img_loaded = False
    if image_url:
        img_loaded = download_product_image(image_url, prod_img_path)

    IMG_BOX_Y = 250
    IMG_BOX_H = 900
    IMG_BOX_W = 900
    IMG_BOX_X = (WIDTH - IMG_BOX_W) // 2

    if img_loaded:
        try:
            prod = Image.open(prod_img_path).convert("RGBA")
            prod.thumbnail((IMG_BOX_W, IMG_BOX_H), Image.LANCZOS)
            offset_x = IMG_BOX_X + (IMG_BOX_W - prod.width) // 2
            offset_y = IMG_BOX_Y + (IMG_BOX_H - prod.height) // 2
            img.paste(prod, (offset_x, offset_y), prod)
        except Exception as e:
            logger.warning(f"Could not paste product image: {e}")
            img_loaded = False

    if not img_loaded:
        # Placeholder dégradé professionnel — affiche le nom du produit
        try:
            font_label = ImageFont.truetype(FONT_PATH_BOLD, 30)
            font_name  = ImageFont.truetype(FONT_PATH_BOLD, 56)
            font_tag   = ImageFont.truetype(FONT_PATH_REGULAR, 34)
        except Exception:
            font_label = ImageFont.load_default(size=30)
            font_name  = ImageFont.load_default(size=56)
            font_tag   = ImageFont.load_default(size=34)
        # Dégradé violet sombre → accent
        for y_grad in range(IMG_BOX_H):
            ratio = y_grad / IMG_BOX_H
            r = int(18 + int(ACCENT[0] * 0.35 * ratio))
            g = int(8  + int(ACCENT[1] * 0.10 * ratio))
            b = int(38 + int(40 * ratio))
            draw.line([(IMG_BOX_X, IMG_BOX_Y + y_grad), (IMG_BOX_X + IMG_BOX_W, IMG_BOX_Y + y_grad)], fill=(r, g, b))
        draw.rounded_rectangle(
            [IMG_BOX_X, IMG_BOX_Y, IMG_BOX_X + IMG_BOX_W, IMG_BOX_Y + IMG_BOX_H],
            radius=30, outline=ACCENT, width=5
        )
        deco_y = IMG_BOX_Y + IMG_BOX_H // 3
        draw.rectangle([(IMG_BOX_X + 60, deco_y), (IMG_BOX_X + IMG_BOX_W - 60, deco_y + 3)], fill=ACCENT)
        draw.text((WIDTH // 2, IMG_BOX_Y + 50), "PRODUIT", font=font_label, fill=ACCENT, anchor="mt")
        name_lines = wrap_text(product_title, font_name, IMG_BOX_W - 80)
        name_y = deco_y + 40
        for line in name_lines[:4]:
            draw.text((WIDTH // 2, name_y), line, font=font_name, fill=TEXT_WHITE, anchor="mt",
                      stroke_width=2, stroke_fill=(0, 0, 0))
            name_y += 70
        badge_y = IMG_BOX_Y + IMG_BOX_H - 90
        draw.rounded_rectangle([(WIDTH // 2 - 160, badge_y), (WIDTH // 2 + 160, badge_y + 60)], radius=30, fill=ACCENT)
        draw.text((WIDTH // 2, badge_y + 30), "amazon.fr", font=font_tag, fill=TEXT_WHITE, anchor="mm")

    # ── Barre accent haut ────────────────────────────────────────────────
    draw.rectangle([(0, 0), (WIDTH, 8)], fill=ACCENT)

    # ── Hook (accroche) ──────────────────────────────────────────────────
    try:
        font_hook = ImageFont.truetype(FONT_PATH_BOLD, 52)
    except Exception:
        font_hook = ImageFont.load_default(size=52)

    hook_text = script_hook or "Découvrez ce produit incroyable !"
    hook_lines = wrap_text(hook_text, font_hook, WIDTH - 80)
    hook_y = 80
    for line in hook_lines[:3]:
        draw.text((WIDTH // 2, hook_y), line, font=font_hook,
                  fill=TEXT_WHITE, anchor="mt", stroke_width=2, stroke_fill=(0, 0, 0))
        hook_y += 65

    # ── Titre produit ─────────────────────────────────────────────────────
    try:
        font_title = ImageFont.truetype(FONT_PATH_BOLD, 44)
    except Exception:
        font_title = ImageFont.load_default(size=44)

    title_y = IMG_BOX_Y + IMG_BOX_H + 40
    title_lines = wrap_text(product_title, font_title, WIDTH - 80)
    for line in title_lines[:2]:
        draw.text((WIDTH // 2, title_y), line, font=font_title,
                  fill=TEXT_WHITE, anchor="mt")
        title_y += 55

    # ── Bouton CTA ────────────────────────────────────────────────────────
    CTA_Y = title_y + 30
    draw.rounded_rectangle(
        [(WIDTH // 2 - 280, CTA_Y), (WIDTH // 2 + 280, CTA_Y + 90)],
        radius=45, fill=ACCENT
    )
    try:
        font_cta = ImageFont.truetype(FONT_PATH_BOLD, 38)
    except Exception:
        font_cta = ImageFont.load_default(size=38)
    draw.text((WIDTH // 2, CTA_Y + 45), "Voir le produit  >>", font=font_cta,
              fill=TEXT_WHITE, anchor="mm")

    # NOTE: Les hashtags ne sont PAS affichés dans la vidéo.
    # Ils appartiennent uniquement à la description/caption Instagram (WF05).

    # ── Barre accent bas ─────────────────────────────────────────────────
    draw.rectangle([(0, HEIGHT - 8), (WIDTH, HEIGHT)], fill=ACCENT)

    img.save(output_path, "PNG", quality=95)
    logger.info(f"Frame generated: {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint principal
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/generate-video", response_model=VideoResponse)
async def generate_video(req: VideoRequest):
    logger.info(f"Generating video for video_id={req.video_id}, product_id={req.product_id}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 1. Télécharger l'audio depuis Azure Blob
        audio_path = str(tmp / "audio.mp3")
        try:
            download_blob(req.audio_blob_name, audio_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Audio download failed: {e}")

        # 2. Générer le frame image 1080×1920
        frame_path = str(tmp / "frame.png")
        try:
            generate_frame(
                product_title=req.product_title,
                script_hook=req.script_hook or "",
                affiliate_link=req.affiliate_link or "",
                hashtags=req.hashtags or "",
                image_url=req.image_url,
                output_path=frame_path
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Frame generation failed: {e}")

        # 3. FFmpeg : image + audio → MP4 portrait 9:16 Instagram Reels
        #    Specs Instagram Reels :
        #      - Résolution  : 1080×1920 (9:16)
        #      - Frame rate  : 30 fps
        #      - Codec vidéo : H.264 High profile level 4.0
        #      - Bitrate vidéo : 3500k (maxrate 4000k, bufsize 8000k)
        #      - Codec audio : AAC 192k 44100 Hz
        #      - Pixel format: yuv420p
        #      - Fast start  : movflags +faststart (streaming web)
        video_path = str(tmp / "video.mp4")
        # Ken Burns gentle zoom-in effect: scale 110%→100% over the audio duration
        # zoompan=z='min(zoom+0.0005,1.1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30
        kenburns_filter = (
            f"zoompan=z='if(lte(zoom,1.0),1.1,max(1.001,zoom-0.0005))':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={WIDTH}x{HEIGHT}:fps={REELS_FPS},"
            f"scale={WIDTH}:{HEIGHT}:flags=lanczos"
        )
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", frame_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-profile:v", "high",             # H.264 High profile
            "-level:v", "4.0",                # Level 4.0 pour 1080p@30fps
            "-b:v", REELS_VIDEO_BR,           # Bitrate vidéo 3500k
            "-maxrate", REELS_VIDEO_MAX,      # Maxrate 4000k
            "-bufsize", REELS_VIDEO_BUF,      # Buffer 8000k
            "-c:a", "aac",
            "-b:a", REELS_AUDIO_BR,           # Audio 192k
            "-ar", REELS_AUDIO_RATE,          # Sample rate 44100 Hz
            "-pix_fmt", "yuv420p",
            "-r", REELS_FPS,                  # Frame rate de sortie 30fps
            "-shortest",
            "-vf", kenburns_filter,           # Ken Burns zoom effect + portrait 1080×1920
            "-movflags", "+faststart",        # Streaming optimisé
            video_path
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"FFmpeg stderr: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"FFmpeg failed: {result.stderr[-500:]}")
        logger.info(f"FFmpeg OK, video: {os.path.getsize(video_path)} bytes")

        # 4. Upload MP4 vers Azure Blob
        # Normalise les accents (é→e, è→e, ô→o…) pour éviter les caractères non-ASCII dans les URLs
        raw_title = req.product_title or "product"
        normalized = unicodedata.normalize("NFKD", raw_title)
        ascii_title = "".join(c for c in normalized if not unicodedata.combining(c))
        safe_title = ascii_title.replace(" ", "_")[:30].lower()
        safe_title = "".join(c for c in safe_title if c.isascii() and (c.isalnum() or c == "_"))
        blob_name = f"videos/{req.product_id}_{safe_title}.mp4"
        try:
            video_url = upload_blob(video_path, blob_name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    return VideoResponse(
        video_id=req.video_id,
        video_url=video_url,
        blob_path=blob_name,
        status="video_ready"
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "ffmpeg-worker"}


@app.get("/")
def root():
    return {"service": "ffmpeg-worker", "version": "1.0.0", "endpoints": ["/generate-video", "/health"]}
