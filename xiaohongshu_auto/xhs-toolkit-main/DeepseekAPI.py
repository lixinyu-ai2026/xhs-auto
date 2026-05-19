import os
import requests
from playwright.sync_api import sync_playwright
import time
import random
import re
from dotenv import load_dotenv
import sys
import asyncio
import argparse

# 尝试导入PIL相关模块
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: PIL库未安装，无法自动创建默认图片，请手动添加图片到default_images目录")

# 导入发布相关模块
from src.core.config import XHSConfig
from src.xiaohongshu.client import XHSClient
from src.xiaohongshu.models import XHSNote
from src.utils.logger import setup_logger, get_logger

# 初始化日志
logger = get_logger(__name__)
setup_logger()

class XiaohongshuAutoGenerator:
    """
    一个使用 Deepseek API 自动生成小红书图文笔记的脚本。
    所有配置直接在此脚本中完成。
    
    支持的图片风格:
    - 标准: 普通的图文展示风格
    - 杂志封面: 时尚杂志封面风格
    - 极简信息: 清晰简洁的信息图表风格
    - 活泼活力: 充满活力的色彩鲜艳风格
    - 自定义信息: 专业的信息展示模板

    """
    def __init__(self):
        """
        初始化生成器，加载配置并创建输出目录。
        """
        print("正在初始化生成器...")

        # ==================== 配置区域 ====================
        # 从环境变量加载API密钥
        load_dotenv()
        self.api_key = os.getenv("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise ValueError("请设置环境变量SILICONFLOW_API_KEY或在.env文件中配置")

        # --- 内容生成配置 ---
        self.notes_count = 1
        self.images_per_note = 4
        self.content_theme = "韩国女团blackpink"  # 可以修改为任何主题
        self.style = "Kpop"  # 可以修改为任何风格
        self.target_audience = "韩女粉"  # 可以修改为任何目标受众
        self.max_content_length = 400  # 文案最大字数限制
        
        # --- 图片生成配置 ---
        # 渲染图片的浏览器视口大小
        self.VIEWPORT_WIDTH = 750
        self.VIEWPORT_HEIGHT = 800
        
        # 图片风格选择 - 可选值: "标准", "杂志封面", "极简信息", "活泼活力", "自定义信息"
        self.image_style = "标准"  # 默认使用标准风格
        
        self.image_themes = {
            "杂志封面": {
                "core": ["magazine cover style", "elegant", "minimalist", "high-end", "premium quality", "fashion editorial"],
                "lighting": ["soft diffused lighting", "studio lighting", "professional lighting"],
                "style": ["VOGUE style", "editorial", "fashion magazine", "luxury", "sophisticated"],
                "background": ["clean background", "muted tones", "Morandi color palette", "monochromatic"],
                "composition": ["plenty of white space", "balanced layout", "serif typography", "editorial layout"]
            },
            "极简信息": {
                "core": ["infographic", "clean design", "information design", "minimal", "organized"],
                "lighting": ["flat lighting", "even lighting", "clean lighting"],
                "style": ["grid layout", "modern", "systematic", "professional", "educational"],
                "background": ["solid color background", "light background", "clean white", "subtle texture"],
                "composition": ["strong typography", "clear hierarchy", "organized grid", "icons and arrows"]
            },
            "手绘涂鸦": {
                "core": ["cute doodle", "hand drawn", "kawaii", "playful", "artistic"],
                "lighting": ["bright and cheerful", "vibrant lighting", "soft pastel lighting"],
                "style": ["cartoon style", "sketchy", "fun", "casual", "whimsical"],
                "background": ["paper texture", "pastel background", "playful pattern", "light texture"],
                "composition": ["scattered elements", "dynamic layout", "sticker style", "decorative elements"]
            },
            "拼贴手帐": {
                "core": ["collage style", "scrapbook", "journal", "vintage collage", "mood board"],
                "lighting": ["natural lighting", "vintage lighting", "soft shadows"],
                "style": ["layered composition", "vintage", "nostalgic", "crafty", "artistic"],
                "background": ["kraft paper", "grid paper", "vintage paper", "textured background"],
                "composition": ["overlapping elements", "mixed media", "polaroid frames", "washi tape"]
            },
            "复古胶片": {
                "core": ["film photography", "vintage film", "analog style", "cinematic", "retro"],
                "lighting": ["film lighting", "golden hour", "kodak portra", "light leaks"],
                "style": ["35mm film", "grainy texture", "movie still", "nostalgic"],
                "background": ["urban scene", "street photography", "natural setting"],
                "composition": ["16:9 ratio", "film borders", "date stamp", "grain texture"]
            },
            "大字报": {
                "core": ["bold typography", "eye-catching", "dramatic", "impactful", "vibrant"],
                "lighting": ["high contrast lighting", "dramatic lighting", "bold shadows"],
                "style": ["poster style", "advertising", "bold design", "youth culture"],
                "background": ["high saturation", "neon colors", "contrasting colors"],
                "composition": ["large text", "product close-up", "before after", "minimal elements"]
            }
        }
        
        # 通用图片质量设置
        self.image_quality = [
            "high quality", "masterpiece", "ultra detailed", "8k", "sharp focus",
            "professional", "commercial photography", "advertising quality"
        ]
        
        # 通用氛围设置
        self.image_atmosphere = [
            "aesthetic", "trendy", "modern", "social media style",
            "xiaohongshu style", "popular on social media", "viral content"
        ]
        
        # 字体风格
        self.font_styles = {
            "优雅": ["serif typography", "elegant font", "traditional chinese typography"],
            "现代": ["sans-serif", "clean typography", "modern font"],
            "可爱": ["cute typography", "handwritten", "casual font"]
        }
        
        # 色彩风格
        self.color_styles = {
            "高级": ["muted colors", "morandi color palette", "sophisticated palette"],
            "活力": ["vibrant colors", "high saturation", "contrasting colors"],
            "清新": ["fresh colors", "pastel palette", "light and airy"]
        }
        
        # --- 发布配置 ---
        self.auto_publish = True          # 是否自动发布到小红书
        self.publish_delay = 10           # 生成后等待多少秒发布
        self.publish_interval = 60        # 两篇笔记之间的发布间隔
        
        # Playwright 浏览器路径配置
        self.playwright_browsers_path = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
        # ==================================================

        print(f"配置加载完成：将生成 {self.notes_count} 篇关于 '{self.content_theme}' 的笔记。")
        if self.auto_publish:
            print(f"自动发布已启用：笔记将在生成后 {self.publish_delay} 秒内发布到小红书。")

        # 创建必要的目录
        for dir_path in ["output/notes", "output/images", "default_images"]:
            os.makedirs(dir_path, exist_ok=True)
            print(f"目录已准备就绪: {dir_path}")
        
        # 检查并创建默认图片
        default_image_path = os.path.join("default_images", "default_image.jpg")
        if not os.path.exists(default_image_path):
            self.create_default_image(default_image_path)
        
        # 初始化XHS客户端（全局）
        self.xhs_client = None

    def create_default_image(self, image_path):
        """创建一个简单的默认图片"""
        if not PIL_AVAILABLE:
            print("无法创建默认图片: PIL库未安装")
            print("请手动将图片添加到以下位置:")
            print(f"- {image_path}")
            return False
        
        try:
            # 创建800x800的图片
            img = Image.new('RGB', (800, 800), color=(240, 248, 255))
            draw = ImageDraw.Draw(img)
            
            # 在图片中间绘制文本
            try:
                # 尝试加载字体，如果失败则使用默认字体
                font = ImageFont.truetype("arial.ttf", 36)
            except:
                font = ImageFont.load_default()
                
            text = f"关于{self.content_theme}的笔记"
            
            # 不同版本的PIL接口可能不同
            try:
                # 新版PIL
                text_width = draw.textlength(text, font=font)
            except AttributeError:
                # 旧版PIL，估算宽度
                text_width = len(text) * 20
                
            position = ((800 - text_width) / 2, 400)
            
            draw.text(position, text, font=font, fill=(0, 0, 0))
            
            # 保存图片
            img.save(image_path)
            print(f"成功创建默认图片: {image_path}")
            return True
            
        except Exception as e:
            print(f"创建默认图片失败: {e}")
            print("请手动将图片添加到以下位置:")
            print(f"- {image_path}")
            return False

    def call_api(self, prompt: str) -> str:
        """
        调用 Siliconflow API 并返回结果。
        包含错误处理和自动重试逻辑。
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-ai/DeepSeek-V3",  # 或者使用 deepseek-ai/DeepSeek-R1
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        max_retries = 3
        base_delay = 3

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.siliconflow.cn/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 429:  # 速率限制
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"⚠️ API速率限制，等待 {delay:.1f} 秒后重试... ({attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                    
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️ API请求失败: {e}，{delay}秒后重试...")
                    time.sleep(delay)
                else:
                    raise Exception(f"API调用失败，已重试{max_retries}次: {e}")
        
        raise Exception("API调用失败，已达到最大重试次数")

    def generate_note_title(self) -> str:
        """生成小红书笔记标题"""
        prompt = f"""请为小红书生成一个关于"{self.content_theme}"的爆款标题，要求：
1. 标题必须明确与"{self.content_theme}"主题强相关，不要偏离主题。
2. 包含1-2个相关的 emoji 表情。
3. 长度不超过20个字。
4. 风格为"{self.style}"。
5. 目标受众是"{self.target_audience}"。

重要提示：
- 标题必须直接与"{self.content_theme}"相关，不要生成其他主题的内容。
- 标题中必须包含明确的与主题相关的关键词。
- 不要将主题与目标受众混淆。

请直接返回标题内容，不要包含任何解释或修饰。
"""
        title = self.call_api(prompt).strip().strip('"')
        
        return title

    def generate_note_content(self, title: str) -> str:
        """根据标题生成完整的小红书笔记文案。"""
        prompt = f"""根据以下标题为小红书生成一篇精简完整的笔记文案：
标题：{title}
主题：{self.content_theme}

要求：
1. 文案风格为"{self.style}"。
2. 目标受众是"{self.target_audience}"。
3. 包含适当的表情符号，让内容更生动。
4. 段落分明，排版清晰，易于阅读。
5. 总字数控制在250-300字，简洁有力。
6. 内容结构：简短开头 + 3个核心要点（每个要点1-2句话） + 简短结尾。
7. 不要在文末添加任何标签，纯文本内容即可。
8. 重要：不要在文案开头重复标题内容，直接开始正文。
9. 文案要写完整，可以简约但不能写一半。

重要提示：
- 文案必须严格围绕"{self.content_theme}"主题展开，不要偏离主题。
- 文案中必须包含与"{self.content_theme}"直接相关的具体内容、产品、方法或建议。
- 不要将主题与目标受众混淆。

请直接返回文案内容，不需要任何解释或修饰。
"""
        content = self.call_api(prompt)
        
        # 清理内容中的多余标记
        content = content.strip('"').strip()
        content = re.sub(r'\*\*|\#\#|\=\=|\-\-', '', content)
        
        # 检查是否以标题开头，如果是则去除
        if content.startswith(title) or content.startswith(title.strip('✨🌟💄💋')):
            # 找到第一个段落结束位置
            first_para_end = content.find('\n\n')
            if first_para_end > 0:
                content = content[first_para_end + 2:]
            else:
                # 如果找不到段落分隔，尝试找到第一个句号
                first_sentence_end = content.find('。')
                if first_sentence_end > 0 and first_sentence_end < len(title) + 10:
                    content = content[first_sentence_end + 1:]
        
        # 确保文案不超过最大长度限制
        max_length = min(self.max_content_length, 300)  # 设置更短的长度限制
        if len(content) > max_length:
            # 查找最后一个完整句子的位置
            last_sentence = content[:max_length].rfind('。')
            if last_sentence > max_length * 0.7:  # 确保至少保留70%的内容
                content = content[:last_sentence+1]
            else:
                content = content[:max_length] + "..."
        
        # 移除文案中可能存在的标签
        content = re.sub(r'(#\w+\s*)+$', '', content).strip()
        
        return content

    def generate_default_tags(self):
        """生成默认标签"""
        tags = [
            f"#{self.content_theme}",
            f"#{self.style}风格",
            f"#{self.target_audience}必看",
            "#小红书探店",
            "#精选推荐"
        ]
        return random.sample(tags, min(5, len(tags)))

    def extract_tags_from_content(self, content):
        """从内容中提取话题标签。"""
        # 使用正则表达式匹配标签
        tags = re.findall(r'#([^#\s]+)', content)
        
        # 去重并保持顺序
        seen = set()
        unique_tags = []
        for tag in tags:
            tag = tag.strip('.,;:!?')  # 清理标点符号
            if tag.lower() not in seen:
                seen.add(tag.lower())
                unique_tags.append(tag)
        
        # 如果没有找到标签，生成相关标签
        if not unique_tags:
            prompt = f"""
请为这篇小红书笔记生成3-5个相关的话题标签，要求：
1. 主题：{self.content_theme}
2. 风格：{self.style}
3. 目标受众：{self.target_audience}
4. 内容概要：{content[:100]}...

标签要求：
1. 不要带#号
2. 每个标签2-8个字
3. 符合小红书平台特点
4. 容易被搜索到
5. 与内容高度相关
6. 必须与主题"{self.content_theme}"强相关

请直接返回标签，用空格分隔，不要任何解释。
"""
            tags_text = self.call_api(prompt)
            unique_tags = [tag.strip() for tag in tags_text.split() if tag.strip()]
        
        return unique_tags[:5]  # 最多返回5个标签

    def get_image_theme_prompts(self, content_type="美食"):
        """根据内容类型获取相应的图片生成提示词"""
        theme = self.image_themes.get(content_type, self.image_themes["美食"])
        
        # 随机选择每个类别的1-2个关键词
        core = random.sample(theme["core"], min(2, len(theme["core"])))
        lighting = random.sample(theme["lighting"], min(2, len(theme["lighting"])))
        style = random.sample(theme["style"], min(2, len(theme["style"])))
        background = random.sample(theme["background"], 1)
        
        # 随机选择1-2个通用质量关键词
        quality = random.sample(self.image_quality, min(2, len(self.image_quality)))
        
        # 随机选择1-2个氛围关键词
        atmosphere = random.sample(self.image_atmosphere, min(2, len(self.image_atmosphere)))
        
        # 组合所有关键词
        prompts = core + lighting + style + background + quality + atmosphere
        return ", ".join(prompts)

    def generate_image_prompt(self, description: str, image_index: int) -> str:
        """生成图片提示词"""
        # 确保图片主题与内容主题强相关
        content_theme_keywords = f"{self.content_theme} related content, {self.content_theme} themed image"
        
        # 根据描述内容判断主题类型
        content_type = "美食"  # 默认类型
        for theme in self.image_themes.keys():
            if any(keyword in description for keyword in self.image_themes[theme]["core"]):
                content_type = theme
                break
        
        # 获取主题相关的提示词
        theme_prompts = self.get_image_theme_prompts(content_type)
        
        # 构建完整的提示词
        prompt = f"""
Generate a beautiful image for Xiaohongshu (Little Red Book) post with the following requirements:

Theme: {self.content_theme} - {description}

Main subject: {content_theme_keywords}

Style requirements:
{theme_prompts}

Additional requirements:
1. Clean and minimalist composition
2. Suitable for social media
3. Text space reserved if needed
4. Modern and trendy aesthetic
5. High-quality and professional look
6. Must be clearly related to {self.content_theme}

--v 6.0 --style raw
"""
        return prompt

    def generate_image_html(self, description: str, image_index: int) -> str:
        """生成图片的HTML描述，用于生成图片。"""
        # 使用固定的图片风格，不再随机选择
        style_type = self.image_style
        
        if style_type == "杂志封面":
            return self.generate_magazine_html(description, image_index)
        elif style_type == "极简信息":
            return self.generate_minimal_info_html(description, image_index)
        elif style_type == "活泼活力":
            return self.generate_vibrant_html(description, image_index)
        elif style_type == "自定义信息":
            return self.generate_custom_info_html(description, image_index)
        else:
            return self.generate_standard_html(description, image_index)
    
    def generate_magazine_html(self, description: str, image_index: int) -> str:
        """生成杂志封面风格的HTML模板"""
        # 随机选择配色方案
        color_schemes = [
            {
                "primary": "#FF4081",  # 粉红色
                "secondary": "#3F51B5", # 靛蓝色
                "text": "#212121",      # 深灰色
                "background": "#F5F5F5", # 浅灰色
                "accent": "#FFC107"     # 琥珀色
            },
            {
                "primary": "#009688",   # 蓝绿色
                "secondary": "#FF5722", # 深橙色
                "text": "#212121",      # 深灰色
                "background": "#FAFAFA", # 浅灰色
                "accent": "#FFEB3B"     # 黄色
            },
            {
                "primary": "#673AB7",   # 深紫色
                "secondary": "#4CAF50", # 绿色
                "text": "#212121",      # 深灰色
                "background": "#F5F5F5", # 浅灰色
                "accent": "#FF9800"     # 橙色
            }
        ]
        colors = random.choice(color_schemes)
        
        # 提取标题和内容
        parts = description.split('，', 1)
        if len(parts) > 1:
            title = parts[0].strip()
            content = parts[1].strip()
        else:
            title = self.content_theme
            content = description.strip()
            
        # 确保标题与主题相关
        if self.content_theme not in title:
            title = f"{self.content_theme} | {title}"
            
        # 生成随机的副标题
        subtitles = [
            f"探索{self.content_theme}的魅力",
            f"{self.content_theme}必看指南",
            f"{self.target_audience}的{self.content_theme}攻略",
            f"{self.style}风格的{self.content_theme}分享",
            f"独家{self.content_theme}推荐"
        ]
        subtitle = random.choice(subtitles)
        
        # 随机选择表情符号
        emojis = ["✨", "🌟", "💖", "🎀", "🌸", "💕", "🌈", "🍭", "🌺", "🌹", "🎉", "🎊", "💫", "⭐", "🔆"]
        random_emojis = random.sample(emojis, 5)
        
        # 生成随机的装饰元素位置
        decoration_positions = [
            {"top": f"{random.randint(5, 15)}%", "left": f"{random.randint(5, 15)}%", "size": f"{random.randint(40, 60)}px"},
            {"top": f"{random.randint(70, 85)}%", "right": f"{random.randint(5, 15)}%", "size": f"{random.randint(30, 50)}px"},
            {"top": f"{random.randint(40, 60)}%", "left": f"{random.randint(80, 90)}%", "size": f"{random.randint(20, 40)}px"}
        ]
        
        # 生成随机的强调文本
        highlight_texts = [
            f"{random_emojis[0]} 本期特辑 {random_emojis[1]}",
            f"{random_emojis[2]} 独家专访 {random_emojis[3]}",
            f"{random_emojis[4]} 精选推荐",
            "🔍 深度解析",
            "🌟 年度精选"
        ]
        highlight_text = random.choice(highlight_texts)
        
        # 生成随机的专栏标题
        column_titles = [
            f"「{self.content_theme}」特别专栏",
            f"「{self.style}」风格指南",
            f"「{self.target_audience}」必读专题",
            f"「{self.content_theme}」趋势前瞻",
            f"「{self.style}」美学解析"
        ]
        column_title = random.choice(column_titles)
        
        # 生成随机的杂志特色内容
        features = [
            [
                f"✓ {self.style}风格{self.content_theme}全解析",
                f"✓ 适合{self.target_audience}的个性化指南",
                f"✓ 专业达人独家分享"
            ],
            [
                f"✓ 本季流行趋势预测",
                f"✓ {self.content_theme}搭配秘籍",
                f"✓ 编辑精选单品推荐"
            ],
            [
                f"✓ {self.content_theme}进阶指南",
                f"✓ 从入门到精通的全方位攻略",
                f"✓ 达人亲身体验分享"
            ]
        ]
        feature_list = random.choice(features)
        
        # 生成随机的杂志封面号码
        issue_number = f"NO.{random.randint(1, 199)}"
        
        # 生成随机的杂志价格
        price = f"¥{random.randint(15, 49)}"
        
        # 将内容分段
        content_parts = content.split("\n\n")
        if len(content_parts) < 2:
            content_parts = [content[:len(content)//2], content[len(content)//2:]]
        
        # 生成随机的专题标签
        special_tags = [
            f"年度{self.content_theme}专题",
            f"{self.style}风格特辑",
            f"{self.target_audience}专属指南",
            "编辑精选",
            "达人推荐"
        ]
        special_tag = random.choice(special_tags)
        
        # 生成随机的热门话题
        hot_topics = [
            f"{self.content_theme}的未来发展趋势",
            f"如何打造专属{self.style}风格",
            f"{self.target_audience}必知的{self.content_theme}技巧",
            f"{self.content_theme}与生活方式的完美融合",
            f"从零开始学习{self.content_theme}"
        ]
        hot_topic = random.choice(hot_topics)
        
        # 生成HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap');
                
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Noto Sans SC', sans-serif;
                    background: {colors['background']};
                    color: {colors['text']};
                    overflow: hidden;
                }}
                
                .container {{
                    width: 750px;
                    height: 800px;
                    margin: 0 auto;
                    padding: 0;
                    box-sizing: border-box;
                    position: relative;
                    overflow: hidden;
                    background: linear-gradient(135deg, {colors['primary']}20, {colors['secondary']}20);
                }}
                
                .magazine-header {{
                    background: {colors['primary']};
                    color: white;
                    padding: 15px 25px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                
                .magazine-name {{
                    font-family: 'Playfair Display', serif;
                    font-weight: 900;
                    font-size: 24px;
                    text-transform: uppercase;
                    letter-spacing: 2px;
                }}
                
                .magazine-info {{
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    font-size: 14px;
                }}
                
                .issue {{
                    border: 1px solid white;
                    padding: 3px 8px;
                }}
                
                .price {{
                    font-weight: 700;
                }}
                
                .main-content {{
                    padding: 30px;
                    position: relative;
                }}
                
                .title-area {{
                    margin-bottom: 25px;
                }}
                
                .main-title {{
                    font-size: 48px;
                    font-weight: 900;
                    line-height: 1.1;
                    margin-bottom: 15px;
                    color: {colors['primary']};
                    font-family: 'Playfair Display', serif;
                    text-shadow: 2px 2px 0 {colors['secondary']}40;
                }}
                
                .subtitle {{
                    font-size: 18px;
                    font-weight: 500;
                    color: {colors['secondary']};
                    margin-bottom: 15px;
                }}
                
                .special-tag {{
                    display: inline-block;
                    background: {colors['accent']};
                    color: white;
                    padding: 5px 12px;
                    font-size: 14px;
                    font-weight: 700;
                    margin-bottom: 20px;
                    transform: rotate(-2deg);
                    box-shadow: 3px 3px 0 {colors['primary']}60;
                }}
                
                .content-area {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 25px;
                    margin-bottom: 25px;
                }}
                
                .content-box {{
                    background: white;
                    padding: 20px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                    position: relative;
                }}
                
                .content-box::before {{
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 5px;
                    height: 100%;
                    background: {colors['primary']};
                }}
                
                .content {{
                    font-size: 14px;
                    line-height: 1.6;
                }}
                
                .highlight-box {{
                    background: {colors['secondary']}15;
                    border: 2px solid {colors['secondary']};
                    padding: 15px;
                    margin: 20px 0;
                    text-align: center;
                    font-weight: 700;
                    font-size: 18px;
                    color: {colors['secondary']};
                }}
                
                .feature-list {{
                    background: {colors['primary']}10;
                    border-radius: 5px;
                    padding: 15px 20px;
                    margin: 20px 0;
                }}
                
                .feature-title {{
                    font-size: 16px;
                    font-weight: 700;
                    margin-bottom: 10px;
                    color: {colors['primary']};
                    display: flex;
                    align-items: center;
                }}
                
                .feature-title::before {{
                    content: "{random_emojis[0]}";
                    margin-right: 8px;
                }}
                
                .feature-item {{
                    margin-bottom: 8px;
                    font-size: 14px;
                }}
                
                .hot-topic {{
                    background: {colors['accent']}20;
                    border-left: 4px solid {colors['accent']};
                    padding: 15px;
                    margin: 20px 0;
                }}
                
                .hot-topic-title {{
                    font-size: 16px;
                    font-weight: 700;
                    margin-bottom: 10px;
                    color: {colors['accent']};
                }}
                
                .hot-topic-content {{
                    font-size: 14px;
                }}
                
                .tag-container {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    margin-top: 20px;
                }}
                
                .tag {{
                    display: inline-block;
                    background: {colors['primary']}20;
                    color: {colors['primary']};
                    padding: 5px 12px;
                    border-radius: 20px;
                    font-size: 13px;
                }}
                
                .decoration {{
                    position: absolute;
                    z-index: 1;
                    opacity: 0.8;
                }}
                
                .decoration-1 {{
                    width: 150px;
                    height: 150px;
                    top: 20%;
                    right: -50px;
                    background: {colors['primary']}30;
                    border-radius: 50%;
                }}
                
                .decoration-2 {{
                    width: 100px;
                    height: 100px;
                    bottom: 10%;
                    left: -30px;
                    background: {colors['secondary']}30;
                    border-radius: 50%;
                }}
                
                .emoji-decoration {{
                    position: absolute;
                    font-size: 24px;
                    z-index: 5;
                    text-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                
                .barcode {{
                    position: absolute;
                    bottom: 20px;
                    right: 20px;
                    width: 80px;
                    height: 40px;
                    background: repeating-linear-gradient(90deg, #000, #000 2px, #fff 2px, #fff 4px);
                }}
                
                .barcode::after {{
                    content: 'ISSN 1234-5678';
                    position: absolute;
                    bottom: -20px;
                    left: 0;
                    font-size: 10px;
                    color: {colors['text']};
                }}
                
                .corner-label {{
                    position: absolute;
                    top: 0;
                    right: 0;
                    background: {colors['accent']};
                    color: white;
                    padding: 30px 20px 10px;
                    font-size: 14px;
                    font-weight: 700;
                    transform: translateY(-50%) rotate(45deg) translateX(70%);
                    width: 200px;
                    text-align: center;
                    box-shadow: 0 5px 10px rgba(0,0,0,0.1);
                }}
                
                .column-box {{
                    background: {colors['secondary']}10;
                    border: 1px dashed {colors['secondary']};
                    padding: 15px;
                    margin: 20px 0;
                }}
                
                .column-title {{
                    font-size: 16px;
                    font-weight: 700;
                    color: {colors['secondary']};
                    margin-bottom: 10px;
                    text-align: center;
                }}
                
                .quote-box {{
                    font-style: italic;
                    padding: 10px 15px;
                    border-left: 3px solid {colors['accent']};
                    margin: 15px 0;
                    background: {colors['accent']}10;
                    font-size: 14px;
                }}
                
                .quote-box::before {{
                    content: '"';
                    font-size: 24px;
                    color: {colors['accent']};
                    margin-right: 5px;
                    vertical-align: -5px;
                }}
                
                .quote-box::after {{
                    content: '"';
                    font-size: 24px;
                    color: {colors['accent']};
                    margin-left: 5px;
                    vertical-align: -5px;
                }}
                
                .footer {{
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    width: 100%;
                    padding: 10px 30px;
                    background: {colors['primary']};
                    color: white;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    font-size: 12px;
                    box-sizing: border-box;
                }}
                
                .social-icons {{
                    display: flex;
                    gap: 10px;
                }}
                
                .social-icon {{
                    width: 20px;
                    height: 20px;
                    background: white;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;
                    color: {colors['primary']};
                    font-weight: 700;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="decoration decoration-1"></div>
                <div class="decoration decoration-2"></div>
                
                <div class="emoji-decoration" style="top: {decoration_positions[0]['top']}; left: {decoration_positions[0]['left']}; font-size: {decoration_positions[0]['size']};">{random_emojis[0]}</div>
                <div class="emoji-decoration" style="top: {decoration_positions[1]['top']}; right: {decoration_positions[1]['right']}; font-size: {decoration_positions[1]['size']};">{random_emojis[1]}</div>
                
                <div class="corner-label">{self.style}风格</div>
                
                <div class="magazine-header">
                    <div class="magazine-name">{self.content_theme} MAG</div>
                    <div class="magazine-info">
                        <div class="issue">{issue_number}</div>
                        <div class="price">{price}</div>
                    </div>
                </div>
                
                <div class="main-content">
                    <div class="title-area">
                        <div class="special-tag">{special_tag}</div>
                        <div class="main-title">{title}</div>
                        <div class="subtitle">{subtitle}</div>
                    </div>
                    
                    <div class="content-area">
                        <div class="content-box">
                            <div class="content">
                                {content_parts[0]}
                            </div>
                            
                            <div class="quote-box">
                                {self.content_theme}是{self.target_audience}展现{self.style}风格的绝佳方式
                            </div>
                        </div>
                        
                        <div class="content-box">
                            <div class="content">
                                {content_parts[1] if len(content_parts) > 1 else ''}
                            </div>
                            
                            <div class="column-box">
                                <div class="column-title">{column_title}</div>
                                <div class="content">
                                    {self.content_theme}正成为{self.target_audience}的新宠，尤其是{self.style}风格的表现形式更是备受关注。
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="highlight-box">
                        {highlight_text}
                    </div>
                    
                    <div class="feature-list">
                        <div class="feature-title">本期亮点</div>
                        <div class="feature-item">{feature_list[0]}</div>
                        <div class="feature-item">{feature_list[1]}</div>
                        <div class="feature-item">{feature_list[2]}</div>
                    </div>
                    
                    <div class="hot-topic">
                        <div class="hot-topic-title">热门话题</div>
                        <div class="hot-topic-content">{hot_topic}</div>
                    </div>
                    
                    <div class="tag-container">
                        <span class="tag">#{self.content_theme}</span>
                        <span class="tag">#{self.style}风格</span>
                        <span class="tag">#{self.target_audience}</span>
                        <span class="tag">#杂志风格</span>
                        <span class="tag">#时尚潮流</span>
                    </div>
                </div>
                
                <div class="barcode"></div>
                
                <div class="footer">
                    <div>{self.content_theme} MAGAZINE © 2023</div>
                    <div class="social-icons">
                        <div class="social-icon">f</div>
                        <div class="social-icon">in</div>
                        <div class="social-icon">ig</div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
        
    def generate_minimal_info_html(self, description: str, image_index: int) -> str:
        """生成极简信息风格的HTML模板"""
        # 随机选择配色方案
        color_schemes = [
            {
                "primary": "#2C3E50",   # 深蓝灰色
                "secondary": "#E74C3C", # 红色
                "text": "#333333",      # 深灰色
                "background": "#ECF0F1", # 浅灰色
                "accent": "#3498DB"     # 蓝色
            },
            {
                "primary": "#34495E",   # 深蓝色
                "secondary": "#F39C12", # 橙色
                "text": "#2C3E50",      # 深蓝灰色
                "background": "#FFFFFF", # 白色
                "accent": "#2ECC71"     # 绿色
            },
            {
                "primary": "#1A237E",   # 深靛蓝色
                "secondary": "#FFC107", # 琥珀色
                "text": "#212121",      # 深灰色
                "background": "#F5F5F5", # 浅灰色
                "accent": "#FF5722"     # 深橙色
            }
        ]
        colors = random.choice(color_schemes)
        
        # 提取标题和内容
        parts = description.split('，', 1)
        if len(parts) > 1:
            title = parts[0].strip()
            content = parts[1].strip()
        else:
            title = self.content_theme
            content = description.strip()
            
        # 确保标题与主题相关
        if self.content_theme not in title:
            title = f"{self.content_theme} | {title}"
            
        # 将内容分段
        content_parts = content.split("\n\n")
        if len(content_parts) < 2:
            content_parts = [content[:len(content)//2], content[len(content)//2:]]
            
        # 随机选择表情符号
        emojis = ["✨", "🌟", "💖", "🎀", "🌸", "💕", "🌈", "🍭", "🌺", "🌹", "🎉", "🎊", "💫", "⭐", "🔆"]
        random_emojis = random.sample(emojis, 5)
        
        # 生成随机的关键词
        keywords = [
            f"{self.content_theme}",
            f"{self.style}风格",
            f"{self.target_audience}必备",
            f"精选推荐",
            f"达人分享",
            f"时尚潮流",
            f"个性搭配"
        ]
        selected_keywords = random.sample(keywords, 4)
        
        # 生成随机的数据点
        data_points = [
            {"label": "满意度", "value": f"{random.randint(85, 99)}%"},
            {"label": "推荐指数", "value": f"{random.randint(4, 5)}.{random.randint(0, 9)}/5"},
            {"label": "流行趋势", "value": f"{random.choice(['上升', '稳定', '热门'])}"},
            {"label": "适用场景", "value": f"{random.randint(3, 8)}+"}
        ]
        selected_data_points = random.sample(data_points, 3)
        
        # 生成随机的要点
        key_points = [
            f"{self.style}风格{self.content_theme}的特点",
            f"适合{self.target_audience}的选择理由",
            f"{self.content_theme}的搭配技巧",
            f"如何打造个性化{self.style}风格",
            f"{self.content_theme}的日常应用"
        ]
        selected_key_points = random.sample(key_points, 3)
        
        # 生成随机的独立文字内容
        extra_info_items = [
            [
                f"✓ {random.choice(['简约', '高级', '时尚', '个性', '优雅'])}{self.style}风格",
                f"✓ 适合{random.choice(['日常', '约会', '工作', '休闲', '正式'])}场合",
                f"✓ {random.choice(['百搭', '易于搭配', '高性价比', '经典永不过时', '突显个性'])}单品"
            ],
            [
                f"✓ {random.choice(['2023', '2024', '本季', '流行', '经典'])}必备款式",
                f"✓ {random.choice(['达人', '博主', '明星', '设计师', '时尚编辑'])}推荐",
                f"✓ {random.choice(['高级感', '质感', '设计感', '实用性', '舒适度'])}极佳"
            ],
            [
                f"✓ {random.choice(['新手', '入门', '进阶', '高级', '专业'])}级别指南",
                f"✓ {random.choice(['快速', '简单', '高效', '精准', '全面'])}掌握要点",
                f"✓ {random.choice(['独家', '专属', '定制', '个性化', '量身打造'])}建议"
            ]
        ]
        extra_info = random.choice(extra_info_items)
        
        # 生成随机的小贴士
        tips = [
            f"小贴士：{self.content_theme}最适合{self.target_audience}尝试！",
            f"达人建议：选择{self.style}风格更显个性！",
            f"注意：{self.content_theme}需要注意细节搭配哦~",
            f"经验分享：{self.content_theme}的关键在于用心体验！",
            f"独家秘诀：掌握这些技巧，轻松驾驭{self.content_theme}！"
        ]
        tip = random.choice(tips)
        
        # 生成随机的比较数据
        comparison_data = [
            {"category": f"传统{self.content_theme}", "pros": "经典稳重", "cons": "缺乏新意"},
            {"category": f"{self.style}风格{self.content_theme}", "pros": "个性时尚", "cons": "需要搭配技巧"},
            {"category": f"流行{self.content_theme}", "pros": "紧跟潮流", "cons": "更新较快"}
        ]
        
        # 生成HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&family=Roboto:wght@300;400;500;700&display=swap');
                
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Noto Sans SC', 'Roboto', sans-serif;
                    background: {colors['background']};
                    color: {colors['text']};
                    overflow: hidden;
                }}
                
                .container {{
                    width: 750px;
                    height: 800px;
                    margin: 0 auto;
                    padding: 30px;
                    box-sizing: border-box;
                    position: relative;
                    overflow: hidden;
                }}
                
                .header {{
                    margin-bottom: 25px;
                }}
                
                .title {{
                    font-size: 28px;
                    font-weight: 700;
                    color: {colors['primary']};
                    margin-bottom: 15px;
                    line-height: 1.3;
                    position: relative;
                    display: inline-block;
                }}
                
                .title::after {{
                    content: '';
                    position: absolute;
                    bottom: -5px;
                    left: 0;
                    width: 100%;
                    height: 3px;
                    background: {colors['secondary']};
                }}
                
                .subtitle {{
                    font-size: 16px;
                    color: {colors['text']}99;
                    margin-bottom: 10px;
                }}
                
                .grid-container {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin-bottom: 20px;
                }}
                
                .content-box {{
                    background: white;
                    border-radius: 8px;
                    padding: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                }}
                
                .content {{
                    font-size: 14px;
                    line-height: 1.6;
                    color: {colors['text']};
                }}
                
                .keywords-container {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    margin: 20px 0;
                }}
                
                .keyword {{
                    background: {colors['primary']}15;
                    color: {colors['primary']};
                    padding: 8px 15px;
                    border-radius: 20px;
                    font-size: 13px;
                    font-weight: 500;
                    display: flex;
                    align-items: center;
                }}
                
                .keyword::before {{
                    content: "#";
                    margin-right: 5px;
                    font-weight: 700;
                }}
                
                .data-container {{
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 15px;
                    margin: 20px 0;
                }}
                
                .data-item {{
                    background: white;
                    border-radius: 8px;
                    padding: 15px;
                    text-align: center;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                }}
                
                .data-value {{
                    font-size: 24px;
                    font-weight: 700;
                    color: {colors['secondary']};
                    margin-bottom: 5px;
                }}
                
                .data-label {{
                    font-size: 12px;
                    color: {colors['text']}99;
                    text-transform: uppercase;
                }}
                
                .key-points {{
                    margin: 20px 0;
                }}
                
                .key-point {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 12px;
                    background: white;
                    border-radius: 8px;
                    padding: 12px 15px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                }}
                
                .key-point-number {{
                    width: 25px;
                    height: 25px;
                    background: {colors['primary']};
                    color: white;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 14px;
                    font-weight: 700;
                    margin-right: 12px;
                }}
                
                .key-point-text {{
                    font-size: 14px;
                    color: {colors['text']};
                }}
                
                .extra-info-box {{
                    background: {colors['primary']}10;
                    border-radius: 8px;
                    padding: 15px 20px;
                    margin: 20px 0;
                }}
                
                .extra-info-title {{
                    font-size: 16px;
                    font-weight: 700;
                    color: {colors['primary']};
                    margin-bottom: 12px;
                    display: flex;
                    align-items: center;
                }}
                
                .extra-info-title::before {{
                    content: "{random_emojis[0]}";
                    margin-right: 8px;
                }}
                
                .extra-info-item {{
                    margin-bottom: 8px;
                    font-size: 14px;
                }}
                
                .tip-box {{
                    background: {colors['secondary']}15;
                    border-radius: 8px;
                    padding: 12px 15px;
                    margin: 20px 0;
                    font-size: 14px;
                    color: {colors['text']};
                    position: relative;
                }}
                
                .tip-box::before {{
                    content: "💡";
                    margin-right: 8px;
                }}
                
                .comparison-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                }}
                
                .comparison-table th {{
                    background: {colors['primary']};
                    color: white;
                    text-align: left;
                    padding: 12px 15px;
                    font-size: 14px;
                    font-weight: 500;
                }}
                
                .comparison-table td {{
                    padding: 12px 15px;
                    font-size: 14px;
                    border-bottom: 1px solid {colors['background']};
                }}
                
                .comparison-table tr:last-child td {{
                    border-bottom: none;
                }}
                
                .pros {{
                    color: {colors['accent']};
                }}
                
                .cons {{
                    color: {colors['secondary']};
                }}
                
                .footer {{
                    margin-top: 20px;
                    font-size: 12px;
                    color: {colors['text']}80;
                    text-align: center;
                }}
                
                .tag-container {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    margin-top: 20px;
                }}
                
                .tag {{
                    display: inline-block;
                    background: {colors['primary']}20;
                    color: {colors['primary']};
                    padding: 5px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                }}
                
                .corner-ribbon {{
                    position: absolute;
                    top: 25px;
                    right: -30px;
                    background: {colors['secondary']};
                    color: white;
                    padding: 5px 30px;
                    transform: rotate(45deg);
                    font-size: 12px;
                    font-weight: 700;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    z-index: 10;
                }}
                
                .emoji-decoration {{
                    position: absolute;
                    font-size: 20px;
                    z-index: 5;
                    opacity: 0.5;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="emoji-decoration" style="top: 10%; left: 5%;">{random_emojis[0]}</div>
                <div class="emoji-decoration" style="top: 80%; right: 5%;">{random_emojis[1]}</div>
                <div class="emoji-decoration" style="top: 50%; left: 90%;">{random_emojis[2]}</div>
                
                <div class="corner-ribbon">{self.style}风格</div>
                
                <div class="header">
                    <div class="title">{title}</div>
                    <div class="subtitle">专为{self.target_audience}打造的{self.content_theme}指南</div>
                </div>
                
                <div class="keywords-container">
                    {' '.join([f'<div class="keyword">{keyword}</div>' for keyword in selected_keywords])}
                </div>
                
                <div class="data-container">
                    {' '.join([f'<div class="data-item"><div class="data-value">{dp["value"]}</div><div class="data-label">{dp["label"]}</div></div>' for dp in selected_data_points])}
                </div>
                
                <div class="grid-container">
                    <div class="content-box">
                        <div class="content">
                            {content_parts[0]}
                        </div>
                    </div>
                    
                    <div class="extra-info-box">
                        <div class="extra-info-title">{self.style}风格{self.content_theme}指南</div>
                        <div class="extra-info-item">{extra_info[0]}</div>
                        <div class="extra-info-item">{extra_info[1]}</div>
                        <div class="extra-info-item">{extra_info[2]}</div>
                    </div>
                </div>
                
                <div class="key-points">
                    <div class="key-point">
                        <div class="key-point-number">1</div>
                        <div class="key-point-text">{selected_key_points[0]}</div>
                    </div>
                    <div class="key-point">
                        <div class="key-point-number">2</div>
                        <div class="key-point-text">{selected_key_points[1]}</div>
                    </div>
                    <div class="key-point">
                        <div class="key-point-number">3</div>
                        <div class="key-point-text">{selected_key_points[2]}</div>
                    </div>
                </div>
                
                <div class="content-box">
                    <div class="content">
                        {content_parts[1] if len(content_parts) > 1 else ''}
                    </div>
                    
                    <div class="tip-box">
                        {tip}
                    </div>
                </div>
                
                <table class="comparison-table">
                    <tr>
                        <th>类型</th>
                        <th>优点</th>
                        <th>缺点</th>
                    </tr>
                    <tr>
                        <td>{comparison_data[0]['category']}</td>
                        <td class="pros">{comparison_data[0]['pros']}</td>
                        <td class="cons">{comparison_data[0]['cons']}</td>
                    </tr>
                    <tr>
                        <td>{comparison_data[1]['category']}</td>
                        <td class="pros">{comparison_data[1]['pros']}</td>
                        <td class="cons">{comparison_data[1]['cons']}</td>
                    </tr>
                    <tr>
                        <td>{comparison_data[2]['category']}</td>
                        <td class="pros">{comparison_data[2]['pros']}</td>
                        <td class="cons">{comparison_data[2]['cons']}</td>
                    </tr>
                </table>
                
                <div class="tag-container">
                    <span class="tag">#{self.content_theme}</span>
                    <span class="tag">#{self.style}风格</span>
                    <span class="tag">#{self.target_audience}</span>
                    <span class="tag">#极简信息</span>
                    <span class="tag">#小红书笔记</span>
                </div>
                
                <div class="footer">
                    {self.content_theme} · 信息图 {image_index + 1}
                </div>
            </div>
        </body>
        </html>
        """
        return html
        
    def generate_vibrant_html(self, description: str, image_index: int) -> str:
        """生成活泼活力风格的HTML模板"""
        # 活力色彩方案 - 随机选择一种
        color_schemes = [
            {
                "primary": "#FF6B6B",  # 鲜红色
                "secondary": "#FFD166", # 明黄色
                "accent": "#06D6A0",    # 薄荷绿
                "text": "#4A4E69",      # 深蓝灰色
                "background": "#FFF0F3", # 粉色背景
                "border": "#FF9AA2",    # 粉红色边框
            },
            {
                "primary": "#7209B7",   # 紫色
                "secondary": "#3A0CA3",  # 深蓝色
                "accent": "#4CC9F0",     # 亮蓝色
                "text": "#F72585",       # 粉红色
                "background": "#F8EDFF",  # 浅紫色背景
                "border": "#C77DFF",     # 淡紫色边框
            },
            {
                "primary": "#FF9E00",   # 橙色
                "secondary": "#FF4D00",  # 深橙色
                "accent": "#38B000",     # 绿色
                "text": "#006400",       # 深绿色
                "background": "#FFFAE5",  # 奶油色背景
                "border": "#FFB700",     # 金色边框
            }
        ]
        colors = random.choice(color_schemes)
        
        # 提取标题
        title_parts = description.split('，', 1)
        if len(title_parts) > 1:
            title = title_parts[0].strip()
            subtitle = title_parts[1].strip()
        else:
            title = description
            subtitle = self.content_theme
            
        # 生成随机的亮点
        highlights = [
            "超赞景点", 
            "必吃美食", 
            "隐藏宝藏",
            "拍照圣地", 
            "省钱攻略", 
            "达人推荐",
            "网红打卡",
            "季节限定",
            "亲子活动",
            "情侣必去"
        ]
        selected_highlights = random.sample(highlights, 4)
        
        # 生成随机的表情符号
        emojis = ["😍", "✨", "🌈", "🎉", "💕", "🔥", "⭐", "🌟", "🎊", "🥳", "🌸", "🍭", "🎈", "🏆", "🚀"]
        random_emojis = random.sample(emojis, 10)
        
        # 生成随机角度
        card_rotate = random.randint(-3, 3)
        tag_rotate = random.randint(-3, 3)
        
        # 生成随机的装饰元素位置
        decoration_positions = [
            {"top": f"{random.randint(5, 15)}%", "left": f"{random.randint(5, 15)}%", "size": f"{random.randint(40, 60)}px"},
            {"top": f"{random.randint(70, 85)}%", "right": f"{random.randint(5, 15)}%", "size": f"{random.randint(30, 50)}px"},
            {"top": f"{random.randint(30, 50)}%", "left": f"{random.randint(80, 90)}%", "size": f"{random.randint(20, 40)}px"},
            {"top": f"{random.randint(20, 40)}%", "left": f"{random.randint(10, 20)}%", "size": f"{random.randint(25, 45)}px"}
        ]
        
        # 生成随机的提示
        tips = [
            f"小贴士：{self.content_theme}最适合{self.target_audience}尝试！",
            f"达人建议：选择{self.style}风格更显个性！",
            f"注意：{self.content_theme}需要注意细节搭配哦~",
            f"经验分享：{self.content_theme}的关键在于用心体验！",
            f"独家秘诀：掌握这些技巧，轻松驾驭{self.content_theme}！"
        ]
        selected_tip = random.choice(tips)
        
        # 生成随机的评分
        ratings = [
            {"category": "颜值", "score": random.randint(8, 10)},
            {"category": "性价比", "score": random.randint(7, 10)},
            {"category": "实用性", "score": random.randint(8, 10)},
            {"category": "推荐度", "score": random.randint(9, 10)}
        ]
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&family=Baloo+2:wght@400;700&display=swap');
                
                body {{
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    background: {colors['background']};
                    font-family: 'Baloo 2', 'Noto Sans SC', cursive;
                    color: {colors['text']};
                }}
                
                .fun-card {{
                    width: 750px;
                    height: 800px;
                    position: relative;
                    background-color: white;
                    border-radius: 20px;
                    box-shadow: 0 15px 35px rgba(0,0,0,0.1);
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                }}
                
                .header-image {{
                    height: 120px;
                    background: linear-gradient(45deg, {colors['primary']}, {colors['secondary']});
                    position: relative;
                    overflow: hidden;
                }}
                
                .confetti {{
                    position: absolute;
                    width: 15px;
                    height: 15px;
                    border-radius: 50%;
                    opacity: 0.7;
                }}
                
                .confetti-1 {{
                    background: white;
                    top: 20px;
                    left: 30px;
                    transform: scale(1.5);
                }}
                
                .confetti-2 {{
                    background: {colors['accent']};
                    top: 60px;
                    right: 100px;
                    transform: scale(2);
                }}
                
                .confetti-3 {{
                    background: white;
                    bottom: 20px;
                    right: 30px;
                    transform: scale(1.2);
                }}
                
                .confetti-4 {{
                    background: {colors['accent']};
                    bottom: 40px;
                    left: 150px;
                    transform: scale(1.8);
                }}
                
                .title-container {{
                    text-align: center;
                    margin-top: -50px;
                    padding: 0 20px;
                    z-index: 10;
                }}
                
                .title-bubble {{
                    background: white;
                    border: 3px solid {colors['primary']};
                    border-radius: 30px;
                    padding: 20px 30px;
                    display: inline-block;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
                    transform: rotate({card_rotate}deg);
                }}
                
                .title {{
                    font-size: 2.2em;
                    font-weight: 700;
                    color: {colors['primary']};
                    margin: 0;
                    line-height: 1.2;
                    text-shadow: 2px 2px 0px rgba(0,0,0,0.05);
                }}
                
                .subtitle {{
                    font-size: 1.1em;
                    color: {colors['text']};
                    margin-top: 5px;
                    font-weight: 400;
                }}
                
                .content {{
                    flex: 1;
                    padding: 20px 25px;
                    display: flex;
                    flex-direction: column;
                    position: relative;
                    z-index: 5;
                }}
                
                .fun-section {{
                    margin-bottom: 15px;
                }}
                
                .section-title {{
                    font-size: 1.4em;
                    font-weight: 700;
                    color: {colors['secondary']};
                    margin-bottom: 12px;
                    display: flex;
                    align-items: center;
                }}
                
                .section-title::before {{
                    content: "{random_emojis[0]}";
                    margin-right: 10px;
                    font-size: 1.2em;
                }}
                
                .highlight-cards {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 12px;
                }}
                
                .highlight-card {{
                    background: white;
                    border: 2px dashed {colors['border']};
                    border-radius: 15px;
                    padding: 12px;
                    text-align: center;
                    transform: rotate({card_rotate}deg);
                    transition: transform 0.3s ease;
                    position: relative;
                    overflow: hidden;
                }}
                
                .highlight-card:hover {{
                    transform: translateY(-5px) rotate({card_rotate}deg);
                }}
                
                .highlight-emoji {{
                    font-size: 2em;
                    margin-bottom: 8px;
                }}
                
                .highlight-title {{
                    font-size: 1.1em;
                    font-weight: 700;
                    color: {colors['primary']};
                    margin-bottom: 5px;
                }}
                
                .highlight-desc {{
                    font-size: 0.9em;
                    color: {colors['text']};
                }}
                
                .quote-box {{
                    background: {colors['secondary']}30;
                    border-radius: 15px;
                    padding: 15px;
                    margin: 15px 0;
                    position: relative;
                    border: 2px dashed {colors['border']};
                }}
                
                .quote-text {{
                    font-size: 1.1em;
                    font-style: italic;
                    color: {colors['primary']};
                    text-align: center;
                }}
                
                .fun-tags {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    justify-content: center;
                    margin-top: auto;
                    padding-top: 15px;
                }}
                
                .fun-tag {{
                    background: {colors['secondary']};
                    color: white;
                    padding: 8px 15px;
                    border-radius: 20px;
                    font-size: 0.9em;
                    font-weight: 700;
                    display: flex;
                    align-items: center;
                    box-shadow: 3px 3px 0 rgba(0,0,0,0.1);
                    transform: rotate({tag_rotate}deg);
                }}
                
                .fun-tag::before {{
                    content: "#";
                    margin-right: 3px;
                    font-weight: 400;
                }}
                
                .sticker {{
                    position: absolute;
                    width: 80px;
                    height: 80px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    border-radius: 50%;
                    font-weight: 700;
                    font-size: 1em;
                    transform: rotate(15deg);
                    box-shadow: 3px 3px 8px rgba(0,0,0,0.15);
                    z-index: 10;
                }}
                
                .sticker-1 {{
                    background: {colors['accent']};
                    color: white;
                    top: 20px;
                    right: 20px;
                    padding: 5px;
                    text-align: center;
                }}
                
                .sticker-2 {{
                    background: {colors['primary']};
                    color: white;
                    bottom: 100px;
                    left: 30px;
                    padding: 5px;
                    text-align: center;
                    transform: rotate(-10deg);
                }}
                
                .day-counter {{
                    position: absolute;
                    bottom: 20px;
                    left: 30px;
                    background: {colors['primary']};
                    color: white;
                    padding: 5px 15px;
                    border-radius: 20px;
                    font-size: 0.9em;
                    font-weight: 700;
                    transform: rotate(-5deg);
                    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
                }}
                
                .wave-pattern {{
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    width: 100%;
                    height: 30px;
                    background: repeating-radial-gradient(
                        circle at 10px -5px,
                        transparent,
                        transparent 10px,
                        {colors['secondary']}30 10px,
                        {colors['secondary']}30 20px
                    );
                }}
                
                .polaroid {{
                    background: white;
                    padding: 10px 10px 30px 10px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                    transform: rotate({card_rotate * -1}deg);
                    position: absolute;
                    right: 20px;
                    bottom: 60px;
                    width: 100px;
                }}
                
                .polaroid-img {{
                    width: 100%;
                    height: 80px;
                    background: {colors['secondary']}50;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    font-size: 2em;
                }}
                
                .polaroid-caption {{
                    text-align: center;
                    font-size: 0.8em;
                    margin-top: 5px;
                    font-family: 'Noto Sans SC', sans-serif;
                }}
                
                .tape {{
                    position: absolute;
                    width: 40px;
                    height: 15px;
                    background: rgba(255,255,255,0.5);
                    opacity: 0.7;
                    transform: rotate(30deg);
                    top: -5px;
                    left: 20px;
                }}
                
                .emoji-decoration {{
                    position: absolute;
                    font-size: 24px;
                    z-index: 2;
                }}
                
                .rating-box {{
                    background: white;
                    border: 2px solid {colors['border']};
                    border-radius: 12px;
                    padding: 12px;
                    margin: 15px 0;
                    position: relative;
                }}
                
                .rating-title {{
                    position: absolute;
                    top: -10px;
                    left: 15px;
                    background: white;
                    padding: 0 10px;
                    font-size: 0.9em;
                    font-weight: 700;
                    color: {colors['primary']};
                }}
                
                .rating-row {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 8px;
                    align-items: center;
                }}
                
                .rating-category {{
                    font-size: 0.9em;
                    color: {colors['text']};
                }}
                
                .rating-stars {{
                    color: {colors['secondary']};
                    letter-spacing: -3px;
                }}
                
                .bubble-tip {{
                    background: {colors['accent']};
                    color: white;
                    border-radius: 20px;
                    padding: 10px 15px;
                    position: relative;
                    margin: 15px 0;
                    font-size: 0.9em;
                    max-width: 80%;
                    align-self: flex-start;
                }}
                
                .bubble-tip::after {{
                    content: "";
                    position: absolute;
                    bottom: -10px;
                    left: 15px;
                    border-width: 10px 10px 0;
                    border-style: solid;
                    border-color: {colors['accent']} transparent transparent;
                }}
                
                .doodle {{
                    position: absolute;
                    z-index: 1;
                    opacity: 0.1;
                }}
                
                .doodle-1 {{
                    width: 150px;
                    height: 150px;
                    border: 5px solid {colors['primary']};
                    border-radius: 50%;
                    top: 30%;
                    left: 10%;
                    transform: rotate(20deg);
                }}
                
                .doodle-2 {{
                    width: 100px;
                    height: 100px;
                    border: 5px solid {colors['secondary']};
                    top: 60%;
                    right: 15%;
                    transform: rotate(-15deg);
                }}
                
                .doodle-3 {{
                    width: 80px;
                    height: 80px;
                    background: {colors['accent']}30;
                    border-radius: 10px;
                    bottom: 20%;
                    left: 20%;
                    transform: rotate(45deg);
                }}
            </style>
        </head>
        <body>
            <div class="fun-card">
                <div class="header-image">
                    <div class="confetti confetti-1"></div>
                    <div class="confetti confetti-2"></div>
                    <div class="confetti confetti-3"></div>
                    <div class="confetti confetti-4"></div>
                    <div class="wave-pattern"></div>
                </div>
                
                <div class="title-container">
                    <div class="title-bubble">
                        <h1 class="title">{random_emojis[1]} {title} {random_emojis[2]}</h1>
                        <p class="subtitle">{subtitle}</p>
                    </div>
                </div>
                
                <div class="content">
                    <div class="doodle doodle-1"></div>
                    <div class="doodle doodle-2"></div>
                    <div class="doodle doodle-3"></div>
                    
                    <div class="emoji-decoration" style="top: {decoration_positions[0]['top']}; left: {decoration_positions[0]['left']}; font-size: {decoration_positions[0]['size']};">{random_emojis[3]}</div>
                    <div class="emoji-decoration" style="top: {decoration_positions[1]['top']}; right: {decoration_positions[1]['right']}; font-size: {decoration_positions[1]['size']};">{random_emojis[4]}</div>
                    <div class="emoji-decoration" style="top: {decoration_positions[2]['top']}; left: {decoration_positions[2]['left']}; font-size: {decoration_positions[2]['size']};">{random_emojis[5]}</div>
                    <div class="emoji-decoration" style="top: {decoration_positions[3]['top']}; left: {decoration_positions[3]['left']}; font-size: {decoration_positions[3]['size']};">{random_emojis[6]}</div>
                    
                    <div class="quote-box">
                        <div class="tape"></div>
                        <div class="quote-text">
                            {random_emojis[7]} 超级推荐！{self.style}风格的{self.content_theme}攻略 {random_emojis[8]}
                        </div>
                    </div>
                    
                    <div class="bubble-tip">
                        {selected_tip}
                    </div>
                    
                    <div class="fun-section">
                        <div class="section-title">精彩亮点</div>
                        <div class="highlight-cards">
                            <div class="highlight-card">
                                <div class="highlight-emoji">{random_emojis[0]}</div>
                                <div class="highlight-title">{selected_highlights[0]}</div>
                                <div class="highlight-desc">专为{self.target_audience}打造的{self.content_theme}体验</div>
                            </div>
                            <div class="highlight-card">
                                <div class="highlight-emoji">{random_emojis[1]}</div>
                                <div class="highlight-title">{selected_highlights[1]}</div>
                                <div class="highlight-desc">独家分享{self.style}风格的{self.content_theme}秘诀</div>
                            </div>
                            <div class="highlight-card">
                                <div class="highlight-emoji">{random_emojis[2]}</div>
                                <div class="highlight-title">{selected_highlights[2]}</div>
                                <div class="highlight-desc">绝对不能错过的{self.content_theme}精彩亮点</div>
                            </div>
                            <div class="highlight-card">
                                <div class="highlight-emoji">{random_emojis[9]}</div>
                                <div class="highlight-title">{selected_highlights[3]}</div>
                                <div class="highlight-desc">超赞{self.content_theme}指南，人气爆棚</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="rating-box">
                        <div class="rating-title">达人评分</div>
                        <div class="rating-row">
                            <div class="rating-category">{ratings[0]['category']}</div>
                            <div class="rating-stars">{"★" * ratings[0]['score'] + "☆" * (10 - ratings[0]['score'])}</div>
                        </div>
                        <div class="rating-row">
                            <div class="rating-category">{ratings[1]['category']}</div>
                            <div class="rating-stars">{"★" * ratings[1]['score'] + "☆" * (10 - ratings[1]['score'])}</div>
                        </div>
                        <div class="rating-row">
                            <div class="rating-category">{ratings[2]['category']}</div>
                            <div class="rating-stars">{"★" * ratings[2]['score'] + "☆" * (10 - ratings[2]['score'])}</div>
                        </div>
                        <div class="rating-row">
                            <div class="rating-category">{ratings[3]['category']}</div>
                            <div class="rating-stars">{"★" * ratings[3]['score'] + "☆" * (10 - ratings[3]['score'])}</div>
                        </div>
                    </div>
                    
                    <div class="fun-tags">
                        <div class="fun-tag">{self.content_theme}</div>
                        <div class="fun-tag">{self.style}</div>
                        <div class="fun-tag">必看攻略</div>
                        <div class="fun-tag">精选推荐</div>
                        <div class="fun-tag">达人分享</div>
                    </div>
                </div>
                
                <div class="sticker sticker-1">{random_emojis[3]}<br>必看</div>
                <div class="sticker sticker-2">{random_emojis[4]}<br>推荐</div>
                <div class="day-counter">DAY {random.randint(1, 7)} {random_emojis[9]}</div>
                
                <div class="polaroid">
                    <div class="polaroid-img">{random_emojis[5]}</div>
                    <div class="polaroid-caption">打卡必拍</div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def generate_standard_html(self, description: str, image_index: int) -> str:
        """生成标准风格的HTML模板"""
        # 随机选择配色方案
        color_schemes = [
            {
                "primary": "#FF6B6B",  # 红色
                "secondary": "#FFE66D", # 黄色
                "text": "#333333",      # 深灰色
                "background": "#FFFFFF", # 白色
                "accent": "#4ECDC4"     # 强调色
            },
            {
                "primary": "#4ECDC4",   # 青色
                "secondary": "#FF6B6B", # 红色
                "text": "#292F36",      # 深蓝灰色
                "background": "#F7FFF7", # 浅绿色
                "accent": "#FFD166"     # 强调色
            },
            {
                "primary": "#6B48FF",   # 紫色
                "secondary": "#FFD166", # 黄色
                "text": "#333333",      # 深灰色
                "background": "#FFFFFF", # 白色
                "accent": "#FF6B6B"     # 强调色
            }
        ]
        colors = random.choice(color_schemes)
        
        # 提取标题和内容
        parts = description.split('，', 1)
        if len(parts) > 1:
            title = parts[0].strip()
            content = parts[1].strip()
        else:
            title = self.content_theme
            content = description.strip()
            
        # 确保标题与主题相关
        if self.content_theme not in title:
            title = f"{self.content_theme} | {title}"
            
        # 生成随机的副标题
        subtitles = [
            f"探索{self.content_theme}的魅力",
            f"{self.content_theme}必看指南",
            f"{self.target_audience}的{self.content_theme}攻略",
            f"{self.style}风格的{self.content_theme}分享",
            f"独家{self.content_theme}推荐"
        ]
        subtitle = random.choice(subtitles)
        
        # 随机选择表情符号
        emojis = ["✨", "🌟", "💖", "🎀", "🌸", "💕", "🌈", "🍭", "🌺", "🌹", "🎉", "🎊", "💫", "⭐", "🔆"]
        random_emojis = random.sample(emojis, 5)
        
        # 生成随机的装饰元素位置
        decoration_positions = [
            {"top": f"{random.randint(5, 15)}%", "left": f"{random.randint(5, 15)}%", "size": f"{random.randint(40, 60)}px"},
            {"top": f"{random.randint(70, 85)}%", "right": f"{random.randint(5, 15)}%", "size": f"{random.randint(30, 50)}px"},
            {"top": f"{random.randint(40, 60)}%", "left": f"{random.randint(80, 90)}%", "size": f"{random.randint(20, 40)}px"}
        ]
        
        # 生成随机的强调文本
        highlight_texts = [
            f"{random_emojis[0]} 必看重点 {random_emojis[1]}",
            f"{random_emojis[2]} 独家分享 {random_emojis[3]}",
            f"{random_emojis[4]} 达人推荐",
            f"💯 不容错过",
            f"🔍 细节解析"
        ]
        highlight_text = random.choice(highlight_texts)
        
        # 生成随机的小贴士
        tips = [
            f"小贴士：{self.content_theme}最适合{self.target_audience}尝试！",
            f"达人建议：选择{self.style}风格更显个性！",
            f"注意：{self.content_theme}需要注意细节搭配哦~",
            f"经验分享：{self.content_theme}的关键在于用心体验！",
            f"独家秘诀：掌握这些技巧，轻松驾驭{self.content_theme}！"
        ]
        tip = random.choice(tips)
        
        # 生成随机角度
        rotate_angles = ["-3deg", "-2deg", "-1deg", "1deg", "2deg", "3deg"]
        
        # 将内容分段
        content_parts = content.split("\n\n")
        if len(content_parts) < 2:
            content_parts = [content[:len(content)//2], content[len(content)//2:]]
            
        # 生成额外的独立文字内容（与文案不同的内容）
        extra_content_ideas = [
            [
                f"✓ {self.style}风格{self.content_theme}搭配技巧",
                f"✓ 适合{self.target_audience}的个性化建议",
                f"✓ 高级感穿搭秘诀大公开"
            ],
            [
                f"🔥 本季流行元素推荐",
                f"🔥 色彩搭配口诀",
                f"🔥 单品挑选指南"
            ],
            [
                f"👉 如何打造{self.style}风格",
                f"👉 适合场合：日常/约会/工作",
                f"👉 从零开始学{self.content_theme}"
            ],
            [
                f"⭐ 达人都在用的单品",
                f"⭐ 新手必备搭配公式",
                f"⭐ 进阶技巧分享"
            ]
        ]
        extra_content = random.choice(extra_content_ideas)
        
        # 生成随机的评分
        ratings = [
            {"category": "颜值", "score": random.randint(8, 10)},
            {"category": "实用性", "score": random.randint(7, 10)},
            {"category": "推荐度", "score": random.randint(9, 10)}
        ]
        
        # 生成随机的产品/单品推荐
        products = [
            f"{self.style}风格{random.choice(['上衣', '裙子', '裤装', '外套', '鞋子', '包包', '配饰'])}",
            f"高级感{random.choice(['衬衫', '西装', '连衣裙', '半身裙', '阔腿裤', '小白鞋', '珍珠耳环'])}",
            f"百搭{random.choice(['基础款', '经典款', '入门款', '高阶款', '进阶款'])}单品"
        ]
        
        # 生成HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
                
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Noto Sans SC', sans-serif;
                    background: {colors['background']};
                    color: {colors['text']};
                    overflow: hidden;
                }}
                
                .container {{
                    width: 750px;
                    height: 800px;
                    margin: 0 auto;
                    padding: 25px;
                    box-sizing: border-box;
                    position: relative;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                }}
                
                .header {{
                    margin-bottom: 15px;
                    position: relative;
                    z-index: 10;
                }}
                
                .title {{
                    font-size: 30px;
                    font-weight: 700;
                    margin-bottom: 8px;
                    color: {colors['primary']};
                    line-height: 1.3;
                    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
                }}
                
                .subtitle {{
                    font-size: 16px;
                    color: {colors['secondary']};
                    font-weight: 500;
                    margin-bottom: 15px;
                }}
                
                .content-container {{
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                    flex: 1;
                }}
                
                .content-section {{
                    background: white;
                    border-radius: 12px;
                    padding: 15px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.05);
                    position: relative;
                    border-left: 4px solid {colors['primary']};
                }}
                
                .content {{
                    font-size: 15px;
                    line-height: 1.6;
                }}
                
                .highlight {{
                    background: linear-gradient(transparent 60%, {colors['secondary']}40 40%);
                    padding: 0 5px;
                }}
                
                .tag-container {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    margin-top: 12px;
                }}
                
                .tag {{
                    display: inline-block;
                    background: {colors['primary']}20;
                    color: {colors['primary']};
                    padding: 5px 12px;
                    border-radius: 20px;
                    font-size: 13px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
                }}
                
                .footer {{
                    text-align: center;
                    font-size: 13px;
                    color: {colors['text']}80;
                    padding-top: 15px;
                    margin-top: auto;
                }}
                
                .decoration {{
                    position: absolute;
                    border-radius: 50%;
                    z-index: 1;
                    opacity: 0.6;
                }}
                
                .decoration-1 {{
                    width: 150px;
                    height: 150px;
                    top: -50px;
                    right: -50px;
                    background: {colors['primary']}30;
                }}
                
                .decoration-2 {{
                    width: 100px;
                    height: 100px;
                    bottom: 50px;
                    left: -30px;
                    background: {colors['secondary']}30;
                }}
                
                .decoration-3 {{
                    width: 80px;
                    height: 80px;
                    top: 40%;
                    right: 10%;
                    background: {colors['accent']}20;
                }}
                
                .theme-badge {{
                    position: absolute;
                    top: 20px;
                    right: 20px;
                    background: {colors['primary']};
                    color: white;
                    padding: 8px 15px;
                    border-radius: 20px;
                    font-size: 13px;
                    font-weight: 500;
                    box-shadow: 0 3px 10px rgba(0,0,0,0.1);
                    z-index: 10;
                }}
                
                .emoji-decoration {{
                    position: absolute;
                    font-size: 24px;
                    z-index: 5;
                    text-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                
                .highlight-box {{
                    background: {colors['secondary']}15;
                    border: 2px dashed {colors['secondary']};
                    border-radius: 12px;
                    padding: 12px;
                    margin: 15px 0;
                    position: relative;
                    text-align: center;
                    font-weight: 500;
                    color: {colors['primary']};
                    font-size: 16px;
                    transform: rotate({random.choice(rotate_angles)});
                    box-shadow: 0 3px 8px rgba(0,0,0,0.05);
                }}
                
                .tip-box {{
                    background: {colors['accent']}15;
                    border-radius: 10px;
                    padding: 12px 15px;
                    margin-top: 12px;
                    font-size: 14px;
                    color: {colors['text']};
                    position: relative;
                }}
                
                .tip-box::before {{
                    content: "💡";
                    margin-right: 8px;
                }}
                
                .sticker {{
                    position: absolute;
                    background: {colors['accent']};
                    color: white;
                    width: 60px;
                    height: 60px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    border-radius: 50%;
                    font-weight: 700;
                    font-size: 14px;
                    transform: rotate(-15deg);
                    box-shadow: 0 3px 8px rgba(0,0,0,0.15);
                    z-index: 10;
                    right: 40px;
                    bottom: 40px;
                }}
                
                .extra-content-box {{
                    background: {colors['primary']}10;
                    border-radius: 10px;
                    padding: 15px;
                    margin: 12px 0;
                }}
                
                .extra-content-title {{
                    font-size: 15px;
                    font-weight: 700;
                    margin-bottom: 10px;
                    color: {colors['primary']};
                    display: flex;
                    align-items: center;
                }}
                
                .extra-content-title::before {{
                    content: "{random_emojis[2]}";
                    margin-right: 8px;
                }}
                
                .extra-content-list {{
                    margin: 0;
                    padding-left: 15px;
                }}
                
                .extra-content-item {{
                    margin-bottom: 8px;
                    font-size: 14px;
                }}
                
                .rating-box {{
                    background: white;
                    border: 1px solid {colors['border'] if 'border' in colors else colors['secondary']}30;
                    border-radius: 10px;
                    padding: 12px;
                    margin: 12px 0;
                }}
                
                .rating-title {{
                    font-size: 14px;
                    font-weight: 700;
                    margin-bottom: 8px;
                    color: {colors['primary']};
                }}
                
                .rating-row {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 6px;
                    align-items: center;
                }}
                
                .rating-category {{
                    font-size: 13px;
                    color: {colors['text']};
                }}
                
                .rating-stars {{
                    color: {colors['secondary']};
                    letter-spacing: -2px;
                    font-size: 13px;
                }}
                
                .product-box {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    margin: 12px 0;
                }}
                
                .product-tag {{
                    background: {colors['accent']}20;
                    color: {colors['accent']};
                    padding: 5px 10px;
                    border-radius: 8px;
                    font-size: 13px;
                    display: flex;
                    align-items: center;
                }}
                
                .product-tag::before {{
                    content: "🔍";
                    margin-right: 5px;
                    font-size: 12px;
                }}
                
                .corner-ribbon {{
                    position: absolute;
                    top: 25px;
                    left: -30px;
                    background: {colors['secondary']};
                    color: white;
                    padding: 5px 30px;
                    transform: rotate(-45deg);
                    font-size: 12px;
                    font-weight: 700;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    z-index: 10;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="decoration decoration-1"></div>
                <div class="decoration decoration-2"></div>
                <div class="decoration decoration-3"></div>
                
                <div class="emoji-decoration" style="top: {decoration_positions[0]['top']}; left: {decoration_positions[0]['left']}; font-size: {decoration_positions[0]['size']};">{random_emojis[0]}</div>
                <div class="emoji-decoration" style="top: {decoration_positions[1]['top']}; right: {decoration_positions[1]['right']}; font-size: {decoration_positions[1]['size']};">{random_emojis[1]}</div>
                <div class="emoji-decoration" style="top: {decoration_positions[2]['top']}; left: {decoration_positions[2]['left']}; font-size: {decoration_positions[2]['size']};">{random_emojis[2]}</div>
                
                <div class="theme-badge">{self.content_theme}</div>
                <div class="corner-ribbon">{self.style}风格</div>
                
                <div class="header">
                    <div class="title">{random_emojis[3]} {title}</div>
                    <div class="subtitle">{subtitle}</div>
                </div>
                
                <div class="content-container">
                    <div class="highlight-box">
                        {highlight_text}
                    </div>
                    
                    <div class="content-section">
                        <div class="content">
                            {content_parts[0]}
                        </div>
                    </div>
                    
                    <div class="extra-content-box">
                        <div class="extra-content-title">{self.style}风格{self.content_theme}指南</div>
                        <ul class="extra-content-list">
                            <li class="extra-content-item">{extra_content[0]}</li>
                            <li class="extra-content-item">{extra_content[1]}</li>
                            <li class="extra-content-item">{extra_content[2]}</li>
                        </ul>
                    </div>
                    
                    <div class="content-section">
                        <div class="content">
                            {content_parts[1] if len(content_parts) > 1 else ''}
                        </div>
                        
                        <div class="tip-box">
                            {tip}
                        </div>
                    </div>
                    
                    <div class="rating-box">
                        <div class="rating-title">达人评分</div>
                        <div class="rating-row">
                            <div class="rating-category">{ratings[0]['category']}</div>
                            <div class="rating-stars">{"★" * ratings[0]['score'] + "☆" * (10 - ratings[0]['score'])}</div>
                        </div>
                        <div class="rating-row">
                            <div class="rating-category">{ratings[1]['category']}</div>
                            <div class="rating-stars">{"★" * ratings[1]['score'] + "☆" * (10 - ratings[1]['score'])}</div>
                        </div>
                        <div class="rating-row">
                            <div class="rating-category">{ratings[2]['category']}</div>
                            <div class="rating-stars">{"★" * ratings[2]['score'] + "☆" * (10 - ratings[2]['score'])}</div>
                        </div>
                    </div>
                    
                    <div class="product-box">
                        <div class="product-tag">{products[0]}</div>
                        <div class="product-tag">{products[1]}</div>
                        <div class="product-tag">{products[2]}</div>
                    </div>
                    
                    <div class="tag-container">
                        <span class="tag">#{self.content_theme}</span>
                        <span class="tag">#{self.style}风格</span>
                        <span class="tag">#{self.target_audience}</span>
                        <span class="tag">#小红书推荐</span>
                    </div>
                </div>
                
                <div class="sticker">{random_emojis[4]}<br>必看</div>
                
                <div class="footer">
                    {self.content_theme} · 图片 {image_index + 1}
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def generate_custom_info_html(self, description: str, image_index: int) -> str:
        """生成自定义信息风格的HTML模板，严格控制尺寸为750x800px"""
        # 专业色彩方案
        colors = {
            "primary": "#3366CC",  # 主色调蓝色
            "secondary": "#5CADFF", # 次要蓝色
            "accent": "#FF5722",    # 强调色（橙色）
            "text": "#333333",      # 主文本色
            "muted": "#666666",     # 次要文本色
            "light": "#F5F8FA",     # 浅色背景
            "border": "#E0E0E0",    # 边框色
            "success": "#4CAF50",   # 成功色（绿色）
            "warning": "#FFC107"    # 警告色（黄色）
        }
        
        # 提取标题和内容
        title_parts = description.split('，', 1)
        if len(title_parts) > 1:
            title = title_parts[0].strip()
            subtitle = title_parts[1].strip()
        else:
            title = description
            subtitle = self.content_theme or "专业指南"
        
        # 生成随机的信息点
        info_points = [
            "核心要点", 
            "关键数据", 
            "实用技巧",
            "专业建议", 
            "常见问题", 
            "重要提示",
            "方法论",
            "最佳实践",
            "注意事项",
            "专家观点"
        ]
        selected_points = random.sample(info_points, 3)
        
        # 生成随机的统计数据
        stats = [
            {"icon": "📊", "label": "满意度", "value": f"{random.randint(85, 99)}%"},
            {"icon": "👍", "label": "推荐率", "value": f"{random.randint(80, 98)}%"},
            {"icon": "👀", "label": "关注度", "value": f"{random.randint(70, 95)}%"},
            {"icon": "⭐", "label": "评分", "value": f"{random.randint(4, 5)}.{random.randint(0, 9)}/5"},
            {"icon": "💰", "label": "性价比", "value": f"{random.randint(4, 5)}.{random.randint(0, 9)}/5"},
            {"icon": "🔄", "label": "复购率", "value": f"{random.randint(75, 95)}%"},
            {"icon": "🎯", "label": "目标达成", "value": f"{random.randint(80, 99)}%"}
        ]
        selected_stats = random.sample(stats, 2)
        
        # 生成随机的标签
        tags = [
            self.content_theme,
            self.style,
            "专业指南",
            "干货分享",
            "实用技巧",
            "必看攻略",
            "行业趋势",
            "深度解析",
            "精选推荐"
        ]
        selected_tags = random.sample(tags, 4)
        if not self.content_theme:
            selected_tags = selected_tags[1:]  # 如果没有主题，则少选一个标签
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');
                
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    margin: 0;
                    padding: 0;
                    width: 750px;
                    height: 800px;
                    background: white;
                    font-family: 'Noto Sans SC', sans-serif;
                    color: {colors['text']};
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                }}
                
                .header {{
                    background: {colors['light']};
                    padding: 15px 20px;
                    border-bottom: 1px solid {colors['border']};
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                
                .logo {{
                    font-size: 1.2em;
                    font-weight: 700;
                    color: {colors['primary']};
                    letter-spacing: 1px;
                }}
                
                .nav {{
                    display: flex;
                    gap: 15px;
                }}
                
                .nav-item {{
                    font-size: 0.8em;
                    color: {colors['muted']};
                    font-weight: 500;
                }}
                
                .main {{
                    flex: 1;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                }}
                
                .title-section {{
                    margin-bottom: 20px;
                }}
                
                .category-tag {{
                    display: inline-block;
                    background: {colors['primary']};
                    color: white;
                    font-size: 0.7em;
                    padding: 4px 10px;
                    border-radius: 4px;
                    margin-bottom: 8px;
                    font-weight: 500;
                }}
                
                .title {{
                    font-size: 1.8em;
                    font-weight: 700;
                    margin-bottom: 5px;
                    line-height: 1.3;
                    color: {colors['text']};
                }}
                
                .subtitle {{
                    font-size: 1em;
                    color: {colors['muted']};
                    line-height: 1.4;
                }}
                
                .content-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 15px;
                    margin-bottom: 20px;
                }}
                
                .info-card {{
                    background: {colors['light']};
                    border-radius: 8px;
                    padding: 15px;
                    border-left: 4px solid {colors['primary']};
                }}
                
                .info-card-header {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 10px;
                }}
                
                .info-number {{
                    background: {colors['primary']};
                    color: white;
                    width: 24px;
                    height: 24px;
                    border-radius: 50%;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    font-size: 0.8em;
                    font-weight: 700;
                    margin-right: 10px;
                }}
                
                .info-title {{
                    font-size: 1em;
                    font-weight: 700;
                    color: {colors['primary']};
                }}
                
                .info-content {{
                    font-size: 0.9em;
                    line-height: 1.5;
                    color: {colors['text']};
                }}
                
                .stats-section {{
                    margin-bottom: 20px;
                }}
                
                .section-title {{
                    font-size: 1em;
                    font-weight: 700;
                    margin-bottom: 10px;
                    color: {colors['text']};
                    display: flex;
                    align-items: center;
                }}
                
                .section-title::before {{
                    content: "";
                    display: inline-block;
                    width: 4px;
                    height: 16px;
                    background: {colors['primary']};
                    margin-right: 8px;
                    border-radius: 2px;
                }}
                
                .stats-row {{
                    display: flex;
                    justify-content: space-between;
                    gap: 15px;
                }}
                
                .stat-card {{
                    flex: 1;
                    background: white;
                    border: 1px solid {colors['border']};
                    border-radius: 8px;
                    padding: 12px;
                    text-align: center;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }}
                
                .stat-icon {{
                    font-size: 1.5em;
                    margin-bottom: 5px;
                }}
                
                .stat-value {{
                    font-size: 1.4em;
                    font-weight: 700;
                    color: {colors['accent']};
                    margin-bottom: 2px;
                }}
                
                .stat-label {{
                    font-size: 0.8em;
                    color: {colors['muted']};
                }}
                
                .highlight-box {{
                    background: linear-gradient(to right, {colors['primary']}15, {colors['light']});
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 20px;
                    border-left: 4px solid {colors['primary']};
                }}
                
                .highlight-title {{
                    font-size: 1em;
                    font-weight: 700;
                    color: {colors['primary']};
                    margin-bottom: 5px;
                    display: flex;
                    align-items: center;
                }}
                
                .highlight-title::before {{
                    content: "💡";
                    margin-right: 8px;
                }}
                
                .highlight-content {{
                    font-size: 0.9em;
                    line-height: 1.5;
                }}
                
                .tags-section {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    margin-top: auto;
                    padding-top: 15px;
                }}
                
                .tag {{
                    background: {colors['light']};
                    color: {colors['primary']};
                    padding: 5px 12px;
                    border-radius: 20px;
                    font-size: 0.8em;
                    font-weight: 500;
                    display: flex;
                    align-items: center;
                }}
                
                .tag::before {{
                    content: "#";
                    margin-right: 2px;
                    opacity: 0.7;
                }}
                
                .footer {{
                    background: {colors['light']};
                    padding: 12px 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    font-size: 0.8em;
                    color: {colors['muted']};
                    border-top: 1px solid {colors['border']};
                }}
                
                .reference {{
                    display: flex;
                    align-items: center;
                }}
                
                .reference-icon {{
                    width: 18px;
                    height: 18px;
                    background: {colors['muted']};
                    color: white;
                    border-radius: 50%;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    font-size: 0.8em;
                    margin-right: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">INFO GUIDE</div>
                <div class="nav">
                    <div class="nav-item">方法论</div>
                    <div class="nav-item">技巧分享</div>
                    <div class="nav-item">实用工具</div>
                </div>
            </div>
            
            <div class="main">
                <div class="title-section">
                    <div class="category-tag">{self.style}</div>
                    <h1 class="title">{title}</h1>
                    <p class="subtitle">{subtitle}</p>
                </div>
                
                <div class="content-grid">
                    <div class="info-card">
                        <div class="info-card-header">
                            <div class="info-number">1</div>
                            <div class="info-title">{selected_points[0]}</div>
                        </div>
                        <div class="info-content">针对{self.target_audience or '用户'}的{self.content_theme or '专业'}指南，提供清晰的方法步骤</div>
                    </div>
                    
                    <div class="info-card">
                        <div class="info-card-header">
                            <div class="info-number">2</div>
                            <div class="info-title">{selected_points[1]}</div>
                        </div>
                        <div class="info-content">基于实践经验总结的核心要点，帮助快速掌握关键技能</div>
                    </div>
                    
                    <div class="info-card">
                        <div class="info-card-header">
                            <div class="info-number">3</div>
                            <div class="info-title">{selected_points[2]}</div>
                        </div>
                        <div class="info-content">专业角度分析常见问题，提供有效解决方案和建议</div>
                    </div>
                    
                    <div class="info-card">
                        <div class="info-card-header">
                            <div class="info-number">4</div>
                            <div class="info-title">注意事项</div>
                        </div>
                        <div class="info-content">避免常见误区，确保正确实施并获得最佳效果</div>
                    </div>
                </div>
                
                <div class="stats-section">
                    <div class="section-title">数据分析</div>
                    <div class="stats-row">
                        <div class="stat-card">
                            <div class="stat-icon">{selected_stats[0]['icon']}</div>
                            <div class="stat-value">{selected_stats[0]['value']}</div>
                            <div class="stat-label">{selected_stats[0]['label']}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon">{selected_stats[1]['icon']}</div>
                            <div class="stat-value">{selected_stats[1]['value']}</div>
                            <div class="stat-label">{selected_stats[1]['label']}</div>
                        </div>
                    </div>
                </div>
                
                <div class="highlight-box">
                    <div class="highlight-title">专家提示</div>
                    <div class="highlight-content">
                        {self.style}风格的{self.content_theme or '内容'}需要特别注意细节处理，掌握核心技巧后能够事半功倍。建议从基础开始，循序渐进地学习和实践。
                    </div>
                </div>
                
                <div class="tags-section">
                    {' '.join(f'<div class="tag">{tag}</div>' for tag in selected_tags if tag)}
                </div>
            </div>
            
            <div class="footer">
                <div>信息图表 #{image_index + 1}</div>
                <div class="reference">
                    <div class="reference-icon">i</div>
                    <div>专业指南 {time.strftime("%Y")}</div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def render_html_to_image(self, html: str, filename: str):
        """将HTML内容渲染为图片。"""
        try:
            with sync_playwright() as p:
                # 使用系统安装的Chrome浏览器
                browser = p.chromium.launch(
                    headless=True,  # 无头模式
                    channel='chrome'  # 使用系统Chrome
                )
                
                # 创建页面并设置视口
                page = browser.new_page(viewport={"width": self.VIEWPORT_WIDTH, "height": self.VIEWPORT_HEIGHT})
                
                # 设置HTML内容
                page.set_content(html)
                
                # 等待内容加载完成
                page.wait_for_load_state("networkidle")
                
                # 获取内容实际高度
                height = page.evaluate("""() => {
                    const body = document.body;
                    const html = document.documentElement;
                    return Math.max(
                        body.scrollHeight,
                        body.offsetHeight,
                        html.clientHeight,
                        html.scrollHeight,
                        html.offsetHeight
                    );
                }""")
                
                # 调整页面大小以适应内容
                page.set_viewport_size({"width": self.VIEWPORT_WIDTH, "height": height})
                
                # 截图
                page.screenshot(path=filename, full_page=True)
                browser.close()
                
                print(f"    • 图片已保存: {filename}")
                return True
                
        except Exception as e:
            print(f"    ❌ 生成图片失败: {e}")
            if "channel" in str(e):
                print("    提示: 请确保系统已安装Chrome浏览器，或尝试使用其他浏览器引擎")
            return False

    def initialize_xhs_client(self):
        """初始化小红书客户端"""
        if not self.xhs_client:
            config = XHSConfig()
            self.xhs_client = XHSClient(config)
        return self.xhs_client

    def publish_to_xiaohongshu(self, title, content, images, tags):
        """
        发布笔记到小红书
        
        Args:
            title: 笔记标题
            content: 笔记内容
            images: 图片路径列表
            tags: 标签列表
            
        Returns:
            发布结果
        """
        print("🚀 开始发布笔记到小红书...")
        
        try:
            # 初始化客户端
            self.initialize_xhs_client()
            
            # 将标签列表转换为逗号分隔的字符串
            # 确保标签不重复且去掉#符号
            unique_topics = []
            seen_topics = set()
            for tag in tags:
                # 去除#符号和可能的标点符号
                clean_topic = tag.replace('#', '').rstrip('.,;:!?')
                topic_lower = clean_topic.lower()
                if clean_topic and topic_lower not in seen_topics:
                    unique_topics.append(clean_topic)
                    seen_topics.add(topic_lower)
            
            topics = ",".join(unique_topics)
            
            # 图片参数 - 确保图片文件存在，并转换为绝对路径
            valid_images = []
            for img_path in images:
                # 转换为绝对路径
                if not os.path.isabs(img_path):
                    abs_path = os.path.abspath(img_path)
                else:
                    abs_path = img_path
                    
                if os.path.exists(abs_path):
                    valid_images.append(abs_path)
                    print(f"✓ 有效图片路径: {abs_path}")
                else:
                    print(f"⚠️ 警告: 图片不存在: {abs_path}")
            
            # 如果没有有效图片，检查是否有默认图片
            if not valid_images:
                default_image = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_images", "default_image.jpg")
                if os.path.exists(default_image):
                    valid_images.append(default_image)
                    print(f"使用默认图片: {default_image}")
                else:
                    # 尝试在output/images目录中找到任何图片
                    image_dir = "output/images"
                    if os.path.exists(image_dir):
                        for file in os.listdir(image_dir):
                            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                                img_path = os.path.join(image_dir, file)
                                valid_images.append(img_path)
                                print(f"使用找到的图片: {img_path}")
                                break
            
            if not valid_images:
                raise ValueError("没有找到有效的图片文件，无法发布笔记")
            
            # 图片参数 - 使用有效的图片
            images_str = ",".join(valid_images)
            
            # 创建笔记对象
            note = XHSNote.smart_create(
                title=title,
                content=content,
                topics=topics,
                location="",
                images=images_str,
                videos=""
            )
            
            print(f"📝 笔记信息准备完毕: 标题={note.title}, 话题={note.topics}")
            
            # 发布笔记 - 使用同步方式调用异步方法
            result = asyncio.run(self.xhs_client.publish_note(note))
            
            if result.success:
                print(f"✅ 笔记发布成功!")
                if hasattr(result, 'final_url') and result.final_url:
                    print(f"🔗 笔记链接: {result.final_url}")
            else:
                print(f"❌ 笔记发布失败: {result.message if hasattr(result, 'message') else '未知错误'}")
            
            return result
            
        except Exception as e:
            print(f"💥 发布过程出错: {e}")
            import traceback
            print(f"详细错误信息: {traceback.format_exc()}")
            # 创建一个简单的结果对象
            class Result:
                def __init__(self, success, message):
                    self.success = success
                    self.message = message
                    
            return Result(False, str(e))

    def generate_single_note(self, index: int):
        """生成单篇完整的小红书笔记（包括文案和图片）。"""
        print("=" * 50)
        print(f"正在生成笔记 {index + 1}/{self.notes_count}...")
        
        title = self.generate_note_title()
        print(f"  • 标题生成: {title}")

        content = self.generate_note_content(title)
        print(f"  • 文案已生成，字数: {len(content)}。")

        image_filenames = []
        print(f"  • 正在生成 {self.images_per_note} 张配图...")
        for i in range(self.images_per_note):
            # 确保每张图片的主题相关但不完全相同
            if len(content) < 50:
                description = f"{title} {content}"
            else:
                # 根据图片索引选择不同部分的内容作为描述
                content_parts = content.split('\n\n')
                if len(content_parts) >= 3:
                    description = content_parts[i % len(content_parts)]
                else:
                    # 在内容不足3段时，使用标题加内容片段
                    start_pos = (i * 50) % max(1, len(content) - 50)
                    description = f"{title} - {content[start_pos:start_pos+50]}"
            
            # 确保描述中没有星号和连字符
            description = description.replace('**', '')
            description = description.replace('*', '')
            description = description.replace('-', '•')
            
            print(f"    • 正在为图片 {i+1} 生成HTML...")
            html_content = self.generate_image_html(description, i)
            
            image_filename = f"output/images/note_{index+1}_img_{i+1}.png"
            self.render_html_to_image(html_content, image_filename)
            image_filenames.append(image_filename)

        # 保存笔记内容到文件，分离标题和内容
        note_filename = f"output/notes/note_{index+1}.txt"
        with open(note_filename, "w", encoding="utf-8") as f:
            # 写入标题行
            f.write(f"标题: {title}\n\n")
            
            # 写入文案，不再包含标题
            f.write(f"文案:\n{content}\n\n")
            
            # 写入配图文件列表
            f.write("配图文件:\n")
            for img in image_filenames:
                f.write(f"{img}\n")
                
        print(f"  • 笔记内容已保存到: {note_filename}")
        
        # 生成标签但不添加到文案中
        prompt = f"""
请为这篇小红书笔记生成3-5个相关的话题标签，要求：
1. 主题：{self.content_theme}
2. 风格：{self.style}
3. 目标受众：{self.target_audience}
4. 内容概要：{content[:100]}...

标签要求：
1. 不要带#号
2. 每个标签2-8个字
3. 符合小红书平台特点
4. 容易被搜索到
5. 与内容高度相关
6. 必须与主题"{self.content_theme}"强相关

请直接返回标签，用空格分隔，不要任何解释。
"""
        tags_text = self.call_api(prompt)
        tags = [tag.strip() for tag in tags_text.split() if tag.strip()]
        
        # 确保至少有一些默认标签
        if not tags:
            tags = [self.content_theme, self.style, "小红书笔记", "精选推荐"]
        
        # 限制标签数量
        tags = tags[:5]
        
        print(f"  • 生成的标签: {tags}")
        
        # 如果启用了自动发布，则执行发布流程
        if self.auto_publish:
            return {
                "title": title,
                "content": content,
                "images": image_filenames,
                "tags": tags
            }
        return None

    def publish_note(self, note_data):
        """发布笔记"""
        if not note_data:
            return False
            
        print(f"⏳ 等待 {self.publish_delay} 秒后发布笔记...")
        time.sleep(self.publish_delay)
        
        result = self.publish_to_xiaohongshu(
            note_data["title"], 
            note_data["content"], 
            note_data["images"],
            note_data["tags"]
        )
        
        # 确保我们能正确处理返回值
        if hasattr(result, "success"):
            return result.success
        elif isinstance(result, dict) and "success" in result:
            return result["success"]
        else:
            print(f"⚠️ 警告: 无法确定发布结果状态，返回False")
            return False

    def generate_all_notes(self):
        """循环调用，生成所有指定数量的笔记。"""
        print("\n开始批量生成小红书笔记...")
        for i in range(self.notes_count):
            try:
                # 生成笔记内容和图片
                note_data = self.generate_single_note(i)
                print(f"成功生成笔记 {i+1}/{self.notes_count}\n")
                
                # 如果启用了自动发布，则发布笔记
                if self.auto_publish and note_data:
                    success = self.publish_note(note_data)
                    if success:
                        print(f"笔记 {i+1}/{self.notes_count} 发布成功!")
                        
                        # 如果还有下一篇笔记，等待指定的时间间隔
                        if i < self.notes_count - 1:
                            wait_time = self.publish_interval
                            print(f"⏳ 等待 {wait_time} 秒后继续生成下一篇笔记...")
                            time.sleep(wait_time)
                    else:
                        print(f"笔记 {i+1}/{self.notes_count} 发布失败，跳过后续笔记发布")
                        break
                
            except Exception as e:
                print(f"生成笔记 {i+1} 时出错: {e}")
                import traceback
                print(f"详细错误信息: {traceback.format_exc()}")

if __name__ == "__main__":
    try:
        # 创建命令行参数解析器
        parser = argparse.ArgumentParser(description='小红书笔记自动生成工具')
        
        # 初始化生成器
        generator = XiaohongshuAutoGenerator()
        
        # 添加图片风格选项
        parser.add_argument('--style', type=str, choices=["标准", "杂志封面", "极简信息", "活泼活力", "自定义信息"],
                            default="标准", help='指定图片风格: 标准, 杂志封面, 极简信息, 活泼活力, 自定义信息')
                            
        # 添加其他可能的命令行参数
        parser.add_argument('--count', type=int, default=1, help='生成笔记的数量')
        parser.add_argument('--theme', type=str, default=generator.content_theme, help='笔记主题')
        parser.add_argument('--content-style', type=str, default=generator.style, help='内容风格')
        parser.add_argument('--audience', type=str, default=generator.target_audience, help='目标受众')
        parser.add_argument('--images', type=int, default=3, help='每篇笔记的图片数量')
        
        # 解析命令行参数
        args = parser.parse_args()
        
        # 设置从命令行获取的参数
        generator.image_style = args.style
        generator.notes_count = args.count
        generator.content_theme = args.theme
        generator.style = args.content_style
        generator.target_audience = args.audience
        generator.images_per_note = args.images
        
        print(f"使用图片风格: {generator.image_style}")
        
        generator.generate_all_notes()
        print("-" * 50)
        print("所有笔记生成完成！请到 'output' 目录查看成果。")
    except Exception as e:
        print(f"\n程序执行出错: {e}")
        print(f"\n程序执行出错: {e}")