"""
数据模型 - OneBot 11 事件和消息数据结构
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class MessageInfo:
    """消息信息数据模型"""
    
    # 基本字段
    time: int
    message_type: str  # private, group
    message_id: int
    user_id: int
    message: str
    raw_message: str
    font: int = 0
    
    # 群相关字段（私聊为 None）
    group_id: Optional[int] = None
    anonymous: Optional[Dict[str, Any]] = None
    sender: Dict[str, Any] = field(default_factory=dict)
    
    # 扩展字段
    sub_type: str = ""  # friend, normal, group, notice
    temp_source: Optional[int] = None  # 临时会话来源（群号）
    
    @classmethod
    def from_event(cls, event: Dict[str, Any], self_id: int = 0) -> "MessageInfo":
        """
        从 OneBot 事件创建 MessageInfo
        
        Args:
            event: OneBot 事件数据
            self_id: 机器人 ID（用于标识）
        
        Returns:
            MessageInfo: 消息信息对象
        """
        return cls(
            time=event.get("time", 0),
            message_type=event.get("message_type", ""),
            message_id=event.get("message_id", 0),
            user_id=event.get("user_id", 0),
            message=event.get("message", ""),
            raw_message=event.get("raw_message", ""),
            font=event.get("font", 0),
            group_id=event.get("group_id"),
            anonymous=event.get("anonymous"),
            sender=event.get("sender", {}),
            sub_type=event.get("sub_type", ""),
            temp_source=event.get("temp_source"),
        )


@dataclass
class EventData:
    """事件数据基类"""
    
    time: int
    self_id: int
    post_type: str


@dataclass
class NoticeEvent(EventData):
    """通知事件"""
    
    notice_type: str


@dataclass
class RequestEvent(EventData):
    """请求事件"""
    
    request_type: str


@dataclass
class MetaEvent(EventData):
    """元事件"""
    
    meta_event_type: str


@dataclass
class CQCode:
    """CQ 码表示"""
    
    def __init__(self, function: str, **params):
        """
        初始化 CQ 码
        
        Args:
            function: CQ 码函数名
            **params: CQ 码参数
        """
        self.function = function
        self.params = params
    
    def __str__(self) -> str:
        """转换为 CQ 码字符串"""
        if not self.params:
            return f"[CQ:{self.function}]"
        
        params_str = ",".join(
            f"{k}={v}" for k, v in self.params.items()
        )
        return f"[CQ:{self.function},{params_str}]"
    
    @staticmethod
    def face(id: int) -> "CQCode":
        """QQ 表情"""
        return CQCode("face", id=id)
    
    @staticmethod
    def emoji(id: int) -> "CQCode":
        """emoji 表情"""
        return CQCode("emoji", id=id)
    
    @staticmethod
    def bface(id: int) -> "CQCode":
        """原创表情"""
        return CQCode("bface", id=id)
    
    @staticmethod
    def sface(id: int) -> "CQCode":
        """小黄脸表情"""
        return CQCode("sface", id=id)
    
    @staticmethod
    def image(file: str, subType: int = 0, url: str = None, cache: int = 1, #type:ignore
              id: int = 0, c: int = 0) -> "CQCode":
        """图片"""
        params = {"file": file, "subType": subType, "cache": cache}
        if url:
            params["url"] = url
        if id:
            params["id"] = id
        if c:
            params["c"] = c
        return CQCode("image", **params)
    
    @staticmethod
    def record(file: str, magic: int = None, url: str = None, cache: int = 1) -> "CQCode":#type:ignore
        """语音"""
        params = {"file": file}
        if magic:
            params["magic"] = magic#type:ignore
        if url:
            params["url"] = url
        params["cache"] = cache#type:ignore
        return CQCode("record", **params)
    
    @staticmethod
    def video(file: str, cover: str = None, c: int = None) -> "CQCode":#type:ignore
        """视频"""
        params = {"file": file}
        if cover:
            params["cover"] = cover
        if c:
            params["c"] = c#type:ignore
        return CQCode("video", **params)
    
    @staticmethod
    def at(qq: int, name: str = None) -> "CQCode":#type:ignore
        """@某人"""
        params = {"qq": qq}
        if name:
            params["name"] = name#type:ignore
        return CQCode("at", **params)
    
    @staticmethod
    def at_all() -> "CQCode":
        """@全体"""
        return CQCode("at", qq="all")
    
    @staticmethod
    def rps() -> "CQCode":
        """猜拳"""
        return CQCode("rps")
    
    @staticmethod
    def dice() -> "CQCode":
        """骰子"""
        return CQCode("dice")
    
    @staticmethod
    def shake() -> "CQCode":
        """窗口抖动"""
        return CQCode("shake")
    
    @staticmethod
    def poke(type: str, id: int) -> "CQCode":
        """戳一戳"""
        return CQCode("poke", type=type, id=id)
    
    @staticmethod
    def anonymous(ignore: int = 0) -> "CQCode":
        """匿名发送"""
        return CQCode("anonymous", ignore=ignore)
    
    @staticmethod
    def share(url: str, title: str = "", content: str = "", image: str = "") -> "CQCode":
        """分享链接"""
        params = {"url": url, "title": title}
        if content:
            params["content"] = content
        if image:
            params["image"] = image
        return CQCode("share", **params)
    
    @staticmethod
    def forward(id: int) -> "CQCode":
        """合并转发"""
        return CQCode("forward", id=id)
    
    @staticmethod
    def node(id: int) -> "CQCode":
        """转发节点（消息ID）"""
        return CQCode("node", id=id)
    
    @staticmethod
    def node_custom(user_id: int, nickname: str, content: str) -> "CQCode":
        """转发节点（自定义）"""
        return CQCode("node", user_id=user_id, nickname=nickname, content=content)
    
    @staticmethod
    def music(type: str, id: int) -> "CQCode":
        """音乐"""
        return CQCode("music", type=type, id=id)
    
    @staticmethod
    def music_custom(url: str, audio: str, title: str, content: str = "", 
                     image: str = "") -> "CQCode":
        """自定义音乐"""
        params = {"url": url, "audio": audio, "title": title}
        if content:
            params["content"] = content
        if image:
            params["image"] = image
        return CQCode("music", **params)
    
    @staticmethod
    def reply(id: int) -> "CQCode":
        """回复"""
        return CQCode("reply", id=id)
    
    @staticmethod
    def tts(text: str) -> "CQCode":
        """文本转语音"""
        return CQCode("tts", text=text)


class MessageBuilder:
    """消息构建器"""
    
    def __init__(self):
        """初始化消息构建器"""
        self.message: List[str] = []
    
    def text(self, content: str) -> "MessageBuilder":
        """添加文本"""
        self.message.append(content)
        return self
    
    def add(self, content: Any) -> "MessageBuilder":
        """添加内容（文本或 CQ 码）"""
        self.message.append(str(content))
        return self
    
    def build(self) -> str:
        """构建消息"""
        return "".join(self.message)
    
    def __str__(self) -> str:
        """转换为字符串"""
        return self.build()
