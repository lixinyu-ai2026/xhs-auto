import os
import requests
from playwright.sync_api import sync_playwright
import time
import random
import re
from dotenv import load_dotenv
import sys
import asyncio

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
    一个使用 Kimi API 自动生成小红书图文笔记的脚本。
    所有配置直接在此脚本中完成。
    """
    def __init__(self):
        """
        初始化生成器，加载配置并创建输出目录。
        """
        print("正在初始化生成器...")

        # ==================== 配置区域 ====================
        # 请直接在此处填入你的 Kimi API 密钥 (来自 Moonshot AI 开放平台)
        # 注意：如果API密钥不正确或过期，请更换
        self.api_key = "sk-OTyKBzLPwr8v7AqhQGBSxB0C2H9ge5Y8jWbtdEADcgDRxBSG" # <--- 确保这里填入了你的密钥

        # --- 内容生成配置 ---
        self.notes_count = 1
        self.images_per_note = 3
        self.content_theme = "运动健将"  # 可以修改为任何主题
        self.style = "轻松幽默"  # 可以修改为任何风格，如"轻松幽默"、"专业严谨"、"文艺清新"等
        self.target_audience = "运动达人"  # 可以修改为任何目标受众
        self.max_content_length = 400  # 文案最大字数限制
        
        # 专业领域术语库
        self.professional_terms = {
            # 健康与减脂相关
            "减脂": ["热量赤字", "基础代谢率(BMR)", "TDEE", "体脂率", "代谢适应", "生酮饮食", "间歇性断食(IF)", 
                   "HIIT训练", "有氧心率区", "胰岛素敏感性", "营养密度", "宏量营养素", "能量平衡", "去水肿",
                   "肌糖原", "卡路里", "蛋白质摄入", "脂肪酸", "代谢窗口", "复合碳水化合物"],
            "运动": ["肌肉增长", "力量训练", "无氧运动", "有氧耐力", "肌肉记忆", "爆发力", "动作分解", "核心激活",
                   "训练容量", "组间休息", "离心收缩", "向心收缩", "超级组", "动作轨迹", "关节稳定性",
                   "代偿动作", "肌肉失衡", "神经肌肉连接", "运动表现", "恢复期"],
            "健康": ["微营养素", "抗氧化剂", "多酚类化合物", "生物利用度", "肠道菌群平衡", "血糖指数", 
                   "胰岛素负荷", "抗炎饮食", "细胞代谢", "线粒体功能", "氧化应激", "免疫调节", "肠-脑轴",
                   "表观遗传学", "神经递质平衡", "代谢适应性", "荷尔蒙平衡", "生物钟调节", "细胞自噬"],
            
            # 美食相关
            "美食": ["风味层次", "口感丰富度", "质地感知", "风味融合", "提鲜", "隐性甜度", "嗅觉记忆",
                   "五味平衡", "鲜度指标", "风味馥郁度", "脂溶性风味物质", "回甘", "持久度", "风味释放曲线",
                   "烟熏风味", "焦香", "醇厚度", "香气复合", "口感层次", "风味扩散"],
            "烹饪": ["焦糖化反应", "美拉德反应", "热传导", "乳化技术", "酵母发酵", "低温烹饪", "压力烹饪",
                   "调味分层", "酸碱平衡", "质地对比", "刀工技术", "温度控制", "风味提取", "浸渍法",
                   "腌制工艺", "热冲击法", "蛋白质变性", "淀粉糊化", "还原糖", "氨基酸反应"],
            
            # 美妆与时尚相关
            "美妆": ["妆前调理", "遮瑕技巧", "高光修容", "粉底匹配", "定妆技术", "修容立体", "眼妆层次",
                   "唇部妆效", "底妆质感", "眉形设计", "肤色校正", "妆感调整", "妆效持久", "肌肤纹理",
                   "透明质酸", "胶原蛋白", "水油平衡", "角质层", "皮脂膜", "保湿因子"],
            "护肤": ["角质代谢", "肌肤屏障", "抗老成分", "活性因子", "氧化还原", "胶原再生", "透皮吸收",
                   "细胞更新", "皮肤PH值", "脂质层", "滋养修护", "舒敏抗炎", "光老化防护", "皮肤微生态",
                   "神经酰胺", "肽类成分", "精华浓度", "分子量大小", "渗透机制", "结构稳定性"],
            "时尚": ["色彩理论", "面料垂坠", "轮廓线条", "造型比例", "色彩互补", "风格定位", "材质混搭",
                   "图案编排", "版型剪裁", "搭配平衡", "视觉焦点", "肤色色调", "服装语言", "流行趋势",
                   "个人印象", "时尚周期", "色彩心理", "衣着场合", "风格一致性", "服装功能性"],
            
            # 科技相关
            "科技": ["算法优化", "用户界面", "响应式设计", "云计算架构", "数据加密", "网络协议", "编程范式",
                   "接口设计", "系统集成", "前端渲染", "后端处理", "数据结构", "内存管理", "并行计算",
                   "人工智能", "机器学习", "深度神经网络", "量子计算", "区块链技术", "虚拟现实"],
            "数码": ["像素密度", "色彩准确度", "刷新率", "处理器架构", "散热系统", "功耗优化", "接口协议",
                   "信号传输", "电池容量", "充电速率", "无线连接", "数据传输", "存储介质", "编码解码",
                   "传感器灵敏度", "影像处理", "光学防抖", "音频解析度", "触控响应", "显示技术"],
            
            # 商业与职场
            "商业": ["市场定位", "品牌策略", "价值主张", "商业模式", "营销漏斗", "转化路径", "用户获取",
                   "客户生命周期", "定价策略", "竞争分析", "市场细分", "品牌资产", "投资回报率", "增长黑客",
                   "数据驱动", "用户体验", "产品迭代", "渠道建设", "品牌定位", "商业生态"],
            "职场": ["领导力发展", "团队协作", "沟通技巧", "冲突管理", "情商培养", "时间管理", "目标设定",
                   "绩效评估", "职业规划", "谈判策略", "影响力构建", "决策制定", "危机处理", "资源分配",
                   "组织文化", "变革管理", "创新思维", "战略眼光", "执行力", "职场政治"],
            
            # 教育与学习
            "教育": ["认知发展", "学习策略", "知识结构", "记忆固化", "思维模式", "批判性思考", "创造性解决",
                   "元认知", "深度加工", "知识迁移", "学习动机", "注意力分配", "反馈机制", "教学设计",
                   "评估标准", "学习曲线", "知识图谱", "能力层级", "学科交叉", "项目学习"],
            "学习": ["间隔重复", "刻意练习", "费曼技巧", "心流状态", "知识内化", "记忆宫殿", "思维导图",
                   "主动回忆", "学习区间", "概念连接", "知识编码", "联想记忆", "输出倒逼", "归纳总结",
                   "类比推理", "问题解构", "自我测试", "知识复习", "注意力管理", "学习反思"],
            
            # 旅行与自然
            "旅行": ["目的地规划", "行程优化", "文化浸入", "体验设计", "旅行摄影", "景点评估", "住宿选择",
                   "交通策略", "预算控制", "风险管理", "季节因素", "语言障碍", "文化冲击", "旅行节奏",
                   "地域特色", "历史脉络", "深度游览", "自然景观", "城市探索", "美食体验"],
            "自然": ["生态系统", "生物多样性", "环境适应", "自然循环", "气候变化", "种群平衡", "栖息地",
                   "光合作用", "植物生理", "土壤结构", "水文循环", "生物地理", "演化适应", "基因表达",
                   "物种互动", "能量流动", "物种分类", "生物节律", "环境压力", "自然选择"],
            
            # 艺术与创作
            "艺术": ["美学原理", "构图技巧", "色彩心理", "空间关系", "艺术风格", "历史脉络", "表现手法",
                   "媒介特性", "艺术语言", "视觉叙事", "情感表达", "符号象征", "艺术流派", "创作过程",
                   "艺术批评", "观者体验", "文化影响", "艺术市场", "创意发展", "概念探索"],
            "设计": ["用户体验", "界面交互", "视觉层次", "信息架构", "设计思维", "原型迭代", "用户研究",
                   "可用性测试", "情感设计", "品牌一致性", "设计系统", "视觉表达", "版式布局", "色彩配方",
                   "形式语言", "功能美学", "设计约束", "创意过程", "用户旅程", "设计伦理"],
            
            # 情感与人际
            "情感": ["情绪识别", "共情能力", "心理弹性", "自我意识", "情绪调节", "亲密关系", "依恋模式",
                   "人际边界", "冲突解决", "有效沟通", "心理安全", "情感需求", "关系动态", "行为模式",
                   "潜意识影响", "心理防御", "认知重构", "价值观差异", "情感连接", "自我成长"],
            "人际": ["社交智能", "非语言沟通", "人际吸引", "信任建立", "影响策略", "团队协作", "冲突管理",
                   "社交网络", "关系维护", "社会支持", "角色理论", "群体动力", "领导风格", "人格特质",
                   "文化差异", "沟通障碍", "印象管理", "社交焦虑", "共情倾听", "反馈技巧"],
            

        }
        
        # 初始化主题关键词映射
        self.theme_keywords = {
            # 美容与时尚
            "美妆": ["美妆", "化妆", "美容", "护肤", "彩妆", "妆容", "口红", "粉底", "眼影", "保湿"],
            "时尚": ["时尚", "穿搭", "服装", "衣服", "搭配", "潮流", "穿衣", "风格", "衣橱", "流行"],
            
            # 健康与运动
            "减脂": ["减脂", "减肥", "健身", "瘦身", "塑形", "健康饮食", "热量", "碳水", "蛋白质", "脂肪"],
            "运动": ["运动", "健身", "锻炼", "训练", "跑步", "力量", "拉伸", "瑜伽", "肌肉", "有氧"],
            
            # 科技与商业
            "科技": ["科技", "数码", "编程", "电脑", "手机", "智能", "互联网", "设备", "应用", "技术"],
            "商业": ["商业", "创业", "管理", "职场", "工作", "企业", "市场", "营销", "投资", "策略"],
            
            # 旅行与自然
            "旅行": ["旅行", "旅游", "旅程", "风景", "景点", "度假", "出游", "攻略", "行程", "目的地"],
            "自然": ["自然", "环保", "生态", "植物", "动物", "花卉", "园艺", "绿植", "种植", "环境"],
            
            # 美食与生活
            "美食": ["美食", "食谱", "料理", "烹饪", "餐饮", "菜谱", "厨房", "美味", "食材", "做菜"],
            "生活": ["生活", "日常", "家居", "家庭", "习惯", "技巧", "收纳", "整理", "家务", "居家"],
            
            # 教育与艺术
            "教育": ["教育", "学习", "知识", "课程", "考试", "培训", "成长", "思维", "技能", "方法"],
            "艺术": ["艺术", "设计", "创作", "绘画", "摄影", "音乐", "创意", "插画", "画作", "审美"],
            
            # 其他通用类别
            "情感": ["情感", "心理", "人际", "恋爱", "婚姻", "沟通", "成长", "亲密", "相处", "关系"]
        }
        
        # --- 发布配置 ---
        self.auto_publish = True          # 是否自动发布到小红书
        self.publish_delay = 10           # 生成后等待多少秒发布
        self.publish_interval = 60        # 两篇笔记之间的发布间隔
        
        # Playwright 浏览器路径配置
        self.playwright_browsers_path = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
        
    def find_best_terms_category(self, theme):
        """改进的主题-术语匹配算法"""
        # 评分系统 - 为每个术语类别计算与主题的匹配得分
        category_scores = {}
        for category, terms in self.professional_terms.items():
            score = 0
            # 1. 检查类别名称是否直接出现在主题中
            if category in theme:
                score += 10  # 直接匹配类别名称得高分
            
            # 2. 检查主题中是否包含该类别的关键词
            if category in self.theme_keywords:
                for keyword in self.theme_keywords[category]:
                    if keyword in theme:
                        score += 5  # 匹配关键词得中等分数
                        
            # 3. 额外的语义匹配（简化版）
            if category == "美妆" and any(kw in theme for kw in ["妆容", "美丽", "护肤", "化妆品"]):
                score += 3
            elif category == "减脂" and any(kw in theme for kw in ["瘦身", "体重", "瘦", "苗条"]):
                score += 3
            elif category == "科技" and any(kw in theme for kw in ["智能", "数字", "app", "软件"]):
                score += 3
                
            category_scores[category] = score
            
        # 根据得分排序，选择得分最高的类别
        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 如果有得分大于0的类别，返回得分最高的
        if sorted_categories and sorted_categories[0][1] > 0:
            return self.professional_terms[sorted_categories[0][0]]
        
        # 如果没有匹配的类别，尝试更广泛的主题分类
        broad_themes = {
            "美容美妆": ["美妆", "护肤", "时尚"],
            "健康健身": ["减脂", "运动", "健康"],
            "饮食烹饪": ["美食", "烹饪"],
            "科技数码": ["科技", "数码"],
            "商业职场": ["商业", "职场"],
            "教育学习": ["教育", "学习"],
            "旅行自然": ["旅行", "自然"],
            "艺术设计": ["艺术", "设计"],
            "情感人际": ["情感", "人际"]
        }
        
        for broad_theme, categories in broad_themes.items():
            # 检查主题中是否含有广义主题的关键词
            if any(broad_keyword in theme for broad_keyword in broad_theme):
                # 随机选择该广义主题下的一个术语类别
                import random
                selected_category = random.choice(categories)
                return self.professional_terms[selected_category]
        
        # 如果还是没有匹配，根据风格选择合适的术语集
        style_term_mapping = {
            "专业严谨": ["科技", "教育", "健康"],
            "可爱幽默": ["美妆", "美食", "生活"],
            "文艺清新": ["艺术", "自然", "旅行"],
            "轻松活泼": ["时尚", "运动", "旅行"],
            "简约现代": ["设计", "科技", "商业"]
        }
        
        current_style = self.style
        if current_style in style_term_mapping:
            import random
            style_categories = style_term_mapping[current_style]
            selected_category = random.choice(style_categories)
            return self.professional_terms[selected_category]
        
        # 最后的后备方案 - 返回通用术语
        common_categories = ["教育", "生活", "商业"]
        import random
        return self.professional_terms[random.choice(common_categories)]

        if not self.api_key or self.api_key == "your_kimi_api_key_here":
            raise ValueError("请在脚本的 __init__ 方法中设置你的 Kimi API 密钥 (self.api_key)")

        print(f"配置加载完成：将生成 {self.notes_count} 篇关于 '{self.content_theme}' 的笔记。")
        if self.auto_publish:
            print(f"自动发布已启用：笔记将在生成后 {self.publish_delay} 秒内发布到小红书。")

        os.makedirs("output/notes", exist_ok=True)
        os.makedirs("output/images", exist_ok=True)
        
        # 创建默认图片目录
        default_images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_images")
        os.makedirs(default_images_dir, exist_ok=True)
        
        # 检查默认图片是否存在，不存在则创建简单的默认图片
        default_image_path = os.path.join(default_images_dir, "default_image.jpg")
        if not os.path.exists(default_image_path):
            self.create_default_image(default_image_path)
            print(f"已创建默认图片: {default_image_path}")
        
        print("输出目录 'output/notes' 和 'output/images' 已准备就绪。")
        
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

    def call_kimi_api(self, prompt: str) -> str:
        """
        调用 Kimi (Moonshot) API 并返回结果。
        【重要更新】: 此函数已加入错误处理和自动重试逻辑。
        """
        print(f"      开始调用 Kimi API...")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "moonshot-v1-8k",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        
        max_retries = 5  # 最多重试5次
        base_delay = 5   # 基础延迟时间5秒

        for i in range(max_retries):
            try:
                print(f"      第{i+1}次尝试调用API...")
                response = requests.post(
                    "https://api.moonshot.cn/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60 # 设置60秒超时
                )
                
                # 检查状态码
                print(f"      API返回状态码: {response.status_code}")
                
                # 如果遇到429错误，则等待后重试
                if response.status_code == 429:
                    # 计算下一次重试的等待时间（指数退避）
                    delay = base_delay * (2 ** i) + random.uniform(0, 1)
                    print(f"    [警告] 遇到API速率限制(429)。将在 {delay:.1f} 秒后进行第 {i+1}/{max_retries} 次重试...")
                    time.sleep(delay)
                    continue # 继续下一次循环尝试
                
                # 检查响应内容
                try:
                    response_json = response.json()
                    print(f"      API返回JSON格式响应")
                except Exception as json_error:
                    print(f"      API返回非JSON响应: {response.text[:100]}...")
                    raise Exception(f"API返回非JSON响应: {json_error}")

                response.raise_for_status() # 如果是其他错误 (如 401, 500), 则直接抛出异常
                
                # 检查返回的内容结构
                if "choices" not in response_json or len(response_json["choices"]) == 0:
                    print(f"      API返回异常，没有choices字段: {response_json}")
                    raise Exception("API返回异常，没有choices字段")
                    
                result = response_json["choices"][0]["message"]["content"]
                print(f"      API调用成功，返回内容长度: {len(result)} 字符")
                return result

            except requests.exceptions.RequestException as e:
                # 对于其他网络问题，也进行重试
                if i < max_retries - 1:
                    delay = base_delay * (2 ** i)
                    print(f"    [警告] API请求失败: {e}。将在 {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    # 如果所有重试都失败了，则抛出最终的异常
                    print(f"    [错误] API请求失败，已达到最大重试次数: {e}")
                    return None
            except Exception as e:
                print(f"    [错误] 处理API响应时出错: {e}")
                if i < max_retries - 1:
                    delay = base_delay * (2 ** i)
                    print(f"    将在 {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    print(f"    [错误] API处理失败，已达到最大重试次数")
                    return None
        
        # 如果循环结束仍未成功，返回None而不是抛出异常
        print("    [错误] Kimi API 请求失败，已达到最大重试次数。")
        return None


    def generate_note_title(self) -> str:
        """根据主题、风格和受众生成小红书标题。"""
        prompt = f"""
                    请为小红书生成一个关于"{self.content_theme}"的爆款标题，要求：
                    1. 包含2-3个相关的emoji表情。
                    2. 标题总长度严格控制在20字以内（包括emoji）。
                    3. 风格为"{self.style}"。
                    4. 目标受众是"{self.target_audience}"。
                    5. 标题应该引人入胜，突出主题的特色和亮点。
                    请直接返回标题内容，不要包含任何解释或修饰。
                    注意：标题必须少于20字，请仔细检查字数。
                """
        return self.call_kimi_api(prompt).strip().strip('"')

    def generate_note_content(self, title: str) -> str:
        """根据标题生成完整的小红书笔记文案。"""
        prompt = f"""
                    根据以下标题为小红书生成一篇简短的笔记文案：
                    标题：{title}
                    要求：
                    1. 文案风格为"{self.style}"。
                    2. 目标受众是"{self.target_audience}"。
                    3. 包含小红书能够发布的emoji表情。
                    4. 段落分明，排版清晰，易于阅读。
                    5. 文案内容简洁精炼，总字数在200-400字之间。
                    6. 内容需要围绕"{self.content_theme}"展开，突出主题特色。
                    7. 文案最后一行添加3-4个相关的话题标签，标签可以点击并搜索到话题。
                    8. 严禁使用星号(*)和连字符(-)符号，不要使用任何markdown格式标记。
                    9. 非常重要: 不要把标题重复作为文案的第一行或开头，直接从正文内容开始。
                    
                    请直接返回文案内容，不需要任何解释或修饰。
                """
        content = self.call_kimi_api(prompt)
        # 清理内容中的星号和连字符
        content = content.replace('**', '')
        content = content.replace('*', '')
        content = content.replace(' - ', ' • ')
        content = content.replace('\n---\n', '\n\n')
        
        # 检查内容是否以标题开头，如果是则移除
        if content.startswith(title) or content.strip().startswith(title):
            # 移除标题，可能标题后有换行符
            if content.startswith(title + '\n'):
                content = content[len(title + '\n'):]
            elif content.startswith(title):
                content = content[len(title):]
            content = content.lstrip() # 移除开头的空白字符
        
        # 提取并去重标签
        tags = []
        seen_tags = set()  # 用于跟踪已经添加过的标签
        for word in content.split():
            if word.startswith('#'):
                # 去除可能的标点符号
                clean_tag = word.rstrip('.,;:!?')
                # 转小写用于比较，确保大小写不同的相同标签被视为重复
                tag_lower = clean_tag.lower()
                if tag_lower not in seen_tags:
                    tags.append(clean_tag)
                    seen_tags.add(tag_lower)
        
        # 检查内容中是否已经包含了标签行
        lines = content.split('\n')
        has_tag_line = False
        content_without_tag_line = []
        
        for line in lines:
            # 检查该行是否主要由标签组成
            words = line.split()
            tag_count = sum(1 for word in words if word.startswith('#'))
            if tag_count > 0 and tag_count >= len(words) * 0.5:  # 如果一行中超过一半的单词是标签
                has_tag_line = True
            else:
                content_without_tag_line.append(line)
        
        # 如果内容超过200字，则截断
        content = '\n'.join(content_without_tag_line)
        if len(content) > self.max_content_length:
            # 找到200字附近的句号位置进行截断
            end_pos = content[:self.max_content_length].rfind('。')
            if end_pos == -1:  # 如果没有找到句号，则找空格
                end_pos = content[:self.max_content_length].rfind(' ')
            if end_pos == -1:  # 如果还没找到，直接在200字处截断
                end_pos = self.max_content_length
            
            # 截断内容，不包含标签部分
            content = content[:end_pos+1]
        
        # 如果内容中没有标签行，则添加标签
        if not has_tag_line and tags:
            content += '\n\n' + ' '.join(tags)
        
        return content

    def get_variant_title(self, image_index: int) -> str:
        """根据图片索引生成与主题相关但不同的标题变体"""
        base_theme = self.content_theme
        
        # 针对美妆主题的标题变体
        if any(kw in base_theme.lower() for kw in ["美妆", "化妆", "美容", "护肤", "彩妆"]):
            variants = [
                f"{base_theme}｜化妆小白必知",
                f"美妆达人不外传｜{base_theme.replace('那些你不知道的', '').replace('小知识', '秘籍')}",
                f"新手入门｜{base_theme.replace('那些你不知道的', '').replace('小知识', '技巧')}"
            ]
        # 针对减脂主题的标题变体
        elif any(kw in base_theme.lower() for kw in ["减脂", "减肥", "健身", "瘦身"]):
            variants = [
                f"{base_theme}｜健身达人分享",
                f"科学减脂｜{base_theme.replace('如何', '').replace('正确', '健康')}",
                f"塑形指南｜{base_theme.replace('如何', '怎样')}"
            ]
        # 针对美食主题的标题变体
        elif any(kw in base_theme.lower() for kw in ["美食", "食谱", "料理", "烹饪"]):
            variants = [
                f"{base_theme}｜厨房小白必学",
                f"美食达人分享｜{base_theme.replace('那些你不知道的', '')}",
                f"味蕾探索｜{base_theme.replace('那些', '这些')}"
            ]
        # 默认标题变体
        else:
            variants = [
                f"{base_theme}｜必知小技巧",
                f"达人分享｜{base_theme}",
                f"{base_theme.replace('那些', '这些').replace('如何', '怎样')}"
            ]
        
        # 确保索引在有效范围内
        safe_index = image_index % len(variants)
        return variants[safe_index]
        
    def generate_image_html(self, description: str, image_index: int) -> str:
        """根据文字描述和图片索引生成用于渲染图片的HTML代码，不同索引生成不同风格的图片。"""
        print(f"      生成图片{image_index+1} HTML，主题：{self.content_theme}")
        
        # 获取当前图片的变体标题
        variant_title = self.get_variant_title(image_index)
        
        # 调用函数获取最匹配的术语集
        try:
            selected_terms = self.find_best_terms_category(self.content_theme.lower())
            print(f"      找到匹配术语: {len(selected_terms)}个")
        except Exception as e:
            print(f"      术语匹配失败: {str(e)}")
            import traceback
            print(f"      错误详情: {traceback.format_exc()}")
            # 使用钓鱼术语作为备选
            selected_terms = self.professional_terms.get("钓鱼", ["钓鱼技巧", "鱼饵选择", "钓点选择"])
        
        # 随机选择5-8个专业术语加入提示中
        import random
        random.seed(image_index + hash(description) % 100)  # 确保每次生成相同内容图片会选择相同术语
        num_terms = min(random.randint(5, 8), len(selected_terms))
        chosen_terms = random.sample(selected_terms, num_terms)
        
        # 生成强制渐变背景提示
        background_requirement = """
        - HTML必须包含完整的<!DOCTYPE html>和HTML结构
        - 必须在<style>中明确定义渐变背景：body{background:linear-gradient(to bottom right, #颜色1, #颜色2) !important;}
        - 背景渐变必须可见，使用明亮美观的配色
        - 使用半透明白色卡片和磨砂玻璃效果(backdrop-filter:blur)展示内容
        """
        
        # 所有图片都使用问答式卡片布局（图2样式）
        prompt = f"""
        请创建一个问答式的HTML图片，类似于专业知识讲解的Q&A卡片，要点如下：
        
        1. 整体布局：
           - 顶部：有吸引人的主标题，字体大而醒目，显示"{variant_title}"
           - 内容区：2-3个问答卡片，每个卡片包含一个问题和对应的解答
           - 问题使用大号字体，解答使用普通字体
           - 整个图片需要有精美的渐变背景
        
        2. 视觉元素：
           - 背景配色需与"{self.content_theme}"主题相符，反映"{self.style}"风格
           - 问题可使用彩色标记或与主题相关的可爱图标
           - 卡片有阴影和圆角，给人舒适感
           - 卡片使用半透明或磨砂玻璃效果
           - 可以使用分隔线或不同颜色区分不同问题
           - 整体设计应符合"{self.target_audience}"的审美喜好
        
        3. 内容构建：
           - 基于以下描述生成2-3个问答对：{description}
           - 采用中英文混合模式：问题用中文，解答中将关键概念/专业术语用英文表达，并附中文解释
           - 例如："什么是粉底液的妆效？" → "粉底液的妆效主要分为Matte(哑光)和Dewy(水润)..."
           - 问题应当简短有力，解答应当清晰直接
           - 可在卡片底部添加小标签或备注信息
           - 整体风格要符合"{self.style}"气质
           - 内容中需要融入以下专业术语（至少使用3个）：{', '.join(chosen_terms)}
           - 确保这些专业术语同时提供英文表达和中文解释
           - 解答应当既专业又通俗易懂，适合"{self.target_audience}"阅读理解
           - 确保内容具有双语特色，提高知识传播的专业感
        
        {background_requirement}
        
        请生成完整的HTML代码，包含内联CSS样式，特别是渐变背景和磨砂玻璃效果。不要使用外部资源，确保所有样式都是内联的。
        不需要任何解释，只返回可直接使用的HTML代码。
        """
        
        try:
            result = self.call_kimi_api(prompt)
            if result is None:
                print(f"      警告: API返回为空，使用默认HTML")
                return f"""
                <div class="title">{variant_title}</div>
                <div class="card">
                    <div class="food-icon">📝</div>
                    <div class="food-name">{self.content_theme}</div>
                    <div class="food-desc">
                        {description[:100]}...
                    </div>
                </div>
                """
            return result
        except Exception as e:
            print(f"      图片生成出错: {e}")
            return f"""
            <div class="title">{variant_title}</div>
            <div class="card">
                <div class="food-icon">📝</div>
                <div class="food-name">{self.content_theme}</div>
                <div class="food-desc">
                    {description[:100]}...
                </div>
            </div>
            """

    def render_html_to_image(self, html: str, filename: str):
        """使用 Playwright 将 HTML 代码渲染成图片并保存。"""
        # 检查是否有有效的HTML内容
        if html is None or not html.strip() or len(html) < 1000:  # HTML太短可能导致图片内容不足
            print("警告: 生成的HTML内容为空，使用默认HTML模板")
            html = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>内容生成失败</title>
                <style>
                    body {{
                        margin: 0;
                        padding: 0;
                        font-family: 'Microsoft YaHei', sans-serif;
                        background: linear-gradient(to bottom right, #f6d365, #fda085);
                        width: 750px;
                        height: 100vh;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                    }}
                    .container {{
                        width: 90%;
                        max-width: 700px;
                        padding: 30px;
                    }}
                    .title {{
                        text-align: center;
                        font-size: 28px;
                        font-weight: bold;
                        color: #fff;
                        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                        margin: 0 0 30px 0;
                        padding: 15px;
                        background-color: rgba(255, 255, 255, 0.2);
                        backdrop-filter: blur(5px);
                        border-radius: 12px;
                    }}
                    .card {{
                        width: 100%;
                        margin: 0 auto;
                        border-radius: 15px;
                        background-color: rgba(255, 255, 255, 0.85);
                        backdrop-filter: blur(10px);
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                        padding: 25px;
                        box-sizing: border-box;
                    }}
                    .food-name {{
                        font-size: 22px;
                        color: #333;
                        margin: 0 0 15px 0;
                        padding: 0;
                        font-weight: 600;
                    }}
                    .food-desc {{
                        font-size: 16px;
                        color: #444;
                        margin: 0;
                        line-height: 1.7;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="title">内容生成失败，请重试</div>
                    <div class="card">
                        <div class="food-name">主题: {self.content_theme}</div>
                        <div class="food-desc">
                            抱歉，我们无法为此主题生成详细内容。可能是网络连接问题或API限制。
                            <br><br>
                            您可以尝试重新运行程序，或者修改主题后再试。
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
        
        # 清理HTML代码，去除代码块标记和可能的提示文字
        clean_html = html.strip()
        if clean_html.startswith("```html"):
            clean_html = clean_html[7:]
        if clean_html.endswith("```"):
            clean_html = clean_html[:-3]
        
        # 清除可能出现的任何注释、提示文字以及特定符号
        clean_html = clean_html.strip()
        
        # 移除markdown相关的星号和连字符符号
        clean_html = clean_html.replace('**', '')
        clean_html = clean_html.replace('*', '')
        clean_html = clean_html.replace(' - ', ' • ')
        
        # 根据图片索引确定背景样式
        # 从文件名获取索引信息
        try:
            # 从文件名中提取索引 (例如 note_1_img_2.png -> 索引 2-1=1)
            image_index = int(filename.split('_img_')[1].split('.')[0]) - 1
        except:
            image_index = 0
        
        # 根据主题和风格动态选择背景渐变
        # 定义主题关键词与颜色映射关系（大幅扩展主题覆盖范围）
        theme_colors = {
            # 美容与时尚
            "美妆": [
                "linear-gradient(to bottom right, #FF9A9E, #FECFEF)",  # 粉红渐变 - 简化语法
                "linear-gradient(to bottom right, #FFDEE9, #B5FFFC)",  # 粉蓝渐变 - 简化语法
                "linear-gradient(to bottom right, #FFB6C1, #FFD700)"   # 粉金渐变 - 简化语法
            ],
            "时尚": [
                "linear-gradient(to bottom right, #a18cd1, #fbc2eb)",  # 时尚紫粉渐变 - 简化语法
                "linear-gradient(to bottom right, #f6d365, #fda085)",  # 时尚橙黄渐变 - 简化语法
                "linear-gradient(to bottom right, #96deda, #50c9c3)"   # 时尚青绿渐变 - 简化语法
            ],
            
            # 健康与运动
            "减脂": [
                "linear-gradient(to bottom right, #43cea2, #185a9d)",  # 健康绿蓝渐变
                "linear-gradient(to bottom right, #56ab2f, #85FFBD)",  # 浅薄荷绿渐变
                "linear-gradient(to bottom right, #76b852, #8DC26F)"   # 自然绿渐变
            ],
            "运动": [
                "linear-gradient(to bottom right, #3494E6, #EC6EAD)",  # 活力蓝粉渐变
                "linear-gradient(to bottom right, #11998e, #38ef7d)",  # 活力绿渐变
                "linear-gradient(to bottom right, #536976, #BBD2C5)"   # 冷静灰绿渐变
            ],
            
            # 科技与商业
            "科技": [
                "linear-gradient(135deg, #2b5876 0%, #4e4376 100%)",  # 科技蓝紫渐变
                "linear-gradient(135deg, #0F2027 0%, #2C5364 100%)",  # 深蓝渐变
                "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)"  # 暗蓝渐变
            ],
            "商业": [
                "linear-gradient(135deg, #003973 0%, #E5E5BE 100%)",  # 商务蓝金渐变
                "linear-gradient(135deg, #334d50 0%, #cbcaa5 100%)",  # 商务绿棕渐变
                "linear-gradient(135deg, #1F1C2C 0%, #928DAB 100%)"   # 商务深紫渐变
            ],
            
            # 旅行与自然
            "旅行": [
                "linear-gradient(135deg, #5f2c82 0%, #49a09d 100%)",  # 梦幻紫绿渐变
                "linear-gradient(135deg, #00F260 0%, #0575E6 100%)",  # 明亮蓝绿渐变
                "linear-gradient(135deg, #134E5E 0%, #71B280 100%)"   # 海岸线渐变
            ],
            "自然": [
                "linear-gradient(135deg, #3C8CE7 0%, #00EAFF 100%)",  # 自然天蓝渐变
                "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",  # 自然紫蓝渐变
                "linear-gradient(135deg, #1D976C 0%, #93F9B9 100%)"   # 自然青草渐变
            ],
            
            # 美食与生活
            "美食": [
                "linear-gradient(135deg, #FF8008 0%, #FFC837 100%)",  # 橙色渐变
                "linear-gradient(135deg, #f12711 0%, #f5af19 100%)",  # 红黄渐变
                "linear-gradient(135deg, #e65c00 0%, #F9D423 100%)"   # 暖橙渐变
            ],
            "生活": [
                "linear-gradient(135deg, #ff758c 0%, #ff7eb3 100%)",  # 生活温馨粉渐变
                "linear-gradient(135deg, #f46b45 0%, #eea849 100%)",  # 生活橙棕渐变
                "linear-gradient(135deg, #c79081 0%, #dfa579 100%)"   # 生活棕黄渐变
            ],
            
            # 教育与艺术
            "教育": [
                "linear-gradient(135deg, #1A2980 0%, #26D0CE 100%)",  # 知识蓝绿渐变
                "linear-gradient(135deg, #9CECFB 0%, #65C7F7 50%, #0052D4 100%)",  # 学习蓝渐变
                "linear-gradient(135deg, #4776E6 0%, #8E54E9 100%)"   # 思考紫蓝渐变
            ],
            "艺术": [
                "linear-gradient(135deg, #B24592 0%, #F15F79 100%)",  # 艺术紫粉渐变
                "linear-gradient(135deg, #c2e59c 0%, #64b3f4 100%)",  # 艺术青蓝渐变
                "linear-gradient(135deg, #6a11cb 0%, #2575fc 100%)"   # 艺术深蓝紫渐变
            ],
            
            # 其他通用类别
            "情感": [
                "linear-gradient(135deg, #b92b27 0%, #1565C0 100%)",  # 情感红蓝渐变
                "linear-gradient(135deg, #f857a6 0%, #ff5858 100%)",  # 情感粉红渐变
                "linear-gradient(135deg, #4568dc 0%, #b06ab3 100%)"   # 情感蓝紫渐变
            ]
        }
        
        # 根据风格选择不同色调系列
        style_color_sets = {
            "专业严谨": {
                "default": [  # 默认系列 - 深沉稳重
                    "linear-gradient(to bottom right, #334d50, #cbcaa5)",
                    "linear-gradient(to bottom right, #1A2980, #26D0CE)",
                    "linear-gradient(to bottom right, #0F2027, #2C5364)"
                ]
            },
            "可爱幽默": {
                "default": [  # 默认系列 - 明亮活泼
                    "linear-gradient(to bottom right, #FF9A9E, #FECFEF)", 
                    "linear-gradient(to bottom right, #FDDB92, #D1FDFF)",
                    "linear-gradient(to bottom right, #9890e3, #b1f4cf)"
                ]
            },
            "文艺清新": {
                "default": [  # 默认系列 - 柔和
                    "linear-gradient(to bottom right, #a8edea, #fed6e3)",
                    "linear-gradient(to bottom right, #dfe9f3, white)",
                    "linear-gradient(to bottom right, #f5f7fa, #c3cfe2)"
                ]
            },
            "轻松活泼": {
                "default": [  # 默认系列 - 鲜艳
                    "linear-gradient(to bottom right, #00F260, #0575E6)",
                    "linear-gradient(to bottom right, #f6d365, #fda085)",
                    "linear-gradient(to bottom right, #f093fb, #f5576c)"
                ]
            },
            "简约现代": {
                "default": [  # 默认系列 - 中性
                    "linear-gradient(to bottom right, #bdc3c7, #2c3e50)",
                    "linear-gradient(to bottom right, #7F7FD5, #86A8E7, #91EAE4)",
                    "linear-gradient(to bottom right, #5D4157, #A8CABA)"
                ]
            },
            "清新可爱": {
                "default": [  # 默认系列 - 清新明亮
                    "linear-gradient(to bottom right, #fdcbf1, #e6dee9)",
                    "linear-gradient(to bottom right, #a1c4fd, #c2e9fb)",
                    "linear-gradient(to bottom right, #d4fc79, #96e6a1)"
                ]
            }
        }
        
        # 扩展主题关键词识别
        theme_keywords = {
            # 美容与时尚
            "美妆": ["美妆", "化妆", "美容", "护肤", "彩妆", "妆容", "口红", "粉底", "眼影", "保湿"],
            "时尚": ["时尚", "穿搭", "服装", "衣服", "搭配", "潮流", "穿衣", "风格", "衣橱", "流行"],
            
            # 健康与运动
            "减脂": ["减脂", "减肥", "健身", "瘦身", "塑形", "健康饮食", "热量", "碳水", "蛋白质", "脂肪"],
            "运动": ["运动", "健身", "锻炼", "训练", "跑步", "力量", "拉伸", "瑜伽", "肌肉", "有氧"],
            
            # 科技与商业
            "科技": ["科技", "数码", "编程", "电脑", "手机", "智能", "互联网", "设备", "应用", "技术"],
            "商业": ["商业", "创业", "管理", "职场", "工作", "企业", "市场", "营销", "投资", "策略"],
            
            # 旅行与自然
            "旅行": ["旅行", "旅游", "旅程", "风景", "景点", "度假", "出游", "攻略", "行程", "目的地"],
            "自然": ["自然", "环保", "生态", "植物", "动物", "花卉", "园艺", "绿植", "种植", "环境"],
            
            # 美食与生活
            "美食": ["美食", "食谱", "料理", "烹饪", "餐饮", "菜谱", "厨房", "美味", "食材", "做菜"],
            "生活": ["生活", "日常", "家居", "家庭", "习惯", "技巧", "收纳", "整理", "家务", "居家"],
            
            # 教育与艺术
            "教育": ["教育", "学习", "知识", "课程", "考试", "培训", "成长", "思维", "技能", "方法"],
            "艺术": ["艺术", "设计", "创作", "绘画", "摄影", "音乐", "创意", "插画", "画作", "审美"],
            
            # 其他通用类别
            "情感": ["情感", "心理", "人际", "恋爱", "婚姻", "沟通", "成长", "亲密", "相处", "关系"]
        }
        
        # 确定当前主题最匹配哪个类别
        theme_category = None  # 默认为None，后面处理
        matched_keywords = 0
        matched_category = ""
        
        for category, keywords in theme_keywords.items():
            category_match_count = 0
            for keyword in keywords:
                if keyword in self.content_theme:
                    category_match_count += 1
            
            # 如果找到更多关键词匹配的类别
            if category_match_count > matched_keywords:
                matched_keywords = category_match_count
                matched_category = category
        
        if matched_keywords > 0:
            theme_category = matched_category
        
        # 获取颜色渐变
        if theme_category and theme_category in theme_colors:
            # 如果找到特定主题匹配，使用对应颜色
            theme_gradients = theme_colors[theme_category]
        else:
            # 如果没有找到主题匹配，根据风格选择颜色
            current_style = self.style
            default_style = "简约现代"  # 默认风格
            
            if current_style in style_color_sets:
                theme_gradients = style_color_sets[current_style]["default"]
            else:
                theme_gradients = style_color_sets[default_style]["default"]
        
        # 返回适合的渐变色
        gradients = theme_gradients
        
        safe_index = image_index % len(gradients)
        gradient = gradients[safe_index]
        
        # 确保HTML有完整的结构
        if not clean_html.lower().startswith("<!doctype") and not clean_html.lower().startswith("<html"):
            clean_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>内容展示</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Noto Sans SC', sans-serif;
            background: {gradient} !important; /* 强制应用渐变背景 */
            background-image: {gradient} !important; /* 强制应用渐变背景 */
            width: 750px;
            overflow-x: hidden;
            color: #333;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            align-items: center;
        }}
        
        /* 确保渐变背景覆盖整个视口 */
        html {{
            background: {gradient} !important;
            min-height: 100%;
        }}
        .container {{
            width: 100%;
            max-width: 750px;
            margin: 0 auto;
            padding: 20px;
            box-sizing: border-box;
        }}
        .title {{
            text-align: center;
            font-size: 28px;
            font-weight: bold;
            color: #fff;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            margin: 0 0 40px 0; /* 增加标题和第一个卡片之间的间距 */
            padding: 15px 0;
            background-color: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(5px);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }}
        /* 玻璃态卡片效果 */
        .card {{
            width: 95%;
            margin: 0 auto 25px auto;
            border-radius: 15px;
            background-color: rgba(255, 255, 255, 0.65);
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            padding: 22px;
            box-sizing: border-box;
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.5);
        }}
        .card:nth-child(2) {{
            background-color: rgba(255, 240, 240, 0.7); /* 半透明浅粉色 */
        }}
        .card:nth-child(3) {{
            background-color: rgba(255, 250, 229, 0.7); /* 半透明浅黄色 */
        }}
        .card:nth-child(4) {{
            background-color: rgba(240, 248, 255, 0.7); /* 半透明浅蓝色 */
        }}
        .food-icon {{
            font-size: 32px;
            margin-bottom: 12px;
            filter: drop-shadow(0 2px 3px rgba(0,0,0,0.2));
        }}
        .food-name {{
            font-size: 22px;
            color: #333;
            margin: 0 0 12px 0;
            padding: 0;
            font-weight: 600;
            text-shadow: 0 1px 2px rgba(255,255,255,0.5);
        }}
        .food-desc {{
            font-size: 16px;
            color: #444;
            margin: 0;
            line-height: 1.7;
            letter-spacing: 0.02em;
        }}
        .pro-term {{
            font-weight: 600;
            color: #0066cc;
            background-color: rgba(200, 230, 255, 0.5);
            padding: 0 5px;
            border-radius: 4px;
        }}
        .en-term {{
            font-weight: 600;
            font-style: italic;
            color: #9933cc;
            padding: 0 3px;
        }}
        .term-explanation {{
            font-size: 0.9em;
            color: #666;
            margin-left: 4px;
        }}
        .qa-question {{
            font-size: 18px;
            font-weight: 600;
            color: #222;
            margin-bottom: 10px;
        }}
        .qa-answer {{
            font-size: 16px;
            line-height: 1.8;
            color: #444;
        }}
    </style>
</head>
<body>
    <div class="container">
        {clean_html}
    </div>
</body>
</html>"""

        with sync_playwright() as p:
            # 根据环境变量配置浏览器路径
            launch_options = {}
            try:
                # 尝试使用默认浏览器启动选项，不指定特定路径
                # Windows环境下浏览器安装路径可能会有差异
                browser = p.chromium.launch(headless=True)
                print("    - 成功使用默认配置启动浏览器")
            except Exception as e:
                print(f"    - 使用默认配置启动浏览器失败: {e}")
                print("    - 尝试使用备用方式启动浏览器...")
                
                # 备用方案：尝试指定浏览器路径
                if self.playwright_browsers_path:
                    launch_options['executable_path'] = os.path.join(
                        self.playwright_browsers_path,
                        'chromium-1179/chrome-win/chrome.exe'
                    )
                    try:
                        browser = p.chromium.launch(**launch_options)
                        print("    - 成功使用自定义路径启动浏览器")
                    except Exception as e2:
                        print(f"    - 使用自定义路径启动浏览器失败: {e2}")
                        raise Exception("无法启动浏览器，请检查Playwright配置")
                else:
                    # 最后尝试
                    try:
                        browser = p.chromium.launch(headless=True, executable_path="")
                        print("    - 成功使用空路径启动浏览器")
                    except:
                        raise Exception("无法启动浏览器，请检查Playwright配置")
            page = browser.new_page()
            page.set_viewport_size({"width": 750, "height": 500})
            page.set_content(clean_html)
            
            # 等待内容渲染完成 - 增加等待时间确保CSS加载完成
            time.sleep(3)
            
            # 注入额外CSS以确保渐变背景生效
            page.add_style_tag(content="""
                html, body {
                    background-image: linear-gradient(to bottom right, #a1c4fd, #c2e9fb) !important;
                    background: linear-gradient(to bottom right, #a1c4fd, #c2e9fb) !important;
                    min-height: 100vh !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }
            """)
            
            # 确保背景渐变已经应用
            page.evaluate("""() => {
                // 强制应用背景渐变
                document.body.style.backgroundImage = document.body.style.backgroundImage || 'linear-gradient(to bottom right, #a1c4fd, #c2e9fb)';
                document.body.style.background = document.body.style.background || 'linear-gradient(to bottom right, #a1c4fd, #c2e9fb)';
                // 设置html背景
                document.documentElement.style.background = 'linear-gradient(to bottom right, #a1c4fd, #c2e9fb)';
                document.documentElement.style.backgroundImage = 'linear-gradient(to bottom right, #a1c4fd, #c2e9fb)';
                // 强制重绘
                document.body.getBoundingClientRect();
            }""")
            
            # 使用evaluate来获取实际内容高度
            body_height = page.evaluate("""() => {
                const body = document.body;
                const html = document.documentElement;
                return Math.max(
                    body.scrollHeight, body.offsetHeight,
                    html.clientHeight, html.scrollHeight, html.offsetHeight
                );
            }""")
            
            # 设置最小内容高度以确保一致性
            MIN_HEIGHT = 750  # 设置为与宽度相同，即1:1的宽高比
            
            # 强制所有图片使用相同高度
            content_height = MIN_HEIGHT  # 固定高度为750px，与宽度相同
            
            # 总是添加额外的空间，确保内容能完整显示
            page.evaluate(f"""() => {{
                // 确保所有内容都能完整显示
                const spacer = document.createElement('div');
                spacer.style.height = '50px';  // 添加额外空间
                document.body.appendChild(spacer);
                
                // 强制调整所有卡片的高度，避免内容被截断
                const cards = document.querySelectorAll('.card, .content-card, section');
                cards.forEach(card => {{
                    card.style.minHeight = 'auto';  // 允许卡片自然扩展
                    card.style.overflow = 'visible';  // 确保内容不会被截断
                }});
            }}""")
                
            page.set_viewport_size({"width": 750, "height": content_height})
            
            # 确保所有图片高度一致，使用固定宽高比的截图区域
            FIXED_HEIGHT = 750  # 设置为与宽度相同，即1:1的宽高比
            
            clip = {
                "x": 0,
                "y": 0,
                "width": 750,
                "height": FIXED_HEIGHT
            }
            
            # 截图前多等待一下，确保所有内容和CSS渐变都已完全渲染
            time.sleep(2)
            
            # 强制重绘确保背景和内容都已正确渲染
            page.evaluate("""() => {
                // 强制重绘
                document.body.style.visibility = 'hidden';
                document.body.offsetHeight;  // 触发重排
                document.body.style.visibility = 'visible';
            }""")
            
            # 截图并保存
            page.screenshot(path=filename, clip=clip)
            
            print(f"    - 图片已保存: {filename}，尺寸: 750x{content_height}px")
            browser.close()
            
        print(f"    - 图片已保存到: {filename}")

    def initialize_xhs_client(self):
        """初始化小红书客户端"""
        try:
            if not hasattr(self, 'xhs_client') or self.xhs_client is None:
                print("正在初始化小红书客户端...")
                config = XHSConfig()
                self.xhs_client = XHSClient(config)
                print("小红书客户端初始化完成")
            return self.xhs_client
        except Exception as e:
            print(f"初始化小红书客户端失败: {e}")
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
            # 创建一个简单的空客户端
            self.xhs_client = type('DummyClient', (), {})()
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

    def extract_tags_from_content(self, content):
        """从内容中提取标签，并去除重复标签"""
        tags = []
        seen_tags = set()  # 用于跟踪已经添加过的标签
        lines = content.split('\n')
        for line in lines:
            if '#' in line:
                # 提取每个以#开头的标签
                words = line.split()
                for word in words:
                    if word.startswith('#'):
                        # 去除可能的标点符号
                        clean_tag = word.rstrip('.,;:!?')
                        # 转小写用于比较，确保大小写不同的相同标签被视为重复
                        tag_lower = clean_tag.lower()
                        if tag_lower not in seen_tags:
                            tags.append(clean_tag)
                            seen_tags.add(tag_lower)
        return tags

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
        
        # 提取标签
        tags = self.extract_tags_from_content(content)
        print(f"  • 提取的标签: {tags}")
        
        # 如果没有提取到标签，生成一些默认标签
        if not tags:
            default_tags = [f"#{self.content_theme}", f"#{self.style}", "#上热门"]
            print(f"  • 未找到标签，使用默认标签: {default_tags}")
            tags = default_tags
        
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
        generator = XiaohongshuAutoGenerator()
        generator.generate_all_notes()
        print("-" * 50)
        print("所有笔记生成完成！请到 'output' 目录查看成果。")
    except Exception as e:
        print(f"\n程序执行出错: {e}")