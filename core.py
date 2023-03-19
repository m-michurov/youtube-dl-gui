import io
import re
from enum import Enum
from pathlib import Path
from shutil import which
from typing import NamedTuple, Callable, Any

import yt_dlp as youtube_dl
from PIL import Image
# noinspection PyProtectedMember
from mutagen.id3 import ID3, APIC
from mutagen.easyid3 import EasyID3

FFMPEG_COMMAND = 'ffmpeg'
YOUTUBE_DL_COMMAND = 'yt-dlp'


def detect_missing_commands() -> list[str]:
    return list(filter(lambda cmd: which(cmd) is None, (YOUTUBE_DL_COMMAND, FFMPEG_COMMAND)))


VIDEO_URL_REGEX_STR = \
    r'https?://(?:www\.)?youtu(?:\.be/|be\.com/(?:watch\?v=|v/|embed/|user/(?:[\w#]+/)+))([^&#?\n]+)[^\s]*'
VIDEO_URL_REGEX = re.compile(pattern=VIDEO_URL_REGEX_STR)


def get_video_id(url: str) -> str | None:
    if match := VIDEO_URL_REGEX.fullmatch(url):
        return match.group(1)

    return None


class YouTubeDLProgressKey(str, Enum):
    STATUS = 'status'
    SPEED = '_speed_str'
    ELAPSED = 'elapsed'
    ETA = '_eta_str'
    PERCENT = '_percent_str'


class YouTubeDLStatus(str, Enum):
    DOWNLOADING = 'downloading'
    FINISHED = 'finished'
    ERROR = 'error'


class YouTubeDLProgress(NamedTuple):
    status: YouTubeDLStatus
    completion_percentage: str | None


class DiscardLogger:
    def info(self, _) -> None:
        pass

    def warning(self, _) -> None:
        pass

    def error(self, _) -> None:
        pass

    def debug(self, _) -> None:
        pass


def download_audio(
        video_id: str,
        download_folder: Path,
        on_progress_changed: Callable[[YouTubeDLProgress], Any | None]
) -> Path:
    codec = 'mp3'

    def progress_hook(progress: dict[str, str | int | float]) -> None:
        on_progress_changed(
            YouTubeDLProgress(
                status=YouTubeDLStatus(progress.get(YouTubeDLProgressKey.STATUS)),
                completion_percentage=progress.get(YouTubeDLProgressKey.PERCENT)
            )
        )

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': codec,
                'preferredquality': '320',
            },
            {
                'key': 'FFmpegMetadata'
            },
            {
                'key': 'EmbedThumbnail',
                'already_have_thumbnail': False
            }
        ],
        'addmetadata': True,
        'logger': DiscardLogger(),
        'progress_hooks': [progress_hook],
        'writethumbnail': True,
        'outtmpl': f'{download_folder}\\%(id)s.%(ext)s',
        'quiet': True
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f'https://www.youtube.com/watch?v={video_id}'])

    return download_folder / f'{video_id}.{codec}'


def crop_thumbnail(mp3: Path, thumbnail_size: (int, int) = (512, 512)) -> None:
    id3 = ID3(str(mp3))

    key_album_cover = 'APIC'
    album_cover_frame = None

    for key in id3:
        if key_album_cover in key:
            album_cover_frame = id3[key]
            break

    if album_cover_frame is None:
        return

    with (
        io.BytesIO(album_cover_frame.data) as image_data_io,
        Image.open(image_data_io) as album_cover
    ):
        width, height = album_cover.size
        center = width // 2
        width, height = height, height
        album_cover = album_cover.crop(box=(center - width // 2, 0, center + width // 2, height))
        album_cover.thumbnail(size=thumbnail_size)

        image_data_io.seek(0)
        album_cover.save(image_data_io, format='jpeg')
        image_data_io.truncate()
        image_data_io.seek(0)
        image_data = image_data_io.read()

    id3[key_album_cover] = APIC(
        encoding=3,
        mime='image/jpeg',
        type=3,
        desc=u'Cover',
        data=image_data
    )

    id3.save(mp3, v2_version=3)


def cleanup_metadata(mp3: Path) -> tuple[str, str]:
    id3 = EasyID3(str(mp3))

    key_album = 'album'
    key_title = 'title'
    key_artist = 'artist'

    title: str = id3[key_title][0]
    artist: str = id3[key_artist][0]
    album: str = id3.get(key_album, [None])[0]

    title = re.sub(rf'{artist}\s+.+?\s+', '', title)
    id3[key_title] = title

    if not album:
        id3[key_album] = title

    id3.save(str(mp3))
    return title, artist


def download(
        video_id: str,
        download_folder: Path,
        status_changed: Callable[[str], Any | None],
        return_title_and_artist: bool = False
) -> Path | tuple[Path, str, str]:
    def youtube_dl_progress_changed(progress: YouTubeDLProgress) -> None:
        match progress.status:
            case YouTubeDLStatus.DOWNLOADING:
                status_changed(f'Downloading {progress.completion_percentage}')
            case YouTubeDLStatus.FINISHED:
                status_changed(f'Converting')
            case YouTubeDLStatus.ERROR:
                status_changed(f'Error occurred')

    status_changed(f'Initializing download')
    mp3_path = download_audio(video_id, download_folder, on_progress_changed=youtube_dl_progress_changed)
    status_changed(f'Cropping thumbnail')
    crop_thumbnail(mp3_path)
    status_changed(f'Cleaning up metadata')
    title, artist = cleanup_metadata(mp3_path)
    status_changed(f'Saved as {mp3_path}')

    if return_title_and_artist:
        return mp3_path, title, artist

    return mp3_path
