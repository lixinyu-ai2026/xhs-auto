# 小红书自动生成+发布工具

这个脚本使用 Kimi API 生成高质量的小红书图文笔记内容，并可以自动发布到小红书平台。

## 功能特点

- 自动生成符合小红书风格的标题、文案和图片
- 生成精美的HTML图片预览
- 自动提取文案中的标签用于发布
- 自动发布到小红书平台
- 可配置生成和发布的各种参数

## 使用前准备

1. 确保已完成小红书工具包的基础配置
2. 确保已获取有效的Cookie（使用 `python xhs_toolkit.py cookie save` 命令）
3. 获取Kimi (Moonshot) API密钥，在脚本中设置

## 配置说明

在脚本的 `__init__` 方法中，可以直接修改以下配置参数：

```python
# 请直接在此处填入你的 Kimi API 密钥 (来自 Moonshot AI 开放平台)
self.api_key = "your_kimi_api_key_here"

# --- 内容生成配置 ---
self.notes_count = 3               # 要生成的笔记数量
self.images_per_note = 3           # 每个笔记生成的图片数量
self.content_theme = "泰国旅游攻略"  # 笔记主题
self.style = "潮流打卡风"           # 内容风格
self.target_audience = "20-35岁热爱旅行、关注性价比/体验感的群体" # 目标受众

# --- 发布配置 ---
self.auto_publish = True          # 是否自动发布到小红书
self.publish_delay = 60           # 生成后等待多少秒发布（单位：秒）
self.publish_interval = 120       # 两篇笔记之间的发布间隔（单位：秒）
```

## 使用方法

1. 首先确保已经通过以下命令获取小红书的Cookie：

```
python xhs_toolkit.py cookie save
```

2. 修改脚本中的配置参数（设置API密钥、主题、风格等）

3. 运行脚本开始生成并发布：

```
python "Kimi API.py"
```

## 输出说明

脚本会在当前目录下创建两个输出文件夹：

- `output/notes/` - 保存生成的笔记文本内容
- `output/images/` - 保存生成的笔记配图

每个笔记会生成：
- 一个文本文件，包含标题、内容和图片路径
- 多张图片文件（数量由 `images_per_note` 参数决定）

## 自动发布流程

1. 生成一篇完整的笔记（包含标题、内容和图片）
2. 等待 `publish_delay` 秒
3. 自动将笔记发布到小红书
4. 发布成功后，等待 `publish_interval` 秒再生成下一篇
5. 如果发布失败，则中止后续笔记的发布

## 注意事项

1. 请合理设置发布间隔，避免频繁发布导致账号异常
2. 首次使用前，建议先将 `auto_publish` 设置为 `False`，检查生成的内容是否符合预期
3. 如果发布失败，请检查Cookie是否有效，可以使用 `python xhs_toolkit.py cookie validate` 命令验证

## 故障排除

- 如果遇到发布失败，请检查Cookie是否有效
- 如果内容生成失败，请检查API密钥是否正确
- 如果脚本运行中断，请检查日志了解详细错误信息

## 免责声明

本工具仅供学习和研究使用，请勿用于商业用途。使用本工具产生的任何后果由用户自行承担。 