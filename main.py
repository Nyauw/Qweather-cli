# main.py
from dotenv import load_dotenv
import os
from geo_api import search_city, display_city_info, select_city, get_selected_city_data
from weather_api import get_weather, display_weather
from jwt_token import generate_qweather_token
import map_visualization

load_dotenv()

API_HOST = os.environ.get("API_HOST")


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

        # 获取完整城市数据（包含经纬度）
        city_data = get_selected_city_data(cities, location_id)
        
        # 查询天气
        weather_data = get_weather(token, location_id, API_HOST)
        if weather_data:
            # 显示天气信息
            display_weather(weather_data, city_data)
            
            # 询问是否查看地图
            show_map = input("\n是否查看天气地图？(y/n): ").strip().lower()
            if show_map == 'y':
                try:
                    print("正在生成天气地图，请稍候...")
                    map_file = map_visualization.create_weather_map(city_data, weather_data)
                    print(f"地图已生成，正在打开浏览器...")
                    map_visualization.html_to_png(map_file)
                except Exception as e:
                    print(f"生成地图时出错: {e}")
                    # 提供静态地图URL作为回退选项
                    lat, lon = city_data.get("lat", 0), city_data.get("lon", 0)
                    static_map_url = map_visualization.get_static_map_url(lat, lon)
                    print(f"您可以通过访问以下链接查看静态地图:\n{static_map_url}")


if __name__ == "__main__":
    main()
