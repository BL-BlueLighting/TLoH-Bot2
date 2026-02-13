"""
事件系统 - 处理事件接收、条件过滤和事件分发
"""

from typing import Callable, Tuple, Any, List
from dataclasses import dataclass
from includes.models import MessageInfo
import re


class EventHandler:
    """事件处理器基类"""
    
    def __init__(self, whens: Tuple, conditions: Tuple):
        """
        初始化事件处理器
        
        Args:
            whens: When 条件元组
            conditions: Condition 条件元组
        """
        self.whens = whens if isinstance(whens, tuple) else (whens,)
        self.conditions = conditions if isinstance(conditions, tuple) else (conditions,)
        self.callback = None
    
    def __call__(self, func: Callable):
        """装饰器，绑定处理函数"""
        self.callback = func
        return self
    
    def should_process(self, info: Any) -> bool:
        """判断是否应该处理此事件"""
        # 检查 When 条件
        for when_condition in self.whens:
            if isinstance(when_condition, WhenCondition):
                if not when_condition.check(info):
                    return False
        
        # 检查 Condition 条件
        for condition in self.conditions:
            if isinstance(condition, ConditionBase):
                if not condition.check(info): #type: ignore
                    return False
        
        return True
    
    def execute(self, bot, info: Any):
        """执行处理函数"""
        if self.callback:
            self.callback(bot, info)


class WhenCondition:
    """When 条件基类"""
    
    def check(self, info: Any) -> bool:
        """检查条件是否满足"""
        raise NotImplementedError


class ConditionBase:
    """条件基类"""
    
    def check(self, info: Any) -> bool:
        """检查条件是否满足"""
        raise NotImplementedError


class Received(WhenCondition):
    """条件：消息已接收"""
    
    def check(self, info: Any) -> bool:
        return True


class GotCommand(WhenCondition):
    """条件：获取到特定命令"""
    
    def __init__(self, name: str, prefix: str = "/"):
        """
        初始化命令条件
        
        Args:
            name: 命令名称
            prefix: 命令前缀（默认 /）
        """
        self.name = name
        self.prefix = prefix
    
    def check(self, info: Any) -> bool:
        """检查是否收到指定命令"""
        if not isinstance(info, MessageInfo):
            return False
        
        message = info.raw_message.strip()
        command_str = f"{self.prefix}{self.name}"
        
        # 检查消息是否以命令开头
        if message.startswith(command_str):
            # 检查命令后是空格或消息结束
            if len(message) == len(command_str) or message[len(command_str)].isspace():
                return True
        
        return False


class AllMessage(ConditionBase):
    """条件：所有消息"""
    
    def check(self, info: Any) -> bool:
        return isinstance(info, MessageInfo)


class PrivateMessage(ConditionBase):
    """条件：私聊消息"""
    
    def check(self, info: Any) -> bool:
        if not isinstance(info, MessageInfo):
            return False
        return info.message_type == "private"


class GroupMessage(ConditionBase):
    """条件：群聊消息"""
    
    def check(self, info: Any) -> bool:
        if not isinstance(info, MessageInfo):
            return False
        return info.message_type == "group"


class GroupIdCondition(ConditionBase):
    """条件：特定群组"""
    
    def __init__(self, group_id: int):
        """
        初始化群ID条件
        
        Args:
            group_id: 群号
        """
        self.group_id = group_id
    
    def check(self, info: Any) -> bool:
        if not isinstance(info, MessageInfo):
            return False
        return info.group_id == self.group_id


class UserIdCondition(ConditionBase):
    """条件：特定用户"""
    
    def __init__(self, user_id: int):
        """
        初始化用户ID条件
        
        Args:
            user_id: 用户ID
        """
        self.user_id = user_id
    
    def check(self, info: Any) -> bool:
        if not isinstance(info, MessageInfo):
            return False
        return info.user_id == self.user_id


class RegexCondition(ConditionBase):
    """条件：正则表达式匹配"""
    
    def __init__(self, pattern: str):
        """
        初始化正则条件
        
        Args:
            pattern: 正则表达式
        """
        self.pattern = re.compile(pattern)
    
    def check(self, info: Any) -> bool:
        if not isinstance(info, MessageInfo):
            return False
        return bool(self.pattern.search(info.raw_message))


class ContainsKeyword(ConditionBase):
    """条件：包含关键词"""
    
    def __init__(self, keywords: List[str]):
        """
        初始化关键词条件
        
        Args:
            keywords: 关键词列表
        """
        self.keywords = keywords
    
    def check(self, info: Any) -> bool:
        if not isinstance(info, MessageInfo):
            return False
        
        message = info.raw_message.lower()
        for keyword in self.keywords:
            if keyword.lower() in message:
                return True
        return False


class MessageReceiver:
    """消息接收器"""
    
    def Message(self, When: Tuple | None = None, Conditions: Tuple | None = None) -> EventHandler:
        """
        创建消息事件处理器
        
        Args:
            When: When 条件元组
            Conditions: Condition 条件元组
        
        Returns:
            EventHandler: 事件处理器
        """
        whens = When if When else (Received(),)
        conditions = Conditions if Conditions else (AllMessage(),)
        return EventHandler(whens, conditions)


class When:
    """When 条件命名空间"""
    
    Received = Received()
    
    @staticmethod
    def GotCommand(name: str, prefix: str = "/") -> GotCommand:
        """
        获取命令条件
        
        Args:
            name: 命令名称
            prefix: 命令前缀
        
        Returns:
            GotCommand: 命令条件
        """
        return GotCommand(name, prefix)


class Condition:
    """条件命名空间"""
    
    AllMessage = AllMessage()
    PrivateMessage = PrivateMessage()
    GroupMessage = GroupMessage()
    
    @staticmethod
    def GroupId(group_id: int) -> GroupIdCondition:
        """
        群ID条件
        
        Args:
            group_id: 群号
        
        Returns:
            GroupIdCondition: 群ID条件
        """
        return GroupIdCondition(group_id)
    
    @staticmethod
    def UserId(user_id: int) -> UserIdCondition:
        """
        用户ID条件
        
        Args:
            user_id: 用户ID
        
        Returns:
            UserIdCondition: 用户ID条件
        """
        return UserIdCondition(user_id)
    
    @staticmethod
    def Regex(pattern: str) -> RegexCondition:
        """
        正则表达式条件
        
        Args:
            pattern: 正则表达式
        
        Returns:
            RegexCondition: 正则表达式条件
        """
        return RegexCondition(pattern)
    
    @staticmethod
    def ContainsKeyword(keywords: List[str]) -> ContainsKeyword:
        """
        关键词条件
        
        Args:
            keywords: 关键词列表
        
        Returns:
            ContainsKeyword: 关键词条件
        """
        return ContainsKeyword(keywords)


class Receive:
    """接收器命名空间"""
    
    Message = MessageReceiver().Message
