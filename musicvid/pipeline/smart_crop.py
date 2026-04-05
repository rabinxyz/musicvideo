"""Smart crop utilities for social media portrait format conversion."""

import numpy as np
from PIL import Image, ImageFilter
from pathlib import Path

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None


PLATFORM_SIZES = {
    "reels": (1080, 1920),
    "shorts": (1080, 1920),
    "square": (1080, 1080),
}


def detect_poi(image_path):
    """Detect point of interest in image via face detection or saliency.

    Returns (x, y) coordinates in original image.
    Fallback: image center (w//2, h//2).
    """
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not open image: {image_path}")

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Method 1: Face detection via Haar cascade
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    if len(faces) > 0:
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        return fx + fw // 2, fy + fh // 2

    # Method 2: Saliency map
    saliency = cv2.saliency.StaticSaliencyFineGrained_create()
    success, saliency_map = saliency.computeSaliency(img)
    if success:
        saliency_8u = (saliency_map * 255).astype(np.uint8)
        _, _, _, max_loc = cv2.minMaxLoc(saliency_8u)
        return max_loc[0], max_loc[1]

    # Method 3: Center fallback
    return w // 2, h // 2


def smart_crop(image_path, target_w, target_h, poi=None):
    """Crop image to target_w x target_h centered on point of interest.

    Args:
        image_path: Path to source image.
        target_w: Target width in pixels.
        target_h: Target height in pixels.
        poi: Optional (x, y) tuple; calls detect_poi() when None.

    Returns:
        PIL.Image resized to (target_w, target_h).
    """
    if poi is None:
        poi = detect_poi(image_path)

    img = Image.open(str(image_path)).convert("RGB")
    orig_w, orig_h = img.size
    target_ratio = target_w / target_h

    if orig_w / orig_h > target_ratio:
        # Original wider than target: crop width, keep full height
        crop_h = orig_h
        crop_w = int(orig_h * target_ratio)
    else:
        # Original taller or same ratio: crop height, keep full width
        crop_w = orig_w
        crop_h = int(orig_w / target_ratio)

    poi_x, poi_y = poi
    crop_x = poi_x - crop_w // 2
    crop_x = max(0, min(crop_x, orig_w - crop_w))
    crop_y = poi_y - crop_h // 2
    crop_y = max(0, min(crop_y, orig_h - crop_h))

    cropped = img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
    return cropped.resize((target_w, target_h), Image.LANCZOS)


def blur_bg_composite(image_path, target_w, target_h):
    """Create portrait composite: blurred background + sharp smart crop overlay.

    Returns:
        PIL.Image sized (target_w, target_h).
    """
    img = Image.open(str(image_path)).convert("RGB")
    orig_w, orig_h = img.size

    # Scale to fill target height (background layer)
    scale = target_h / orig_h
    bg_w = int(orig_w * scale)
    bg = img.resize((bg_w, target_h), Image.LANCZOS)

    # Center-crop background to target width
    bg_x = max(0, (bg_w - target_w) // 2)
    bg = bg.crop((bg_x, 0, bg_x + target_w, target_h))

    # Heavy Gaussian blur on background
    bg = bg.filter(ImageFilter.GaussianBlur(radius=30))

    # Sharp smart crop centered on POI
    sharp = smart_crop(image_path, target_w, target_h)

    result = bg.copy()
    result.paste(sharp, (0, 0))
    return result


def convert_for_platform(image_path, platform, style="blur-bg"):
    """Convert image for social media platform format.

    Args:
        image_path: Path to source image.
        platform: "reels" | "shorts" | "square"
        style: "blur-bg" (recommended) | "crop"

    Returns:
        Path string to converted image (saved alongside source with smart_ prefix).
    """
    target_w, target_h = PLATFORM_SIZES.get(platform, (1080, 1920))

    if style == "blur-bg":
        result = blur_bg_composite(image_path, target_w, target_h)
    else:
        result = smart_crop(image_path, target_w, target_h)

    src = Path(image_path)
    out_path = src.parent / f"smart_{src.stem}.jpg"
    result.save(str(out_path), "JPEG", quality=95)
    return str(out_path)
