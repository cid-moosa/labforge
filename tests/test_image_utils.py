"""
tests/test_image_utils.py
Comprehensive unit test suite for scripts/image_utils.py (Requirement R1).
Executes strictly in isolated temporary directories using synthetic test images.
"""

import io
import os
import shutil
import tempfile
import unittest
from PIL import Image

from scripts.image_utils import (
    add_border,
    adjust_aspect_ratio,
    adjust_image,
    auto_crop,
    batch_process_images,
    crop_box,
    crop_margins,
    crop_terminal_window,
    detect_terminal_window,
    get_image_metadata,
    main as image_utils_main,
    parse_args,
    prepare_screenshot,
)
from tests.helpers.integrity import (
    BASELINE_ENGINE_SHA256,
    LOCKED_ENGINE_FILE,
    assert_safe_test_path,
    hash_file,
)
from tests.helpers.sample_factory import create_synthetic_image


class TestImageUtils(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_img_utils_")
        assert_safe_test_path(self.temp_dir)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_image_metadata(self):
        # 1. Dialog image
        dialog_path = os.path.join(self.temp_dir, "dialog.png")
        create_synthetic_image(dialog_path, width=600, height=450, image_type="dialog")
        meta = get_image_metadata(dialog_path)

        self.assertEqual(meta["width_px"], 600)
        self.assertEqual(meta["height_px"], 450)
        self.assertAlmostEqual(meta["aspect_ratio"], 1.3333, places=2)
        self.assertEqual(meta["classification"], "dialog_box")
        self.assertGreater(meta["size_kb"], 0.0)

        # 2. Widescreen image
        ws_path = os.path.join(self.temp_dir, "ws.png")
        create_synthetic_image(ws_path, image_type="widescreen")
        meta_ws = get_image_metadata(ws_path)

        self.assertEqual(meta_ws["width_px"], 1920)
        self.assertEqual(meta_ws["height_px"], 1080)
        self.assertGreaterEqual(meta_ws["aspect_ratio"], 1.45)
        self.assertEqual(meta_ws["classification"], "widescreen")

        # 3. In-memory PIL Image
        mem_img = Image.new("RGB", (400, 200), (100, 100, 100))
        meta_mem = get_image_metadata(mem_img)
        self.assertEqual(meta_mem["width_px"], 400)
        self.assertEqual(meta_mem["height_px"], 200)
        self.assertEqual(meta_mem["classification"], "widescreen")

    def test_auto_crop_white_border(self):
        img_path = os.path.join(self.temp_dir, "padded_white.png")
        create_synthetic_image(img_path, width=800, height=600, image_type="padded_white", margin_px=100)

        with Image.open(img_path) as img:
            orig_w, orig_h = img.size
            cropped = auto_crop(img, bg_color="white", tolerance=5, padding=0)
            cw, ch = cropped.size

            # The 100px border around an 800x600 image leaves ~600x400 content area
            self.assertLess(cw, orig_w)
            self.assertLess(ch, orig_h)
            self.assertAlmostEqual(cw, 600, delta=10)
            self.assertAlmostEqual(ch, 400, delta=10)

            # Test with padding=10
            cropped_pad = auto_crop(img, bg_color="auto", tolerance=5, padding=10)
            pw, ph = cropped_pad.size
            self.assertEqual(pw, cw + 20)
            self.assertEqual(ph, ch + 20)

    def test_auto_crop_dark_border(self):
        img_path = os.path.join(self.temp_dir, "padded_black.png")
        create_synthetic_image(img_path, width=700, height=500, image_type="padded_black", margin_px=80)

        with Image.open(img_path) as img:
            cropped = auto_crop(img, bg_color="auto", tolerance=5)
            cw, ch = cropped.size
            self.assertLess(cw, 700)
            self.assertLess(ch, 500)
            self.assertAlmostEqual(cw, 700 - 160, delta=10)
            self.assertAlmostEqual(ch, 500 - 160, delta=10)

    def test_auto_crop_uniform_image(self):
        # A completely uniform image should not crash or return a 0-pixel image
        uniform = Image.new("RGB", (300, 300), (255, 255, 255))
        res = auto_crop(uniform, bg_color="auto")
        self.assertEqual(res.size, (300, 300))

    def test_auto_crop_invalid_args(self):
        img = Image.new("RGB", (100, 100), (200, 200, 200))
        with self.assertRaises(ValueError):
            auto_crop(img, tolerance=-1)
        with self.assertRaises(ValueError):
            auto_crop(img, padding=-5)

    def test_crop_box_pixels(self):
        img = Image.new("RGB", (1000, 1000), (255, 255, 255))
        cropped = crop_box(img, (100, 150, 500, 450), normalized=False)
        self.assertEqual(cropped.size, (400, 300))

    def test_crop_box_normalized(self):
        img = Image.new("RGB", (1000, 800), (255, 255, 255))
        # 0.1 to 0.5 of width (1000) is 100 to 500 -> 400px
        # 0.2 to 0.6 of height (800) is 160 to 480 -> 320px
        cropped = crop_box(img, (0.1, 0.2, 0.5, 0.6), normalized=True)
        self.assertEqual(cropped.size, (400, 320))

    def test_crop_box_validation(self):
        img = Image.new("RGB", (500, 500), (255, 255, 255))
        # left >= right
        with self.assertRaises(ValueError):
            crop_box(img, (300, 100, 200, 400))
        # top >= bottom
        with self.assertRaises(ValueError):
            crop_box(img, (100, 400, 300, 200))
        # out of bounds
        with self.assertRaises(ValueError):
            crop_box(img, (0, 0, 600, 500))
        # invalid normalized
        with self.assertRaises(ValueError):
            crop_box(img, (-0.1, 0.2, 0.5, 0.6), normalized=True)

    def test_crop_margins(self):
        img = Image.new("RGB", (1000, 800), (255, 255, 255))
        cropped = crop_margins(img, top=40, right=30, bottom=50, left=20)
        # width: 1000 - 20 - 30 = 950
        # height: 800 - 40 - 50 = 710
        self.assertEqual(cropped.size, (950, 710))

    def test_crop_margins_invalid(self):
        img = Image.new("RGB", (500, 400), (255, 255, 255))
        with self.assertRaises(ValueError):
            crop_margins(img, top=-10)
        with self.assertRaises(ValueError):
            crop_margins(img, left=300, right=300)

    def test_adjust_aspect_ratio_pad(self):
        # Image is 800x600 (aspect 1.333). Target aspect 1.6 (wider)
        # In pad mode, vertical pillarboxing or letterboxing:
        # Since current aspect 1.333 < target 1.6, image is taller than target:
        # width will be expanded: new_w = int(round(600 * 1.6)) = 960.
        img = Image.new("RGB", (800, 600), (200, 50, 50))
        adjusted = adjust_aspect_ratio(img, target_aspect=1.6, mode="pad", fill_color="white")
        w, h = adjusted.size
        self.assertEqual(h, 600)
        self.assertEqual(w, 960)
        self.assertAlmostEqual(w / h, 1.6, places=2)
        # Check pillarbox margin pixel is white
        self.assertEqual(adjusted.getpixel((10, 300)), (255, 255, 255))

    def test_adjust_aspect_ratio_crop(self):
        # Image is 1000x500 (aspect 2.0). Target aspect 1.5.
        # In crop mode, center crop width: new_w = int(round(500 * 1.5)) = 750.
        img = Image.new("RGB", (1000, 500), (50, 200, 50))
        adjusted = adjust_aspect_ratio(img, target_aspect=1.5, mode="crop")
        w, h = adjusted.size
        self.assertEqual(w, 750)
        self.assertEqual(h, 500)
        self.assertAlmostEqual(w / h, 1.5, places=2)

    def test_adjust_image(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        # Brightness
        b_img = adjust_image(img, brightness=1.5)
        self.assertGreater(b_img.getpixel((50, 50))[0], 128)
        # Contrast
        c_img = adjust_image(img, contrast=1.2)
        self.assertIsNotNone(c_img)
        # Sharpness
        s_img = adjust_image(img, sharpness=1.5)
        self.assertIsNotNone(s_img)

    def test_add_border(self):
        img = Image.new("RGB", (400, 300), (255, 255, 255))
        bordered = add_border(img, width=2, color="black")
        self.assertEqual(bordered.size, (404, 304))
        # Top-left corner must be black
        self.assertEqual(bordered.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(bordered.getpixel((1, 1)), (0, 0, 0))
        # Inside content must be white
        self.assertEqual(bordered.getpixel((2, 2)), (255, 255, 255))

    def test_prepare_screenshot_pipeline(self):
        src_path = os.path.join(self.temp_dir, "raw_capture.png")
        out_path = os.path.join(self.temp_dir, "prepared.png")
        create_synthetic_image(src_path, width=1000, height=800, image_type="padded_white", margin_px=100)

        res = prepare_screenshot(
            image_input=src_path,
            output_path=out_path,
            auto_crop_bg=True,
            margins=(10, 10, 10, 10),
            target_aspect=1.45,
            aspect_mode="pad",
            brightness=1.1,
            contrast=1.1,
            border_width=1,
            border_color="black",
            max_dimensions=(600, 400),
        )

        self.assertTrue(os.path.isfile(out_path))
        self.assertLessEqual(res.width, 602)
        self.assertLessEqual(res.height, 402)
        self.assertEqual(res.getpixel((0, 0)), (0, 0, 0))  # 1px black border

    def test_prepare_screenshot_rgba_to_jpeg(self):
        rgba_path = os.path.join(self.temp_dir, "rgba.png")
        jpg_out = os.path.join(self.temp_dir, "output.jpg")
        create_synthetic_image(rgba_path, image_type="rgba")

        res = prepare_screenshot(rgba_path, output_path=jpg_out)
        self.assertTrue(os.path.isfile(jpg_out))
        self.assertEqual(res.mode, "RGBA")  # returned in-memory object

        # Loaded JPEG should be RGB
        with Image.open(jpg_out) as saved_jpg:
            self.assertEqual(saved_jpg.mode, "RGB")

    def test_batch_process_images(self):
        batch_in = os.path.join(self.temp_dir, "batch_in")
        batch_out = os.path.join(self.temp_dir, "batch_out")
        os.makedirs(batch_in, exist_ok=True)

        for i in range(3):
            create_synthetic_image(os.path.join(batch_in, f"img_{i}.png"), width=400, height=300)

        summary = batch_process_images(
            input_dir=batch_in,
            output_dir=batch_out,
            operations={"border_width": 1, "contrast": 1.1},
        )

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["success"], 3)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(len(summary["files"]), 3)

        for f in summary["files"]:
            self.assertTrue(os.path.isfile(f))

    def test_cli_operations(self):
        img_path = os.path.join(self.temp_dir, "cli_test.png")
        out_path = os.path.join(self.temp_dir, "cli_out.png")
        create_synthetic_image(img_path, width=500, height=400)

        # 1. Test CLI Inspect
        args = parse_args(["--input", img_path, "--inspect"])
        self.assertTrue(args.inspect)
        self.assertEqual(args.input, img_path)

        # 2. Test CLI Processing
        args_proc = parse_args([
            "--input", img_path,
            "--output", out_path,
            "--contrast", "1.2",
            "--border-width", "1",
        ])
        self.assertEqual(args_proc.contrast, 1.2)
        self.assertEqual(args_proc.border_width, 1)

    def test_prepare_screenshot_downscale_min_dimension_clamping(self):
        # Defect 1 Regression: Downscaling extreme aspect ratio images must clamp to min dimension >= 1
        img_tall = Image.new("RGB", (1, 500), (255, 0, 0))
        res_tall = prepare_screenshot(img_tall, max_dimensions=(10, 50))
        self.assertGreaterEqual(res_tall.width, 1)
        self.assertGreaterEqual(res_tall.height, 1)
        self.assertEqual(res_tall.size, (1, 50))

        img_wide = Image.new("RGB", (500, 1), (0, 255, 0))
        res_wide = prepare_screenshot(img_wide, max_dimensions=(50, 10))
        self.assertGreaterEqual(res_wide.width, 1)
        self.assertGreaterEqual(res_wide.height, 1)
        self.assertEqual(res_wide.size, (50, 1))

    def test_adjust_aspect_ratio_crop_min_dimension_clamping(self):
        # Defect 2 Regression: Center crop must clamp desired dimensions to >= 1 and <= dimension
        img_wide = Image.new("RGB", (2, 1), (0, 0, 255))
        cropped_w = adjust_aspect_ratio(img_wide, target_aspect=0.2, mode="crop")
        self.assertEqual(cropped_w.size, (1, 1))
        # Ensure image is valid and writable
        save_path_w = os.path.join(self.temp_dir, "crop_w.png")
        cropped_w.save(save_path_w)
        self.assertTrue(os.path.isfile(save_path_w))

        img_tall = Image.new("RGB", (1, 2), (255, 255, 0))
        cropped_h = adjust_aspect_ratio(img_tall, target_aspect=3.0, mode="crop")
        self.assertEqual(cropped_h.size, (1, 1))
        save_path_h = os.path.join(self.temp_dir, "crop_h.png")
        cropped_h.save(save_path_h)
        self.assertTrue(os.path.isfile(save_path_h))

    def test_batch_process_images_pattern_filtering(self):
        # Defect 3 Regression: batch_process_images must honor pattern parameter
        batch_in = os.path.join(self.temp_dir, "batch_pattern_in")
        batch_out_png = os.path.join(self.temp_dir, "batch_pattern_out_png")
        batch_out_jpg = os.path.join(self.temp_dir, "batch_pattern_out_jpg")
        os.makedirs(batch_in, exist_ok=True)

        Image.new("RGB", (20, 20), (255, 0, 0)).save(os.path.join(batch_in, "doc1.png"))
        Image.new("RGB", (20, 20), (0, 255, 0)).save(os.path.join(batch_in, "doc2.png"))
        Image.new("RGB", (20, 20), (0, 0, 255)).save(os.path.join(batch_in, "photo.jpg"))
        Image.new("RGB", (20, 20), (128, 128, 128)).save(os.path.join(batch_in, "notes.bmp"))

        # Filter *.png
        res_png = batch_process_images(batch_in, batch_out_png, pattern="*.png")
        self.assertEqual(res_png["total"], 2)
        self.assertEqual(res_png["success"], 2)
        processed_png_names = [os.path.basename(f) for f in res_png["files"]]
        self.assertEqual(sorted(processed_png_names), ["doc1.png", "doc2.png"])

        # Filter case-insensitive *.JPG
        res_jpg = batch_process_images(batch_in, batch_out_jpg, pattern="*.JPG")
        self.assertEqual(res_jpg["total"], 1)
        self.assertEqual(res_jpg["success"], 1)
        processed_jpg_names = [os.path.basename(f) for f in res_jpg["files"]]
        self.assertEqual(processed_jpg_names, ["photo.jpg"])

    def test_detect_and_crop_terminal_window_synthetic(self):
        # Create a synthetic 1920x1080 desktop with a terminal window on the left
        img = Image.new("RGB", (1920, 1080), (15, 23, 30))  # dark desktop wallpaper
        # Top panel at y=0..34
        for y in range(34):
            for x in range(1920):
                img.putpixel((x, y), (30, 30, 30))
        # Draw terminal text content on left: x in [50..800], y in [100..600]
        for y in range(100, 600, 10):
            for x in range(50, 800, 4):
                img.putpixel((x, y), (220, 220, 220))

        box = detect_terminal_window(img, padding=12)
        # Should crop from x1=0 (prompt snap rule), y1=34 (top panel snap rule)
        self.assertEqual(box[0], 0)
        self.assertEqual(box[1], 34)
        self.assertGreaterEqual(box[2], 800)  # encompasses text width
        self.assertGreaterEqual(box[3], 600)  # encompasses text height

        cropped = crop_terminal_window(img, padding=12)
        self.assertEqual(cropped.size, (box[2] - box[0], box[3] - box[1]))
        self.assertLess(cropped.width, 1920)

    def test_detect_terminal_window_read_only_and_preservation(self):
        real_img_path = "input/lab 6/Screenshot_2026-11-18_04_15_09.png"
        if os.path.isfile(real_img_path):
            hash_before = hash_file(real_img_path)
            with Image.open(real_img_path) as img:
                box = detect_terminal_window(img)
                self.assertEqual(box, (900, 34, 1920, 566))
                cropped = crop_terminal_window(img)
                self.assertEqual(cropped.size, (1020, 532))

            # SourceGuard verification: input file on disk must never be modified
            hash_after = hash_file(real_img_path)
            self.assertEqual(hash_before, hash_after, "Source file in input/ was altered!")

    def test_prepare_screenshot_recoverability_and_toggling(self):
        # Verify that crop can be enabled ("auto_terminal" or True), custom cropped, or completely undone (crop=False)
        real_img_path = "input/lab 6/Screenshot_2026-11-18_04_15_09.png"
        if os.path.isfile(real_img_path):
            with Image.open(real_img_path) as img:
                orig_w, orig_h = img.size

                # 1. Terminal crop enabled
                res_crop = prepare_screenshot(img, crop="auto_terminal", border_width=1)
                # Cropped to 1020x532 + 2px border = 1022x534
                self.assertEqual(res_crop.size, (1022, 534))

                # 2. Recoverability / Undo: setting crop=False restores full original resolution
                res_undo = prepare_screenshot(img, crop=False, border_width=1)
                self.assertEqual(res_undo.size, (orig_w + 2, orig_h + 2))

                # 3. Explicit crop box
                res_box = prepare_screenshot(img, crop=[100, 50, 500, 400], border_width=1)
                self.assertEqual(res_box.size, (402, 352))

    def test_cli_terminal_crop_options(self):
        img_path = os.path.join(self.temp_dir, "cli_crop.png")
        create_synthetic_image(img_path, width=400, height=300)

        args_crop = parse_args(["--input", img_path, "--crop-terminal"])
        self.assertTrue(args_crop.crop_terminal)
        self.assertFalse(args_crop.no_crop)

        args_no_crop = parse_args(["--input", img_path, "--no-crop"])
        self.assertTrue(args_no_crop.no_crop)
        self.assertFalse(args_crop.no_crop)

    def test_engine_immutability(self):
        # Verify that scripts/labforge_engine.py is 100% untouched
        self.assertTrue(os.path.isfile(LOCKED_ENGINE_FILE))
        current_hash = hash_file(LOCKED_ENGINE_FILE)
        self.assertEqual(
            current_hash,
            BASELINE_ENGINE_SHA256,
            "Integrity violation: scripts/labforge_engine.py was altered!",
        )


if __name__ == "__main__":
    unittest.main()
