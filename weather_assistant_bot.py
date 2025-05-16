import os
import json
import logging
import aiofiles
import aiohttp
from datetime import datetime
from telegram import Update, Bot, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackContext,
)
import asyncio
import jwt_token
from weather_api import get_weather
from geo_api import search_city, get_selected_city_data
from dotenv import load_dotenv
from telegram.helpers import escape_markdown
from telegram.error import Forbidden
import map_visualization
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



def format_telegram_message(weather_data, ai_suggestion, city_name=None):
    if not weather_data:
        return "❌ 无法获取天气数据"

    now = weather_data["now"]
    msg = []
    safe_city = escape_markdown(str(city_name)) if city_name else None
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
        }
    else:
        user_data[user_id]["active"] = True  # 始终启用提醒
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
            "• /start - 开始使用机器人\n"
            "• /help - 显示帮助信息\n"
            "• /weather - 查看当前天气\n"
            "• /map - 查看天气地图可视化\n"
            "• /setcity - 设置你的城市\n"
            "• /settimes - 设置提醒时间\n"
            "• /status - 查看当前设置\n"
            "• /stop - 暂停天气提醒\n"
            "• /start - 重新开启天气提醒\n\n"
            "*关于提醒时间:*\n"
            "默认在每天06:00、12:00和16:00发送天气提醒\n"
            "使用/settimes命令可以自定义时间\n\n"
            "*智能提醒:*\n"
            "机器人会根据天气情况，通过GROK AI智能分析给你提供:\n"
            "• 穿衣建议\n"
            "• 是否需要带伞\n"
            "• 其他天气注意事项\n\n"
            "*地图功能:*\n"
            "使用/map命令可查看天气地图可视化\n"
            "• 支持直观查看城市地理位置\n"
            "• 显示当前天气状况"
        ),
        parse_mode="Markdown"  # 保持原有设置
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

    weather_data, ai_suggestion = await get_city_weather(city_id)
    message = format_telegram_message(weather_data, ai_suggestion, city_name)
    await update.message.reply_text(message, parse_mode="Markdown")


async def map_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """提供地图可视化命令处理函数"""
    user_id = str(update.effective_user.id)

    if user_id not in user_data or not user_data[user_id].get("city_id"):
        await update.message.reply_text(
            "❌ 您尚未设置城市。请使用 /setcity 命令设置您的城市。"
        )
        return

    await update.message.reply_text("🗺️ 正在生成天气地图...")
    
    try:
        city_id = user_data[user_id]["city_id"]
        
        # 获取完整城市数据（包含经纬度）
        token = jwt_token.generate_qweather_token()
        cities = search_city(token, user_data[user_id]["city_name"].split(" ")[0], API_HOST)
        if not cities:
            await update.message.reply_text("❌ 获取城市数据失败，请稍后再试。")
            return
            
        city_data = get_selected_city_data(cities, city_id)
        if not city_data:
            await update.message.reply_text("❌ 无法获取城市坐标信息。")
            return
        
        # 获取天气数据
        weather_data, _ = await get_city_weather(city_id)
        if not weather_data:
            await update.message.reply_text("❌ 获取天气数据失败，请稍后再试。")
            return
            
        # 生成地图
        map_file = map_visualization.create_weather_map(city_data, weather_data)
        
        # 发送静态地图URL（因为Telegram Bot无法直接发送HTML文件）
        lat, lon = city_data.get("lat", 0), city_data.get("lon", 0)
        static_map_url = map_visualization.get_static_map_url(lat, lon)
        
        await update.message.reply_text(
            f"🗺️ *{city_data.get('name', '未知')}* 天气地图:\n\n"
            f"[点击查看地图]({static_map_url})\n\n"
            f"🌡️ 温度: {weather_data['now']['temp']}°C\n"
            f"☁️ 天气: {weather_data['now']['text']}\n",
            parse_mode="Markdown"
        )
        
        # 告知用户本地地图已生成
        await update.message.reply_text(
            "💡 完整交互式地图已在服务器生成，但Telegram无法直接显示。\n"
            f"地图文件位置: {map_file}"
        )
        
    except Exception as e:
        logger.error(f"生成地图时出错: {e}")
        await update.message.reply_text(f"❌ 生成地图时出错: {str(e)}")


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
        now = datetime.now().astimezone()
        current_time = now.strftime("%H:%M")
        logger.debug(f"开始执行定时任务，当前系统时间: {current_time}")

        # 使用深拷贝避免数据修改冲突
        users = user_data.copy().items()

        # 批量处理用户
        tasks = []
        for user_id, data in users:
            if validate_user(data, current_time):
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


def validate_user(data: dict, current_time: str) -> bool:
    """用户验证逻辑"""
    return (
            data.get("active", True) and
            data.get("city_id") and
            current_time in data.get("reminder_times", []) and
            data.get("city_name")
    )


async def send_user_weather(bot: Bot, user_id: str, city_id: str, city_name: str):
    """发送单个用户天气信息"""
    try:
        # 获取天气数据
        weather_data, ai_suggestion = await get_city_weather(city_id)
        if not weather_data:
            logger.warning(f"城市 {city_name}({city_id}) 天气数据为空")
            return

        # 构建安全的消息内容
        safe_city_name = escape_markdown(city_name)
        message = format_telegram_message(weather_data, ai_suggestion, safe_city_name)

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


def main():
    """同步主函数，初始化并启动机器人"""
    # 获取当前事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # 同步运行初始化的异步任务
    loop.run_until_complete(load_user_data())

    # 创建 Telegram 应用
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_stop(post_stop)
        .build()
    )

    # 添加命令处理器
    handlers = [
        CommandHandler("start", start_command),
        CommandHandler("help", help_command),
        CommandHandler("setcity", set_city_command),
        CommandHandler("settimes", set_times_command),
        CommandHandler("weather", weather_command),
        CommandHandler("map", map_command),
        CommandHandler("status", status_command),
        CommandHandler("stop", stop_command),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    ]
    for handler in handlers:
        app.add_handler(handler)
    # 使用 PTB 内置的 JobQueue 设置定时任务
    app.job_queue.run_repeating(
        send_scheduled_weather,  # 直接使用 PTB 的上下文回调
        interval=60,  # 30 秒间隔
        first=10  # 5 秒后首次执行
    )
    # 启动机器人
    logger.info("机器人已启动")
    app.run_polling()
async def post_init(app: Application):
    """启动后执行的操作"""
    logger.info("机器人初始化完成")
    await app.bot.set_my_commands([
        ("start", "开始使用"),
        ("help", "帮助文档"),
        ("weather", "获取天气"),
        ("setcity", "设置城市"),
        ("settimes", "设置提醒时间"),
        ("status", "当前状态"),
        ("stop", "暂停提醒"),
        ("test", "测试消息")
    ])

async def post_stop(_app: Application):
    """停止前执行的操作"""
    logger.info("机器人正在关闭...")
    await save_user_data()


if __name__ == "__main__":
    main()
