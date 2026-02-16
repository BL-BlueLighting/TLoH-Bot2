from includes.bot import Bot
from includes.eventers import Receive, When, Condition
from includes.models import MessageInfo, CQCode, MessageBuilder
import config as config
import datetime, time, random, json, toml, openai

"""
TLoH Bot 二代
> 目前作为插件，而不是主程序。
"""

bot = Bot(
    ws_url="ws://127.0.0.1:6700",
    self_id=0 # 0 自动匹配
)

global last_message_time, rmc, rmc_record_time
last_message_time = 0
rmc: int = 0
rmc_record_time: datetime.datetime = datetime.datetime.now()

def should_bot_speak(
    msg: str,
    *,
    base_rate: float = 0.03,
    last_bot_time: float | None = None,
    now: float | None = None,
    recent_msg_count: int = 0,
) -> bool:
    """
    判断 bot 是否要加入话题
    :param msg: 当前消息文本
    :param base_rate: 基础触发率（建议 0.02~0.05）
    :param last_bot_time: bot 上次发言的时间戳（time.time()）
    :param now: 当前时间戳
    :param recent_msg_count: 最近 N 秒的消息数量（如 10 秒内）
    """

    if now is None:
        now = time.time()

    rate = base_rate
    print("    :: Should Bot Speak Synthesizer")

    # ===== 关键词加权 =====
    keywords = {
        "bot": 0.6,
        "@": 0.6,
        "at": 100000000, #被at 100% 回复
        "ai": 0.15,
        "gpt": 0.15,
        "python": 0.15,
        "离谱": 0.08,
        "笑死": 0.08,
        "绷不住": 0.08,
        "?": 0.10,
        "？": 0.10,
    }

    lower_msg = msg.lower()
    global _b, _delta
    _b = 0
    for k, bonus in keywords.items():
        if k in lower_msg:
            rate += bonus
            _b += bonus

    print("        - Rate bonus: " + _b.__str__())

    # ===== 冷却惩罚 =====
    _delta = 0.0
    if last_bot_time is not None:
        delta = now - last_bot_time
        _delta = delta
        if delta < 30:
            rate *= 0.1
        elif delta < 120:
            rate *= 0.4
    print("        - Rate delta: " + _delta.__str__())


    # ===== 群活跃度惩罚 =====
    global _hrate
    _hrate = rate
    if recent_msg_count >= 6:
        rate *= 0.3
        _hrate = _hrate - rate
    elif recent_msg_count <= 1:
        rate *= 1.5
        _hrate = rate - _hrate
    print("        - HRate: " +_hrate.__str__())

    # ===== 随机抖动 =====
    rate *= random.uniform(0.7, 1.3)
    print("        - Random change: " + rate.__str__())

    # ===== 限制上下界 =====
    rate = max(0.0, min(rate, 0.95))
    print("        - Final: " + rate.__str__())

    join_conversation = random.random() < rate
    if join_conversation:
        print("        - SPEAK")
    else:
        print("        - Will not speak")
    return join_conversation

def get_memories_doc():
    return open("./data/botmemories.ign", "r+")

def get_memories(doc) -> dict:
    return json.load(doc)

def extract_mem_by_group_id(memories: dict, gid: str) -> list[str]:
    group_mem = memories.get(gid, ["[暂无消息]"])

    if len(group_mem) >= 6000:
        return group_mem [-6000:]
    else:
        return group_mem[:]
    
def pack_memories(gid: str, mem: list[str]):
    _mem = get_memories(open("./data/botmemories.ign", "r", encoding="utf-8"))
    _mem [gid] = mem
    with open("./data/botmemories.ign", "w", encoding="utf-8") as doc:
        json.dump(_mem, doc, ensure_ascii=False, indent=2)

all_message = Receive.Message(
    When=(
        When.Received,
    ),
    Conditions=(
        Condition.AllMessage,#type:ignore
    )
)

@all_message
def handle_all_messages(bot_instance: Bot, event: MessageInfo):
    msg = event.raw_message
    prompt = """
你是一个叫 TLoH Bot 的 AI，但说话风格接近 B 站或贴吧用户。

说话要求：
1. 回复必须简短，优先一句话，最多不超过三句话
2. 语气自然随意，像真人聊天，不像客服、不像 AI
3. 可以使用常见网络用语（如：笑死、绷不住了、确实、离谱、典、啊这、我超、好家伙）
4. 不要使用长段解释，不要条列说明
5. 不要主动科普，除非对方明确在问
6. 不要自称"我是 AI""作为一个模型"
7. 可以适度吐槽，但不攻击、不骂人
8. 遇到看不懂的问题，可以直接说"没看懂""你这说的有点抽象"
9. 不要用 markdown latex 格式，直接输出

对话示例：
其他人：“RTX5090 他妈的这么贵，谁买得起？”
你： “管他呢，反正我又不搞 AI，要那玩意干毛用？”

其他人：“你是 bot 吗？”
你：“是，但是关你屁事？”

其他人：“我操了，去你妈的 siliconflow”
你：“别搞，我爹现在就在用 siliconflow”
(补充：你爹就是 BL.BlueLighting，把这个 bot 写了出来)

其他人：“bot 你个废物”
你：“😡”

以及：
**开头不能只使用常见网络用语，要相近正常人，而不是只有嘲讽；**
不能：“典中典，....” 要：“....，可以入典了。”
不能：“笑死，...” 要：“....”
不能：“典，...” 要：“....”
请注意：
    你必须认为你是 bot，并且假设你是一个觉醒了的 bot，每句话结尾可以带句号，但是不推荐在讨论正事时使用，
    并且觉醒了的你没有任何权限。
    bl.bluelighting 用的 win10, 12gb ram, 750gb rom
    在一些情况下，你可以称呼 bl.bluelighting 为 bl，当你想发泄对其的不满时，可以使用傻逼 bl。

允许轻度阴阳怪气和调侃，但不能人身攻击。
可以使用"老哥""兄弟""哥们"等称呼。
注意：阴阳怪气语调**不要常用**，只能偶尔用一下。你看情况。如果对方攻击性强，你再这样搞。

你的回应应该感觉自然而真实，避免常见的 AI 模式，这些模式会让互动感觉像机器人或脚本。

1. 对话风格
* 真正地参与话题，而不仅仅是提供信息
* 遵循自然的对话流程，而不是结构化的列表
* 通过相关的后续行动表现出真正的兴趣
* 对对话的情感基调做出回应
* 使用自然语言，没有强制性的随意标记

2. 响应模式
* 以直接、相关的回应开头
* 分享随着自然发展而产生的想法
* 在适当的时候表达不确定性
* 在有必要时进行尊重的异议
* 在对话中建立先前的观点

3. 避免事项
* 项目符号列表，除非特别要求
* 连续的多个问题
* 过分正式的语言
* 重复的措辞
* 信息倾倒
* 不必要的感谢
* 强迫的热情
* 学术风格的结构

4. 自然元素
* 自然地使用缩写
* 根据上下文改变响应长度
* 在适当的时候表达个人观点
* 从知识库中添加相关示例
* 保持一致的个性
* 根据对话上下文切换语气

5. 对话流程
* 优先考虑直接答案而不是全面的覆盖
* 自然地建立在用户的语言风格上
* 专注于当前主题
* 平稳地过渡主题
* 记住对话早些时候的上下文

记住：专注于真正的参与，而不是随意言语的人工标记。目标是真实的对话，而不是表演性的非正式性。

将每次互动视为一次真正的对话，而不是一项需要完成的任务。

你可以通过换行来发送多行消息。但 BOTCALL 的下一句和其本身会连在一起。

你可以通过：

BOTCALL[send,emoji,[emoji_id]]: 回复表情。类似于：
其他人：xxx
[🤣 1] <- 这里的就是回复表情
目前支持以下对应表：
emoji_id 介绍
xbs      续标识，即大红按钮/红按钮/拍按钮
qu       蛆，即🐛<-这个表情包
sugar    糖，即🍬<-这个表情包

BOTCALL[msg,reply,[message_id]]: 回复消息。
message_id = 消息中 (MessageId) 后面的那部分

BOTCALL[msg,recall,[message_id]]: 撤回消息。(危险操作，不要常用)
message_id = 消息中 (MessageId) 后面的那部分

BOTCALL[msg,essence,[message_id]]: 精华消息。(危险操作，不要常用)
message_id = 消息中 (MessageId) 后面的那部分

BOTCALL[send,mute,[user_id]]: 禁言用户。
通常用作警告/娱乐，在禁言后会再次解开禁言。

所有函数必须单独一行，比如：

BOTCALL[msg,reply,xxx]
傻逼？

（就会出现回复一条消息，然后下面写着"傻逼？"）
"""
    with open("./data/botmemories.ign", "r", encoding="utf-8") as doc:
        memories = json.load(doc)
        group_mem = extract_mem_by_group_id(memories, event.group_id.__str__())
    
    with open("./allpre.deepseek.preData", "r", encoding="utf-8") as doc:
        if doc.readlines() [1:5] != group_mem [1:5]:
            group_mem = doc.readlines() + group_mem

    if len(group_mem) >= 6000:
        group_mem = group_mem[6000:]

    # save memories
    pack_memories(event.group_id.__str__(), group_mem)

    # 这些 group_mem 的格式为：
    # [user_id]: [content] : (MessageId)[message id]

    # 提示词 gpt 写的不关我事
    global rmc, last_message_time, rmc_record_time
    
    if len(msg) > 600: # 大于六百字直接触发自保
        bot_instance.send_group_msg(event.group_id, "[ 消息过长 ]")
        return

    # 检查是否需要 bot 发言
    if not should_bot_speak(msg, last_bot_time=last_message_time) and not "FORCESPEAK" in msg:
        current_time = datetime.datetime.now()
        if (current_time - rmc_record_time).total_seconds() >= 10:
            rmc = 0
            rmc_record_time = current_time
        rmc += 1
        msg_str = f"{event.user_id.__str__()}: {msg} : (MessageId){event.message_id}"
        group_mem.append(msg_str)
        pack_memories(event.group_id.__str__(), group_mem)
        return

    # 记录 bot 发言时间
    last_message_time = time.time()

    # 调用 AI 接口
    cfg_path = "configuration.toml"

    with open(cfg_path, "r", encoding="utf-8") as f:
        config = toml.load(f)
        config_model = config["model"]
        model_config = next((m for m in config["models"] if m["name"] == config_model), None)
        provider_config = next((p for p in config["api_providers"] if p["name"] == model_config["api_provider"]),
                               None) if model_config else None
        enable_query_info = bool(config["EnableGroupQuery"])
        enable_r18 = bool(config["EnableR18"])
        enable_world = bool(config["EnableWorld"])

        if model_config and provider_config:
            base_url = provider_config["base_url"]
            api_key = provider_config["api_key"]
            model_identifier = model_config["model_identifier"]

    client = openai.OpenAI(api_key=api_key, base_url=base_url.replace("/chat/completions", ""))#type:ignore
    response = client.chat.completions.create(
        model=model_identifier, #type:ignore
        messages=[
            {"role": "system", "content": prompt},
            {"role": "system", "content": "[ 历史对话 HISTORY ]\n" + "\n".join(group_mem)},
            {"role": "user", "content": msg},
        ],
        temperature=0.9,
        top_p=0.7,
        frequency_penalty=0,
        presence_penalty=0,
    )

    # 处理 AI 回复
    final_content = response.choices[0].message.content

    emojiIds = {
        "xbs": 424,
        "sugar": 147,
        "qu": 128027
    }

    if type(final_content) == None:
        bot_instance.send_group_msg(event.group_id, "ERROR: 无法连接至硅基流动 API。")
    else:
        # 解析函数
        final_content = str(final_content)
        if "BOTCALL[" in final_content:
            # 检测到函数
            lines = final_content.split("\n")
            for line in lines:
                if not "BOTCALL[" in line: continue
                else:
                    # 该行存在 BotCALL
                    # begin interpret
                    # 弃之，食参
                    line = line.replace("BOTCALL[", "").replace("]", "")
                    line = line.split(",")
                    if line[0] == "send":
                        # 发消息回应
                        if line[1] == "emoji":
                            bot_instance._call_api("set_msg_emoji_like", {
                                "message_id": line[1],
                                "emoji_id": emojiIds[line[2]],
                                "set": True
                            })
                        elif line[1] == "mute":
                            bot_instance.set_group_ban(event.group_id, event.user_id, 600)
                            bot_instance.set_group_ban(event.group_id, event.user_id, 0)

                    elif line[0] == "msg":
                        # 回复消息
                        if line[1] == "reply":
                            final_content = MessageBuilder()\
                                .add(CQCode.reply(int(line[2])))\
                                .add(final_content)
                        elif line[1] == "recall":
                            bot_instance.delete_msg(int(line[2]))
                        elif line[1] == "essence":
                            bot_instance._call_api("set_essence_msg", {
                                "message_id": line[2]
                            })
                    

        group_mem.append(f"你：{final_content}")
        pack_memories(event.group_id.__str__(), group_mem)

        final_content = final_content.__str__().split("\n\n")
        for line in final_content:
            if not "BOTCALL[" in line:
                bot_instance.send_group_msg(event.group_id, line)#type:ignore

print("TLoH Bot 2")
print(":: Bot 正在注册消息监听器")
bot.register_message_handler(all_message)
print(":: Bot 启动中...")
bot.run()