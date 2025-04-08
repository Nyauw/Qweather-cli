# main.py
from geo_api import search_city, display_city_info, select_city
from weather_api import get_weather, display_weather
from jwt_token import generate_qweather_token

API_HOST = "https://your_api_host"


def main():
    # 配置信息

    # 自动生成Token
    try:
        token = generate_qweather_token()
        print("🔑 已自动生成有效Token")
    except Exception as e:
        print(f"❌ Token生成失败: {str(e)}")
        return

    while True:
        # 用户输入
        keyword = input("\n🏙 请输入城市名称 (q退出): ").strip()
        if keyword.lower() == "q":
            break

        # 搜索城市
        cities = search_city(token, keyword, API_HOST)
        if not cities:
            print("没有找到相关城市")
            continue

        # 显示并选择城市
        display_city_info(cities)
        location_id = select_city(cities)
        if not location_id:
            continue

        # 查询天气
        weather_data = get_weather(token, location_id, API_HOST)
        if weather_data:
            selected_city = next((c for c in cities if c["id"] == location_id), None)
            display_weather(weather_data, selected_city)


if __name__ == "__main__":
    main()
