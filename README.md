# ComfyUI-Image-Choose

ComfyUI 可视化图片选择器插件——点击预览并选择图片，灵活控制批次图像的路由与筛选。包含图片计数和批次合并功能。

## 功能特性

| 节点 | 功能说明 |
|------|----------|
| **Image Chooser（图片预览选择器）** | 可视化预览批次图片，通过索引选择需要的图片输出，支持 `1,3,5` 或 `2:5` 语法 |
| **Image Count（图片计数）** | 输出批次中的图片数量 |
| **Image Batch Combine（批次合并）** | 将多路图片输入合并为一个批次，自动调整尺寸 |
| **DeepSeek Chat（DeepSeek 对话）** | 通过 DeepSeek API 进行 LLM 对话 |
| **GrsAI Chat（GrsAI 对话）** | 通过 GrsAI API 进行 LLM 对话 |

### 图片选择器

- **路由中断模式**：等待用户选择后，中断当前执行，仅传递选中的图片
- **继续上次选择模式**：复用上一次的选择结果，适合迭代调试
- 选择语法：逗号分隔（`1,3,5`）、范围选择（`2:5`）、混合使用

### 批次合并

- 支持最多 8 路图片输入合并
- 自动统一尺寸（最大/最小/第一张尺寸三种策略）

## 安装

### 方法一：ComfyUI Manager（推荐）

在 ComfyUI Manager 中搜索 `ComfyUI-Image-Choose` 安装。

### 方法二：手动安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/your-username/ComfyUI-Image-Choose
cd ComfyUI-Image-Choose
pip install -r requirements.txt
```

### 配置 API 密钥

在插件目录创建 `api_key.json` 文件：

```json
{
    "deepseek_api_key": "你的deepseek密钥",
    "grsai_api_key": "你的grsai密钥",
    "grsai_host": "https://grsaiapi.com"
}
```

也可以通过环境变量配置：
- `DEEPSEEK_API_KEY`
- `GRSAI_API_KEY`

密钥获取地址：
- DeepSeek: https://platform.deepseek.com/
- GrsAI: https://grsai.ai/zh

## Demo 展示

### 图片预览选择

![图片预览选择](demo/demo%20(1).png)

### 图片计数和路由

![图片计数和路由](demo/demo%20(2).png)

### 多图批次处理

![多图批次处理](demo/demo%20(3).png)

### 循环运算

![循环运算](demo/demo%20(4).png)

### 服装和动作更换

![服装和动作更换](demo/demo%20(5).png)

## 工作流

所有工作流示例文件存放在 `workflows/` 目录下，你可以直接拖入 ComfyUI 使用：

### 基础功能工作流

| 工作流文件 | 说明 |
|-----------|------|
| `开发的节点插件.json` | 所有开发节点的展示和测试 |
| `测试llm.json` | LLM 对话节点测试 |
| `grsAI_chat_LLM.json` | GrsAI Chat LLM 测试 |
| `gguf.json` | GGUF 模型测试 |
| `测试deepseek反推.json` | DeepSeek 反推测试 |
| `反推测试.json` | 通用反推测试 |

### 图像处理工作流

| 工作流文件 | 说明 |
|-----------|------|
| `图片路由选择.json` | Image Chooser 图片路由选择核心工作流 |
| `解决批次图像被裁剪的bug.json` | 批次图像裁剪修复 |
| `前端传入多图for循环判断.json` | 多图循环处理 |
| `人脸模糊和绑定图片.json` | 人脸模糊 + 参考图绑定 |
| `测试人体分割和骨架提取.json` | 人体分割和骨架提取 |
| `提取人物身上的服装或产品.json` | 从人物提取服装/产品 |

### 商业应用工作流

| 工作流文件 | 说明 |
|-----------|------|
| `服装和动作更换工作流.json` | 服装和动作替换 |
| `姿势控制.json` | 姿势控制生成 |
| `产品精修.json` | 产品图精修 |
| `输入模特产品动作.json` | 模特 + 产品 + 动作组合 |
| `模特三视图创作.json` | 模特三视图生成 |
| `分镜列表索引拆解.json` | 分镜索引拆解 |
| `循环运算.json` | 循环运算处理 |
| `循环运算 图像.json` | 图像循环运算 |

### 达到商业量产的流

`workflows/达到商业量产的流/` 目录包含经过验证的商业生产级工作流：

| 工作流文件 | 说明 |
|-----------|------|
| `2图输入txt_to_image输入模特产品动作 - 升级 .json` | 2图输入商业工作流 |
| `3图txt_to_image输入模特产品动作 - 升级.json` | 3图输入商业工作流 |
| `4图输入模特产品动作 - 升级.json` | 4图输入商业工作流 |
| `模特三视图创作.json` | 商业级模特三视图 |

## 依赖

```
openai
```

## 许可证

MIT License

## 致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - 强大的 AI 图像工作流引擎
- [DeepSeek](https://platform.deepseek.com/) - LLM API 服务
- [GrsAI](https://grsai.ai) - AI 服务提供商
