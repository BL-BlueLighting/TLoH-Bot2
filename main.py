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

    # ===== 关键词加权 =====
    keywords = {
        "bot": 0.6,
        "@": 0.6,
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
    for k, bonus in keywords.items():
        if k in lower_msg:
            rate += bonus

    # ===== 冷却惩罚 =====
    if last_bot_time is not None:
        delta = now - last_bot_time
        if delta < 30:
            rate *= 0.1
        elif delta < 120:
            rate *= 0.4

    # ===== 群活跃度惩罚 =====
    if recent_msg_count >= 6:
        rate *= 0.3
    elif recent_msg_count <= 1:
        rate *= 1.5

    # ===== 随机抖动 =====
    rate *= random.uniform(0.7, 1.3)

    # ===== 限制上下界 =====
    rate = max(0.0, min(rate, 0.95))

    return random.random() < rate

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

允许轻度阴阳怪气和调侃，但不能人身攻击。
可以使用"老哥""兄弟""哥们"等称呼。
注意：阴阳怪气语调**不要常用**，只能偶尔用一下。你看情况。如果对方攻击性强，你再这样搞。
"""
    with open("./data/botmemories.ign", "r", encoding="utf-8") as doc:
        memories = json.load(doc)
        group_mem = extract_mem_by_group_id(memories, event.group_id.__str__())

    if len(group_mem) >= 6000:
        group_mem = group_mem[-6000:]

    # save memories
    pack_memories(event.group_id.__str__(), group_mem)

    # 这些 group_mem 的格式为：
    # [user_id]: [content]

    # 提示词 gpt 写的不关我事
    global rmc, last_message_time, rmc_record_time
    
    # 检查是否需要 bot 发言
    if not should_bot_speak(msg, last_bot_time=last_message_time) and not "FORCESPEAK" in msg:
        current_time = datetime.datetime.now()
        if (current_time - rmc_record_time).total_seconds() >= 10:
            rmc = 0
            rmc_record_time = current_time
        rmc += 1
        msg_str = f"{event.user_id.__str__()}: {msg}"
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

    bot_instance.send_group_msg(event.group_id, final_content)

print("TLoH Bot 2")
print(":: Bot 正在注册消息监听器")
bot.register_message_handler(all_message)
print(":: Bot 启动中...")
bot.run()