import os
import sys
import smtplib
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
# 导入现有模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from geo_api import search_city
from weather_api import get_weather
from jwt_token import generate_qweather_token

# 配置信息
API_HOST = os.environ.get("API_HOST")
PRIVATE_KEY_PATH = "ed25519-private.pem"

# 邮件配置
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = os.environ.get("EMAIL_PORT")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")


def get_city_weather(city_name, token):
    """
    获取指定城市的天气信息
    :param city_name: 城市名称
    :param token: API令牌
    :return: (城市信息, 天气数据) 或 (None, None)
    """
    # 搜索城市
    cities = search_city(token, city_name, API_HOST)
    if not cities or len(cities) == 0:
        print(f"⚠️ 未找到城市: {city_name}")
        return None, None

    # 使用第一个匹配的城市
    city = cities[0]
    city_id = city["id"]
    
    # 获取天气数据
    weather_data = get_weather(token, city_id, API_HOST)
    if not weather_data:
        print(f"⚠️ 无法获取{city['name']}的天气数据")
        return city, None
    
    return city, weather_data


def format_weather_message(city_info, weather_data):
    """
    格式化天气信息为邮件内容
    :param city_info: 城市信息
    :param weather_data: 天气数据
    :return: 格式化的HTML邮件内容
    """
    if not city_info or not weather_data:
        return "<p>获取天气信息失败</p>"

    now = weather_data["now"]
    admin_info = f"{city_info['adm1']}/{city_info['adm2']}" if city_info['adm1'] != city_info['adm2'] else city_info['adm1']
    
    # 创建HTML内容
    html = f"""
    <html>
    <body>
        <h2>🌈 今日天气: {city_info['name']} ({admin_info})</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>🕒 观测时间</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{now['obsTime']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>🌡 温度</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{now['temp']}℃ (体感 {now['feelsLike']}℃)</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>☁️ 天气状况</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{now['text']} (代码: {now['icon']})</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>🌪 风向风力</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{now['windDir']} {now['windScale']}级</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>💧 湿度</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{now['humidity']}%</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>👁 能见度</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{now['vis']}公里</td>
            </tr>
        </table>
        <p><small>📡 数据来源: {' | '.join(weather_data['refer']['sources'])}</small></p>
        <p><small>⏱️ 邮件生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
    </body>
    </html>
    """
    return html


def send_weather_email(city_name, html_content):
    """
    发送天气邮件
    :param city_name: 城市名称
    :param html_content: HTML格式的邮件内容
    :return: 是否发送成功
    """
    try:
        # 创建邮件对象
        message = MIMEMultipart()
        message['From'] = EMAIL_USER
        message['To'] = EMAIL_RECEIVER
        message['Subject'] = Header(f"{city_name}天气预报 - {datetime.now().strftime('%Y-%m-%d')}", 'utf-8')
        
        # 添加HTML内容
        message.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # 连接SMTP服务器并发送
        with smtplib.SMTP(EMAIL_HOST, int(EMAIL_PORT)) as server:
            server.starttls()  # 启用TLS加密
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(message)
        
        print(f"✅ 天气邮件已发送至 {EMAIL_RECEIVER}")
        return True
        
    except Exception as e:
        print(f"❌ 邮件发送失败: {str(e)}")
        return False


def main():
    """主函数"""
    # 参数解析
    parser = argparse.ArgumentParser(description="天气信息邮件发送工具")
    parser.add_argument("city", help="要查询的城市名称")
    args = parser.parse_args()
    
    city_name = args.city
    
    try:
        # 生成Token
        token = generate_qweather_token(PRIVATE_KEY_PATH)
        print(f"🔑 已生成Token，准备获取{city_name}的天气")
        
        # 获取天气数据
        city_info, weather_data = get_city_weather(city_name, token)
        if city_info and weather_data:
            # 格式化邮件内容
            html_content = format_weather_message(city_info, weather_data)
            # 发送邮件
            send_weather_email(city_name, html_content)
        else:
            print("❌ 无法获取天气数据，邮件发送失败")
            
    except Exception as e:
        print(f"❌ 程序执行错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
