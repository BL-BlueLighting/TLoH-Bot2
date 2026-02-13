"""
使用示例 - 展示各种 Bot 功能的使用方法
主要是为了防止我自己都记不清怎么用（划掉）
"""

from includes.bot import Bot
from includes.eventers import Receive, When, Condition
from includes.models import MessageInfo, CQCode, MessageBuilder
import config as config

# ============================================
# 初始化 Bot
# ============================================

bot = Bot(
    ws_url="ws://127.0.0.1:6700",
    self_id=0 # 0 自动匹配
)


# ============================================
# 示例 1: 处理所有消息
# ============================================

all_message = Receive.Message(
    When=(
        When.Received,
    ),
    Conditions=(
        Condition.AllMessage,#type:ignore
    )
)

@all_message
def handle_all_messages(bot_instance: Bot, info: MessageInfo):
    """处理所有接收到的消息"""
    print(f"[{info.user_id}] {info.raw_message}")


# ============================================
# 示例 2: 处理特定命令
# ============================================

help_command = Receive.Message(
    When=(
        When.Received,
        When.GotCommand(name="help")
    ),
    Conditions=(
        Condition.AllMessage,
    )
)

@help_command
def handle_help_command(bot_instance: Bot, info: MessageInfo):
    """处理 /help 命令"""
    message = MessageBuilder()\
        .text("帮助信息:\n")\
        .text("/help - 显示帮助\n")\
        .text("/echo <内容> - 重复内容\n")\
        .text("/info - 显示用户信息")\
        .build()
    
    if info.message_type == "group":
        bot_instance.send_group_msg(info.group_id, message)
    else:
        bot_instance.send_private_msg(info.user_id, message)


# ============================================
# 示例 3: 处理 echo 命令
# ============================================

echo_command = Receive.Message(
    When=(
        When.Received,
        When.GotCommand(name="echo")
    ),
    Conditions=(
        Condition.AllMessage,
    )
)

@echo_command
def handle_echo_command(bot_instance: Bot, info: MessageInfo):
    """处理 /echo 命令"""
    # 提取命令参数
    args = info.raw_message.replace("/echo", "", 1).strip()
    
    if not args:
        message = "用法: /echo <内容>"
    else:
        message = f"你说: {args}"
    
    if info.message_type == "group":
        bot_instance.send_group_msg(info.group_id, message)
    else:
        bot_instance.send_private_msg(info.user_id, message)


# ============================================
# 示例 4: 处理特定群组消息
# ============================================

group_command = Receive.Message(
    When=(
        When.Received,
        When.GotCommand(name="group_info")
    ),
    Conditions=(
        Condition.GroupMessage,
        Condition.GroupId(123456789),  # 替换为实际的群号
    )
)

@group_command
def handle_group_info(bot_instance: Bot, info: MessageInfo):
    """处理特定群的 /group_info 命令"""
    group_info = bot_instance.get_group_info(info.group_id)#type:ignore
    
    message = MessageBuilder()\
        .text(f"群号: {group_info.get('group_id', 'N/A')}\n")\
        .text(f"群名: {group_info.get('group_name', 'N/A')}\n")\
        .text(f"成员: {group_info.get('member_count', 'N/A')}")\
        .build()
    
    bot_instance.send_group_msg(info.group_id, message)


# ============================================
# 示例 5: 处理私聊消息
# ============================================

private_message = Receive.Message(
    When=(
        When.Received,
    ),
    Conditions=(
        Condition.PrivateMessage,
    )
)

@private_message
def handle_private_message(bot_instance: Bot, info: MessageInfo):
    """处理所有私聊消息"""
    user_info = bot_instance.get_stranger_info(info.user_id)
    
    message = MessageBuilder()\
        .text(f"你好 {user_info.get('nickname', 'User')}\n")\
        .text(f"你说: {info.raw_message}")\
        .build()
    
    bot_instance.send_private_msg(info.user_id, message)


# ============================================
# 示例 6: 使用正则表达式条件
# ============================================

regex_message = Receive.Message(
    When=(
        When.Received,
    ),
    Conditions=(
        Condition.Regex(r"^/img\s+(.+)"),
    )
)

@regex_message
def handle_regex_message(bot_instance: Bot, info: MessageInfo):
    """处理匹配正则的消息"""
    import re
    match = re.match(r"^/img\s+(.+)", info.raw_message)
    if match:
        image_name = match.group(1)
        message = CQCode.image(file=f"file:///path/to/{image_name}.png")
        
        if info.message_type == "group":
            bot_instance.send_group_msg(info.group_id, str(message))
        else:
            bot_instance.send_private_msg(info.user_id, str(message))


# ============================================
# 示例 7: 发送含有 CQ 码的消息
# ============================================

cq_code_message = Receive.Message(
    When=(
        When.Received,
        When.GotCommand(name="mention")
    ),
    Conditions=(
        Condition.AllMessage,
    )
)

@cq_code_message
def handle_cq_code_message(bot_instance: Bot, info: MessageInfo):
    """发送含 CQ 码的消息"""
    if info.message_type == "group":
        # 发送 @全体 + 文本 + 表情
        message = MessageBuilder()\
            .add(CQCode.at_all())\
            .text("大家好，我是机器人")\
            .add(CQCode.emoji(id=1))\
            .build()
        
        bot_instance.send_group_msg(info.group_id, message)


# ============================================
# 示例 8: 处理关键词触发
# ============================================

keyword_message = Receive.Message(
    When=(
        When.Received,
    ),
    Conditions=(
        Condition.ContainsKeyword(["hello", "hi", "你好"]) #type:ignore
    )
)

@keyword_message
def handle_keyword_message(bot_instance: Bot, info: MessageInfo):
    """处理包含特定关键词的消息"""
    reply_message = "你好，很高兴认识你！"
    
    if info.message_type == "group":
        bot_instance.send_group_msg(info.group_id, reply_message)
    else:
        bot_instance.send_private_msg(info.user_id, reply_message)


# ============================================
# 示例 9: 获取用户信息
# ============================================

user_info_command = Receive.Message(
    When=(
        When.Received,
        When.GotCommand(name="user")
    ),
    Conditions=(
        Condition.AllMessage,
    )
)

@user_info_command
def handle_user_info_command(bot_instance: Bot, info: MessageInfo):
    """处理 /user 命令 - 获取用户信息"""
    user_info = bot_instance.get_stranger_info(info.user_id)
    
    message = MessageBuilder()\
        .text(f"用户 ID: {user_info.get('user_id', 'N/A')}\n")\
        .text(f"昵称: {user_info.get('nickname', 'N/A')}\n")\
        .text(f"年龄: {user_info.get('age', 'N/A')}\n")\
        .text(f"性别: {user_info.get('sex', 'N/A')}")\
        .build()
    
    if info.message_type == "group":
        bot_instance.send_group_msg(info.group_id, message)
    else:
        bot_instance.send_private_msg(info.user_id, message)


# ============================================
# 示例 10: 群管理操作
# ============================================

admin_command = Receive.Message(
    When=(
        When.Received,
        When.GotCommand(name="ban")
    ),
    Conditions=(
        Condition.GroupMessage,
    )
)

@admin_command
def handle_ban_command(bot_instance: Bot, info: MessageInfo):
    """处理 /ban <qq> 命令 - 禁言用户"""
    args = info.raw_message.replace("/ban", "", 1).strip()
    
    try:
        target_user_id = int(args)
        bot_instance.set_group_ban(info.group_id, target_user_id, duration=60)  # 禁言60秒#type:ignore
        message = f"已禁言用户 {target_user_id}"
        bot_instance.send_group_msg(info.group_id, message)
    except (ValueError, IndexError):
        bot_instance.send_group_msg(info.group_id, "用法: /ban <qq>")


# ============================================
# 主程序
# ============================================

if __name__ == "__main__":
    print("机器人启动中...")
    
    # 注册所有处理器到 bot
    bot.register_message_handler(all_message)
    bot.register_message_handler(help_command)
    bot.register_message_handler(echo_command)
    bot.register_message_handler(group_command)
    bot.register_message_handler(private_message)
    bot.register_message_handler(regex_message)
    bot.register_message_handler(cq_code_message)
    bot.register_message_handler(keyword_message)
    bot.register_message_handler(user_info_command)
    bot.register_message_handler(admin_command)
    
    # 启动 bot（阻塞式）
    bot.run()
