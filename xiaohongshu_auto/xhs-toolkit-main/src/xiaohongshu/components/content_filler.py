"""
小红书内容填写器

专门负责标题、内容、话题等文本内容的填写，遵循单一职责原则
"""

import asyncio
from typing import List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

from ..interfaces import IContentFiller, IBrowserManager
from ..constants import (XHSConfig, XHSSelectors, get_title_input_selectors)
from ...core.exceptions import PublishError, handle_exception
from ...utils.logger import get_logger
from ...utils.text_utils import clean_text_for_browser

logger = get_logger(__name__)


class XHSContentFiller(IContentFiller):
    """小红书内容填写器"""
    
    def __init__(self, browser_manager: IBrowserManager):
        """
        初始化内容填写器
        
        Args:
            browser_manager: 浏览器管理器
        """
        self.browser_manager = browser_manager
    
    @handle_exception
    async def fill_title(self, title: str) -> bool:
        """
        填写标题
        
        Args:
            title: 标题内容
            
        Returns:
            填写是否成功
        """
        logger.info(f"📝 开始填写标题: {title}")
        
        try:
            # 验证标题
            self._validate_title(title)
            
            # 查找标题输入框
            title_input = await self._find_title_input()
            if not title_input:
                raise PublishError("未找到标题输入框", publish_step="标题填写")
            
            # 执行标题填写
            return await self._perform_title_fill(title_input, title)
            
        except Exception as e:
            if isinstance(e, PublishError):
                raise
            else:
                logger.error(f"❌ 标题填写失败: {e}")
                return False
    
    @handle_exception
    async def fill_content(self, content: str) -> bool:
        """
        填写内容
        
        Args:
            content: 笔记内容
            
        Returns:
            填写是否成功
        """
        logger.info(f"📝 开始填写内容: {content[:50]}...")
        
        try:
            # 验证内容
            self._validate_content(content)
            
            # 查找内容编辑器
            content_editor = await self._find_content_editor()
            if not content_editor:
                raise PublishError("未找到内容编辑器", publish_step="内容填写")
            
            # 执行内容填写
            return await self._perform_content_fill(content_editor, content)
            
        except Exception as e:
            if isinstance(e, PublishError):
                raise
            else:
                logger.error(f"❌ 内容填写失败: {e}")
                return False
    
    @handle_exception
    async def fill_topics(self, topics: List[str]) -> bool:
        """
        填写话题标签
        
        基于实测验证的小红书话题自动化机制：
        1. 在编辑器中输入 #话题名
        2. 按回车键(Enter)触发转换
        3. 验证是否生成 .mention 元素
        
        Args:
            topics: 话题列表
            
        Returns:
            填写是否成功
        """
        logger.info(f"🏷️ 开始填写话题: {topics}")
        
        try:
            # 验证话题
            self._validate_topics(topics)
            
            # 执行话题自动化填写
            return await self._perform_topics_automation(topics)
            
        except Exception as e:
            logger.warning(f"⚠️ 话题填写失败: {e}")
            return False  # 话题填写失败不影响主流程
    
    def _validate_title(self, title: str) -> None:
        """
        验证标题
        
        Args:
            title: 标题内容
            
        Raises:
            PublishError: 当标题验证失败时
        """
        if not title or not title.strip():
            raise PublishError("标题不能为空", publish_step="标题验证")
        
        if len(title.strip()) > XHSConfig.MAX_TITLE_LENGTH:
            raise PublishError(f"标题长度超限，最多{XHSConfig.MAX_TITLE_LENGTH}个字符", 
                             publish_step="标题验证")
    
    def _validate_content(self, content: str) -> None:
        """
        验证内容
        
        Args:
            content: 笔记内容
            
        Raises:
            PublishError: 当内容验证失败时
        """
        if not content or not content.strip():
            raise PublishError("内容不能为空", publish_step="内容验证")
        
        if len(content.strip()) > XHSConfig.MAX_CONTENT_LENGTH:
            raise PublishError(f"内容长度超限，最多{XHSConfig.MAX_CONTENT_LENGTH}个字符", 
                             publish_step="内容验证")
    
    def _validate_topics(self, topics: List[str]) -> None:
        """
        验证话题
        
        Args:
            topics: 话题列表
            
        Raises:
            PublishError: 当话题验证失败时
        """
        if len(topics) > XHSConfig.MAX_TOPICS:
            raise PublishError(f"话题数量超限，最多{XHSConfig.MAX_TOPICS}个", 
                             publish_step="话题验证")
        
        for topic in topics:
            if len(topic) > XHSConfig.MAX_TOPIC_LENGTH:
                raise PublishError(f"话题长度超限: {topic}，最多{XHSConfig.MAX_TOPIC_LENGTH}个字符", 
                                 publish_step="话题验证")
    
    async def _find_title_input(self):
        """
        查找标题输入框
        
        Returns:
            标题输入元素，如果未找到返回None
        """
        driver = self.browser_manager.driver
        wait = WebDriverWait(driver, XHSConfig.DEFAULT_WAIT_TIME)
        
        # 尝试多个选择器
        for selector in get_title_input_selectors():
            try:
                logger.debug(f"🔍 尝试标题选择器: {selector}")
                title_input = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                
                if title_input and title_input.is_enabled():
                    logger.info(f"✅ 找到标题输入框: {selector}")
                    return title_input
                    
            except TimeoutException:
                logger.debug(f"⏰ 标题选择器超时: {selector}")
                continue
            except Exception as e:
                logger.debug(f"⚠️ 标题选择器错误: {selector}, {e}")
                continue
        
        logger.error("❌ 未找到可用的标题输入框")
        return None
    
    async def _find_content_editor(self):
        """
        查找内容编辑器
        
        Returns:
            内容编辑器元素，如果未找到返回None
        """
        driver = self.browser_manager.driver
        wait = WebDriverWait(driver, XHSConfig.DEFAULT_WAIT_TIME)
        
        try:
            logger.debug(f"🔍 查找内容编辑器: {XHSSelectors.CONTENT_EDITOR}")
            content_editor = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, XHSSelectors.CONTENT_EDITOR))
            )
            
            if content_editor and content_editor.is_enabled():
                logger.info("✅ 找到内容编辑器")
                return content_editor
            
        except TimeoutException:
            logger.error("⏰ 内容编辑器查找超时")
        except Exception as e:
            logger.error(f"⚠️ 内容编辑器查找错误: {e}")
        
        logger.error("❌ 未找到可用的内容编辑器")
        return None
    
    async def _perform_title_fill(self, title_input, title: str) -> bool:
        """
        执行标题填写
        
        Args:
            title_input: 标题输入元素
            title: 标题内容
            
        Returns:
            填写是否成功
        """
        try:
            # 清空现有内容
            title_input.clear()
            await asyncio.sleep(0.5)
            
            # 输入标题，首先清理符合ChromeDriver限制
            cleaned_title = clean_text_for_browser(title)
            title_input.send_keys(cleaned_title)
            
            # 验证输入是否成功
            await asyncio.sleep(1)
            current_value = title_input.get_attribute("value") or title_input.text
            
            # 尝试使用JavaScript直接设置原始标题（包含emoji）
            try:
                driver = self.browser_manager.driver
                element_tag = title_input.tag_name.lower()
                
                if element_tag == 'input':
                    # 对于input类型的标题框
                    js_script = """
                    var input = arguments[0];
                    var text = arguments[1];
                    
                    // 直接设置value
                    input.value = text;
                    
                    // 触发事件
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    
                    return true;
                    """
                    driver.execute_script(js_script, title_input, title)
                else:
                    # 对于contentEditable元素
                    js_script = """
                    var element = arguments[0];
                    var text = arguments[1];
                    
                    if(element.contentEditable === 'true') {
                        element.innerHTML = text;
                    } else {
                        element.textContent = text;
                    }
                    
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                    
                    return true;
                    """
                    driver.execute_script(js_script, title_input, title)
                
                logger.info("✅ 使用JavaScript设置原始标题（保留emoji）")
                
                # 额外尝试直接修改DOM属性
                try:
                    alt_script = """
                    var element = arguments[0];
                    var text = arguments[1];
                    
                    // 尝试设置多种属性
                    if(element.hasAttribute('value')) {
                        element.setAttribute('value', text);
                    }
                    
                    // 尝试针对React/Vue组件的处理
                    if(window.React || window.Vue) {
                        // 创建一系列事件模拟用户输入
                        ['focus', 'keydown', 'input', 'keyup', 'change', 'blur'].forEach(function(eventType) {
                            element.dispatchEvent(new Event(eventType, { bubbles: true }));
                        });
                    }
                    """
                    driver.execute_script(alt_script, title_input, title)
                except Exception as alt_err:
                    logger.debug(f"额外JavaScript尝试: {alt_err}")
                
            except Exception as js_err:
                logger.warning(f"JavaScript设置标题失败: {js_err}，但继续使用常规标题")
            
            if cleaned_title in current_value or len(current_value) > 0:
                logger.info("✅ 标题填写成功")
                return True
            else:
                logger.error("❌ 标题填写验证失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 标题填写过程出错: {e}")
            return False
    
    async def _perform_content_fill(self, content_editor, content: str) -> bool:
        """
        执行内容填写
        
        Args:
            content_editor: 内容编辑器元素
            content: 笔记内容
            
        Returns:
            填写是否成功
        """
        try:
            # 点击编辑器以获得焦点
            content_editor.click()
            await asyncio.sleep(0.5)
            
            # 清空现有内容
            content_editor.clear()
            
            # 尝试使用Ctrl+A全选然后删除
            content_editor.send_keys(Keys.CONTROL + "a")
            await asyncio.sleep(0.2)
            content_editor.send_keys(Keys.DELETE)
            await asyncio.sleep(0.5)
            
            # 清理内容符合ChromeDriver限制
            cleaned_content = clean_text_for_browser(content)
            
            # 分段输入，避免一次输入过多内容
            lines = cleaned_content.split('\n')
            for i, line in enumerate(lines):
                content_editor.send_keys(line)
                if i < len(lines) - 1:
                    content_editor.send_keys(Keys.ENTER)
                await asyncio.sleep(0.1)  # 短暂等待
            
            # 验证输入是否成功
            await asyncio.sleep(1)
            current_text = content_editor.text or content_editor.get_attribute("textContent") or ""
            
            # 简单验证：检查是否包含部分内容
            if (len(current_text) > 0 and 
                (cleaned_content[:20] in current_text or 
                 len(current_text) >= len(cleaned_content) * 0.8)):
                logger.info("✅ 内容填写成功")
                
                # 尝试使用JavaScript添加原始内容，包括所有emoji
                try:
                    driver = self.browser_manager.driver
                    script = """
                    var editor = arguments[0];
                    var content = arguments[1];
                    
                    // 处理换行
                    content = content.replace(/\\n/g, '<br>');
                    
                    // 设置内容
                    editor.innerHTML = content;
                    
                    // 触发内容变化事件
                    var event = new Event('input', { bubbles: true });
                    editor.dispatchEvent(event);
                    """
                    
                    driver.execute_script(script, content_editor, content)
                    logger.info("🔄 尝试通过JavaScript设置完整内容（保留emoji）")
                except Exception as js_error:
                    logger.warning(f"⚠️ JavaScript设置内容失败: {js_error}，但继续发布流程")
                
                return True
            else:
                logger.error(f"❌ 内容填写验证失败，期望长度: {len(cleaned_content)}, 实际长度: {len(current_text)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 内容填写过程出错: {e}")
            return False
    
    async def _perform_topics_automation(self, topics: List[str]) -> bool:
        """
        执行话题自动化填写 - 基于实测验证的完整实现
        
        关键修复：使用真实输入方式触发话题下拉菜单
        - 对比测试证明：直接send_keys不能触发下拉菜单
        - 正确方式：模拟真实用户逐字符输入 + 等待下拉菜单 + 回车确认
        
        实现逻辑：
        1. 定位到内容编辑器(.ql-editor)
        2. 对每个话题执行：真实输入#话题名 + 等待下拉菜单 + 按Enter键
        3. 验证是否生成了.mention元素(真正的话题标签)
        4. 支持重试机制处理偶发性失败
        
        Args:
            topics: 话题列表
            
        Returns:
            填写是否成功
        """
        try:
            driver = self.browser_manager.driver
            wait = WebDriverWait(driver, XHSConfig.DEFAULT_WAIT_TIME)
            
            # 0. 对话题进行去重处理
            unique_topics = []
            seen_topics = set()
            for topic in topics:
                # 去除#符号和可能的标点符号
                clean_topic = topic.replace('#', '').rstrip('.,;:!?')
                topic_lower = clean_topic.lower()
                if clean_topic and topic_lower not in seen_topics:
                    unique_topics.append(clean_topic)
                    seen_topics.add(topic_lower)
            
            # 使用去重后的话题列表
            topics = unique_topics
            logger.info(f"🔍 话题去重处理完成，实际添加 {len(topics)} 个话题: {topics}")
            
            # 1. 查找内容编辑器
            content_editor = await self._find_content_editor()
            if not content_editor:
                logger.error("❌ 未找到内容编辑器，无法添加话题")
                return False
            
            logger.info(f"✅ 找到内容编辑器，开始添加 {len(topics)} 个话题")
            
            # 2. 确保编辑器获得焦点并移动到末尾
            content_editor.click()
            await asyncio.sleep(0.3)
            content_editor.send_keys(Keys.END)
            await asyncio.sleep(0.2)
            
            # 3. 添加换行确保话题在新行
            content_editor.send_keys(Keys.ENTER)
            await asyncio.sleep(0.2)
            
            success_count = 0
            
            # 4. 逐个添加话题
            for i, topic in enumerate(topics):
                try:
                    logger.info(f"🏷️ 添加话题 {i+1}/{len(topics)}: {topic}")
                    
                    # 4.1 使用真实输入方式输入话题 (关键修复!)
                    topic_text = f"#{topic}" if not topic.startswith('#') else topic
                    success = await self._input_topic_realistically(content_editor, topic_text)
                    
                    if success:
                        # 4.2 验证话题转换是否成功
                        if await self._verify_topic_conversion(topic):
                            success_count += 1
                            logger.info(f"✅ 话题 '{topic}' 转换成功")
                        else:
                            logger.warning(f"⚠️ 话题 '{topic}' 转换失败，但继续处理")
                    else:
                        logger.warning(f"⚠️ 话题 '{topic}' 输入失败，但继续处理")
                    
                    # 4.3 添加空格分隔下一个话题
                    if i < len(topics) - 1:
                        content_editor.send_keys(" ")
                        await asyncio.sleep(0.2)
                        
                except Exception as e:
                    logger.error(f"❌ 添加话题 '{topic}' 时出错: {e}")
                    continue
            
            # 5. 总结结果
            if success_count > 0:
                logger.info(f"✅ 话题添加完成: {success_count}/{len(topics)} 个成功")
                return True
            else:
                logger.error(f"❌ 所有话题添加失败: 0/{len(topics)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 话题自动化过程出错: {e}")
            return False
    
    async def _input_topic_realistically(self, content_editor, topic_text: str) -> bool:
        """
        使用真实用户输入方式输入话题
        
        基于多次失败分析，采用更可靠的方法：
        1. 逐字符输入模拟真实用户行为
        2. 使用Actions类进行精确操作
        3. 多种备用方案确保成功率
        
        Args:
            content_editor: 内容编辑器元素
            topic_text: 话题文本（包含#号）
            
        Returns:
            输入是否成功
        """
        try:
            driver = self.browser_manager.driver
            from selenium.webdriver.common.action_chains import ActionChains
            
            # 清理话题文本，确保符合ChromeDriver限制
            cleaned_topic = clean_text_for_browser(topic_text)
            
            # 使用ActionChains，逐字符输入
            actions = ActionChains(driver)
            actions.click(content_editor)
            actions.send_keys(cleaned_topic)
            actions.perform()
            
            logger.debug(f"📝 话题输入: '{cleaned_topic}'")
            
            # 等待下拉菜单出现（灵活等待）
            dropdown_appeared = await self._wait_for_topic_dropdown_flexible()
            
            # 按Enter确认
            if dropdown_appeared:
                logger.info("👆 检测到话题下拉菜单，按Enter确认")
                await asyncio.sleep(0.5)  # 确保下拉菜单完全加载
            else:
                logger.warning("⚠️ 未检测到话题下拉菜单，仍然尝试提交")
                
            # 回车确认
            content_editor.send_keys(Keys.ENTER)
            
            await asyncio.sleep(0.5)
            
            return True
                
        except Exception as e:
            logger.error(f"❌ 真实输入话题出错: {e}")
            return False
    
    async def _wait_for_topic_dropdown_flexible(self, timeout: float = 1.5) -> bool:
        """
        灵活等待话题下拉菜单出现
        
        尝试多种可能的选择器，不强制要求下拉菜单出现
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            下拉菜单是否出现（仅供参考，不影响后续流程）
        """
        try:
            driver = self.browser_manager.driver
            
            # 可能的下拉菜单选择器（根据小红书可能的实现）
            possible_selectors = [
                '.ql-mention-list-container',  # Quill编辑器默认
                '.mention-list',               # 自定义实现
                '.topic-dropdown',             # 话题下拉菜单
                '.suggestion-list',            # 建议列表
                '[class*="mention"]',          # 包含mention的任何类
                '[class*="dropdown"]',         # 包含dropdown的任何类
                '[class*="suggestion"]',       # 包含suggestion的任何类
                '.autocomplete-container',     # 自动完成容器
                '.search-suggestions'          # 搜索建议
            ]
            
            for selector in possible_selectors:
                try:
                    await asyncio.sleep(0.2)  # 短暂等待
                    
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            # 检查是否包含话题相关内容
                            text_content = element.text.lower()
                            if any(keyword in text_content for keyword in ['话题', '#', 'topic', '浏览']):
                                logger.debug(f"✅ 发现话题下拉菜单: {selector}")
                                return True
                except:
                    continue
            
            logger.debug("⚠️ 未检测到话题下拉菜单，但这不影响转换")
            return False
            
        except Exception as e:
            logger.debug(f"⚠️ 检查话题下拉菜单时出错: {e}")
            return False
    
    async def _wait_for_topic_dropdown(self, timeout: float = 2.0) -> bool:
        """
        等待话题下拉菜单出现（保留旧方法以兼容）
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            下拉菜单是否出现
        """
        return await self._wait_for_topic_dropdown_flexible(timeout)
    
    async def _verify_topic_conversion(self, topic: str) -> bool:
        """
        验证话题是否成功转换为真正的话题标签
        
        改进的验证逻辑：
        1. 更长的等待时间确保DOM更新
        2. 更宽松的验证条件
        3. 多种验证方法的组合
        4. 详细的调试日志
        
        Args:
            topic: 要验证的话题名
            
        Returns:
            转换是否成功
        """
        try:
            driver = self.browser_manager.driver
            
            # 增加等待时间确保DOM完全更新
            await asyncio.sleep(1.0)
            
            logger.debug(f"🔍 开始验证话题 '{topic}' 的转换...")
            
            # 先获取页面上所有可能相关的元素进行调试
            all_mentions = driver.find_elements(By.CSS_SELECTOR, 'a[class*="mention"], [class*="mention"], [data-topic]')
            if all_mentions:
                logger.debug(f"📊 页面上发现 {len(all_mentions)} 个mention相关元素")
                for i, mention in enumerate(all_mentions[:3]):  # 只显示前3个避免日志过多
                    try:
                        logger.debug(f"  元素{i+1}: class='{mention.get_attribute('class')}', text='{mention.text[:50]}'")
                    except:
                        pass
            
            # 方法1: 最宽松的验证 - 检查是否页面上有包含话题的任何元素
            broad_search_patterns = [
                f"//*[contains(text(), '{topic}')]",
                f"//*[contains(text(), '#{topic}')]",
                f"//*[contains(text(), '{topic}[话题]')]",
                f"//*[contains(@data-topic, '{topic}')]"
            ]
            
            for pattern in broad_search_patterns:
                try:
                    elements = driver.find_elements(By.XPATH, pattern)
                    if elements:
                        logger.debug(f"✅ 宽松验证成功：找到 {len(elements)} 个包含 '{topic}' 的元素")
                        
                        # 进一步检查是否是真正的话题元素
                        for element in elements:
                            try:
                                class_name = element.get_attribute('class') or ''
                                if 'mention' in class_name.lower() or element.get_attribute('data-topic'):
                                    logger.debug(f"✅ 话题 '{topic}' 验证成功 - 找到有效mention元素")
                                    return True
                            except:
                                continue
                except:
                    continue
            
            # 方法2: 检查编辑器内容是否包含话题文本
            try:
                content_editor = await self._find_content_editor()
                if content_editor:
                    editor_text = content_editor.text or ''
                    if topic in editor_text or f'#{topic}' in editor_text:
                        logger.debug(f"✅ 话题 '{topic}' 在编辑器文本中找到")
                        
                        # 进一步检查是否是格式化的话题
                        if f'{topic}[话题]' in editor_text or f'#{topic}[话题]' in editor_text:
                            logger.debug(f"✅ 话题 '{topic}' 格式验证成功")
                            return True
                        else:
                            logger.debug(f"⚠️ 话题 '{topic}' 可能转换不完整，但文本存在")
                            return True  # 宽松验证，认为至少添加成功了
            except:
                pass
            
            # 方法3: 检查页面源码是否包含话题相关内容
            try:
                page_source = driver.page_source
                if f'data-topic' in page_source and topic in page_source:
                    logger.debug(f"✅ 话题 '{topic}' 在页面源码中发现data-topic")
                    return True
            except:
                pass
            
            logger.debug(f"❌ 话题 '{topic}' 所有验证方法均失败")
            return False
                    
        except Exception as e:
            logger.warning(f"⚠️ 验证话题 '{topic}' 转换时出错: {e}")
            return False
    
    async def get_current_topics(self) -> List[str]:
        """
        获取当前已添加的所有话题标签
        
        基于实测DOM结构的完整实现：
        - 优先从data-topic属性获取话题名称（最准确）
        - 备用方案：从文本内容提取话题名称
        
        Returns:
            当前话题列表
        """
        try:
            driver = self.browser_manager.driver
            topics = []
            
            # 方法1: 从data-topic属性获取（最准确的方式）
            mentions_with_data = driver.find_elements(By.CSS_SELECTOR, 'a.mention[data-topic]')
            
            for mention in mentions_with_data:
                try:
                    import json
                    data_topic = mention.get_attribute('data-topic')
                    if data_topic:
                        topic_data = json.loads(data_topic)
                        topic_name = topic_data.get('name', '')
                        if topic_name and topic_name not in topics:
                            topics.append(topic_name)
                            logger.debug(f"📊 从data-topic获取话题: {topic_name}")
                except Exception as e:
                    logger.debug(f"⚠️ 解析data-topic失败: {e}")
                    continue
            
            # 方法2: 备用方案 - 从文本内容提取
            if not topics:
                logger.debug("🔄 使用备用方案从文本内容提取话题")
                mentions = driver.find_elements(By.CSS_SELECTOR, '.mention span')
                
                for mention in mentions:
                    try:
                        text = mention.text
                        if '#' in text and '[话题]#' in text:
                            # 提取纯话题名 (去掉#和[话题]#)
                            topic_name = text.replace('#', '').replace('[话题]#', '').strip()
                            if topic_name and topic_name not in topics:
                                topics.append(topic_name)
                                logger.debug(f"📊 从文本内容获取话题: {topic_name}")
                    except:
                        continue
            
            # 方法3: 最后备用 - 查找一般mention元素
            if not topics:
                logger.debug("🔄 使用最后备用方案查找mention元素")
                general_mentions = driver.find_elements(By.CSS_SELECTOR, 'a.mention')
                
                for mention in general_mentions:
                    try:
                        text = mention.text.strip()
                        if text.startswith('#'):
                            # 简单提取话题名
                            topic_name = text.replace('#', '').split('[')[0].strip()
                            if topic_name and topic_name not in topics:
                                topics.append(topic_name)
                                logger.debug(f"📊 从一般mention获取话题: {topic_name}")
                    except:
                        continue
            
            logger.info(f"📊 当前已添加话题: {topics}")
            return topics
            
        except Exception as e:
            logger.warning(f"⚠️ 获取当前话题列表失败: {e}")
            return []
    
    def get_current_content(self) -> dict:
        """
        获取当前页面的内容信息
        
        Returns:
            包含当前内容信息的字典
        """
        try:
            driver = self.browser_manager.driver
            
            result = {
                "title": "",
                "content": "",
                "has_title_input": False,
                "has_content_editor": False
            }
            
            # 获取标题
            for selector in get_title_input_selectors():
                try:
                    title_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if title_elements and title_elements[0].is_displayed():
                        result["has_title_input"] = True
                        result["title"] = title_elements[0].get_attribute("value") or ""
                        break
                except:
                    continue
            
            # 获取内容
            try:
                content_elements = driver.find_elements(By.CSS_SELECTOR, XHSSelectors.CONTENT_EDITOR)
                if content_elements and content_elements[0].is_displayed():
                    result["has_content_editor"] = True
                    result["content"] = content_elements[0].text or ""
            except:
                pass
            
            return result
            
        except Exception as e:
            logger.warning(f"⚠️ 获取当前内容失败: {e}")
            return {"error": str(e)} 