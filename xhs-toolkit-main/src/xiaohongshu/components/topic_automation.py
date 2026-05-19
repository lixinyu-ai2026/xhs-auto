"""
小红书话题自动化实现模块

基于实测验证的完整话题自动化功能实现
参考文档：小红书话题标签自动化实现方案.md
"""

import asyncio
import re
from typing import List, Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains

from ..interfaces import IBrowserManager
from ..constants import XHSConfig
from ...core.exceptions import PublishError, handle_exception
from ...utils.logger import get_logger

logger = get_logger(__name__)


class XHSTopicAutomation:
    """小红书话题自动化处理器"""
    
    def __init__(self, browser_manager: IBrowserManager):
        """
        初始化话题自动化处理器
        
        Args:
            browser_manager: 浏览器管理器
        """
        self.browser_manager = browser_manager
    
    async def add_single_topic(self, topic_text: str) -> bool:
        """
        添加单个话题标签
        
        基于实测验证的工作流程：
        1. 定位编辑器
        2. 输入#话题名
        3. 按回车键触发转换
        4. 验证转换成功
        
        Args:
            topic_text: 话题文本
            
        Returns:
            添加是否成功
        """
        try:
            logger.info(f"🏷️ 添加话题: {topic_text}")
            
            # 1. 定位小红书编辑器
            editor = await self._find_content_editor()
            if not editor:
                logger.error("❌ 未找到内容编辑器")
                return False
            
            # 2. 移动到编辑器末尾
            editor.click()
            await asyncio.sleep(0.2)
            editor.send_keys(Keys.END)
            
            # 3. 输入话题文本 (确保有#号)
            if not topic_text.startswith('#'):
                topic_text = f'#{topic_text}'
            
            editor.send_keys(topic_text)
            await asyncio.sleep(0.3)
            
            # 4. 按回车键触发自动转换 (关键步骤!)
            editor.send_keys(Keys.ENTER)
            await asyncio.sleep(0.5)  # 等待转换完成
            
            # 5. 验证是否生成了mention元素
            if await self.verify_topic_conversion(topic_text.replace('#', '')):
                logger.info(f"✅ 话题标签 '{topic_text}' 添加成功")
                return True
            else:
                logger.warning(f"⚠️ 话题标签 '{topic_text}' 转换失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 添加话题标签失败: {e}")
            return False
    
    async def add_multiple_topics(self, topics_list: List[str]) -> int:
        """
        批量添加多个话题标签
        
        Args:
            topics_list: 话题列表
            
        Returns:
            成功添加的话题数量
        """
        success_count = 0
        
        logger.info(f"🚀 开始批量添加 {len(topics_list)} 个话题")
        
        for i, topic in enumerate(topics_list):
            logger.info(f"正在添加第 {i+1}/{len(topics_list)} 个话题: {topic}")
            
            if await self.add_single_topic(topic):
                success_count += 1
                await asyncio.sleep(0.3)  # 避免操作过快
            else:
                logger.warning(f"跳过话题: {topic}")
        
        logger.info(f"✅ 批量添加完成: {success_count}/{len(topics_list)} 个话题成功")
        return success_count
    
    async def verify_topic_conversion(self, topic_text: str) -> bool:
        """
        验证话题是否正确转换为标签
        
        检查DOM中是否生成了正确的mention元素结构
        
        Args:
            topic_text: 话题文本（不含#号）
            
        Returns:
            转换是否成功
        """
        try:
            driver = self.browser_manager.driver
            
            # 查找包含指定话题的mention元素
            # 小红书真正的话题标签格式：#话题名[话题]#
            mention_xpath = f"//a[@class='mention']//span[contains(text(), '{topic_text}[话题]#')]"
            mention_elements = driver.find_elements(By.XPATH, mention_xpath)
            
            if mention_elements:
                logger.debug(f"✅ 话题 '{topic_text}' 转换验证成功")
                return True
            else:
                # 备用验证方法
                backup_xpath = f"//a[@class='mention'][contains(text(), '{topic_text}')]"
                backup_elements = driver.find_elements(By.XPATH, backup_xpath)
                
                if backup_elements:
                    logger.debug(f"✅ 话题 '{topic_text}' 备用验证成功")
                    return True
                else:
                    logger.debug(f"❌ 话题 '{topic_text}' 转换验证失败")
                    return False
                    
        except Exception as e:
            logger.warning(f"⚠️ 验证话题转换时出错: {e}")
            return False
    
    async def get_current_topics(self) -> List[str]:
        """
        获取当前已添加的所有话题标签
        
        Returns:
            话题列表
        """
        try:
            driver = self.browser_manager.driver
            mentions = driver.find_elements(By.CSS_SELECTOR, '.mention span')
            topics = []
            
            for mention in mentions:
                try:
                    text = mention.text
                    if '[话题]#' in text:
                        # 提取纯话题名 (去掉#和[话题]#)
                        topic_name = text.replace('#', '').replace('[话题]#', '')
                        if topic_name:
                            topics.append(topic_name)
                except:
                    continue
            
            logger.info(f"📊 当前话题列表: {topics}")
            return topics
            
        except Exception as e:
            logger.warning(f"⚠️ 获取话题列表失败: {e}")
            return []
    
    async def remove_topic(self, topic_text: str) -> bool:
        """
        删除指定话题标签
        
        Args:
            topic_text: 要删除的话题文本
            
        Returns:
            删除是否成功
        """
        try:
            driver = self.browser_manager.driver
            
            # 找到要删除的话题元素
            mention_xpath = f"//a[@class='mention']//span[contains(text(), '{topic_text}[话题]#')]"
            mention_elements = driver.find_elements(By.XPATH, mention_xpath)
            
            if mention_elements:
                mention = mention_elements[0]
                # 选中并删除
                mention.click()
                mention.send_keys(Keys.DELETE)
                
                logger.info(f"✅ 话题 '{topic_text}' 删除成功")
                return True
            else:
                logger.warning(f"⚠️ 未找到话题 '{topic_text}'")
                return False
                
        except Exception as e:
            logger.error(f"❌ 删除话题失败: {e}")
            return False
    
    async def smart_topic_input(self, content_text: str, suggested_topics: List[str]) -> int:
        """
        智能话题建议和输入
        
        分析内容相关性，智能推荐并添加话题
        
        Args:
            content_text: 笔记内容
            suggested_topics: 候选话题池
            
        Returns:
            成功添加的话题数量
        """
        # 分析内容，智能推荐相关话题
        relevant_topics = self._analyze_content_topics(content_text, suggested_topics)
        
        if relevant_topics:
            logger.info(f"🤖 智能推荐话题: {relevant_topics}")
            return await self.add_multiple_topics(relevant_topics)
        else:
            logger.info("📝 未找到相关话题推荐")
            return 0
    
    def _analyze_content_topics(self, content: str, topic_pool: List[str]) -> List[str]:
        """
        分析内容相关性，推荐话题
        
        简单关键词匹配算法，可扩展为更复杂的NLP分析
        
        Args:
            content: 笔记内容
            topic_pool: 候选话题池
            
        Returns:
            相关话题列表
        """
        relevant = []
        content_lower = content.lower()
        
        for topic in topic_pool:
            # 简单关键词匹配
            if any(keyword in content_lower for keyword in topic.lower().split()):
                relevant.append(topic)
        
        # 限制最多5个话题，避免过度标记
        return relevant[:5]
    
    async def _find_content_editor(self):
        """
        查找内容编辑器
        
        Returns:
            编辑器元素，如果未找到返回None
        """
        try:
            driver = self.browser_manager.driver
            wait = WebDriverWait(driver, XHSConfig.DEFAULT_WAIT_TIME)
            
            # 尝试查找小红书内容编辑器
            editor = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.ql-editor'))
            )
            
            if editor and editor.is_enabled():
                logger.debug("✅ 找到内容编辑器")
                return editor
            else:
                logger.warning("⚠️ 内容编辑器不可用")
                return None
                
        except TimeoutException:
            logger.error("❌ 查找内容编辑器超时")
            return None
        except Exception as e:
            logger.error(f"❌ 查找内容编辑器失败: {e}")
            return None


class AdvancedXHSTopicAutomation(XHSTopicAutomation):
    """高级话题自动化功能"""
    
    async def batch_process_with_retry(self, topics: List[str], max_retries: int = 2) -> Dict[str, Any]:
        """
        带重试机制的批量话题处理
        
        Args:
            topics: 话题列表
            max_retries: 最大重试次数
            
        Returns:
            处理结果详情
        """
        results = {
            "total": len(topics),
            "success": 0,
            "failed": [],
            "retried": []
        }
        
        for topic in topics:
            success = False
            retry_count = 0
            
            while not success and retry_count <= max_retries:
                success = await self.add_single_topic(topic)
                
                if not success:
                    retry_count += 1
                    if retry_count <= max_retries:
                        logger.info(f"🔄 重试话题 '{topic}' (第{retry_count}次)")
                        results["retried"].append(f"{topic}(重试{retry_count}次)")
                        await asyncio.sleep(1)  # 重试间隔
            
            if success:
                results["success"] += 1
            else:
                results["failed"].append(topic)
        
        logger.info(f"📊 批量处理完成: {results}")
        return results
    
    async def validate_all_topics(self) -> Dict[str, bool]:
        """
        验证所有已添加话题的有效性
        
        Returns:
            话题验证结果字典
        """
        current_topics = await self.get_current_topics()
        validation_results = {}
        
        for topic in current_topics:
            is_valid = await self.verify_topic_conversion(topic)
            validation_results[topic] = is_valid
            
        logger.info(f"✅ 话题验证完成: {validation_results}")
        return validation_results


class XHSEmojiHelper:
    """小红书emoji处理工具类"""
    
    def __init__(self, browser_manager: IBrowserManager):
        """
        初始化emoji处理工具
        
        Args:
            browser_manager: 浏览器管理器
        """
        self.browser_manager = browser_manager
        
    async def insert_full_title_with_emoji(self, title_element, title_text: str) -> bool:
        """
        使用多种方法尝试插入带有emoji的完整标题
        
        Args:
            title_element: 标题输入元素
            title_text: 完整标题文本（带emoji）
            
        Returns:
            是否成功
        """
        driver = self.browser_manager.driver
        
        try:
            # 方法1: 使用JavaScript直接设置value/innerHTML
            script1 = """
            var element = arguments[0];
            var text = arguments[1];
            
            // 检测元素类型并设置相应属性
            if (element.tagName.toLowerCase() === 'input' || element.tagName.toLowerCase() === 'textarea') {
                element.value = text;
            } else if (element.contentEditable === 'true' || element.contentEditable === true) {
                element.innerHTML = text;
            } else {
                element.textContent = text;
            }
            
            // 触发事件
            ['input', 'change'].forEach(function(event) {
                var e = new Event(event, { bubbles: true });
                element.dispatchEvent(e);
            });
            """
            driver.execute_script(script1, title_element, title_text)
            
            # 方法2: 尝试使用剪贴板API
            script2 = """
            var element = arguments[0];
            var text = arguments[1];
            
            // 尝试使用剪贴板API插入文本
            element.focus();
            
            const textAreaValue = text;
            
            // 创建一个辅助的文本区域元素
            const textArea = document.createElement('textarea');
            textArea.value = textAreaValue;
            document.body.appendChild(textArea);
            textArea.select();
            
            // 尝试复制文本到剪贴板
            const successful = document.execCommand('copy');
            
            // 粘贴剪贴板内容
            element.focus();
            document.execCommand('paste');
            
            // 移除临时文本区域
            document.body.removeChild(textArea);
            
            // 触发输入事件
            ['input', 'change'].forEach(function(event) {
                var e = new Event(event, { bubbles: true });
                element.dispatchEvent(e);
            });
            """
            driver.execute_script(script2, title_element, title_text)
            
            # 方法3: 使用模拟粘贴事件
            script3 = """
            var element = arguments[0];
            var text = arguments[1];
            
            // 直接模拟粘贴事件
            element.focus();
            
            // 在input/change事件之前创建一个新的粘贴事件
            var pasteEvent = new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: new DataTransfer()
            });
            
            // 设置剪贴板数据
            Object.defineProperty(pasteEvent.clipboardData, 'getData', {
                value: function() {
                    return text;
                }
            });
            
            // 分派事件
            element.dispatchEvent(pasteEvent);
            """
            driver.execute_script(script3, title_element, title_text)
            
            logger.info("✅ 多方法尝试插入带emoji标题完成")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ 插入带emoji标题失败: {e}")
            return False
    
    async def insert_full_content_with_emoji(self, content_element, content_text: str) -> bool:
        """
        使用多种方法尝试插入带有emoji的完整内容
        
        Args:
            content_element: 内容编辑器元素
            content_text: 完整内容文本（带emoji）
            
        Returns:
            是否成功
        """
        driver = self.browser_manager.driver
        
        try:
            # 富文本编辑器通常使用innerHTML
            script = """
            var editor = arguments[0];
            var content = arguments[1];
            
            // 处理换行符
            content = content.replace(/\\n/g, '<br>');
            
            // 设置内容
            if (editor.contentEditable === 'true' || editor.contentEditable === true) {
                editor.innerHTML = content;
            } else {
                editor.textContent = content;
            }
            
            // 触发事件
            ['input', 'change'].forEach(function(event) {
                var e = new Event(event, { bubbles: true });
                editor.dispatchEvent(e);
            });
            """
            
            driver.execute_script(script, content_element, content_text)
            logger.info("✅ 插入完整内容成功")
            return True
        
        except Exception as e:
            logger.warning(f"⚠️ 插入完整内容失败: {e}")
            return False 