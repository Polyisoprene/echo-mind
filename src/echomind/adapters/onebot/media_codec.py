"""Multimodal GIF 2x2 storyboard synthesizer (Pillow-based, zero external binary dependency)."""

from __future__ import annotations

import base64
import io

from PIL import Image, ImageDraw

GRID_CELL_SIZE = 240
GRID_PADDING = 4


def _sample_four_frame_indices(n_frames: int) -> tuple[int, int, int, int]:
    if n_frames <= 1:
        return (0, 0, 0, 0)
    last = n_frames - 1
    return (
        0,
        max(0, round(last * 0.33)),
        max(0, round(last * 0.66)),
        last,
    )


def _extract_resized_frame(img: Image.Image, frame_idx: int) -> Image.Image:
    img.seek(frame_idx)
    rgba = img.convert("RGBA")
    bg = Image.new("RGB", rgba.size, (255, 255, 255))
    bg.paste(rgba, mask=rgba.split()[3])
    return bg.resize((GRID_CELL_SIZE, GRID_CELL_SIZE), Image.Resampling.BILINEAR)


def gif_to_storyboard_data_url(raw_bytes: bytes) -> str:
    """Convert an animated GIF/WebP into a 2x2 sequential JPEG storyboard data URL."""
    if not raw_bytes:
        return ""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        n_frames = int(getattr(img, "n_frames", 1))
        indices = _sample_four_frame_indices(n_frames)
        frames = [_extract_resized_frame(img, idx) for idx in indices]

    canvas_size = GRID_CELL_SIZE * 2 + GRID_PADDING * 3
    canvas = Image.new("RGB", (canvas_size, canvas_size), (28, 28, 32))
    positions = (
        (GRID_PADDING, GRID_PADDING),
        (GRID_CELL_SIZE + GRID_PADDING * 2, GRID_PADDING),
        (GRID_PADDING, GRID_CELL_SIZE + GRID_PADDING * 2),
        (GRID_CELL_SIZE + GRID_PADDING * 2, GRID_CELL_SIZE + GRID_PADDING * 2),
    )
    draw = ImageDraw.Draw(canvas)
    for idx, (frame, (x_pos, y_pos)) in enumerate(zip(frames, positions, strict=True), start=1):
        canvas.paste(frame, (x_pos, y_pos))
        draw.rectangle((x_pos, y_pos, x_pos + 22, y_pos + 18), fill=(0, 0, 0))
        draw.text((x_pos + 6, y_pos + 3), str(idx), fill=(255, 255, 255))

    out_buf = io.BytesIO()
    canvas.save(out_buf, format="JPEG", quality=82)
    b64_str = base64.b64encode(out_buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64_str}"
