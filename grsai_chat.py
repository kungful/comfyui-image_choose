import os
import json
import random
import base64
from io import BytesIO

import torch
import numpy as np
from PIL import Image
import urllib.request
import urllib.error

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_API_KEY_FILE = os.path.join(_PLUGIN_DIR, "api_key.json")

_CHAT_MODELS = [
    "gpt-5.5 (🖼 支持图片)",
    "gpt-5.4 (🖼 支持图片)",
    "gemini-3.5-flash (🖼 支持图片)",
    "gemini-3.1-pro (🖼 支持图片)",
    "gemini-3.1-flash-lite (🖼 支持图片)",
    "gemini-3-pro (🖼 支持图片)",
    "gemini-3-flash (🖼 支持图片)",
    "gemini-2.5-pro (🖼 支持图片)",
    "gemini-2.5-flash (🖼 支持图片)",
]

_CHAT_MODEL_NAMES = [m.split(" (")[0] for m in _CHAT_MODELS]


def _read_grsai_config():
    if os.path.isfile(_API_KEY_FILE):
        try:
            with open(_API_KEY_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            key = cfg.get("grsai_api_key", "").strip()
            host = cfg.get("grsai_host", "").strip()
            if key:
                return key, host if host else "https://grsai.dakka.com.cn"
        except (json.JSONDecodeError, OSError):
            pass
    return "", "https://grsai.dakka.com.cn"


def _tensor_to_base64(img_tensor):
    arr = 255.0 * img_tensor[0].cpu().numpy()
    pil_img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class GrsAIChat:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "模型": (_CHAT_MODELS, {"default": "gemini-3.1-pro (🖼 支持图片)"}),
                "系统提示词": ("STRING", {
                    "default": "你是一个有用的助手。",
                    "multiline": True,
                }),
                "用户提示词": ("STRING", {
                    "default": "",
                    "multiline": True,
                }),
                "温度": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.01,
                    "display": "slider",
                }),
                "最大输出长度": ("INT", {
                    "default": 4096,
                    "min": 1,
                    "max": 131072,
                    "step": 1,
                    "display": "number",
                }),
                "存在惩罚": ("FLOAT", {
                    "default": 0.0,
                    "min": -2.0,
                    "max": 2.0,
                    "step": 0.01,
                    "display": "slider",
                }),
                "频率惩罚": ("FLOAT", {
                    "default": 0.0,
                    "min": -2.0,
                    "max": 2.0,
                    "step": 0.01,
                    "display": "slider",
                }),
                "随机种子": ("BOOLEAN", {"default": True}),
                "种子数值": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 2147483647,
                    "step": 1,
                    "display": "number",
                }),
            },
            "optional": {
                "参考图片": ("IMAGE",),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("回复内容", "完整响应JSON", "积分余额")
    FUNCTION = "run"
    CATEGORY = "ai/grsai"
    OUTPUT_NODE = True

    def run(self, 模型="gemini-3.1-pro (🖼 支持图片)", 系统提示词="你是一个有用的助手。",
            用户提示词="", 温度=1.0, 最大输出长度=4096, 存在惩罚=0.0, 频率惩罚=0.0,
            随机种子=True, 种子数值=0, 参考图片=None, unique_id=None):

        if not _HAS_OPENAI:
            return ("错误：未安装 openai 包，请执行: pip install openai", "", "")

        api_key, api_host = _read_grsai_config()
        if not api_key:
            return ("错误：未找到 GrsAI API Key，请在 api_key.json 中设置 grsai_api_key 或设置 GRSAI_API_KEY 环境变量", "", "")

        if not 用户提示词.strip():
            return ("错误：用户提示词为空", "", "")

        model_idx = _CHAT_MODELS.index(模型) if 模型 in _CHAT_MODELS else 3
        model_name = _CHAT_MODEL_NAMES[model_idx]

        client = OpenAI(api_key=api_key, base_url=f"{api_host}/v1")

        messages = []
        if 系统提示词.strip():
            messages.append({"role": "system", "content": 系统提示词})

        if 参考图片 is not None and 参考图片.shape[0] > 0:
            b64 = _tensor_to_base64(参考图片)
            user_content = [
                {"type": "text", "text": 用户提示词},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]
        else:
            user_content = 用户提示词

        messages.append({"role": "user", "content": user_content})

        kwargs = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "temperature": 温度,
            "max_tokens": 最大输出长度,
            "presence_penalty": 存在惩罚,
            "frequency_penalty": 频率惩罚,
        }
        if 随机种子:
            kwargs["seed"] = random.randint(0, 2**31 - 1)
        else:
            kwargs["seed"] = 种子数值

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            return (f"API 错误: {e}", "", "")

        choice = response.choices[0]
        content = choice.message.content or ""

        usage_info = {}
        if hasattr(response, "usage") and response.usage:
            usage_info = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }

        credits_val, credits_ok = _query_credits(api_key, api_host)
        credits_msg = _format_credits_info(credits_val, credits_ok == "success")
        print(f"[GrsAI] {credits_msg}")

        full = json.dumps({
            "model": response.model,
            "content": content,
            "finish_reason": choice.finish_reason,
            "usage": usage_info,
            "credits": credits_val,
        }, ensure_ascii=False, indent=2)

        return (content, full, credits_msg)


def _query_credits(api_key, api_host):
    url = f"{api_host}/client/openapi/getAPIKeyCredits"
    req_body = json.dumps({"apiKey": api_key}).encode("utf-8")
    req = urllib.request.Request(
        url, data=req_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            print(f"[GrsAI-Credits] raw: {raw}")
            data = json.loads(raw)
    except urllib.error.URLError as e:
        return -1, "查询失败"
    except json.JSONDecodeError:
        return -1, "响应解析失败"
    if data.get("code") == 0:
        return data.get("data", {}).get("credits", 0), "success"
    return -1, "查询失败"


_CREDIT_TIERS = [
    (999.00, 20000000),
    (499.00, 18000000),
    (99.00,  2880000),
    (49.00,  1200000),
    (20.00,  375000),
    (10.00,  125000),
]


def _credits_to_rmb(credits):
    rmb = 0.0
    remaining = credits
    for price, amount in _CREDIT_TIERS:
        if remaining >= amount:
            qty = remaining // amount
            rmb += qty * price
            remaining -= qty * amount
    if remaining > 0:
        rmb += (remaining / _CREDIT_TIERS[-1][1]) * _CREDIT_TIERS[-1][0]
    return rmb


def _format_credits_info(credits, ok):
    if not ok:
        return "积分查询失败（API Key 无效）"
    rmb = _credits_to_rmb(credits)
    return f"余额: {credits} 积分 ≈ ¥{rmb:.2f}"
