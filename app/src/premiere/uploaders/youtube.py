"""YouTube upload functionality."""

import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from premiere.generators.metadata import VideoMetadata
from premiere.utils.config import YouTubeConfig, get_config
from premiere.utils.logger import get_logger


# OAuth scopes for YouTube upload
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Credentials file paths
CREDENTIALS_DIR = Path.home() / ".premiere"
CLIENT_SECRETS = CREDENTIALS_DIR / "client_secrets.json"
TOKEN_FILE = CREDENTIALS_DIR / "youtube_token.pickle"


def get_authenticated_service():
    """Get authenticated YouTube API service.

    Returns:
        YouTube API service object.

    Raises:
        FileNotFoundError: If client secrets not found.
    """
    logger = get_logger()

    if not CLIENT_SECRETS.exists():
        raise FileNotFoundError(
            f"YouTube client secrets not found at {CLIENT_SECRETS}\n"
            "Download from Google Cloud Console: "
            "https://console.cloud.google.com/apis/credentials"
        )

    creds = None

    # Load existing token
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing YouTube credentials")
            creds.refresh(Request())
        else:
            logger.info("Starting YouTube OAuth flow")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS),
                SCOPES,
            )
            creds = flow.run_local_server(port=8080)

        # Save token for next time
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: Path,
    metadata: VideoMetadata,
    thumbnail_path: Path | None = None,
    config: YouTubeConfig | None = None,
) -> dict:
    """Upload video to YouTube.

    Args:
        video_path: Path to video file.
        metadata: Video metadata (title, description, tags).
        thumbnail_path: Optional thumbnail image path.
        config: YouTube configuration.

    Returns:
        Dict with video_id and url.
    """
    logger = get_logger()
    cfg = config or get_config().youtube

    logger.info(f"Uploading {video_path.name} to YouTube")

    youtube = get_authenticated_service()

    # Use first title from options
    title = metadata.titles[0] if metadata.titles else video_path.stem

    # Format description with chapters
    from premiere.generators.metadata import format_description_with_chapters
    description = format_description_with_chapters(
        metadata.description,
        metadata.chapters,
    )

    # Prepare video metadata
    body = {
        "snippet": {
            "title": title[:100],  # YouTube limit
            "description": description[:5000],  # YouTube limit
            "tags": metadata.tags[:500],  # Tag limit
            "categoryId": cfg.category,
        },
        "status": {
            "privacyStatus": cfg.privacy,
            "madeForKids": cfg.made_for_kids,
            "selfDeclaredMadeForKids": cfg.made_for_kids,
        },
    }

    # Upload video
    media = MediaFileUpload(
        str(video_path),
        mimetype="video/*",
        resumable=True,
        chunksize=1024 * 1024,  # 1MB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            logger.info(f"Upload progress: {progress}%")

    video_id = response["id"]
    logger.info(f"Video uploaded: {video_id}")

    # Upload thumbnail if provided
    if thumbnail_path and thumbnail_path.exists():
        upload_thumbnail(youtube, video_id, thumbnail_path)

    # Add to playlist if configured
    if cfg.playlist_id:
        add_to_playlist(youtube, video_id, cfg.playlist_id)

    return {
        "video_id": video_id,
        "url": f"https://youtube.com/watch?v={video_id}",
        "status": cfg.privacy,
    }


def upload_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> None:
    """Upload custom thumbnail for video.

    Args:
        youtube: Authenticated YouTube service.
        video_id: YouTube video ID.
        thumbnail_path: Path to thumbnail image.
    """
    logger = get_logger()
    logger.info(f"Uploading thumbnail for {video_id}")

    media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")

    youtube.thumbnails().set(
        videoId=video_id,
        media_body=media,
    ).execute()

    logger.info("Thumbnail uploaded")


def add_to_playlist(youtube, video_id: str, playlist_id: str) -> None:
    """Add video to playlist.

    Args:
        youtube: Authenticated YouTube service.
        video_id: YouTube video ID.
        playlist_id: Target playlist ID.
    """
    logger = get_logger()
    logger.info(f"Adding video to playlist {playlist_id}")

    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id,
                },
            },
        },
    ).execute()

    logger.info("Added to playlist")


def setup_credentials() -> bool:
    """Guide user through YouTube API setup.

    Returns:
        True if setup successful.
    """
    logger = get_logger()
    console = get_logger()

    print("\nYouTube API Setup")
    print("=" * 40)
    print("\n1. Go to Google Cloud Console:")
    print("   https://console.cloud.google.com/")
    print("\n2. Create a new project or select existing")
    print("\n3. Enable YouTube Data API v3:")
    print("   APIs & Services > Library > Search 'YouTube Data API v3' > Enable")
    print("\n4. Create OAuth 2.0 credentials:")
    print("   APIs & Services > Credentials > Create Credentials > OAuth client ID")
    print("   - Application type: Desktop app")
    print("   - Download JSON")
    print(f"\n5. Save the JSON file as:\n   {CLIENT_SECRETS}")
    print("\n6. Run this command again to authenticate")

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    return CLIENT_SECRETS.exists()
