import os
import json
import logging
import aiofiles
import aiohttp
from datetime import datetime
from telegram import Update, Bot, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)
import asyncio
import jwt_token
from weather_api import get_weather, get_weather_warning
from geo_api import search_city, get_selected_city_data
from dotenv import load_dotenv
from telegram.helpers import escape_markdown
from telegram.error import Forbidden
import pytz
from telegram.request import HTTPXRequest
import httpx
weather_cache = {}
load_dotenv()
# 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 配置信息
API_HOST = os.environ.get("API_HOST")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
USER_DATA_FILE = "user_data.json"
XAI_API_KEY = os.environ.get("XAI_API_KEY")

# 用户数据
user_data = {}

# 默认定时提醒时间
DEFAULT_REMINDER_TIMES = ["06:00", "12:00", "16:00"]
DEFAULT_TIMEZONE = "Asia/Shanghai"  # 默认时区为北京时间


async def load_user_data():
    """异步加载用户数据"""
    global user_data
    try:
        if os.path.exists(USER_DATA_FILE):
            async with aiofiles.open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.loads(await f.read())
            logger.info(f"成功加载用户数据：{len(user_data)} 条记录")
        else:
            user_data = {}
            logger.info("用户数据文件不存在，创建新的用户数据")
    except Exception as e:
        logger.error(f"加载用户数据时出错: {e}")
        user_data = {}

    for user_id, data in user_data.items():
        if "reminder_times" not in data:
            data["reminder_times"] = DEFAULT_REMINDER_TIMES.copy()
        if "active" not in data:
            data["active"] = True
        if "timezone" not in data:
            data["timezone"] = DEFAULT_TIMEZONE


async def save_user_data():
    """异步保存用户数据"""
    try:
        async with aiofiles.open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(user_data, ensure_ascii=False, indent=2))
        logger.info(f"成功保存用户数据：{len(user_data)} 条记录")
        return True
    except Exception as e:
        logger.error(f"保存用户数据时出错: {e}")
        return False


async def get_grok_ai_response(prompt):
    """异步调用GROK AI获取智能回复"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {XAI_API_KEY}",
        }
        data = {
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个十分侠客仗义的天气助手，根据天气情况给出穿衣建议和雨伞提醒。回答要啰嗦、毒舌、实用，而且必须得是文言文，语言风格像网络热梗古风小生，比如快哉快哉，我应在江湖悠悠。"
                },
                {"role": "user", "content": prompt}
            ],
            "model": "grok-3-mini-beta",
            "stream": False,
            "temperature": 0.5
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    response_data = await response.json()
                    return response_data["choices"][0]["message"]["content"]
                else:
                    logger.error(
                        f"GROK AI 请求失败: {response.status}, {await response.text()}"
                    )
                    return "AI分析暂时不可用，请稍后再试。"
    except Exception as e:
        logger.error(f"调用GROK AI时出错: {e}")
        return "AI分析暂时不可用，请稍后再试。"


async def get_city_weather(city_id):
    # 添加缓存机制（示例）
    cache_key = f"weather_{city_id}"
    if cache_key in weather_cache:
        return weather_cache[cache_key]

    """异步获取城市天气并加入AI分析"""
    token = jwt_token.generate_qweather_token()
    if not token:
        return None, "无法生成天气API令牌"

    weather_data = get_weather(token, city_id, API_HOST)
    if not weather_data:
        return None, "获取天气数据失败"

    now = weather_data["now"]
    prompt = (
        f"我所在城市的当前天气情况如下:\n"
        f"天气: {now['text']}\n"
        f"温度: {now['temp']}°C (体感温度 {now['feelsLike']}°C)\n"
        f"湿度: {now['humidity']}%\n"
        f"风向: {now['windDir']}, 风力等级: {now['windScale']}级\n\n"
        f"请根据以上天气情况，给我提供:\n"
        f"1. 今天应该怎么穿衣服的建议\n"
        f"2. 是否需要带伞\n"
        f"3. 其他需要注意的天气提醒\n"
        f"请用简洁友好的中文回答，不要太长。"
    )

    ai_suggestion = await get_grok_ai_response(prompt)
    weather_cache[cache_key] = (weather_data, ai_suggestion)

    # 创建一个异步任务来处理缓存过期，但不等待它完成
    asyncio.create_task(expire_cache(cache_key))
    return weather_data, ai_suggestion

# 创建一个单独的异步函数来处理缓存过期
async def expire_cache(cache_key):
    await asyncio.sleep(5*60)
    weather_cache.pop(cache_key, None)



def format_telegram_message(weather_data, ai_suggestion, city_name=None, timezone=DEFAULT_TIMEZONE):
    if not weather_data:
        return "❌ 无法获取天气数据"

    now = weather_data["now"]
    msg = []
    safe_city = escape_markdown(str(city_name)) if city_name else None
    
    # 使用指定时区显示时间
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    except Exception:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    title = (
        f"🌈 *{safe_city}天气预报* ({escape_markdown(current_time)})"
        if safe_city
        else f"🌈 *天气预报* ({escape_markdown(current_time)})"
    )
    msg.append(title)

    weather_details = [
        f"🌡️ *温度*: {escape_markdown(str(now['temp']))}°C "
        f"(体感 {escape_markdown(str(now['feelsLike']))}°C)",
        f"☁️ *天气*: {escape_markdown(now['text'])}",
        f"💨 *风向*: {escape_markdown(now['windDir'])} "
        f"{escape_markdown(now['windScale'])}级",
        f"💧 *湿度*: {escape_markdown(str(now['humidity']))}%",
        f"👁️ *能见度*: {escape_markdown(str(now['vis']))}公里"
    ]
    msg.extend(["", *weather_details, ""])

    # AI 建议处理
    safe_ai = escape_markdown(ai_suggestion)
    safe_ai = safe_ai.replace("\\*\\*", "*")
    msg.extend([
        "🤖 *智能提醒*:",
        safe_ai,
        "",
        "_数据来源: 和风天气 & GROK AI_"
    ])
    return "\n".join(msg)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name
    if user_id not in user_data:
        user_data[user_id] = {
            "city_id": None,
            "city_name": None,
            "active": True,
            "reminder_times": DEFAULT_REMINDER_TIMES.copy(),
            "timezone": DEFAULT_TIMEZONE,
            "warning_cities": [],
            "notified_warnings": []
        }
    else:
        user_data[user_id]["active"] = True
        if "warning_cities" not in user_data[user_id]:
            user_data[user_id]["warning_cities"] = []
        if "notified_warnings" not in user_data[user_id]:
            user_data[user_id]["notified_warnings"] = []
            
    await save_user_data()
    # 使用 context.bot 发送消息
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"👋 你好，{user_name}！\n\n"
        f"我是你的智能天气助手，结合了和风天气数据和GROK AI智能分析。\n\n"
        f"🔸 发送 /help 查看使用帮助\n"
        f"🔸 发送 /setcity 设置你的城市\n"
        f"🔸 发送 /weather 获取当前天气",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "*🌈 天气机器人使用帮助*\n\n"
            "*基本命令:*\n"
            "• /start \\- 开始使用机器人\n"
            "• /help \\- 显示帮助信息\n"
            "• /weather \\- 查看当前天气\n"
            "• /compare \\- 多城市天气对比\n"
            "• /setcity \\- 设置你的默认城市（用于天气提醒）\n"
            "• /settimes \\- 设置提醒时间\n"
            "• /status \\- 查看当前设置\n"
            "• /stop \\- 暂停天气提醒\n\n"
            "*灾害预警订阅:*\n"
            "• /add\\_warning\\_city `城市名` \\- 订阅一个城市的天气灾害预警\n"
            "• /del\\_warning\\_city \\- 管理（删除）已订阅的预警城市\n"
            "• /list\\_warning\\_cities \\- 查看已订阅的预警城市列表\n\n"
            "*关于提醒时间:*\n"
            "默认在每天06:00、12:00和16:00发送天气提醒\n"
            "使用 /settimes `HH:MM HH:MM` 格式设置，最多3个时间\n"
            "例如: `/settimes 07:00 19:00`\n\n"
            "*关于多城市对比:*\n"
            "• 格式: /compare 城市1,城市2,城市3"
        ),
        parse_mode="MarkdownV2",
    )

def get_args(context):
    return context.args

async def set_city_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = get_args(context)
    user_id = str(update.effective_user.id)

    if user_id not in user_data:
        user_data[user_id] = {
            "city_id": None,
            "city_name": None,
            "active": True,
            "reminder_times": DEFAULT_REMINDER_TIMES.copy(),
            "timezone": DEFAULT_TIMEZONE,  # 添加默认时区
        }

    if not args:
        await update.message.reply_text(
            "请输入城市名称，例如: /setcity 北京\n" "或者使用格式: /setcity 城市名"
        )
        return

    city_name = " ".join(args)
    await update.message.reply_text(f"🔍 正在搜索城市: {city_name}...")

    token = jwt_token.generate_qweather_token()
    if not token:
        await update.message.reply_text("❌ 无法生成天气API令牌，请稍后再试")
        return

    cities = search_city(token, city_name, API_HOST)
    if not cities:
        await update.message.reply_text(
            f"❌ 没有找到城市 '{city_name}'，请检查拼写或尝试其他城市名称"
        )
        return

    if len(cities) == 1:
        city = cities[0]
        user_data[user_id]["city_id"] = city["id"]
        user_data[user_id]["city_name"] = f"{city['name']}"
        if city["name"] != city["adm1"]:
            user_data[user_id]["city_name"] += f" ({city['adm1']})"
        await save_user_data()

        await update.message.reply_text(
            f"✅ 已将您的城市设置为: {user_data[user_id]['city_name']}\n\n"
            f"发送 /weather 获取当前天气"
        )
    else:
        msg = ["找到多个城市，请选择一个:"]
        for i, city in enumerate(cities[:5], 1):
            admin_info = (
                f"{city['adm1']}/{city['adm2']}"
                if city["adm1"] != city["adm2"]
                else city["adm1"]
            )
            msg.append(f"{i}. {city['name']} ({admin_info}), {city['country']}")
        msg.append("\n请回复数字(1-5)选择城市")

        await update.message.reply_text("\n".join(msg))
        context.user_data["cities"] = cities[:5]
        context.user_data["waiting_for_city_selection"] = True


async def set_times_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in user_data:
        user_data[user_id] = {
            "city_id": None,
            "city_name": None,
            "active": True,
            "reminder_times": DEFAULT_REMINDER_TIMES.copy(),
            "timezone": DEFAULT_TIMEZONE,  # 添加默认时区
        }

    current_times = ", ".join(user_data[user_id]["reminder_times"])
    await update.message.reply_text(
        f"*当前提醒时间*: {current_times}\n\n"
        f"请输入新的提醒时间，用逗号分隔，格式为24小时制(HH:MM)，例如:\n"
        f"`07:00, 13:00, 18:30`\n\n"
        f"最多可设置5个提醒时间\n"
        f"输入 'default' 恢复默认时间(06:00, 12:00, 16:00)",
        parse_mode="Markdown",
    )
    context.user_data["waiting_for_time_settings"] = True


async def weather_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in user_data or not user_data[user_id].get("city_id"):
        await update.message.reply_text(
            "❌ 您尚未设置城市。请使用 /setcity 命令设置您的城市。"
        )
        return

    await update.message.reply_text("🔍 正在获取天气数据...")
    city_id = user_data[user_id]["city_id"]
    city_name = user_data[user_id]["city_name"]
    timezone = user_data[user_id].get("timezone", DEFAULT_TIMEZONE)

    weather_data, ai_suggestion = await get_city_weather(city_id)
    message = format_telegram_message(weather_data, ai_suggestion, city_name, timezone)
    await update.message.reply_text(message, parse_mode="Markdown")


async def status_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in user_data:
        await update.message.reply_text(
            "❌ 您尚未设置任何信息。请使用 /setcity 设置您的城市。"
        )
        return

    data = user_data[user_id]
    status = "✅ 已开启" if data.get("active", True) else "❌ 已关闭"
    city = data.get("city_name", "未设置")
    times = ", ".join(data.get("reminder_times", DEFAULT_REMINDER_TIMES))

    await update.message.reply_text(
        f"*当前设置*\n\n"
        f"🌆 *城市*: {city}\n"
        f"⏰ *提醒时间*: {times}\n"
        f"📅 *定时提醒*: {status}\n\n"
        f"• 更改城市请使用 /setcity\n"
        f"• 更改提醒时间请使用 /settimes\n"
        f"• 暂停提醒请使用 /stop\n"
        f"• 重新开启提醒请使用 /start",
        parse_mode="Markdown",
    )


async def stop_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in user_data:
        user_data[user_id] = {
            "city_id": None,
            "city_name": None,
            "active": False,
            "reminder_times": DEFAULT_REMINDER_TIMES.copy(),
            "timezone": DEFAULT_TIMEZONE,  # 添加默认时区
        }
    else:
        user_data[user_id]["active"] = False

    await save_user_data()
    await update.message.reply_text(
        "✅ 已暂停天气提醒\n"
        "您还可以随时使用 /weather 查询当前天气\n"
        "使用 /start 重新开启定时提醒"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text

    if context.user_data.get("waiting_for_city_selection"):
        try:
            choice = int(text.strip())
            cities = context.user_data.get("cities", [])

            if 1 <= choice <= len(cities):
                city = cities[choice - 1]
                user_data[user_id]["city_id"] = city["id"]
                user_data[user_id]["city_name"] = f"{city['name']}"
                if city["name"] != city["adm1"]:
                    user_data[user_id]["city_name"] += f" ({city['adm1']})"
                await save_user_data()

                await update.message.reply_text(
                    f"✅ 已将您的城市设置为: {user_data[user_id]['city_name']}\n\n"
                    f"发送 /weather 获取当前天气"
                )
            else:
                await update.message.reply_text("❌ 无效的选择，请输入1-5之间的数字")
        except ValueError:
            await update.message.reply_text("❌ 请输入数字选择城市")
        context.user_data["waiting_for_city_selection"] = False
        return

    if context.user_data.get("waiting_for_time_settings"):
        if text.lower() == "default":
            user_data[user_id]["reminder_times"] = DEFAULT_REMINDER_TIMES.copy()
            await save_user_data()
            await update.message.reply_text(
                f"✅ 已恢复默认提醒时间: {', '.join(DEFAULT_REMINDER_TIMES)}"
            )
        else:
            try:
                times = [t.strip() for t in text.split(",")]
                valid_times = []
                for t in times:
                    try:
                        hour, minute = map(int, t.split(":"))
                        if 0 <= hour <= 23 and 0 <= minute <= 59:
                            valid_times.append(f"{hour:02d}:{minute:02d}")
                        else:
                            raise ValueError()
                    except(ValueError, IndexError):
                        await update.message.reply_text(
                            f"❌ 无效的时间格式: {t}\n请使用24小时制(HH:MM)"
                        )
                        return

                if not valid_times:
                    await update.message.reply_text("❌ 未提供有效的时间")
                    return

                if len(valid_times) > 5:
                    await update.message.reply_text("❌ 最多只能设置5个提醒时间")
                    return

                user_data[user_id]["reminder_times"] = valid_times
                await save_user_data()
                await update.message.reply_text(
                    f"✅ 已设置提醒时间: {', '.join(valid_times)}"
                )
            except Exception as e:
                logger.error(f"设置时间出错: {e}")
                await update.message.reply_text(
                    "❌ 时间格式有误\n" "请使用正确的格式，例如: 07:00, 13:00, 18:30"
                )
        context.user_data["waiting_for_time_settings"] = False
        return

    await update.message.reply_text(
        "👋 你好！我是你的智能天气助手\n\n"
        "• 输入 /help 查看所有可用命令\n"
        "• 输入 /weather 获取当前天气\n"
        "• 输入 /setcity 设置你的城市"
    )


async def send_scheduled_weather(context: CallbackContext):
    """优化的定时天气推送"""
    try:
        # 获取UTC时间
        utc_now = datetime.now(pytz.UTC)
        logger.debug(f"开始执行定时任务，当前UTC时间: {utc_now}")

        # 使用深拷贝避免数据修改冲突
        users = user_data.copy().items()

        # 批量处理用户
        tasks = []
        for user_id, data in users:
            if validate_user_timezone(data, utc_now):
                tasks.append(
                    send_user_weather(
                        context.bot,
                        user_id,
                        data["city_id"],
                        data["city_name"]
                    )
                )

        # 控制并发速率（每秒20条）
        for i in range(0, len(tasks), 20):
            await asyncio.gather(*tasks[i:i + 20])
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"定时任务执行失败: {str(e)}", exc_info=True)


def validate_user_timezone(data: dict, utc_now: datetime) -> bool:
    """基于时区的用户验证逻辑"""
    try:
        # 获取用户时区
        timezone = data.get("timezone", DEFAULT_TIMEZONE)
        tz = pytz.timezone(timezone)
        
        # 将UTC时间转换为用户时区
        user_time = utc_now.astimezone(tz)
        current_time = user_time.strftime("%H:%M")
        
        # 验证用户是否活跃、是否设置了城市、当前时间是否在提醒时间列表中
        return (
            data.get("active", True) and
            data.get("city_id") and
            current_time in data.get("reminder_times", []) and
            data.get("city_name")
        )
    except Exception as e:
        logger.error(f"验证用户时区时出错: {e}")
        return False


async def send_user_weather(bot: Bot, user_id: str, city_id: str, city_name: str):
    """发送单个用户天气信息"""
    try:
        # 获取天气数据
        weather_data, ai_suggestion = await get_city_weather(city_id)
        if not weather_data:
            logger.warning(f"城市 {city_name}({city_id}) 天气数据为空")
            return

        # 获取用户时区
        timezone = user_data[user_id].get("timezone", DEFAULT_TIMEZONE)
        
        # 构建安全的消息内容
        safe_city_name = escape_markdown(city_name)
        message = format_telegram_message(weather_data, ai_suggestion, safe_city_name, timezone)

        # 发送消息（带重试机制）
        await retry_async(
            bot.send_message,
            args=(user_id, message),
            kwargs={"parse_mode": "Markdown"},
            max_retries=3,
            delay=1
        )
        logger.debug(f"用户 {user_id} 推送成功")

    except Forbidden as e:
        logger.warning(f"用户 {user_id} 已屏蔽机器人: {e}")
        await deactivate_user(user_id)
    except Exception as e:
        logger.error(f"用户 {user_id} 推送失败: {str(e)}", exc_info=True)

async def deactivate_user(user_id: str):
    """标记用户为非活跃"""
    if user_id in user_data:
        user_data[user_id]["active"] = False
        await save_user_data()
        logger.info(f"已标记用户 {user_id} 为非活跃状态")

async def retry_async(func, args=(), kwargs=None, max_retries=3, delay=1):
    """带指数退避的重试机制"""
    kwargs = kwargs or {}
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = delay * (2 ** attempt)
            logger.warning(f"操作重试中 ({attempt+1}/{max_retries}), {wait}s 后重试，错误: {str(e)}")
            await asyncio.sleep(wait)


async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """多城市天气对比命令"""
    args = context.args
    
    if not args or len(args) == 0:
        await update.message.reply_text(
            "❌ 请提供要对比的城市名称，用逗号分隔\n"
            "例如: /compare 北京,上海,广州"
        )
        return
    
    # 处理逗号分隔的输入
    if len(args) == 1 and "," in args[0]:
        city_names = [name.strip() for name in args[0].split(",") if name.strip()]
    else:
        city_names = [name.strip() for name in " ".join(args).split(",") if name.strip()]
    
    if not city_names:
        await update.message.reply_text("❌ 无效的城市名称格式")
        return
    
    if len(city_names) > 10:
        await update.message.reply_text("⚠️ 一次最多比较10个城市，已截取前10个")
        city_names = city_names[:10]
    
    status_message = await update.message.reply_text(f"🔍 正在查询多个城市的天气: {', '.join(city_names)}...")
    
    # 存储所有选中的城市数据和天气数据
    selected_cities = []
    weather_data_list = []
    token = jwt_token.generate_qweather_token()
    
    # 进度指示器
    progress = ["⬜️"] * len(city_names)
    
    # 逐个处理每个城市
    for i, city_name in enumerate(city_names):
        # 更新进度
        progress[i] = "🔄"
        await status_message.edit_text(
            f"🔍 正在查询中...\n{''.join(progress)}\n当前：{city_name}"
        )
        
        cities = search_city(token, city_name, API_HOST)
        if not cities:
            progress[i] = "❌"
            continue
        
        # 自动选择第一个匹配的城市
        city_data = cities[0]
        selected_cities.append(city_data)
        
        # 获取天气数据
        weather_data, _ = await get_city_weather(city_data["id"])
        if weather_data:
            weather_data_list.append(weather_data)
            progress[i] = "✅"
        else:
            progress[i] = "❌"
    
    # 更新完成状态
    await status_message.edit_text(f"查询完成: {''.join(progress)}")
    
    # 如果找到了城市，显示结果
    if selected_cities and weather_data_list:
        # 构建表格数据
        rows = []
        
        for i, weather_data in enumerate(weather_data_list):
            if i < len(selected_cities):
                city = selected_cities[i]
                now = weather_data["now"]
                
                row = [
                    f"{city['name']}",
                    f"{now['text']}",
                    f"{now['temp']}°C",
                    f"{now['windDir']} {now['windScale']}级",
                    f"{now['humidity']}%"
                ]
                rows.append(row)
        
        # 构建消息
        message = "*📊 多城市天气对比*\n\n"
        
        # 添加表格数据
        table = []
        for row in rows:
            table.append(f"*{row[0]}*: {row[1]}, {row[2]}, {row[3]}, 湿度{row[4]}")
        
        message += "\n".join(table)
        message += f"\n\n🕒 观测时间: {escape_markdown(weather_data_list[0]['now']['obsTime'])}"
        
        await update.message.reply_text(message, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ 未能找到任何有效城市的天气数据")


async def set_timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置用户时区"""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_data:
        user_data[user_id] = {
            "city_id": None,
            "city_name": None,
            "active": True,
            "reminder_times": DEFAULT_REMINDER_TIMES.copy(),
            "timezone": DEFAULT_TIMEZONE,
        }
    
    args = get_args(context)
    if not args:
        # 显示当前时区
        current_timezone = user_data[user_id].get("timezone", DEFAULT_TIMEZONE)
        await update.message.reply_text(
            f"*当前时区设置*\n\n"
            f"🌍 时区: {current_timezone}\n\n"
            f"要更改时区，请使用以下格式：\n"
            f"`/settimezone 时区名称`\n\n"
            f"常用时区示例：\n"
            f"• Asia/Shanghai (北京时间)\n"
            f"• Asia/Tokyo (东京时间)\n"
            f"• America/New_York (纽约时间)\n"
            f"• Europe/London (伦敦时间)\n"
            f"• Australia/Sydney (悉尼时间)\n\n"
            f"您可以在 https://en.wikipedia.org/wiki/List_of_tz_database_time_zones 查看完整的时区列表",
            parse_mode="Markdown"
        )
        return
    
    new_timezone = " ".join(args)
    try:
        # 验证时区是否有效
        pytz.timezone(new_timezone)
        
        # 更新用户时区
        user_data[user_id]["timezone"] = new_timezone
        await save_user_data()
        
        # 获取新时区的当前时间
        tz = pytz.timezone(new_timezone)
        current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        
        await update.message.reply_text(
            f"✅ 时区已更新为: {new_timezone}\n"
            f"当前时间: {current_time}"
        )
    except pytz.exceptions.UnknownTimeZoneError:
        await update.message.reply_text(
            "❌ 无效的时区名称\n"
            "请使用正确的时区名称，例如：Asia/Shanghai"
        )
    except Exception as e:
        logger.error(f"设置时区时出错: {e}")
        await update.message.reply_text("❌ 设置时区时发生错误，请稍后重试")


async def add_warning_city_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """添加一个新的天气预警订阅城市"""
    user_id = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("请提供一个城市名称，例如：`/add_warning_city 北京`")
        return

    city_name = " ".join(context.args)
    token = jwt_token.generate_qweather_token()
    cities = search_city(token, city_name, API_HOST)

    if not cities:
        await update.message.reply_text(f"❌ 找不到城市：{escape_markdown(city_name, version=2)}")
        return

    # 使用第一个匹配结果
    selected_city_info = cities[0]
    city_id = selected_city_info["id"]
    full_city_name = f"{selected_city_info['name']} ({selected_city_info['adm1']})"

    if user_id not in user_data:
        # Should be created by /start, but as a safeguard
        user_data[user_id] = {
            "warning_cities": [],
            "notified_warnings": []
        }
    
    # 初始化预警相关字段
    if "warning_cities" not in user_data[user_id]:
        user_data[user_id]["warning_cities"] = []
    if "notified_warnings" not in user_data[user_id]:
        user_data[user_id]["notified_warnings"] = []

    # 检查是否已订阅
    if any(sub["id"] == city_id for sub in user_data[user_id]["warning_cities"]):
        await update.message.reply_text(f"✅ 您已订阅 {escape_markdown(full_city_name, version=2)} 的预警。")
        return
            
    # 添加到订阅列表
    city_to_add = {"id": city_id, "name": selected_city_info["name"], "adm1": selected_city_info['adm1']}
    user_data[user_id]["warning_cities"].append(city_to_add)
    await save_user_data()
    
    await update.message.reply_text(f"✅ 成功订阅 {escape_markdown(full_city_name, version=2)} 的天气灾害预警！", parse_mode="MarkdownV2")
    # 立即检查一次
    await check_and_send_warning_for_city(context.bot, user_id, city_to_add)


async def list_warning_cities_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出用户订阅的预警城市"""
    user_id = str(update.effective_user.id)
    if user_id not in user_data or not user_data[user_id].get("warning_cities"):
        await update.message.reply_text("您尚未订阅任何城市的天气预警。\n使用 `/add_warning_city <城市名>` 添加。")
        return
        
    cities_list = user_data[user_id]["warning_cities"]
    if not cities_list:
        await update.message.reply_text("您尚未订阅任何城市的天气预警。\n使用 `/add_warning_city <城市名>` 添加。")
        return

    message_lines = ["*您已订阅以下城市的天气预警：*"]
    for city in cities_list:
        city_name = escape_markdown(f"{city['name']} ({city.get('adm1', '')})", version=2)
        message_lines.append(f"\\- {city_name}")
        
    await update.message.reply_text("\n".join(message_lines), parse_mode="MarkdownV2")


async def del_warning_city_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示一个带删除按钮的已订阅城市列表"""
    user_id = str(update.effective_user.id)
    if user_id not in user_data or not user_data[user_id].get("warning_cities"):
        await update.message.reply_text("您尚未订阅任何城市的天气预警。")
        return

    cities_list = user_data[user_id]["warning_cities"]
    if not cities_list:
        await update.message.reply_text("您尚未订阅任何城市的天气预警。")
        return

    keyboard = []
    for city in cities_list:
        callback_data = f"delwarn_{city['id']}"
        button_text = f"❌ 删除 {city['name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('请选择要删除的预警城市:', reply_markup=reply_markup)


async def warning_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理删除预警城市的回调"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    callback_data = query.data
    
    if callback_data.startswith("delwarn_"):
        city_id_to_del = callback_data.split("_")[1]
        
        if user_id in user_data and "warning_cities" in user_data[user_id]:
            cities = user_data[user_id]["warning_cities"]
            city_to_remove = next((c for c in cities if c["id"] == city_id_to_del), None)
            
            if city_to_remove:
                removed_city_name = escape_markdown(city_to_remove['name'], version=2)
                cities.remove(city_to_remove)
                await save_user_data()
                await query.edit_message_text(text=f"已取消对 {removed_city_name} 的预警订阅。")
            else:
                await query.edit_message_text(text="未找到该订阅，可能已被删除。")
        else:
            await query.edit_message_text(text="出现错误，找不到您的订阅数据。")


def format_warning_message(warning, city_name):
    """格式化预警信息用于Telegram发送"""
    title = escape_markdown(warning.get('title', '天气预警'), version=2)
    sender = escape_markdown(warning.get('sender', '未知来源'), version=2)
    pub_time_str = warning.get('pubTime', '')
    if pub_time_str:
        # 格式化时间
        dt_object = datetime.fromisoformat(pub_time_str)
        pub_time = escape_markdown(dt_object.strftime("%Y-%m-%d %H:%M"), version=2)
    else:
        pub_time = "N/A"

    text = escape_markdown(warning.get('text', '无详细信息'), version=2)
    type_name = escape_markdown(warning.get('typeName', 'N/A'), version=2)
    severity = escape_markdown(warning.get('severity', 'N/A'), version=2)
    city_name_escaped = escape_markdown(city_name, version=2)

    return (
        f"‼️ *{city_name_escaped} 天气灾害预警* ‼️\n\n"
        f"*{title}*\n\n"
        f"*类型*: {type_name}\n"
        f"*级别*: {severity}\n"
        f"*发布单位*: {sender}\n"
        f"*发布时间*: {pub_time}\n\n"
        f"*详情*:\n{text}"
    )

async def check_and_send_warning_for_city(bot: Bot, user_id, city):
    """为单个用户和城市检查并发送预警"""
    token = jwt_token.generate_qweather_token()
    if not token:
        logger.error("无法为预警检查生成Token")
        return

    warning_data = get_weather_warning(token, city["id"])
    if not warning_data or not warning_data.get("warning"):
        return

    if user_id not in user_data or "notified_warnings" not in user_data[user_id]:
        user_data[user_id]["notified_warnings"] = []

    for warning in warning_data["warning"]:
        warning_id = warning["id"]
        if warning_id not in user_data[user_id]["notified_warnings"]:
            try:
                message = format_warning_message(warning, city["name"])
                await bot.send_message(chat_id=user_id, text=message, parse_mode="MarkdownV2")
                
                user_data[user_id]["notified_warnings"].append(warning_id)
                
                if len(user_data[user_id]["notified_warnings"]) > 50:
                    user_data[user_id]["notified_warnings"] = user_data[user_id]["notified_warnings"][-25:]
                
                await save_user_data()
                
            except Forbidden:
                await deactivate_user(user_id)
                logger.warning(f"用户 {user_id} 已屏蔽机器人，已将其停用。")
                break
            except Exception as e:
                logger.error(f"发送预警消息给 {user_id} 时出错: {e}")

async def check_weather_warnings(context: CallbackContext):
    """后台定时任务：检查所有用户的预警订阅"""
    logger.info("后台任务：开始检查天气灾害预警...")
    all_cities_to_check = {}
    for user_id, data in user_data.items():
        if data.get("active") and data.get("warning_cities"):
            for city in data["warning_cities"]:
                if city["id"] not in all_cities_to_check:
                    all_cities_to_check[city["id"]] = city
    
    if not all_cities_to_check:
        logger.info("后台任务：没有需要检查的预警城市。")
        return

    token = jwt_token.generate_qweather_token()
    if not token:
        logger.error("无法为后台预警任务生成Token")
        return

    all_warnings_found = {} # {city_id: [warnings]}
    for city_id, city_info in all_cities_to_check.items():
        try:
            warning_data = get_weather_warning(token, city_id)
            if warning_data and warning_data.get("warning"):
                all_warnings_found[city_id] = warning_data["warning"]
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"检查城市 {city_info['name']} ({city_id}) 预警时出错: {e}")

    if not all_warnings_found:
        return
        
    for user_id, data in user_data.items():
        if not data.get("active") or not data.get("warning_cities"):
            continue

        if "notified_warnings" not in data:
            data["notified_warnings"] = []
            
        for subscribed_city in data["warning_cities"]:
            city_id = subscribed_city["id"]
            if city_id in all_warnings_found:
                for warning in all_warnings_found[city_id]:
                    if warning["id"] not in data["notified_warnings"]:
                        try:
                            message = format_warning_message(warning, subscribed_city["name"])
                            await context.bot.send_message(chat_id=user_id, text=message, parse_mode="MarkdownV2")
                            data["notified_warnings"].append(warning["id"])
                            if len(data["notified_warnings"]) > 50:
                                data["notified_warnings"] = data["notified_warnings"][-25:]
                        except Forbidden:
                            await deactivate_user(user_id)
                            logger.warning(f"用户 {user_id} 已屏蔽机器人，已将其停用。")
                            break
                        except Exception as e:
                            logger.error(f"分发预警给 {user_id} 时出错: {e}")
                if not data.get("active"): # Check again in case user was deactivated
                    break
            
    await save_user_data()
    logger.info("后台任务：天气灾害预警检查完成。")

async def post_init(app: Application):
    """在机器人启动后加载用户数据并设置命令列表"""
    await load_user_data()
    await app.bot.set_my_commands([
        ("help", "显示帮助"),
        ("weather", "查询天气"),
        ("setcity", "设置城市"),
        ("settimes", "设置提醒时间"),
        ("compare", "多城市天气对比"),
        ("status", "当前状态"),
        ("stop", "暂停提醒"),
        ("set_timezone", "设置时区")
    ])

async def post_stop(app: Application):
    """在机器人停止前保存用户数据"""
    logger.info("机器人正在关闭...")
    await save_user_data()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """记录更新引起的错误"""
    logger.error("处理更新时发生异常:", exc_info=context.error)

def main():
    """启动机器人"""
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("未设置TELEGRAM_BOT_TOKEN，机器人无法启动")
        return

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_stop)
        .build()
    )

    # 注册错误处理器
    app.add_error_handler(error_handler)

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("setcity", set_city_command))
    app.add_handler(CommandHandler("settimes", set_times_command))
    app.add_handler(CommandHandler("compare", compare_command))
    app.add_handler(CommandHandler("set_timezone", set_timezone_command))

    # Add weather warning handlers
    app.add_handler(CommandHandler("add_warning_city", add_warning_city_command))
    app.add_handler(CommandHandler("list_warning_cities", list_warning_cities_command))
    app.add_handler(CommandHandler("del_warning_city", del_warning_city_command))
    app.add_handler(CallbackQueryHandler(warning_callback_handler, pattern="^delwarn_"))


    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 定时任务
    job_queue = app.job_queue
    job_queue.run_daily(
        send_scheduled_weather,
        time=datetime.strptime("00:00", "%H:%M").time(),
        name="daily_weather_check",
    )
    job_queue.run_repeating(check_weather_warnings, interval=1800, first=10, name="warning_check")


    # 启动机器人
    logger.info("机器人正在启动...")
    app.run_polling()


if __name__ == "__main__":
    main()
