# -*- coding: utf-8 -*-
import os
import time
import glob

import numpy as np
from PIL import Image as PILImage

from fpdf import FPDF

from io import BytesIO

import folder_paths

_PAGE_SIZES = ["A4", "Letter", "A3", "自适应"]
_ORIENTATIONS = ["纵向", "横向"]
_IMAGE_FITS = ["居中留白", "铺满"]

_ORIENTATION_MAP = {"纵向": "P", "横向": "L"}
_FIT_MAP = {"居中留白": "contain", "铺满": "cover"}

_STANDARD_SIZES = {
    "A4": (210, 297),
    "A3": (297, 420),
    "Letter": (215.9, 279.4),
}


def _compute_page_size(yemian_val, fangxiang_val, first_image):
    if yemian_val == "自适应":
        first_w, first_h = first_image.size
        aspect = first_w / first_h
        orient_code = _ORIENTATION_MAP.get(fangxiang_val, "P")
        if orient_code == "P":
            base_h = 297
            base_w = base_h * aspect
            if base_w > 210:
                base_w = 210
                base_h = base_w / aspect
        else:
            base_w = 297
            base_h = base_w / aspect
            if base_h > 210:
                base_h = 210
                base_w = base_h * aspect
        return round(base_w, 1), round(base_h, 1)
    else:
        std_w, std_h = _STANDARD_SIZES[yemian_val]
        orient_code = _ORIENTATION_MAP.get(fangxiang_val, "P")
        if orient_code == "L":
            return std_h, std_w
        else:
            return std_w, std_h

def _add_page_from_pil(pdf, pil_img, page_w, page_h, fit_code, quality=85):
    pdf.add_page()
    img_w, img_h = pil_img.size
    margin = 5
    draw_w = page_w - 2 * margin
    draw_h = page_h - 2 * margin
    img_aspect = img_w / img_h
    draw_aspect = draw_w / draw_h
    if fit_code == "contain":
        if img_aspect >= draw_aspect:
            final_w = draw_w
            final_h = draw_w / img_aspect
        else:
            final_h = draw_h
            final_w = draw_h * img_aspect
    else:
        if img_aspect >= draw_aspect:
            final_h = draw_h
            final_w = draw_h * img_aspect
        else:
            final_w = draw_w
            final_h = draw_w / img_aspect
    x = (page_w - final_w) / 2
    y = (page_h - final_h) / 2
    # JPEG encoding with controlled quality for compact PDF size
    buf = BytesIO()
    pil_img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    pdf.image(buf, x=x, y=y, w=final_w, h=final_h)

class ImagesToPDF:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "文件名前缀": ("STRING", {
                    "default": "images",
                    "multiline": False,
                    "placeholder": "输出 PDF 文件名前缀",
                }),
                "页面大小": (_PAGE_SIZES, {"default": "A4"}),
                "方向": (_ORIENTATIONS, {"default": "纵向"}),
                "图片填充": (_IMAGE_FITS, {"default": "居中留白"}),
                "逆序输出": ("BOOLEAN", {"default": False}),
                "图片质量": ("INT", {
                    "default": 85,
                    "min": 10,
                    "max": 100,
                    "step": 1,
                    "display": "slider",
                }),
            },
            "optional": {
                "images": ("IMAGE",),
                "图片路径列表": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "图片文件路径，每行一个",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("图片", "文件路径")
    FUNCTION = "run"
    CATEGORY = "image"
    OUTPUT_NODE = True

    def run(self, images=None,
            文件名前缀="images",
            页面大小="A4",
            方向="纵向",
            图片填充="居中留白",
            逆序输出=False,
            图片质量=85,
            图片路径列表=""):

        orient_code = _ORIENTATION_MAP.get(方向, "P")
        fit_code = _FIT_MAP.get(图片填充, "contain")

        # Collect all PIL images from IMAGE batch
        pil_images = []
        if images is not None and getattr(images, "shape", None) is not None and images.shape[0] > 0:
            for i in range(images.shape[0]):
                arr = 255.0 * images[i].cpu().numpy()
                arr = np.clip(arr, 0, 255).astype(np.uint8)
                pil_images.append(PILImage.fromarray(arr))

        # Collect images from file paths
        if 图片路径列表:
            path_list = [p.strip() for p in 图片路径列表.split("\n") if p.strip()]
            for p in path_list:
                if os.path.isfile(p):
                    try:
                        pil_images.append(PILImage.open(p).convert("RGB"))
                    except Exception as e:
                        print(f"[ImagesToPDF] Skip invalid image: {p} - {e}")

        if not pil_images:
            if images is not None:
                return (images, "")
            return (None, "")

        # Apply reverse order toggle
        if 逆序输出:
            pil_images.reverse()

        # Compute page size based on first image
        page_w, page_h = _compute_page_size(页面大小, 方向, pil_images[0])

        pdf = FPDF(unit="mm", format=(page_w, page_h))
        pdf.set_auto_page_break(auto=False, margin=0)

        for pil_img in pil_images:
            _add_page_from_pil(pdf, pil_img, page_w, page_h, fit_code, quality=图片质量)

        output_dir = folder_paths.get_output_directory()
        os.makedirs(output_dir, exist_ok=True)
        ts = int(time.time() * 1000)
        filename = f"{文件名前缀}_{ts}.pdf"
        filepath = os.path.join(output_dir, filename)
        pdf.output(filepath)

        return (images if images is not None else None, filepath)


class ImagePathList:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "文件夹路径": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "要扫描的文件夹路径",
                }),
                "递归搜索": ("BOOLEAN", {"default": False}),
                "文件后缀": ("STRING", {
                    "default": ".png,.jpg,.jpeg,.webp,.bmp",
                    "multiline": False,
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("图片路径列表",)
    FUNCTION = "run"
    CATEGORY = "image"
    OUTPUT_NODE = True

    def run(self, 文件夹路径="", 递归搜索=False, 文件后缀=".png,.jpg,.jpeg,.webp,.bmp"):

        results = []
        # Parse file extensions
        exts = set()
        for e in 文件后缀.split(","):
            e = e.strip()
            if e:
                if not e.startswith("."):
                    e = "." + e
                exts.add(e.lower())

        # Scan folder
        if 文件夹路径:
            if os.path.isdir(文件夹路径):
                pattern = "**/*" if 递归搜索 else "*"
                for f in sorted(glob.glob(os.path.join(文件夹路径, pattern), recursive=递归搜索)):
                    if os.path.isfile(f):
                        ext = os.path.splitext(f)[1].lower()
                        if ext in exts:
                            results.append(f)

        return ("\n".join(results),)


NODE_DISPLAY_NAME_MAPPINGS = {
    "ImagesToPDF": "图片转PDF (Images to PDF)",
    "ImagePathList": "图片路径列表 (Image Path List)",
}
