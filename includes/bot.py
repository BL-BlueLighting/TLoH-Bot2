"""
Bot 核心类 - 处理 WebSocket 连接和事件转发
"""

import asyncio
import json
import logging
from typing import Dict, Callable, Any, List, Tuple
import websockets
from dataclasses import dataclass
from datetime import datetime

from .models import MessageInfo, EventData
from .eventers import EventHandler, Receive#type:ignore

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="TIME: %(asctime)s | %(levelname)s | %(message)s"
)

@dataclass
class ApiCall:
    """API 调用请求"""
    action: str
    params: Dict[str, Any]
    echo: str | None = None


class Bot:
    """OneBot 11 WebSocket 客户端 Bot 类"""
    
    def __init__(self, ws_url: str, self_id: int = 0):
        """
        初始化 Bot
        
        Args:
            ws_url: OneBot 实现端的 WebSocket 服务地址
            self_id: 机器人 QQ 号（可选）
        """
        self.ws_url = ws_url
        self.self_id = self_id
        self.connected = False
        self.message_handlers: List[EventHandler] = []
        self.notice_handlers: List[EventHandler] = []
        self.request_handlers: List[EventHandler] = []
        self.meta_event_handlers: List[EventHandler] = []
        self._echo_responses: Dict[str, asyncio.Future] = {}
        self._echo_counter = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self.websocket = None  # 保存主 WebSocket 连接
        
    def register_message_handler(self, handler: EventHandler):
        """注册消息处理器"""
        self.message_handlers.append(handler)
        
    def register_notice_handler(self, handler: EventHandler):
        """注册通知处理器"""
        self.notice_handlers.append(handler)
        
    def register_request_handler(self, handler: EventHandler):
        """注册请求处理器"""
        self.request_handlers.append(handler)
        
    def register_meta_event_handler(self, handler: EventHandler):
        """注册元事件处理器"""
        self.meta_event_handlers.append(handler)
    
    async def _connect(self):
        """建立 WebSocket 连接"""
        try:
            # 保存事件循环引用
            self._loop = asyncio.get_event_loop()
            
            async with websockets.connect(self.ws_url) as websocket:
                self.websocket = websocket  # 保存 WebSocket 连接
                self.connected = True
                logger.info(f"已连接到 {self.ws_url}")
                
                # 创建接收消息任务
                receive_task = asyncio.create_task(
                    self._receive_loop(websocket)
                )
                
                try:
                    await receive_task
                except asyncio.CancelledError:
                    pass
                finally:
                    self.connected = False
                    logger.info("已断开连接")
                    
        except Exception as e:
            logger.error(f"连接错误: {e}")
            self.connected = False
            # 重连逻辑
            await asyncio.sleep(5)
            await self._connect()
    
    async def _receive_loop(self, websocket):
        """接收并处理 WebSocket 消息"""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_event(data)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 解析错误: {e}")
                except Exception as e:
                    logger.error(f"处理事件出错: {e}")
        except asyncio.CancelledError:
            pass
    
    async def _handle_event(self, data: Dict[str, Any]):
        """处理接收到的事件"""
        post_type = data.get("post_type")
        
        if post_type == "message":
            await self._handle_message(data)
        elif post_type == "notice":
            await self._handle_notice(data)
        elif post_type == "request":
            await self._handle_request(data)
        elif post_type == "meta_event":
            await self._handle_meta_event(data)
        else:
            # 处理 API 响应
            echo = data.get("echo")
            if echo and echo in self._echo_responses:
                future = self._echo_responses.pop(echo)
                if not future.done():
                    future.set_result(data)
    
    async def _handle_message(self, data: Dict[str, Any]):
        """处理消息事件"""
        info = MessageInfo.from_event(data, self.self_id)
        
        for handler in self.message_handlers:
            if handler.should_process(info):
                try:
                    await asyncio.to_thread(handler.execute, self, info)
                except Exception as e:
                    logger.error(f"消息处理器执行出错: {e}")
    
    async def _handle_notice(self, data: Dict[str, Any]):
        """处理通知事件"""
        notice_type = data.get("notice_type")
        logger.info(f"通知事件: {notice_type}")
        
        for handler in self.notice_handlers:
            try:
                await asyncio.to_thread(handler.execute, self, data)
            except Exception as e:
                logger.error(f"通知处理器执行出错: {e}")
    
    async def _handle_request(self, data: Dict[str, Any]):
        """处理请求事件"""
        request_type = data.get("request_type")
        logger.info(f"请求事件: {request_type}")
        
        for handler in self.request_handlers:
            try:
                await asyncio.to_thread(handler.execute, self, data)
            except Exception as e:
                logger.error(f"请求处理器执行出错: {e}")
    
    async def _handle_meta_event(self, data: Dict[str, Any]):
        """处理元事件"""
        meta_event_type = data.get("meta_event_type")
        logger.info(f"元事件: {meta_event_type}")
        
        for handler in self.meta_event_handlers:
            try:
                await asyncio.to_thread(handler.execute, self, data)
            except Exception as e:
                logger.error(f"元事件处理器执行出错: {e}")
    
    async def _send_api_call(self, action: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """发送 API 调用请求"""

        if type(params) == None:
            logger.warning("参数列表为空")
            return {"status":"failed", "retcode": -1}

        if not self.connected:
            logger.warning("未连接到 OneBot 实现")
            return {"status": "failed", "retcode": -1}
        
        params = params or {}
        self._echo_counter += 1
        echo = f"echo_{self._echo_counter}"
        
        request = {
            "action": action,
            "params": params,
            "echo": echo
        }
        
        future = asyncio.Future()
        self._echo_responses[echo] = future
        
        try:
            # 通过事件循环发送（在子线程中调用此方法时）
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在运行的事件循环中，需要通过线程池发送
                await self._ws_send_json(request, echo)
            else:
                await self._ws_send_json(request, echo)
            
            # 等待响应（带超时）
            response = await asyncio.wait_for(future, timeout=10.0)
            return response
        except asyncio.TimeoutError:
            logger.error(f"API 调用超时: {action}")
            return {"status": "failed", "retcode": -1}
        except Exception as e:
            logger.error(f"API 调用错误: {e}")
            return {"status": "failed", "retcode": -1}
        finally:
            self._echo_responses.pop(echo, None)
    
    async def _ws_send_json(self, data: Dict[str, Any], echo: str):
        """通过 WebSocket 发送 JSON 数据"""
        try:
            if self.websocket is not None:
                await self.websocket.send(json.dumps(data))
            else:
                logger.error(f"WebSocket 连接未建立或已关闭")
                if echo in self._echo_responses:
                    future = self._echo_responses[echo]
                    if not future.done():
                        future.set_exception(Exception("WebSocket 未连接"))
        except Exception as e:
            logger.error(f"WebSocket 发送失败: {e}")
            if echo in self._echo_responses:
                future = self._echo_responses[echo]
                if not future.done():
                    future.set_exception(e)
    
    def _call_api(self, action: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        调用 API 的通用方法（处理线程和事件循环问题）
        
        Args:
            action: API 动作名
            params: API 参数
        
        Returns:
            API 响应
        """
        if params is None:
            params = {}
        
        # 获取事件循环
        loop = self._loop
        if loop and loop.is_running():
            # 使用保存的事件循环
            future = asyncio.run_coroutine_threadsafe(
                self._send_api_call(action, params),
                loop
            )
            try:
                response = future.result(timeout=360)
            except Exception as e:
                logger.error(f"API 调用失败: {e}")
                response = {"status": "failed", "retcode": -1}
        else:
            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        self._send_api_call(action, params),
                        loop
                    )
                    response = future.result(timeout=10.0)
                else:
                    response = asyncio.run(self._send_api_call(action, params))
            except RuntimeError:
                response = {"status": "failed", "retcode": -1}
        
        return response
    
    def run(self):
        """启动 Bot（阻塞式）"""
        try:
            asyncio.run(self._connect())
        except KeyboardInterrupt:
            logger.info("正在关闭...")
    
    # ========== OneBot 11 API 接口 ==========
    
    def send_private_msg(self, user_id: int | None, message: str, auto_escape: bool = False) -> int:
        """发送私聊消息"""
        if user_id is None:
            return -1

        # 获取事件循环
        loop = self._loop
        if loop and loop.is_running():
            # 使用保存的事件循环发送
            future = asyncio.run_coroutine_threadsafe(
                self._send_api_call("send_private_msg", {
                    "user_id": user_id,
                    "message": message,
                    "auto_escape": auto_escape
                }),
                loop
            )
            response = future.result(timeout=360)
        else:
            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        self._send_api_call("send_private_msg", {
                            "user_id": user_id,
                            "message": message,
                            "auto_escape": auto_escape
                        }),
                        loop
                    )
                    response = future.result(timeout=360)
                else:
                    response = asyncio.run(self._send_api_call("send_private_msg", {
                        "user_id": user_id,
                        "message": message,
                        "auto_escape": auto_escape
                    }))
            except RuntimeError:
                response = {"status": "failed", "retcode": -1}
        
        return response.get("data", {}).get("message_id", -1)
    
    def send_group_msg(self, group_id: int | None, message: str, auto_escape: bool = False) -> int:
        """发送群聊消息"""
        if group_id is None:
            return -1

        # 获取事件循环
        loop = self._loop
        if loop and loop.is_running():
            # 使用保存的事件循环发送
            future = asyncio.run_coroutine_threadsafe(
                self._send_api_call("send_group_msg", {
                    "group_id": group_id,
                    "message": message,
                    "auto_escape": auto_escape
                }),
                loop
            )
            response = future.result(timeout=360)
        else:
            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        self._send_api_call("send_group_msg", {
                            "group_id": group_id,
                            "message": message,
                            "auto_escape": auto_escape
                        }),
                        loop
                    )
                    response = future.result(timeout=360)
                else:
                    response = asyncio.run(self._send_api_call("send_group_msg", {
                        "group_id": group_id,
                        "message": message,
                        "auto_escape": auto_escape
                    }))
            except RuntimeError:
                response = {"status": "failed", "retcode": -1}
        
        return response.get("data", {}).get("message_id", -1)
    
    def send_msg(self, message_type: str, user_id: int | None, group_id: int | None, 
                 message: str = "", auto_escape: bool = False) -> int:
        """发送消息（通用）"""
        if message_type == "private":
            return self.send_private_msg(user_id, message, auto_escape)
        elif message_type == "group":
            return self.send_group_msg(group_id, message, auto_escape)
        return -1
    
    def delete_msg(self, message_id: int):
        """撤回消息"""
        self._call_api("delete_msg", {"message_id": message_id})
    
    def get_msg(self, message_id: int) -> Dict[str, Any]:
        """获取消息"""
        response = self._call_api("get_msg", {"message_id": message_id})
        return response.get("data", {})
    
    def get_forward_msg(self, message_id: int) -> Dict[str, Any]:
        """获取合并转发消息"""
        response = self._call_api("get_forward_msg", {"message_id": message_id})
        return response.get("data", {})
    
    def get_image(self, file: str) -> str:
        """获取图片"""
        response = self._call_api("get_image", {"file": file})
        return response.get("data", {}).get("url", "")
    
    def get_record(self, file: str, out_format: str | None = None) -> str:
        """获取语音"""
        params = {"file": file}
        if out_format:
            params["out_format"] = out_format
        
        response = self._call_api("get_record", params)
        return response.get("data", {}).get("file", "")
    
    def set_friend_add_request(self, flag: str, approve: bool = True, remark: str = ""):
        """处理加好友请求"""
        self._call_api("set_friend_add_request", {
            "flag": flag,
            "approve": approve,
            "remark": remark
        })
    
    def set_group_add_request(self, flag: str, sub_type: str, approve: bool = True, reason: str = ""):
        """处理加群请求"""
        self._call_api("set_group_add_request", {
            "flag": flag,
            "sub_type": sub_type,
            "approve": approve,
            "reason": reason
        })
    
    def get_login_info(self) -> Dict[str, Any]:
        """获取登录号信息"""
        response = self._call_api("get_login_info")
        return response.get("data", {})
    
    def get_stranger_info(self, user_id: int, no_cache: bool = False) -> Dict[str, Any]:
        """获取陌生人信息"""
        response = self._call_api("get_stranger_info", {
            "user_id": user_id,
            "no_cache": no_cache
        })
        return response.get("data", {})
    
    def get_friend_list(self) -> List[Dict[str, Any]]:
        """获取好友列表"""
        response = self._call_api("get_friend_list")
        return response.get("data", [])
    
    def get_group_info(self, group_id: int, no_cache: bool = False) -> Dict[str, Any]:
        """获取群信息"""
        response = self._call_api("get_group_info", {
            "group_id": group_id,
            "no_cache": no_cache
        })
        return response.get("data", {})
    
    def get_group_list(self) -> List[Dict[str, Any]]:
        """获取群列表"""
        response = self._call_api("get_group_list")
        return response.get("data", [])
    
    def get_group_member_info(self, group_id: int, user_id: int, no_cache: bool = False) -> Dict[str, Any]:
        """获取群成员信息"""
        response = self._call_api("get_group_member_info", {
            "group_id": group_id,
            "user_id": user_id,
            "no_cache": no_cache
        })
        return response.get("data", {})
    
    def get_group_member_list(self, group_id: int) -> List[Dict[str, Any]]:
        """获取群成员列表"""
        response = self._call_api("get_group_member_list", {"group_id": group_id})
        return response.get("data", [])
    
    def get_group_honors_info(self, group_id: int, _type: str | None = None) -> Dict[str, Any]:
        """获取群荣誉信息"""
        params = {"group_id": group_id}
        if _type:
            params["type"] = _type
        
        response = self._call_api("get_group_honors_info", params)
        return response.get("data", {})
    
    def set_group_kick(self, group_id: int, user_id: int, reject_add_request: bool = False):
        """群组踢人"""
        self._call_api("set_group_kick", {
            "group_id": group_id,
            "user_id": user_id,
            "reject_add_request": reject_add_request
        })
    
    def set_group_ban(self, group_id: int, user_id: int, duration: int = 0):
        """群组禁言"""
        self._call_api("set_group_ban", {
            "group_id": group_id,
            "user_id": user_id,
            "duration": duration
        })
    
    def set_group_anonymous_ban(self, group_id: int, anonymous_flag: str, duration: int = 0):
        """群组匿名禁言"""
        self._call_api("set_group_anonymous_ban", {
            "group_id": group_id,
            "anonymous_flag": anonymous_flag,
            "duration": duration
        })
    
    def set_group_whole_ban(self, group_id: int, enable: bool):
        """群组全员禁言"""
        self._call_api("set_group_whole_ban", {
            "group_id": group_id,
            "enable": enable
        })
    
    def set_group_admin(self, group_id: int, user_id: int, enable: bool = True):
        """群组设置管理员"""
        self._call_api("set_group_admin", {
            "group_id": group_id,
            "user_id": user_id,
            "enable": enable
        })
    
    def set_group_anonymous(self, group_id: int, enable: bool = True):
        """群组设置匿名"""
        self._call_api("set_group_anonymous", {
            "group_id": group_id,
            "enable": enable
        })
    
    def set_group_card(self, group_id: int, user_id: int, card: str = ""):
        """设置群名片"""
        self._call_api("set_group_card", {
            "group_id": group_id,
            "user_id": user_id,
            "card": card
        })
    
    def set_group_name(self, group_id: int, group_name: str):
        """设置群名"""
        self._call_api("set_group_name", {
            "group_id": group_id,
            "group_name": group_name
        })
    
    def set_group_leave(self, group_id: int, is_dismiss: bool = False):
        """退出群组"""
        self._call_api("set_group_leave", {
            "group_id": group_id,
            "is_dismiss": is_dismiss
        })
    
    def set_group_special_title(self, group_id: int, user_id: int, special_title: str = "", duration: int = -1):
        """设置群组专属头衔"""
        self._call_api("set_group_special_title", {
            "group_id": group_id,
            "user_id": user_id,
            "special_title": special_title,
            "duration": duration
        })
    
    def get_version_info(self) -> Dict[str, Any]:
        """获取版本信息"""
        response = self._call_api("get_version_info")
        return response.get("data", {})
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        response = self._call_api("get_status")
        return response.get("data", {})
