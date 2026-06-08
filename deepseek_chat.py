import os
import json
import random

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_API_KEY_FILE = os.path.join(_PLUGIN_DIR, "api_key.json")


def _read_api_key():
    if os.path.isfile(_API_KEY_FILE):
        try:
            with open(_API_KEY_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            key = cfg.get("deepseek_api_key", "").strip()
            if not key:
                key = cfg.get("api_key", "").strip()
            if key and key not in ("sk-your-deepseek-api-key-here", "sk-your-grsai-api-key-here"):
                return key
        except (json.JSONDecodeError, OSError):
            pass
    return os.environ.get("DEEPSEEK_API_KEY", "")


class DeepSeekChat:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "模型": (["deepseek-v4-flash", "deepseek-v4-pro"], {"default": "deepseek-v4-pro"}),
                "系统提示词": ("STRING", {
                    "default": "你是一个有用的助手。",
                    "multiline": True,
                }),
                "用户提示词": ("STRING", {
                    "default": "",
                    "multiline": True,
                }),
                "思考模式": (["关闭", "开启"], {"default": "开启"}),
                "推理深度": (["低", "中", "高"], {"default": "高"}),
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
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("回复内容", "思考过程")
    FUNCTION = "run"
    CATEGORY = "ai/deepseek"

    def run(self, 模型="deepseek-v4-pro", 系统提示词="你是一个有用的助手。",
            用户提示词="", 思考模式="开启", 推理深度="高", 温度=1.0,
            最大输出长度=4096, 存在惩罚=0.0, 频率惩罚=0.0, 随机种子=True):

        if not _HAS_OPENAI:
            return ("错误：未安装 openai 包，请执行: pip install openai", "")

        api_key = _read_api_key()
        if not api_key:
            return ("错误：未找到 API Key，请在插件目录编辑 api_key.json 或设置 DEEPSEEK_API_KEY 环境变量", "")

        if not 用户提示词.strip():
            return ("错误：用户提示词为空", "")

        messages = []
        if 系统提示词.strip():
            messages.append({"role": "system", "content": 系统提示词})
        messages.append({"role": "user", "content": 用户提示词})

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        extra_body = {}
        if 思考模式 == "开启":
            extra_body["thinking"] = {"type": "enabled"}

        reasoning_effort_map = {"低": "low", "中": "medium", "高": "high"}
        kwargs = {
            "model": 模型,
            "messages": messages,
            "stream": False,
            "reasoning_effort": reasoning_effort_map.get(推理深度, "high"),
            "temperature": 温度,
            "max_tokens": 最大输出长度,
            "presence_penalty": 存在惩罚,
            "frequency_penalty": 频率惩罚,
        }
        if extra_body:
            kwargs["extra_body"] = extra_body
        if 随机种子:
            kwargs["seed"] = random.randint(0, 2**31 - 1)

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            return (f"API 错误: {e}", "")

        choice = response.choices[0]
        content = choice.message.content or ""
        reasoning = getattr(choice.message, 'reasoning_content', '') or ""

        usage_info = {}
        if hasattr(response, "usage") and response.usage:
            usage_info = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }

        reasoning_display = reasoning + (
            f"\n\n[Token 用量] {json.dumps(usage_info, ensure_ascii=False)}"
            if usage_info else ""
        )

        return (content, reasoning_display)
