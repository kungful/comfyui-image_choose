# -*- coding: utf-8 -*-
"""
XGC (仙宫云) GPU 算力 API 完整节点
===================================
提供 6 个 ComfyUI 节点，覆盖仙宫云全部 14 个 API 端点：
  实例管理: 列表/查询/部署/开机/关机/销毁/储存镜像
  镜像管理: 列表/查询/销毁

API 文档来源: https://api-playground.xiangongyun.com
API 基地址:   https://api.xiangongyun.com
令牌获取:     https://www.xiangongyun.com/console/user/accesstoken

用法：
  1. 可选: 使用 XGCAuth 节点设置 API Token（或直接编辑 api_key.json，字段名 xgc_api_token）
  2. 使用 XGCInstanceList 查看实例 / XGCImageList 查看镜像
  3. 使用 XGCInstanceDeploy 部署新实例
  4. 使用 XGCInstanceControl 管理实例（开机/关机/销毁/储存镜像）
  5. 使用 XGCImageDestroy 销毁镜像
"""

import os
import json

import urllib.request
import urllib.error

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_API_KEY_FILE = os.path.join(_PLUGIN_DIR, "api_key.json")

# ---------------------------------------------------------------------------
# 模块级配置缓存（XGCAuth 节点设置后直接生效，其他节点不用再读文件）
# ---------------------------------------------------------------------------
_xgc_config = {"token": "", "host": "https://api.xiangongyun.com"}

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
GPU_MODELS = [
    "NVIDIA GeForce RTX 4090",
    "NVIDIA GeForce RTX 4090 D",
    "NVIDIA GeForce RTX 4090 D 48G",
]

PUBLIC_IMAGE_OPTIONS = [
    "Miniconda3_3.13, ubuntu22.04/CUDA 12.6",
    "Miniconda3_3.12, ubuntu22.04/CUDA 12.8",
    "Miniconda3_3.12, ubuntu22.04/CUDA 12.6",
    "Miniconda3_3.10, ubuntu22.04/CUDA 12.4",
    "Miniconda3_3.10, ubuntu22.04/CUDA 12.2",
    "Miniconda3_3.10, ubuntu22.04/CUDA 12.2 TensorRT",
    "Miniconda3_3.10, ubuntu22.04/CUDA 12.1",
    "Miniconda3_3.10, ubuntu22.04/CUDA 11.8",
    "Miniconda3_3.10, centos7/CUDA 11.4",
    "Miniconda3_3.8, ubuntu20.04/CUDA 11.8",
    "Miniconda3_3.8, ubuntu20.04/CUDA 11.1",
]

PUBLIC_IMAGE_MAP = {
    "Miniconda3_3.13, ubuntu22.04/CUDA 12.6":         "7fd1f863-c2e2-4af6-b41b-cf92a034c2d3",
    "Miniconda3_3.12, ubuntu22.04/CUDA 12.8":         "02b564d3-9510-4f80-b56d-409900dab8da",
    "Miniconda3_3.12, ubuntu22.04/CUDA 12.6":         "5bea96c9-5b0d-4531-b75d-661cc1646e0b",
    "Miniconda3_3.10, ubuntu22.04/CUDA 12.4":         "c0cf4899-24f9-4132-a45d-4dc5f13b009b",
    "Miniconda3_3.10, ubuntu22.04/CUDA 12.2":         "a0607405-d0fd-4efc-b34e-de0872d4a633",
    "Miniconda3_3.10, ubuntu22.04/CUDA 12.2 TensorRT": "2f98442f-1e6e-4531-8b92-88a09d5d8a20",
    "Miniconda3_3.10, ubuntu22.04/CUDA 12.1":         "260cd46a-12aa-44ed-b47a-88f770b49041",
    "Miniconda3_3.10, ubuntu22.04/CUDA 11.8":         "9115617d-3d2a-494d-af82-597319953e46",
    "Miniconda3_3.10, centos7/CUDA 11.4":             "8b73bf90-d6a2-4f21-9521-8aed8ea7d2c9",
    "Miniconda3_3.8, ubuntu20.04/CUDA 11.8":          "438c59fd-886b-4cda-8396-12a9cd4a3b97",
    "Miniconda3_3.8, ubuntu20.04/CUDA 11.1":          "e7a66296-fe56-4fd1-a67d-cff5613b6372",
}

IMAGE_TYPE_OPTIONS = ["public", "community", "private"]

INSTANCE_STATUS_CN = {
    "deploying":        "正在部署",
    "running":          "正在运行",
    "booting":          "正在开机",
    "shutting_down":    "正在关机",
    "shutdown":         "已关机",
    "destroying":       "正在销毁",
    "destroyed":        "已销毁",
    "saving_image":     "正在储存镜像",
    "freezing":         "正在冻结",
    "freeze":           "已冻结",
    "replacing_image":  "正在更换镜像",
}

# ---------------------------------------------------------------------------
# 配置读写
# ---------------------------------------------------------------------------

def _read_xgc_config():
    """从 api_key.json 读取 xgc_api_token 和 xgc_host，作为 fallback。"""
    if os.path.isfile(_API_KEY_FILE):
        try:
            with open(_API_KEY_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            token = cfg.get("xgc_api_token", "").strip()
            host = cfg.get("xgc_host", "").strip()
            if token:
                return token, host if host else "https://api.xiangongyun.com"
        except (json.JSONDecodeError, OSError):
            pass
    return "", "https://api.xiangongyun.com"


def _get_xgc_config():
    """获取当前配置：优先模块级缓存，其次 api_key.json。"""
    token = _xgc_config.get("token", "")
    host = _xgc_config.get("host", "https://api.xiangongyun.com")
    if not token:
        token, host = _read_xgc_config()
        if token:
            _xgc_config["token"] = token
            _xgc_config["host"] = host
    return token, host


def _set_xgc_config(token, host):
    """同时写入模块缓存和 api_key.json。"""
    _xgc_config["token"] = token
    _xgc_config["host"] = host

    # 读取或创建配置文件
    cfg = {}
    if os.path.isfile(_API_KEY_FILE):
        try:
            with open(_API_KEY_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            cfg = {}
    cfg["xgc_api_token"] = token
    cfg["xgc_host"] = host
    try:
        with open(_API_KEY_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[XGC] 写入 api_key.json 失败: {e}")


# ---------------------------------------------------------------------------
# HTTP 请求助手
# ---------------------------------------------------------------------------

def _api_request(method, path, token, host, body=None, timeout=30):
    """通用 API 请求，返回 (data_dict_or_None, error_string_or_None)。"""
    url = f"{host}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8") if e.fp else ""
            return json.loads(raw), f"HTTP {e.code}"
        except Exception:
            return None, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, f"连接错误: {e.reason}"
    except json.JSONDecodeError as e:
        return None, f"JSON 解析错误: {e}"
    except Exception as e:
        return None, f"未知错误: {e}"


def _format_instance_brief(inst):
    """将单个实例信息格式化为一行中文摘要。"""
    sid = inst.get("id", "?")
    name = inst.get("name", "") or "(未命名)"
    status = inst.get("status", "?")
    status_cn = INSTANCE_STATUS_CN.get(status, status)
    gpu = inst.get("gpu_model", "?")
    gpu_count = inst.get("gpu_used", "?")
    price = inst.get("price_per_hour", 0)
    ssh = inst.get("ssh_domain", "")
    jupyter = inst.get("jupyter_url", "")
    return (
        f"[{status_cn}] {name} | ID: {sid[:8]}... | "
        f"GPU: {gpu} x{gpu_count} | ¥{price}/h"
        + (f" | SSH: {ssh}" if ssh else "")
        + (f" | Jupyter: {jupyter}" if jupyter else "")
    )


def _format_image_brief(img):
    """将单个镜像信息格式化为一行中文摘要。"""
    iid = img.get("id", "?")
    name = img.get("name", "?")
    status = img.get("status", "?")
    size_bytes = img.get("size", 0)
    size_gb = size_bytes / (1024**3) if size_bytes else 0
    price = img.get("price", 0)
    return f"[{status}] {name} | ID: {iid[:8]}... | {size_gb:.1f} GB | ¥{price}/h"


# ---------------------------------------------------------------------------
# 节点 1: XGCAuth — 配置认证
# ---------------------------------------------------------------------------

class XGCAuth:
    """设置仙宫云 API Token（写入 api_key.json + 模块缓存）。

    如果不使用本节点，也可以直接在插件目录的 api_key.json 中添加:
      "xgc_api_token": "你的令牌",
      "xgc_host": "https://api.xiangongyun.com"
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_token": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "从 https://www.xiangongyun.com/console/user/accesstoken 获取",
                }),
                "api_host": ("STRING", {
                    "default": "https://api.xiangongyun.com",
                    "multiline": False,
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("配置状态",)
    FUNCTION = "run"
    CATEGORY = "xgcloud"

    def run(self, api_token="", api_host="https://api.xiangongyun.com"):
        if not api_token.strip():
            # 没有输入 token，尝试读取已有配置
            token, host = _get_xgc_config()
            if token:
                return (f"✓ 已使用 api_key.json 中的配置\n  Token: {token[:8]}...{token[-4:]}\n  Host: {host}",)
            return ("⚠ 未设置 API Token。请在 api_token 输入框填入令牌，\n"
                    "或编辑 api_key.json 添加 xgc_api_token 字段。",)

        token = api_token.strip()
        host = api_host.strip() or "https://api.xiangongyun.com"

        # 做个快速验证（获取实例列表）
        data, err = _api_request("GET", "/open/instances", token, host, timeout=15)
        if err:
            return (f"✗ 验证失败: {err}",)

        _set_xgc_config(token, host)
        return (f"✓ 配置成功\n  Token: {token[:8]}...{token[-4:]}\n  Host: {host}",)


# ---------------------------------------------------------------------------
# 节点 2: XGCInstanceList — 查询实例
# ---------------------------------------------------------------------------

class XGCInstanceList:
    """查询仙宫云实例：支持列表、单个实例查询、实例储存镜像查询。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "查询模式": (["实例列表", "单个实例详情", "实例储存的镜像"], {"default": "实例列表"}),
            },
            "optional": {
                "实例ID": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "查询单个实例或实例镜像时需要",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("完整JSON", "摘要信息")
    FUNCTION = "run"
    CATEGORY = "xgcloud"

    def run(self, 查询模式="实例列表", 实例ID=""):
        token, host = _get_xgc_config()
        if not token:
            return ("错误：未配置 API Token，请先使用 XGCAuth 节点或编辑 api_key.json", "")

        if 查询模式 == "实例列表":
            data, err = _api_request("GET", "/open/instances", token, host)
            if err:
                return (f"错误: {err}", "")
            result_list = data.get("list") or data if isinstance(data, list) else []
            total = data.get("total", len(result_list)) if isinstance(data, dict) else len(result_list)
            brief_lines = [f"共 {total} 个实例:\n"]
            for inst in result_list:
                brief_lines.append(_format_instance_brief(inst))
            return (json.dumps(data, ensure_ascii=False, indent=2), "\n".join(brief_lines))

        if not 实例ID.strip():
            return ("错误：此模式需要提供实例ID", "")

        iid = 实例ID.strip()

        if 查询模式 == "单个实例详情":
            data, err = _api_request("GET", f"/open/instance/{iid}", token, host)
            if err:
                return (f"错误: {err}", "")
            brief = _format_instance_brief(data) if isinstance(data, dict) else str(data)
            return (json.dumps(data, ensure_ascii=False, indent=2), brief)

        if 查询模式 == "实例储存的镜像":
            data, err = _api_request("GET", f"/open/instance/{iid}/images", token, host)
            if err:
                return (f"错误: {err}", "")
            result_list = data.get("list") or data if isinstance(data, list) else []
            total = data.get("total", len(result_list)) if isinstance(data, dict) else len(result_list)
            brief_lines = [f"实例 {iid} 储存了 {total} 个镜像:\n"]
            for img in result_list:
                brief_lines.append(_format_image_brief(img))
            return (json.dumps(data, ensure_ascii=False, indent=2), "\n".join(brief_lines))

        return ("未知查询模式", "")


# ---------------------------------------------------------------------------
# 节点 3: XGCInstanceDeploy — 部署实例
# ---------------------------------------------------------------------------

class XGCInstanceDeploy:
    """部署新的 GPU 云实例。请求成功后异步执行，请通过 XGCInstanceList 查看状态。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "GPU型号": (GPU_MODELS, {"default": "NVIDIA GeForce RTX 4090"}),
                "GPU数量": ("INT", {"default": 1, "min": 1, "max": 8, "step": 1}),
                "数据中心ID": ("INT", {"default": 1, "min": 1, "max": 1, "step": 1}),
                "公共镜像": (PUBLIC_IMAGE_OPTIONS, {"default": "Miniconda3_3.10, ubuntu22.04/CUDA 12.1"}),
                "镜像类型": (IMAGE_TYPE_OPTIONS, {"default": "public"}),
                "手动指定镜像ID": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "留空则使用上方选择的公共镜像；填入则覆盖上方选择",
                }),
                "挂载云储存": ("BOOLEAN", {"default": False}),
                "储存挂载路径": ("STRING", {"default": "/root/cloud", "multiline": False}),
                "扩容系统盘": ("BOOLEAN", {"default": False}),
                "系统盘扩容大小(GB)": ("INT", {"default": 0, "min": 0, "max": 2000, "step": 1,
                                         "display": "number"}),
            },
            "optional": {
                "SSH密钥ID": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "可选，SSH 密钥 ID",
                }),
                "实例名称": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "可选，为实例命名",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("完整JSON", "实例ID", "部署状态")
    FUNCTION = "run"
    CATEGORY = "xgcloud"

    def run(self, GPU型号="NVIDIA GeForce RTX 4090", GPU数量=1, 数据中心ID=1,
            公共镜像="Miniconda3_3.10, ubuntu22.04/CUDA 12.1", 镜像类型="public",
            手动指定镜像ID="", 挂载云储存=False, 储存挂载路径="/root/cloud",
            扩容系统盘=False, **kwargs):

        token, host = _get_xgc_config()
        if not token:
            return ("错误：未配置 API Token", "", "")

        # 确定镜像 ID
        image_id = 手动指定镜像ID.strip() if 手动指定镜像ID.strip() else PUBLIC_IMAGE_MAP.get(公共镜像, "")
        if not image_id:
            return (f"错误：未能确定镜像ID（公共镜像'{公共镜像}'未找到对应ID，请手动指定）", "", "")

        # 系统盘扩容大小 - 从 kwargs 或 input key 兼容读取
        _expand_size = kwargs.get("系统盘扩容大小(GB)", 0)
        system_disk_expand_size_bytes = _expand_size * 1024 * 1024 * 1024 if 扩容系统盘 else 0

        body = {
            "gpu_model": GPU型号,
            "gpu_count": GPU数量,
            "data_center_id": 数据中心ID,
            "image": image_id,
            "image_type": 镜像类型,
            "storage": 挂载云储存,
            "storage_mount_path": 储存挂载路径,
            "system_disk_expand": 扩容系统盘,
            "system_disk_expand_size": system_disk_expand_size_bytes,
        }
        if kwargs.get("SSH密钥ID", "").strip():
            body["sshkey"] = kwargs["SSH密钥ID"].strip()
        if kwargs.get("实例名称", "").strip():
            body["name"] = kwargs["实例名称"].strip()

        data, err = _api_request("POST", "/open/instance/deploy", token, host, body, timeout=30)
        if err:
            return (f"错误: {err}", "", "")

        instance_id = data.get("id", "") if isinstance(data, dict) else ""
        status = f"✓ 部署命令已下发，实例 ID: {instance_id}\n请使用 XGCInstanceList 查看部署进度"

        return (json.dumps(data, ensure_ascii=False, indent=2), instance_id, status)


# ---------------------------------------------------------------------------
# 节点 4: XGCInstanceControl — 实例控制（开机/关机/销毁/储存镜像）
# ---------------------------------------------------------------------------

INSTANCE_ACTIONS = [
    "开机",
    "关机（保留GPU）",
    "关机（释放GPU）",
    "关机并销毁",
    "销毁实例",
    "储存镜像",
    "储存镜像并销毁",
]

ACTION_ENDPOINTS = {
    "开机":               "/open/instance/boot",
    "关机（保留GPU）":      "/open/instance/shutdown",
    "关机（释放GPU）":      "/open/instance/shutdown_release_gpu",
    "关机并销毁":           "/open/instance/shutdown_destroy",
    "销毁实例":            "/open/instance/destroy",
    "储存镜像":            "/open/instance/saveimage",
    "储存镜像并销毁":        "/open/instance/saveimage_destroy",
}

ACTION_DESCRIPTIONS = {
    "开机":               "发送开机命令，关机保留磁盘实例可重新选择 GPU 型号和数量",
    "关机（保留GPU）":      "仅关机，GPU 继续为您保留，期间照常收费",
    "关机（释放GPU）":      "关机后释放 GPU 不再计费，磁盘数据安全备份后可随时再次开机（磁盘 ¥0.00003/GB/h）",
    "关机并销毁":           "关机并销毁实例，所有数据将被清除",
    "销毁实例":            "直接销毁实例，所有数据将被清除",
    "储存镜像":            "将当前实例保存为私有镜像",
    "储存镜像并销毁":        "保存镜像后自动销毁实例",
}


class XGCInstanceControl:
    """控制 GPU 实例：开机、关机（保留/释放GPU）、关机并销毁、销毁、储存镜像、储存镜像并销毁。

    所有操作均为异步执行，请通过 XGCInstanceList 查看实例状态。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "操作": (INSTANCE_ACTIONS, {"default": "开机"}),
                "实例ID": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "要操作的实例 ID",
                }),
            },
            "optional": {
                "GPU型号(开机时可选)": (GPU_MODELS + ["（保持原配置）"], {"default": "（保持原配置）"}),
                "GPU数量(开机时可选)": ("INT", {"default": 0, "min": 0, "max": 8, "step": 1,
                                          "placeholder": "0=使用关机时的数量"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("完整JSON", "执行状态")
    FUNCTION = "run"
    CATEGORY = "xgcloud"

    def run(self, 操作="开机", 实例ID="", **kwargs):
        token, host = _get_xgc_config()
        if not token:
            return ("错误：未配置 API Token", "")

        if not 实例ID.strip():
            return ("错误：请提供实例ID", "")

        iid = 实例ID.strip()
        endpoint = ACTION_ENDPOINTS.get(操作, "")
        if not endpoint:
            return (f"错误：未知操作 '{操作}'", "")

        body = {"id": iid}

        # 开机操作允许指定 GPU 型号和数量（仅关机保留磁盘实例使用）
        if 操作 == "开机":
            gpu_model = kwargs.get("GPU型号(开机时可选)", "（保持原配置）")
            gpu_count = kwargs.get("GPU数量(开机时可选)", 0)
            if gpu_model != "（保持原配置）" and gpu_model in GPU_MODELS:
                body["gpu_model"] = gpu_model
            if gpu_count > 0:
                body["gpu_count"] = gpu_count

        desc = ACTION_DESCRIPTIONS.get(操作, "")
        data, err = _api_request("POST", endpoint, token, host, body, timeout=30)
        if err:
            return (f"错误: {err}", "")

        success = data.get("success", False) if isinstance(data, dict) else False
        msg = data.get("msg", "") if isinstance(data, dict) else ""
        status = (
            f"{'✓' if success else '✗'} {操作} — {msg or ('成功' if success else '失败')}\n"
            f"{desc}\n"
            f"请使用 XGCInstanceList 查看实例状态"
        )
        return (json.dumps(data, ensure_ascii=False, indent=2), status)


# ---------------------------------------------------------------------------
# 节点 5: XGCImageList — 镜像查询
# ---------------------------------------------------------------------------

class XGCImageList:
    """查询私有/社区镜像列表或单个镜像详情。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "查询模式": (["镜像列表", "单个镜像详情"], {"default": "镜像列表"}),
            },
            "optional": {
                "镜像ID": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "查询单个镜像时需要",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("完整JSON", "摘要信息")
    FUNCTION = "run"
    CATEGORY = "xgcloud"

    def run(self, 查询模式="镜像列表", 镜像ID=""):
        token, host = _get_xgc_config()
        if not token:
            return ("错误：未配置 API Token", "")

        if 查询模式 == "镜像列表":
            data, err = _api_request("GET", "/open/images", token, host)
            if err:
                return (f"错误: {err}", "")
            result_list = data.get("list") or data if isinstance(data, list) else []
            total = data.get("total", len(result_list)) if isinstance(data, dict) else len(result_list)
            brief_lines = [f"共 {total} 个镜像:\n"]
            for img in result_list:
                brief_lines.append(_format_image_brief(img))
            return (json.dumps(data, ensure_ascii=False, indent=2), "\n".join(brief_lines))

        if not 镜像ID.strip():
            return ("错误：此模式需要提供镜像ID", "")

        iid = 镜像ID.strip()
        data, err = _api_request("GET", f"/open/image/{iid}", token, host)
        if err:
            return (f"错误: {err}", "")
        brief = _format_image_brief(data) if isinstance(data, dict) else str(data)
        return (json.dumps(data, ensure_ascii=False, indent=2), brief)


# ---------------------------------------------------------------------------
# 节点 6: XGCImageDestroy — 销毁镜像
# ---------------------------------------------------------------------------

class XGCImageDestroy:
    """销毁指定的私有/社区镜像。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "镜像ID": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "要销毁的镜像 ID",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("完整JSON", "执行状态")
    FUNCTION = "run"
    CATEGORY = "xgcloud"

    def run(self, 镜像ID=""):
        token, host = _get_xgc_config()
        if not token:
            return ("错误：未配置 API Token", "")

        if not 镜像ID.strip():
            return ("错误：请提供镜像ID", "")

        iid = 镜像ID.strip()
        data, err = _api_request("POST", "/open/image/destroy", token, host, {"id": iid}, timeout=30)
        if err:
            return (f"错误: {err}", "")

        success = data.get("success", False) if isinstance(data, dict) else False
        msg = data.get("msg", "") if isinstance(data, dict) else ""
        status = f"{'✓' if success else '✗'} 销毁镜像 — {msg or ('成功' if success else '失败')}"
        return (json.dumps(data, ensure_ascii=False, indent=2), status)
