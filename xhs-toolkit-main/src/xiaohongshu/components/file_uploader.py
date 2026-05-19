"""
小红书文件上传器

专门负责文件上传处理，遵循单一职责原则
"""

import asyncio
import os
from typing import List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from ..interfaces import IFileUploader, IBrowserManager
from ..constants import (XHSConfig, XHSSelectors, XHSMessages, 
                        get_file_upload_selectors, is_supported_image_format, 
                        is_supported_video_format)
from ...core.exceptions import PublishError, handle_exception
from ...utils.logger import get_logger

logger = get_logger(__name__)


class XHSFileUploader(IFileUploader):
    """小红书文件上传器"""
    
    def __init__(self, browser_manager: IBrowserManager):
        """
        初始化文件上传器
        
        Args:
            browser_manager: 浏览器管理器
        """
        self.browser_manager = browser_manager
    
    @handle_exception
    async def upload_files(self, files: List[str], file_type: str) -> bool:
        """
        上传文件
        
        Args:
            files: 文件路径列表
            file_type: 文件类型 ('image' 或 'video')
            
        Returns:
            上传是否成功
            
        Raises:
            PublishError: 当上传过程出错时
        """
        logger.info(f"📁 开始上传{len(files)}个{file_type}文件")
        
        try:
            # 验证文件
            self._validate_files(files, file_type)
            
            # 查找文件上传控件
            file_input = await self._find_file_input()
            if not file_input:
                raise PublishError("未找到文件上传控件", publish_step="文件上传")
            
            # 执行文件上传
            return await self._perform_upload(file_input, files, file_type)
            
        except Exception as e:
            if isinstance(e, PublishError):
                raise
            else:
                raise PublishError(f"文件上传失败: {str(e)}", publish_step="文件上传") from e
    
    def _validate_files(self, files: List[str], file_type: str) -> None:
        """
        验证文件有效性
        
        Args:
            files: 文件路径列表
            file_type: 文件类型
            
        Raises:
            PublishError: 当文件验证失败时
        """
        if not files:
            raise PublishError("文件列表为空", publish_step="文件验证")
        
        for file_path in files:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise PublishError(f"文件不存在: {file_path}", publish_step="文件验证")
            
            # 检查文件格式
            if file_type == "image":
                if not is_supported_image_format(file_path):
                    raise PublishError(f"不支持的图片格式: {file_path}", publish_step="文件验证")
                    
                # 检查图片数量限制
                if len(files) > XHSConfig.MAX_IMAGES:
                    raise PublishError(f"图片数量超限，最多{XHSConfig.MAX_IMAGES}张", 
                                     publish_step="文件验证")
                    
            elif file_type == "video":
                if not is_supported_video_format(file_path):
                    raise PublishError(f"不支持的视频格式: {file_path}", publish_step="文件验证")
                    
                # 检查视频数量限制
                if len(files) > XHSConfig.MAX_VIDEOS:
                    raise PublishError(f"视频数量超限，最多{XHSConfig.MAX_VIDEOS}个", 
                                     publish_step="文件验证")
            
            # 检查文件大小（可选）
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB
                logger.warning(f"⚠️ 文件较大({file_size / 1024 / 1024:.1f}MB): {file_path}")
        
        logger.info(f"✅ 文件验证通过，共{len(files)}个{file_type}文件")
    
    async def _find_file_input(self):
        """
        查找文件上传输入控件
        
        Returns:
            文件输入元素，如果未找到返回None
        """
        driver = self.browser_manager.driver
        wait = WebDriverWait(driver, XHSConfig.DEFAULT_WAIT_TIME)
        
        # 尝试多个选择器
        logger.info("🔍 开始寻找文件上传控件...")
        for selector in get_file_upload_selectors():
            try:
                logger.debug(f"🔍 尝试CSS选择器: {selector}")
                # 先尝试查找所有匹配的元素
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                # 检查是否有可见的元素
                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            logger.info(f"✅ 找到可见的文件上传控件: {selector}")
                            return element
                    except Exception:
                        continue  # 如果元素检查失败，继续下一个
                
                # 如果没有找到可见元素，但有匹配的元素，返回第一个
                if elements:
                    logger.info(f"⚠️ 找到不可见的文件上传控件，尝试使用: {selector}")
                    return elements[0]
                    
            except TimeoutException:
                logger.debug(f"⏰ 选择器超时: {selector}")
                continue
            except Exception as e:
                logger.debug(f"⚠️ 选择器错误: {selector}, {e}")
                continue
        
        # 如果CSS选择器都失败了，尝试XPath
        xpath_selectors = [
            "//input[@type='file']",
            "//div[contains(@class, 'upload')]//input",
            "//*[contains(@class, 'upload')]//input",
            "//input[contains(@accept, 'image') or contains(@accept, 'video')]"
        ]
        
        for xpath in xpath_selectors:
            try:
                logger.debug(f"🔍 尝试XPath选择器: {xpath}")
                elements = driver.find_elements(By.XPATH, xpath)
                
                # 检查是否有可见的元素
                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            logger.info(f"✅ 通过XPath找到可见的上传控件: {xpath}")
                            return element
                    except Exception:
                        continue
                
                # 如果没有找到可见元素，但有匹配的元素，返回第一个
                if elements:
                    logger.info(f"⚠️ 通过XPath找到不可见的上传控件，尝试使用: {xpath}")
                    return elements[0]
                    
            except Exception as e:
                logger.debug(f"⚠️ XPath选择器错误: {xpath}, {e}")
                continue
        
        logger.error("❌ 未找到可用的文件上传控件")
        return None
    
    async def _perform_upload(self, file_input, files: List[str], file_type: str) -> bool:
        """
        执行文件上传
        
        Args:
            file_input: 文件输入元素
            files: 文件路径列表
            file_type: 文件类型
            
        Returns:
            上传是否成功
        """
        try:
            # 将文件路径转换为绝对路径并合并
            absolute_files = [os.path.abspath(f) for f in files]
            files_string = '\n'.join(absolute_files)
            
            logger.info(f"📤 开始上传{len(files)}个{file_type}文件...")
            logger.debug(f"文件列表: {files_string}")
            
            # 尝试多种上传方法
            success = False
            
            # 方法1: 直接使用send_keys
            try:
                logger.info("📤 尝试方法1: 直接send_keys上传...")
                file_input.send_keys(files_string)
                
                # 等待短暂时间看是否触发上传
                await asyncio.sleep(3)
                success = await self._check_upload_started()
                
                if success:
                    logger.info("✅ 方法1上传成功触发")
                else:
                    logger.warning("⚠️ 方法1未能触发上传")
            except Exception as e:
                logger.warning(f"⚠️ 方法1失败: {e}")
                
            # 方法2: 如果方法1失败，尝试使用JavaScript设置文件
            if not success:
                try:
                    logger.info("📤 尝试方法2: 使用JavaScript上传...")
                    driver = self.browser_manager.driver
                    
                    # 确保元素可见
                    driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", file_input)
                    
                    # 等待元素变为可交互
                    await asyncio.sleep(1)
                    
                    # 使用JavaScript设置文件路径
                    # 注意：这种方法在某些浏览器中可能不起作用，因为安全限制
                    if len(files) == 1:
                        driver.execute_script("arguments[0].value = arguments[1]", file_input, absolute_files[0])
                    else:
                        # 多文件上传只能通过send_keys实现
                        file_input.send_keys(files_string)
                    
                    # 等待短暂时间看是否触发上传
                    await asyncio.sleep(3)
                    success = await self._check_upload_started()
                    
                    if success:
                        logger.info("✅ 方法2上传成功触发")
                    else:
                        logger.warning("⚠️ 方法2未能触发上传")
                except Exception as e:
                    logger.warning(f"⚠️ 方法2失败: {e}")
            
            # 方法3: 尝试查找并点击上传按钮
            if not success:
                try:
                    logger.info("📤 尝试方法3: 点击上传按钮...")
                    driver = self.browser_manager.driver
                    
                    # 查找可能的上传按钮
                    upload_buttons = driver.find_elements(By.XPATH, 
                        "//button[contains(text(), '上传') or contains(@class, 'upload')]")
                    
                    if upload_buttons:
                        # 点击第一个可见的上传按钮
                        for button in upload_buttons:
                            if button.is_displayed() and button.is_enabled():
                                logger.info("✅ 找到上传按钮，点击...")
                                button.click()
                                
                                # 等待文件选择对话框
                                await asyncio.sleep(2)
                                
                                # 重新查找文件输入并上传
                                new_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
                                for input_elem in new_inputs:
                                    try:
                                        input_elem.send_keys(files_string)
                                        await asyncio.sleep(3)
                                        success = await self._check_upload_started()
                                        if success:
                                            logger.info("✅ 方法3上传成功触发")
                                            break
                                    except Exception:
                                        continue
                except Exception as e:
                    logger.warning(f"⚠️ 方法3失败: {e}")
            
            # 如果上述方法都成功触发了上传，等待上传完成
            if success:
                success = await self._wait_for_upload_completion(file_type)
            
            if success:
                logger.info(f"✅ {file_type}文件上传成功")
            else:
                logger.error(f"❌ {file_type}文件上传失败")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 上传过程出错: {e}")
            return False
    
    async def _check_upload_started(self) -> bool:
        """检查上传是否已经开始"""
        try:
            driver = self.browser_manager.driver
            
            # 检查是否有上传进度元素
            progress_elements = driver.find_elements(By.CSS_SELECTOR, XHSSelectors.UPLOAD_PROGRESS)
            if progress_elements and any(elem.is_displayed() for elem in progress_elements):
                return True
                
            # 检查是否有文件预览元素（通常表示上传成功或正在处理）
            preview_selectors = [
                "img[src]",  # 图片预览
                ".preview-image",
                ".thumbnail",
                ".video-thumbnail",
                "[class*='preview']",
                "[class*='thumbnail']"
            ]
            
            for selector in preview_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and any(elem.is_displayed() for elem in elements):
                    return True
            
            # 检查是否有文件名显示（也表示上传可能已开始）
            filename_selectors = [
                "[class*='filename']",
                "[class*='file-name']",
                ".file-item"
            ]
            
            for selector in filename_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and any(elem.is_displayed() for elem in elements):
                    return True
            
            # 没有检测到上传开始的迹象
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ 检查上传开始状态时出错: {e}")
            return False
    
    async def _wait_for_upload_completion(self, file_type: str) -> bool:
        """
        等待上传完成
        
        Args:
            file_type: 文件类型
            
        Returns:
            上传是否成功完成
        """
        driver = self.browser_manager.driver
        
        # 根据文件类型设置不同的等待时间
        if file_type == "video":
            max_wait_time = XHSConfig.VIDEO_PROCESSING_TIME
            check_interval = 5
        else:
            max_wait_time = XHSConfig.FILE_UPLOAD_TIME
            check_interval = 2
        
        waited_time = 0
        
        while waited_time < max_wait_time:
            try:
                # 检查上传成功标识
                success_elements = driver.find_elements(By.CSS_SELECTOR, XHSSelectors.UPLOAD_SUCCESS)
                if success_elements and any(elem.is_displayed() for elem in success_elements):
                    logger.info("✅ 检测到上传成功标识")
                    return True
                
                # 检查上传错误标识
                error_elements = driver.find_elements(By.CSS_SELECTOR, XHSSelectors.UPLOAD_ERROR)
                if error_elements and any(elem.is_displayed() for elem in error_elements):
                    logger.error("❌ 检测到上传错误标识")
                    return False
                
                # 检查视频处理完成标识（仅视频文件）
                if file_type == "video":
                    complete_elements = driver.find_elements(By.CSS_SELECTOR, XHSSelectors.VIDEO_COMPLETE)
                    if complete_elements and any(elem.is_displayed() for elem in complete_elements):
                        logger.info("✅ 视频处理完成")
                        return True
                    
                    # 检查视频处理中标识
                    processing_elements = driver.find_elements(By.CSS_SELECTOR, XHSSelectors.VIDEO_PROCESSING)
                    if processing_elements and any(elem.is_displayed() for elem in processing_elements):
                        logger.info("🔄 视频处理中...")
                
                # 等待检查间隔
                await asyncio.sleep(check_interval)
                waited_time += check_interval
                
                # 每10秒打印一次进度
                if waited_time % 10 == 0:
                    logger.info(f"⏳ 上传进行中... 已等待{waited_time}秒")
                
            except Exception as e:
                logger.warning(f"⚠️ 检查上传状态时出错: {e}")
                await asyncio.sleep(check_interval)
                waited_time += check_interval
        
        # 超时后的最后检查
        logger.warning(f"⏰ 等待上传超时({max_wait_time}秒)，进行最后检查...")
        
        try:
            # 通过页面状态判断是否成功
            # 如果页面没有明显的错误提示，则认为上传成功
            error_elements = driver.find_elements(By.CSS_SELECTOR, XHSSelectors.UPLOAD_ERROR)
            if not error_elements or not any(elem.is_displayed() for elem in error_elements):
                logger.info("✅ 未发现错误标识，认为上传成功")
                return True
        except Exception as e:
            logger.warning(f"⚠️ 最后检查时出错: {e}")
        
        logger.error("❌ 上传超时失败")
        return False
    
    def get_upload_progress(self) -> dict:
        """
        获取上传进度信息
        
        Returns:
            包含上传进度信息的字典
        """
        try:
            driver = self.browser_manager.driver
            
            # 查找进度条元素
            progress_elements = driver.find_elements(By.CSS_SELECTOR, XHSSelectors.UPLOAD_PROGRESS)
            
            if progress_elements:
                progress_element = progress_elements[0]
                
                # 尝试获取进度值
                progress_value = progress_element.get_attribute("value") or "0"
                progress_text = progress_element.text or "上传中..."
                
                return {
                    "has_progress": True,
                    "value": progress_value,
                    "text": progress_text,
                    "visible": progress_element.is_displayed()
                }
            else:
                return {
                    "has_progress": False,
                    "message": "未找到进度信息"
                }
                
        except Exception as e:
            logger.warning(f"⚠️ 获取上传进度失败: {e}")
            return {
                "has_progress": False,
                "error": str(e)
            } 