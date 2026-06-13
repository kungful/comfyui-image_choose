import os
import time

import torch
import numpy as np
from PIL import Image
import folder_paths
from server import PromptServer

WEB_DIRECTORY = ""
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _cache():
    if not hasattr(PromptServer.instance, "_image_choose_cache"):
        PromptServer.instance._image_choose_cache = {}
    return PromptServer.instance._image_choose_cache


def _parse_indexes(indexes_str, max_count):
    selected = []
    total = list(range(max_count))
    for part in indexes_str.strip().split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if ":" in part:
                items = part.split(":", 1)
                s, e = items[0].strip(), items[1].strip()
                if s and e:
                    start, end = int(s) - 1, int(e) - 1
                    selected.extend(total[max(0, start):max(0, end)])
                elif s:
                    selected.extend(total[max(0, int(s) - 1):])
                elif e:
                    selected.extend(total[:max(0, int(e) - 1)])
            else:
                idx = int(part) - 1
                if 0 <= idx < max_count:
                    selected.append(idx)
        except (ValueError, IndexError):
            pass
    return selected


def _save_previews(images, prefix="choose"):
    output_dir = folder_paths.get_temp_directory()
    os.makedirs(output_dir, exist_ok=True)
    results = []
    ts = int(time.time() * 1000)
    for b in range(images.shape[0]):
        arr = 255.0 * images[b].cpu().numpy()
        pil_img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        fname = f"{prefix}_{ts}_{b:05d}.png"
        pil_img.save(os.path.join(output_dir, fname), compress_level=4)
        results.append({"filename": fname, "subfolder": "", "type": "temp"})
    return results


class ImageChooser:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "selected_indexes": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "1,3,5  or  2:5",
                }),
                "trigger": ("BOOLEAN", {
                    "default": False,
                    "label_on": "✓ Applied",
                    "label_off": "▶ Continue",
                }),
                "mode": (["路由中断", "继续上次选择"], {"default": "路由中断"}),
            },
            "hidden": {"my_unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("filtered_images",)
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "image"

    @classmethod
    def IS_CHANGED(cls, selected_indexes, trigger, mode, **kwargs):
        return f"{mode}|{selected_indexes}|{trigger}"

    def run(self, images, selected_indexes="", trigger=False, mode="路由中断", my_unique_id=None):
        node_id = str(my_unique_id) if my_unique_id is not None else "0"
        total = images.shape[0]
        cache = _cache()

        if mode == "继续上次选择":
            if node_id in cache and "last" in cache[node_id]:
                indices = cache[node_id]["last"]
                valid = [i for i in indices if 0 <= i < total]
                if valid:
                    filtered = images[valid]
                    return {"result": (filtered,), "ui": {"images": _save_previews(filtered, f"choose_{node_id}")}}

        if selected_indexes and selected_indexes.strip():
            indices = _parse_indexes(selected_indexes, total)
            if indices:
                cache[node_id] = {"last": indices[:]}
                filtered = images[indices]
            else:
                filtered = images
        else:
            filtered = images

        return {"result": (filtered,), "ui": {"images": _save_previews(filtered, f"choose_{node_id}")}}


class ImageCount:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",)}}

    RETURN_TYPES = ("INT", "STRING")
    RETURN_NAMES = ("count", "count_desc")
    FUNCTION = "run"
    CATEGORY = "image"

    def run(self, images):
        n = images.shape[0]
        return (n, f"{n} image{'s' if n != 1 else ''}")


class ImageBatchCombine:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "match_size": (["最大尺寸", "最小尺寸", "第一张尺寸"], {"default": "最大尺寸"}),
            },
            "optional": {
                "image_a": ("IMAGE",),
                "image_b": ("IMAGE",),
                "image_c": ("IMAGE",),
                "image_d": ("IMAGE",),
                "image_e": ("IMAGE",),
                "image_f": ("IMAGE",),
                "image_g": ("IMAGE",),
                "image_h": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "run"
    CATEGORY = "image"
    OUTPUT_NODE = True

    def run(self, match_size="最大尺寸", **kwargs):
        tensors = []
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            if val is not None:
                tensors.append(val)
        if not tensors:
            empty = torch.zeros(1, 64, 64, 3, dtype=torch.float32)
            return {"result": (empty,), "ui": {"images": []}}
        sizes = set((t.shape[1], t.shape[2]) for t in tensors)
        if len(sizes) <= 1:
            combined = torch.cat(tensors, dim=0)
            return {"result": (combined,), "ui": {"images": _save_previews(combined, "batch_combine")}}
        if match_size == "最小尺寸":
            target_h = min(t.shape[1] for t in tensors)
            target_w = min(t.shape[2] for t in tensors)
        elif match_size == "第一张尺寸":
            target_h = tensors[0].shape[1]
            target_w = tensors[0].shape[2]
        else:
            target_h = max(t.shape[1] for t in tensors)
            target_w = max(t.shape[2] for t in tensors)
        resized = []
        for t in tensors:
            if t.shape[1] == target_h and t.shape[2] == target_w:
                resized.append(t)
            else:
                t_nhwc = t.permute(0, 3, 1, 2)
                r = torch.nn.functional.interpolate(t_nhwc, size=(target_h, target_w), mode="bilinear", align_corners=False)
                resized.append(r.permute(0, 2, 3, 1))
        combined = torch.cat(resized, dim=0)
        return {"result": (combined,), "ui": {"images": _save_previews(combined, "batch_combine")}}


NODE_CLASS_MAPPINGS["ImageChooser"] = ImageChooser
NODE_CLASS_MAPPINGS["ImageCount"] = ImageCount
NODE_CLASS_MAPPINGS["ImageBatchCombine"] = ImageBatchCombine
try:
    from .deepseek_chat import DeepSeekChat
    NODE_CLASS_MAPPINGS["DeepSeekChat"] = DeepSeekChat
    NODE_DISPLAY_NAME_MAPPINGS["DeepSeekChat"] = "DeepSeek Chat (对话)"
except ImportError:
    pass
try:
    from .grsai_chat import GrsAIChat
    NODE_CLASS_MAPPINGS["GrsAIChat"] = GrsAIChat
    NODE_DISPLAY_NAME_MAPPINGS["GrsAIChat"] = "GrsAI Chat (对话)"
except ImportError:
    pass
try:
    from .images_to_pdf import ImagesToPDF, ImagePathList
    NODE_CLASS_MAPPINGS["ImagesToPDF"] = ImagesToPDF
    NODE_CLASS_MAPPINGS["ImagePathList"] = ImagePathList
    NODE_DISPLAY_NAME_MAPPINGS["ImagesToPDF"] = "Images to PDF (图片�