#!/usr/bin/env python3
"""
scripts/image_utils.py
Modular Image Processing & Cropping Utilities for Project LabForge.

Provides automated cropping, margin trimming, aspect ratio normalization,
visual quality enhancements, and screenshot preparation pipelines.
Operates independently; does not modify scripts/labforge_engine.py.
"""

import argparse
import fnmatch
import io
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


def get_image_metadata(image_input: Union[str, Image.Image, io.BytesIO]) -> Dict[str, Any]:
    """
    Returns image metadata: width_px, height_px, aspect_ratio, mode, format,
    classification ('widescreen' if aspect >= 1.45 else 'dialog_box'), and size_kb.
    """
    opened_here = False
    if isinstance(image_input, (str, io.BytesIO)):
        img = Image.open(image_input)
        opened_here = True
    elif isinstance(image_input, Image.Image):
        img = image_input
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    try:
        w_px, h_px = img.size
        aspect = round(w_px / max(h_px, 1), 4)
        classification = "widescreen" if aspect >= 1.45 else "dialog_box"
        size_kb = 0.0

        if isinstance(image_input, str) and os.path.isfile(image_input):
            size_kb = round(os.path.getsize(image_input) / 1024.0, 2)
        elif isinstance(image_input, io.BytesIO):
            size_kb = round(len(image_input.getvalue()) / 1024.0, 2)

        return {
            "width_px": w_px,
            "height_px": h_px,
            "aspect_ratio": aspect,
            "mode": img.mode,
            "format": img.format or "PNG",
            "classification": classification,
            "size_kb": size_kb,
        }
    finally:
        if opened_here:
            img.close()


def auto_crop(
    image: Image.Image,
    bg_color: Optional[Union[str, Tuple[int, ...]]] = "auto",
    tolerance: int = 10,
    padding: int = 0,
) -> Image.Image:
    """
    Auto-detects and crops uniform or near-uniform outer borders/whitespace.
    If bg_color is 'auto', samples the 4 corner pixels of the image.
    Uses diff thresholding to handle compression noise and anti-aliasing.
    Adds optional safety padding in pixels around the detected content.
    """
    if tolerance < 0:
        raise ValueError("Tolerance must be non-negative")
    if padding < 0:
        raise ValueError("Padding must be non-negative")

    # Work in RGB or RGBA mode for consistent color difference
    working_img = image
    if working_img.mode not in ("RGB", "RGBA"):
        working_img = working_img.convert("RGBA" if "transparency" in working_img.info else "RGB")

    w, h = working_img.size
    if w <= 2 or h <= 2:
        return image.copy()

    # Determine reference background color
    if bg_color == "auto" or bg_color is None:
        # Sample four corners: (0, 0), (w-1, 0), (0, h-1), (w-1, h-1)
        corners = [
            working_img.getpixel((0, 0)),
            working_img.getpixel((w - 1, 0)),
            working_img.getpixel((0, h - 1)),
            working_img.getpixel((w - 1, h - 1)),
        ]
        # Use corner mode if at least 2 match or average them
        # Convert to tuple of ints (strip alpha for comparison if RGBA)
        c_tuples = [tuple(c[:3]) if isinstance(c, tuple) else (c, c, c) for c in corners]
        # Find most frequent corner color
        bg_rgb = max(set(c_tuples), key=c_tuples.count)
    elif isinstance(bg_color, str):
        # Parse common color strings
        color_map = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "gray": (128, 128, 128),
            "grey": (128, 128, 128),
        }
        bg_rgb = color_map.get(bg_color.lower(), (255, 255, 255))
    elif isinstance(bg_color, (tuple, list)):
        bg_rgb = tuple(int(c) for c in bg_color[:3])
    else:
        bg_rgb = (255, 255, 255)

    # Create solid background image with reference color
    bg_canvas = Image.new("RGB", (w, h), bg_rgb)
    comp_img = working_img.convert("RGB")

    diff = ImageChops.difference(comp_img, bg_canvas)
    diff_gray = diff.convert("L")

    # Threshold diff: pixel > tolerance becomes 255, else 0
    mask = diff_gray.point(lambda p: 255 if p > tolerance else 0)
    bbox = mask.getbbox()

    if not bbox:
        # Entire image is background color within tolerance; do not crop to zero
        return image.copy()

    left, top, right, bottom = bbox

    # Apply optional padding
    if padding > 0:
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(w, right + padding)
        bottom = min(h, bottom + padding)

    return image.crop((left, top, right, bottom))


def crop_box(
    image: Image.Image,
    box: Tuple[Union[int, float], Union[int, float], Union[int, float], Union[int, float]],
    normalized: bool = False,
) -> Image.Image:
    """
    Crops image to explicit box (left, top, right, bottom).
    If normalized=True, coordinates are fractions between 0.0 and 1.0.
    Validates boundary conditions and raises ValueError on invalid coordinates.
    """
    if len(box) != 4:
        raise ValueError(f"Box must contain 4 values (left, top, right, bottom), got {len(box)}")

    w, h = image.size
    left, top, right, bottom = box

    if normalized:
        if not (0.0 <= left <= 1.0 and 0.0 <= top <= 1.0 and 0.0 <= right <= 1.0 and 0.0 <= bottom <= 1.0):
            raise ValueError(f"Normalized coordinates must be within [0.0, 1.0], got {box}")
        left = int(round(left * w))
        top = int(round(top * h))
        right = int(round(right * w))
        bottom = int(round(bottom * h))
    else:
        left = int(round(left))
        top = int(round(top))
        right = int(round(right))
        bottom = int(round(bottom))

    # Boundary checks
    if left < 0 or top < 0 or right > w or bottom > h:
        raise ValueError(
            f"Crop box ({left}, {top}, {right}, {bottom}) exceeds image dimensions ({w}, {h})"
        )
    if left >= right:
        raise ValueError(f"Invalid crop box: left ({left}) >= right ({right})")
    if top >= bottom:
        raise ValueError(f"Invalid crop box: top ({top}) >= bottom ({bottom})")

    return image.crop((left, top, right, bottom))


def crop_margins(
    image: Image.Image,
    top: int = 0,
    right: int = 0,
    bottom: int = 0,
    left: int = 0,
) -> Image.Image:
    """
    Trims specified pixel margins from image edges.
    Useful for removing OS taskbars, window title bars, or sidebars.
    """
    if top < 0 or right < 0 or bottom < 0 or left < 0:
        raise ValueError(f"Margins must be non-negative: top={top}, right={right}, bottom={bottom}, left={left}")

    w, h = image.size
    new_left = left
    new_top = top
    new_right = w - right
    new_bottom = h - bottom

    if new_left >= new_right:
        raise ValueError(f"Horizontal margins left ({left}) + right ({right}) >= image width ({w})")
    if new_top >= new_bottom:
        raise ValueError(f"Vertical margins top ({top}) + bottom ({bottom}) >= image height ({h})")

    return image.crop((new_left, new_top, new_right, new_bottom))


def detect_terminal_window(
    image_input: Union[str, Image.Image, io.BytesIO],
    padding: int = 12,
    panel_top_height: int = 34,
) -> Tuple[int, int, int, int]:
    """
    Smart terminal / active-window detection & minimal safe cropping.
    Detects the active window boundary (terminal, text editor, file manager dialog)
    and identifies confusing/empty wallpaper and external OS desktop panels.

    Preserves:
      - Window titlebar & titlebar buttons (close/minimize/maximize)
      - Command prompt (e.g. root@kali:~#, user prompt ┌──)
      - Typed commands & all output text lines / status bars
      - Safe margins/padding around window elements

    Safeguards:
      - If image is not a desktop screenshot (w < 800 or h < 500), returns (0, 0, w, h).
      - Never crops into text lines or prompts.
      - If active window spans >= 85% of width and height, keeps full window between panels.
      - Enforces minimum dimensions: at least 320x240 px.

    Returns (left, top, right, bottom) pixel coordinates.
    """
    opened_here = False
    if isinstance(image_input, (str, io.BytesIO)):
        img = Image.open(image_input)
        opened_here = True
    elif isinstance(image_input, Image.Image):
        img = image_input
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    try:
        w, h = img.size
        # Small dialog or non-desktop screenshot: keep intact
        if w < 800 or h < 500:
            return (0, 0, w, h)

        arr = np.array(img)
        gray = np.array(img.convert("L"))

        # 1. OS desktop panels detection (Kali Linux / Linux XFCE / Windows)
        top_panel_h = panel_top_height
        bottom_panel_y = h - 38

        # In standard 1080p desktop captures, Kali panel is at top (y=0..34)
        has_top_panel = False
        if h >= 600:
            top_std = arr[15, 200 : max(201, w - 200)].std(axis=0).mean()
            if top_std < 55.0:  # Consistent panel across width
                has_top_panel = True

        has_bottom_dock = False
        if h >= 600:
            bot_std = arr[h - 15, 200 : max(201, w - 200)].std(axis=0).mean()
            if bot_std < 40.0:
                has_bottom_dock = True

        panel_top = top_panel_h if has_top_panel else 0
        panel_bottom = bottom_panel_y if has_bottom_dock else h
        h_sub = max(1, panel_bottom - panel_top)

        # 2. Window / Terminal Detection via Titlebar & Window Frame
        # Kali Linux active terminal has a distinct red titlebar: R >= 170, G <= 70, B <= 70
        is_red = (arr[:, :, 0] >= 170) & (arr[:, :, 1] <= 70) & (arr[:, :, 2] <= 70)

        tb_runs = []
        for y in range(panel_top, h // 2):
            row_red = is_red[y, :]
            diff = np.diff(np.concatenate(([False], row_red, [False])).astype(int))
            starts = np.where(diff == 1)[0]
            ends = np.where(diff == -1)[0]
            for s, e in zip(starts, ends):
                if (e - s) >= 250:
                    tb_runs.append((y, s, e, e - s))

        if tb_runs:
            y_min = min(r[0] for r in tb_runs)
            cluster_tb = [r for r in tb_runs if r[0] <= y_min + 30]
            tb_y1 = min(r[0] for r in cluster_tb)
            tb_y2 = max(r[0] for r in cluster_tb)

            longest_run = max(cluster_tb, key=lambda r: r[3])
            run_x1, run_x2 = longest_run[1], longest_run[2]

            # Maximized window check: occupies full or nearly full width
            if (run_x2 - run_x1) >= 0.85 * w or (run_x1 <= 50 and run_x2 >= w - 50):
                return (0, panel_top, w, panel_bottom)

            # Floating / partial window
            bot_runs = []
            for y in range(tb_y2 + 40, h):
                row_red = is_red[y, :]
                diff = np.diff(np.concatenate(([False], row_red, [False])).astype(int))
                starts = np.where(diff == 1)[0]
                ends = np.where(diff == -1)[0]
                for s, e in zip(starts, ends):
                    if (e - s) >= 250:
                        bot_runs.append((y, s, e, e - s))

            win_y2 = panel_bottom
            win_x1 = run_x1
            win_x2 = run_x2

            if bot_runs:
                matching_bot = [
                    r
                    for r in bot_runs
                    if max(0, min(r[2], run_x2) - max(r[1], run_x1)) > 150
                ]
                if matching_bot:
                    best_bot = max(matching_bot, key=lambda r: r[3])
                    win_y2 = best_bot[0]
                    win_x1 = min(win_x1, best_bot[1])
                    win_x2 = max(win_x2, best_bot[2])

            if win_y2 == panel_bottom:
                for y in range(tb_y2 + 40, panel_bottom):
                    slice_dark = arr[y, win_x1:win_x2]
                    is_dark = (
                        (slice_dark[:, 0] >= 15)
                        & (slice_dark[:, 0] <= 65)
                        & (slice_dark[:, 1] >= 15)
                        & (slice_dark[:, 1] <= 65)
                        & (slice_dark[:, 2] >= 20)
                        & (slice_dark[:, 2] <= 75)
                    )
                    if is_dark.mean() < 0.2:
                        win_y2 = y
                        break

            # Check if title text / window body extends left of run_x1
            left_border_x = win_x1
            mid_y = (tb_y1 + win_y2) // 2
            for x in range(run_x1, max(0, run_x1 - 300), -1):
                col_dark = arr[mid_y - 20 : mid_y + 20, x]
                is_dark = (
                    (col_dark[:, 0] >= 15)
                    & (col_dark[:, 0] <= 65)
                    & (col_dark[:, 1] >= 15)
                    & (col_dark[:, 1] <= 65)
                    & (col_dark[:, 2] >= 20)
                    & (col_dark[:, 2] <= 75)
                )
                if is_dark.mean() > 0.8:
                    left_border_x = x
                else:
                    break
            win_x1 = min(win_x1, left_border_x)

            crop_x1 = max(0, win_x1 - padding)
            crop_x2 = min(w, win_x2 + padding)
            crop_y1 = max(panel_top, tb_y1 - padding)
            crop_y2 = min(panel_bottom, win_y2 + padding)

            if crop_x1 <= 45:
                crop_x1 = 0
            if crop_x2 >= w - 45:
                crop_x2 = w
            if crop_y1 - panel_top <= 25:
                crop_y1 = panel_top
            if panel_bottom - crop_y2 <= 30:
                crop_y2 = panel_bottom

            return (int(crop_x1), int(crop_y1), int(crop_x2), int(crop_y2))

        # 3. Fallback: Edge gradient density clustering (for non-red desktops / synthetic)
        diff_h = np.abs(
            gray[panel_top:panel_bottom, 1:].astype(int)
            - gray[panel_top:panel_bottom, :-1].astype(int)
        )
        is_text = np.zeros((h_sub, w), dtype=bool)
        is_text[:, : w - 1] = diff_h > 20
        is_text[:, :4] = False
        is_text[:, max(0, w - 6) :] = False

        # Analyze column text density in 32px blocks
        block_w = 32
        n_bx = max(1, w // block_w)
        col_counts = is_text.sum(axis=0)
        bx_densities = [
            col_counts[b * block_w : min(w, (b + 1) * block_w)].sum() for b in range(n_bx)
        ]
        active_bx = [b for b, cnt in enumerate(bx_densities) if cnt > 120]

        if not active_bx:
            return (0, panel_top, w, panel_bottom)

        min_bx = min(active_bx)
        max_bx = max(active_bx)

        crop_x1 = max(0, min_bx * block_w - padding)
        crop_x2 = min(w, (max_bx + 1) * block_w + padding)

        active_in_x = is_text[:, max(0, min_bx * block_w) : min(w, (max_bx + 1) * block_w)]
        row_counts = active_in_x.sum(axis=1)
        block_h = 20
        n_by = max(1, h_sub // block_h)
        by_densities = [
            row_counts[b * block_h : min(h_sub, (b + 1) * block_h)].sum() for b in range(n_by)
        ]
        active_by = [b for b, cnt in enumerate(by_densities) if cnt > 60]

        crop_y1 = panel_top
        if active_by:
            crop_y2 = min(panel_bottom, (max(active_by) + 1) * block_h + panel_top + padding)
        else:
            crop_y2 = panel_bottom

        if crop_x1 <= 45:
            crop_x1 = 0
        if crop_x2 >= w - 45:
            crop_x2 = w
        if crop_y1 - panel_top <= 25:
            crop_y1 = panel_top
        if panel_bottom - crop_y2 <= 30:
            crop_y2 = panel_bottom

        # Safeguard: minimum dimensions
        final_w = max(crop_x2 - crop_x1, 320)
        final_h = max(crop_y2 - crop_y1, 240)
        crop_x2 = min(w, crop_x1 + final_w)
        crop_y2 = min(h, crop_y1 + final_h)

        return (int(crop_x1), int(crop_y1), int(crop_x2), int(crop_y2))
    finally:
        if opened_here:
            img.close()


def crop_terminal_window(
    image: Image.Image,
    padding: int = 12,
    fallback_full: bool = True,
) -> Image.Image:
    """
    Crops image to the detected terminal / active window boundary with safe padding.
    Non-destructive; does not modify source image.
    """
    box = detect_terminal_window(image, padding=padding)
    return image.crop(box)


def adjust_aspect_ratio(
    image: Image.Image,
    target_aspect: float,
    mode: str = "pad",
    fill_color: Union[str, Tuple[int, ...]] = "white",
) -> Image.Image:
    """
    Adjusts image to target aspect ratio (width / height).
    mode='pad': Pillarboxes or letterboxes with fill_color (no distortion/crop).
    mode='crop': Center-crops the excess dimension to fit target_aspect.
    """
    if target_aspect <= 0:
        raise ValueError(f"Target aspect ratio must be positive, got {target_aspect}")

    mode = mode.lower()
    if mode not in ("pad", "crop"):
        raise ValueError(f"Unsupported aspect mode: '{mode}'. Must be 'pad' or 'crop'.")

    w, h = image.size
    current_aspect = w / h

    # If already within 0.1% of target, return copy
    if abs(current_aspect - target_aspect) < 0.001:
        return image.copy()

    if mode == "pad":
        # Resolve fill color
        if isinstance(fill_color, str):
            color_map = {
                "white": (255, 255, 255),
                "black": (0, 0, 0),
                "gray": (128, 128, 128),
                "grey": (128, 128, 128),
            }
            fill_rgb = color_map.get(fill_color.lower(), (255, 255, 255))
        elif isinstance(fill_color, (tuple, list)):
            fill_rgb = tuple(int(c) for c in fill_color[:3])
        else:
            fill_rgb = (255, 255, 255)

        if current_aspect > target_aspect:
            # Image is wider than target: add vertical letterboxing (top and bottom)
            new_w = w
            new_h = int(round(w / target_aspect))
            canvas_mode = "RGBA" if image.mode == "RGBA" else "RGB"
            canvas_fill = fill_rgb + (255,) if canvas_mode == "RGBA" else fill_rgb
            canvas = Image.new(canvas_mode, (new_w, new_h), canvas_fill)
            offset_y = (new_h - h) // 2
            canvas.paste(image, (0, offset_y))
            return canvas
        else:
            # Image is taller than target: add horizontal pillarboxing (left and right)
            new_h = h
            new_w = int(round(h * target_aspect))
            canvas_mode = "RGBA" if image.mode == "RGBA" else "RGB"
            canvas_fill = fill_rgb + (255,) if canvas_mode == "RGBA" else fill_rgb
            canvas = Image.new(canvas_mode, (new_w, new_h), canvas_fill)
            offset_x = (new_w - w) // 2
            canvas.paste(image, (offset_x, 0))
            return canvas

    elif mode == "crop":
        if current_aspect > target_aspect:
            # Image is wider than target: center crop width
            desired_w = max(1, min(w, int(round(h * target_aspect))))
            offset_x = (w - desired_w) // 2
            return image.crop((offset_x, 0, offset_x + desired_w, h))
        else:
            # Image is taller than target: center crop height
            desired_h = max(1, min(h, int(round(w / target_aspect))))
            offset_y = (h - desired_h) // 2
            return image.crop((0, offset_y, w, offset_y + desired_h))

    return image.copy()


def adjust_image(
    image: Image.Image,
    brightness: float = 1.0,
    contrast: float = 1.0,
    sharpness: float = 1.0,
    color: float = 1.0,
) -> Image.Image:
    """
    Enhances visual quality of technical screenshots using PIL.ImageEnhance.
    Factors > 1.0 increase the property; 1.0 leaves unchanged.
    """
    res = image.copy()

    # Ensure in a color mode suitable for enhancement
    if res.mode not in ("RGB", "RGBA", "L"):
        res = res.convert("RGB")

    if brightness != 1.0:
        enhancer = ImageEnhance.Brightness(res)
        res = enhancer.enhance(brightness)

    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(res)
        res = enhancer.enhance(contrast)

    if color != 1.0 and res.mode in ("RGB", "RGBA"):
        enhancer = ImageEnhance.Color(res)
        res = enhancer.enhance(color)

    if sharpness != 1.0:
        enhancer = ImageEnhance.Sharpness(res)
        res = enhancer.enhance(sharpness)

    return res


def add_border(
    image: Image.Image,
    width: int = 1,
    color: Union[str, Tuple[int, ...]] = "black",
) -> Image.Image:
    """
    Applies crisp uniform border around image using ImageOps.expand.
    """
    if width <= 0:
        return image.copy()

    if isinstance(color, str):
        color_val = color
    elif isinstance(color, (tuple, list)):
        color_val = tuple(int(c) for c in color)
    else:
        color_val = "black"

    # Expand handles RGB, RGBA, L modes cleanly
    return ImageOps.expand(image, border=width, fill=color_val)


def prepare_screenshot(
    image_input: Union[str, Image.Image, io.BytesIO],
    output_path: Optional[str] = None,
    auto_crop_bg: bool = False,
    crop_terminal: bool = False,
    crop: Optional[Union[bool, str, Tuple[Union[int, float], ...], List[Union[int, float]]]] = None,
    crop_padding: int = 12,
    crop_box_coords: Optional[Tuple[Union[int, float], ...]] = None,
    normalized_box: bool = False,
    margins: Optional[Tuple[int, int, int, int]] = None,
    target_aspect: Optional[float] = None,
    aspect_mode: str = "pad",
    brightness: float = 1.0,
    contrast: float = 1.0,
    sharpness: float = 1.0,
    border_width: int = 0,
    border_color: str = "black",
    max_dimensions: Optional[Tuple[int, int]] = None,
) -> Image.Image:
    """
    Unified high-level preparation pipeline for screenshot insertion:
    1. Loads image and converts palette/transparency to RGB/RGBA.
    2. Applies smart terminal cropping if requested (crop="auto_terminal" or crop_terminal=True).
    3. Applies explicit crop_box, normalized crop, or margins if requested.
    4. Applies auto_crop if auto_crop_bg=True.
    5. Adjusts aspect ratio if target_aspect is specified.
    6. Applies visual adjustments (contrast, brightness, sharpness).
    7. Proportions/resizes inside max_dimensions if provided (LANCZOS).
    8. Applies border if border_width > 0.
    9. Saves to output_path if provided, returning prepared PIL Image.
    """
    opened_here = False
    if isinstance(image_input, (str, io.BytesIO)):
        img = Image.open(image_input)
        opened_here = True
    elif isinstance(image_input, Image.Image):
        img = image_input.copy()
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    try:
        # Convert palette/transparency to standard RGB/RGBA
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "transparency" in img.info else "RGB")

        # Step 2: Smart Terminal / Window Cropping (Recoverable & Non-destructive)
        should_crop_terminal = crop_terminal
        if isinstance(crop, str) and crop.lower() in ("auto_terminal", "auto", "terminal"):
            should_crop_terminal = True
        elif crop is True:
            should_crop_terminal = True

        if should_crop_terminal:
            img = crop_terminal_window(img, padding=crop_padding)
        elif isinstance(crop, (list, tuple)) and len(crop) == 4:
            img = crop_box(img, tuple(crop), normalized=normalized_box)

        # Step 3: Explicit crop box
        if crop_box_coords is not None:
            img = crop_box(img, crop_box_coords, normalized=normalized_box)

        # Step 4: Margin cropping
        if margins is not None:
            top, right, bottom, left = margins
            img = crop_margins(img, top=top, right=right, bottom=bottom, left=left)

        # Step 5: Auto-crop uniform whitespace / background
        if auto_crop_bg:
            img = auto_crop(img, bg_color="auto", tolerance=10, padding=0)

        # Step 6: Aspect ratio adjustment
        if target_aspect is not None and target_aspect > 0:
            img = adjust_aspect_ratio(img, target_aspect=target_aspect, mode=aspect_mode)

        # Step 7: Visual enhancements
        if brightness != 1.0 or contrast != 1.0 or sharpness != 1.0:
            img = adjust_image(img, brightness=brightness, contrast=contrast, sharpness=sharpness)

        # Step 8: Resize to max_dimensions preserving aspect ratio
        if max_dimensions is not None:
            max_w, max_h = max_dimensions
            if max_w > 0 and max_h > 0:
                cur_w, cur_h = img.size
                scale = min(max_w / cur_w, max_h / cur_h)
                if scale < 1.0:
                    new_size = (max(1, int(round(cur_w * scale))), max(1, int(round(cur_h * scale))))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Step 9: Optional border
        if border_width > 0:
            img = add_border(img, width=border_width, color=border_color)

        # Step 10: Save if output_path specified
        if output_path:
            out_dir = os.path.dirname(os.path.abspath(output_path))
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            # Ensure saving RGBA as PNG or RGB as JPEG/PNG
            if output_path.lower().endswith((".jpg", ".jpeg")) and img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                bg.save(output_path, quality=95)
            else:
                img.save(output_path)

        return img
    finally:
        if opened_here:
            pass  # return img object is open in memory


def batch_process_images(
    input_dir: str,
    output_dir: str,
    operations: Optional[Dict[str, Any]] = None,
    pattern: str = "*.*",
    recursive: bool = False,
) -> Dict[str, Any]:
    """
    Processes all matching images from input_dir and saves results in output_dir.
    Returns processing summary: {'total': int, 'success': int, 'failed': int, 'files': List[str], 'errors': Dict[str, str]}.
    """
    if not os.path.isdir(input_dir):
        raise ValueError(f"Input directory does not exist: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)
    ops = operations or {}

    valid_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
    discovered_files: List[str] = []

    if recursive:
        for root, _, files in os.walk(input_dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in valid_extensions and fnmatch.fnmatch(f.lower(), pattern.lower()):
                    discovered_files.append(os.path.join(root, f))
    else:
        for f in os.listdir(input_dir):
            fp = os.path.join(input_dir, f)
            if os.path.isfile(fp):
                ext = os.path.splitext(f)[1].lower()
                if ext in valid_extensions and fnmatch.fnmatch(f.lower(), pattern.lower()):
                    discovered_files.append(fp)

    discovered_files.sort()
    success_count = 0
    failed_count = 0
    processed_files: List[str] = []
    errors: Dict[str, str] = {}

    for src_path in discovered_files:
        try:
            rel_name = os.path.relpath(src_path, input_dir)
            dest_path = os.path.join(output_dir, rel_name)
            dest_dir = os.path.dirname(dest_path)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)

            prepare_screenshot(
                image_input=src_path,
                output_path=dest_path,
                auto_crop_bg=ops.get("auto_crop_bg", False),
                crop_box_coords=ops.get("crop_box_coords"),
                normalized_box=ops.get("normalized_box", False),
                margins=ops.get("margins"),
                target_aspect=ops.get("target_aspect"),
                aspect_mode=ops.get("aspect_mode", "pad"),
                brightness=ops.get("brightness", 1.0),
                contrast=ops.get("contrast", 1.0),
                sharpness=ops.get("sharpness", 1.0),
                border_width=ops.get("border_width", 0),
                border_color=ops.get("border_color", "black"),
                max_dimensions=ops.get("max_dimensions"),
            )
            success_count += 1
            processed_files.append(dest_path)
        except Exception as e:
            failed_count += 1
            errors[src_path] = str(e)

    return {
        "total": len(discovered_files),
        "success": success_count,
        "failed": failed_count,
        "files": processed_files,
        "errors": errors,
    }


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Modular Image Processing & Cropping Utilities for Project LabForge."
    )
    # Single image mode
    parser.add_argument("--input", "-i", help="Input image file path")
    parser.add_argument("--output", "-o", help="Output image file path")
    parser.add_argument("--inspect", action="store_true", help="Print image metadata and exit")

    # Cropping options
    parser.add_argument("--auto-crop", action="store_true", help="Auto-crop outer uniform background")
    parser.add_argument("--crop-terminal", action="store_true", help="Smart auto-detect and crop to terminal/window")
    parser.add_argument("--no-crop", action="store_true", help="Explicitly disable cropping (recover original)")
    parser.add_argument("--tolerance", type=int, default=10, help="Tolerance for auto-crop diff (default: 10)")
    parser.add_argument("--padding", type=int, default=0, help="Padding in px for auto-crop (default: 0)")
    parser.add_argument(
        "--crop-box",
        nargs=4,
        type=float,
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="Explicit crop box coordinates",
    )
    parser.add_argument("--normalized-box", action="store_true", help="Treat crop-box coordinates as [0.0, 1.0]")
    parser.add_argument(
        "--crop-margins",
        nargs=4,
        type=int,
        metavar=("TOP", "RIGHT", "BOTTOM", "LEFT"),
        help="Trim margins in pixels from edges (top, right, bottom, left)",
    )

    # Aspect ratio
    parser.add_argument("--aspect-ratio", type=float, help="Target aspect ratio (width / height, e.g. 1.45)")
    parser.add_argument(
        "--aspect-mode",
        choices=["pad", "crop"],
        default="pad",
        help="Aspect ratio adjustment mode: 'pad' (default) or 'crop'",
    )

    # Adjustments
    parser.add_argument("--brightness", type=float, default=1.0, help="Brightness factor (1.0 = unchanged)")
    parser.add_argument("--contrast", type=float, default=1.0, help="Contrast factor (1.0 = unchanged)")
    parser.add_argument("--sharpness", type=float, default=1.0, help="Sharpness factor (1.0 = unchanged)")

    # Border
    parser.add_argument("--border-width", type=int, default=0, help="Border width in pixels (default: 0)")
    parser.add_argument("--border-color", default="black", help="Border color (default: 'black')")

    # Batch mode
    parser.add_argument("--batch-input", help="Directory of images to batch process")
    parser.add_argument("--batch-output", help="Directory where batch results will be written")
    parser.add_argument("--recursive", action="store_true", help="Recursively traverse batch directory")
    parser.add_argument("--pattern", default="*.*", help="File pattern for batch processing (default: '*.*')")

    # Output formatting
    parser.add_argument("--json", action="store_true", help="Print summary/results as JSON")

    return parser.parse_args(args)


def main() -> int:
    args = parse_args()

    # Case 1: Inspect image
    if args.inspect:
        if not args.input:
            print("Error: --inspect requires --input <path>", file=sys.stderr)
            return 1
        meta = get_image_metadata(args.input)
        if args.json:
            print(json.dumps(meta, indent=2))
        else:
            print("Image Metadata:")
            for k, v in meta.items():
                print(f"  {k}: {v}")
        return 0

    # Case 2: Batch processing
    if args.batch_input and args.batch_output:
        operations: Dict[str, Any] = {
            "auto_crop_bg": args.auto_crop,
            "crop_terminal": args.crop_terminal and not args.no_crop,
            "brightness": args.brightness,
            "contrast": args.contrast,
            "sharpness": args.sharpness,
            "border_width": args.border_width,
            "border_color": args.border_color,
            "aspect_mode": args.aspect_mode,
        }
        if args.crop_box and not args.no_crop:
            operations["crop_box_coords"] = tuple(args.crop_box)
            operations["normalized_box"] = args.normalized_box
        if args.crop_margins and not args.no_crop:
            operations["margins"] = tuple(args.crop_margins)
        if args.aspect_ratio:
            operations["target_aspect"] = args.aspect_ratio

        result = batch_process_images(
            input_dir=args.batch_input,
            output_dir=args.batch_output,
            operations=operations,
            pattern=args.pattern,
            recursive=args.recursive,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(
                f"Batch processed {result['total']} images: {result['success']} succeeded, {result['failed']} failed."
            )
            if result["failed"] > 0:
                for f, err in result["errors"].items():
                    print(f"  Error on {f}: {err}", file=sys.stderr)
        return 0 if result["failed"] == 0 else 1

    # Case 3: Single image processing
    if args.input:
        if not args.output:
            print("Error: Single image processing requires --output <path>", file=sys.stderr)
            return 1

        crop_box_coords = tuple(args.crop_box) if (args.crop_box and not args.no_crop) else None
        margins = tuple(args.crop_margins) if (args.crop_margins and not args.no_crop) else None
        should_crop_term = args.crop_terminal and not args.no_crop

        img = prepare_screenshot(
            image_input=args.input,
            output_path=args.output,
            auto_crop_bg=args.auto_crop,
            crop_terminal=should_crop_term,
            crop_box_coords=crop_box_coords,
            normalized_box=args.normalized_box,
            margins=margins,
            target_aspect=args.aspect_ratio,
            aspect_mode=args.aspect_mode,
            brightness=args.brightness,
            contrast=args.contrast,
            sharpness=args.sharpness,
            border_width=args.border_width,
            border_color=args.border_color,
        )
        if args.json:
            meta = get_image_metadata(img)
            meta["output_path"] = args.output
            print(json.dumps(meta, indent=2))
        else:
            print(f"Prepared screenshot saved to: {args.output}")
        return 0

    print("No operation specified. Use --help for usage instructions.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
