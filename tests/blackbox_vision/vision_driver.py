"""
VisionChatDriver — extends GoChatDriver with two-phase image upload
and a send_image_turn helper for vision eval cases.

Upload flow (mirrors FileAPI.swift):
  POST /v1/files/upload/request   → { presigned_url, file_id }
  PUT  presigned_url              → 200
  POST /v1/files/upload/confirm   → { file_id }

Then pass file_id in ChatAPI.sendMessageStream's imageIds.
"""
from __future__ import annotations

import mimetypes

# Reuse the existing driver and types
import sys
from dataclasses import dataclass
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "blackbox_multiturn"))

from go_driver import GoChatDriver, Turn  # noqa: E402


@dataclass
class UploadedFile:
    file_id: str
    mime_type: str
    path: str


class VisionChatDriver(GoChatDriver):
    """
    GoChatDriver with image-upload capability for chat vision eval.

    Extra constructor arguments:
      file_base: base URL for file-service, e.g. http://localhost:8006/v1
    """

    def __init__(
        self,
        chat_base: str,
        user_base: str,
        jwt_secret: str,
        memory_base: str,
        file_base: str,
        timeout_s: float = 30.0,
    ) -> None:
        super().__init__(
            chat_base=chat_base,
            user_base=user_base,
            jwt_secret=jwt_secret,
            memory_base=memory_base,
            timeout_s=timeout_s,
        )
        self._file_base = file_base.rstrip("/")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload_image(self, token: str, file_path: str) -> UploadedFile:
        """
        Two-phase upload: request presigned URL → PUT bytes → confirm.
        Returns an UploadedFile whose file_id can be passed to send_image_turn.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"image not found: {file_path}")

        mime_type = _guess_mime(path)
        size_bytes = path.stat().st_size

        # Phase 1 — request presigned PUT URL
        req_body = {
            "category": "chat_image",
            "original_name": path.name,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
        }
        resp = requests.post(
            f"{self._file_base}/files/upload/request",
            json=req_body,
            headers=_auth(token),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        presigned_url: str = data["presigned_url"]
        file_id: str = data["file_id"]

        # Phase 2 — PUT raw bytes to presigned URL (no auth header)
        with path.open("rb") as fh:
            raw = fh.read()
        put_resp = requests.put(
            presigned_url,
            data=raw,
            headers={"Content-Type": mime_type},
            timeout=self.timeout_s,
        )
        put_resp.raise_for_status()

        # Phase 3 — confirm upload
        confirm_resp = requests.post(
            f"{self._file_base}/files/upload/confirm",
            json={"file_id": file_id},
            headers=_auth(token),
            timeout=self.timeout_s,
        )
        confirm_resp.raise_for_status()

        return UploadedFile(file_id=file_id, mime_type=mime_type, path=file_path)

    def send_image_turn(
        self,
        token: str,
        session_id: str,
        content: str,
        image_paths: list[str],
    ) -> Turn:
        """
        Upload all images then send a chat turn with their file IDs.
        Falls back to text-only if image_paths is empty (covers VIS-010).
        """
        file_ids: list[str] = []
        for p in image_paths:
            uploaded = self.upload_image(token, p)
            file_ids.append(uploaded.file_id)

        return self.send_turn(
            token=token,
            session_id=session_id,
            content=content,
            image_ids=file_ids,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime and mime.startswith("image/"):
        return mime
    # Default to JPEG (normalizeAsJPEG re-encodes on iOS anyway)
    return "image/jpeg"
