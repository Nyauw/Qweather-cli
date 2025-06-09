# main.py
from dotenv import load_dotenv
import os
from geo_api import search_city, display_city_info, select_city, get_selected_city_data, select_multiple_cities
from weather_api import get_weather, display_weather, display_multiple_weather, get_weather_warning, display_weather_warning, display_multiple_weather_warnings
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
        print("\n选择查询模式:")
        print("1. 单城市查询")
        print("2. 多城市查询")
        print("3. 天气灾害预警查询")
        print("q. 退出程序")
        
        mode = input("请选择功能 (1/2/3/q): ").strip().lower()
        
        if mode == 'q':
            break
        elif mode == '1':
            single_city_query(token)
        elif mode == '2':
            multiple_cities_query(token)
        elif mode == '3':
            warning_query(token)
        else:
            print("❌ 无效选择，请重新输入")


def single_city_query(token):
    """单城市天气查询"""
    # 用户输入
    keyword = input("\n🏙 请输入城市名称 (b返回): ").strip()
    if keyword.lower() == "b":
        return

    # 搜索城市
    cities = search_city(token, keyword, API_HOST)
    if not cities:
        print("没有找到相关城市")
        return

    # 显示并选择城市
    display_city_info(cities)
    location_id = select_city(cities)
    if not location_id:
        return

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


def warning_query(token):
    """天气灾害预警查询"""
    # 用户输入
    keywords = input("\n🏙 请输入一个或多个城市名称，用逗号分隔 (b返回): ").strip()
    if keywords.lower() == "b":
        return
    
    city_names = [name.strip() for name in keywords.split(",") if name.strip()]
    if not city_names:
        print("❌ 未输入有效城市名称")
        return

    selected_cities = []
    warning_data_list = []

    # 处理每个输入的城市名称
    for i, city_name in enumerate(city_names):
        print(f"\n🔍 正在搜索城市: {city_name} ({i+1}/{len(city_names)})")
        cities = search_city(token, city_name, API_HOST)
        
        if not cities:
            print(f"❌ 未找到城市: {city_name}")
            continue
        
        # 如果只找到一个城市，直接选择
        if len(cities) == 1:
            city_data = cities[0]
            print(f"✅ 自动选择唯一匹配城市: {city_data['name']} ({city_data['adm1']})")
        else:
            # 找到多个城市，让用户选择
            display_city_info(cities)
            location_id = select_city(cities)
            if not location_id:
                continue
            city_data = get_selected_city_data(cities, location_id)

        if city_data:
            selected_cities.append(city_data)
            # 获取天气预警数据
            print(f"📜 正在获取 {city_data['name']} 的天气灾害预警...")
            warning_data = get_weather_warning(token, city_data["id"])
            if warning_data:
                warning_data_list.append(warning_data)
            else:
                print(f"❌ 获取 {city_data['name']} 的天气灾害预警失败")

    # 根据查询的城市数量，选择不同的显示方式
    if not selected_cities:
        print("❌ 未选择任何城市，无法查询预警")
        return

    if len(selected_cities) == 1:
        display_weather_warning(warning_data_list[0], selected_cities[0])
    else:
        display_multiple_weather_warnings(warning_data_list, selected_cities)


def multiple_cities_query(token):
    """多城市天气查询"""
    # 用户输入
    keywords = input("\n🏙 请输入多个城市名称，用逗号分隔 (b返回): ").strip()
    if keywords.lower() == "b":
        return
    
    city_names = [name.strip() for name in keywords.split(",") if name.strip()]
    if not city_names:
        print("❌ 未输入有效城市名称")
        return
    
    # 询问用户查询模式
    print("\n选择查询模式:")
    print("1. 自动选择匹配度最高的城市 (快速模式)")
    print("2. 逐个城市手动选择 (精确模式)")
    
    query_mode = input("请选择模式 (1/2): ").strip()
    
    # 存储所有选中的城市数据和天气数据
    selected_cities = []
    weather_data_list = []
    
    # 自动选择模式
    if query_mode == "1":
        for i, city_name in enumerate(city_names):
            print(f"\n🔍 正在搜索城市: {city_name} ({i+1}/{len(city_names)})")
            cities = search_city(token, city_name, API_HOST)
            
            if not cities:
                print(f"❌ 未找到城市: {city_name}")
                continue
            
            # 自动选择第一个城市（通常是匹配度最高的）
            city_data = cities[0]
            selected_cities.append(city_data)
            
            print(f"✅ 自动选择: {city_data['name']} ({city_data['adm1']})")
            
            # 获取天气数据
            print(f"🌤️ 正在获取 {city_data['name']} 的天气数据...")
            weather_data = get_weather(token, city_data["id"], API_HOST)
            if weather_data:
                weather_data_list.append(weather_data)
            else:
                print(f"❌ 获取 {city_data['name']} 的天气数据失败")
    
    # 手动选择模式
    elif query_mode == "2":
        # 处理每个输入的城市名称
        for i, city_name in enumerate(city_names):
            print(f"\n🔍 正在搜索城市: {city_name} ({i+1}/{len(city_names)})")
            cities = search_city(token, city_name, API_HOST)
            
            if not cities:
                print(f"❌ 未找到城市: {city_name}")
                continue
            
            # 如果只找到一个城市，直接选择
            if len(cities) == 1:
                city_data = cities[0]
                print(f"✅ 自动选择唯一匹配城市: {city_data['name']} ({city_data['adm1']})")
                selected_cities.append(city_data)
                
                # 获取天气数据
                print(f"🌤️ 正在获取 {city_data['name']} 的天气数据...")
                weather_data = get_weather(token, city_data["id"], API_HOST)
                if weather_data:
                    weather_data_list.append(weather_data)
                else:
                    print(f"❌ 获取 {city_data['name']} 的天气数据失败")
            else:
                # 找到多个城市，显示选项
                display_city_info(cities)
                
                # 提供两种选择方式
                choice_mode = input("选择方式：1.选择一个城市 2.批量选择城市 (1/2): ").strip()
                
                if choice_mode == "1":
                    # 单个选择
                    location_id = select_city(cities)
                    if not location_id:
                        continue
                    
                    city_data = get_selected_city_data(cities, location_id)
                    selected_cities.append(city_data)
                    
                    # 获取天气数据
                    print(f"🌤️ 正在获取 {city_data['name']} 的天气数据...")
                    weather_data = get_weather(token, location_id, API_HOST)
                    if weather_data:
                        weather_data_list.append(weather_data)
                    else:
                        print(f"❌ 获取 {city_data['name']} 的天气数据失败")
                elif choice_mode == "2":
                    # 批量选择
                    location_ids = select_multiple_cities(cities)
                    for loc_id in location_ids:
                        city_data = get_selected_city_data(cities, loc_id)
                        if city_data:
                            selected_cities.append(city_data)
                            
                            # 获取天气数据
                            print(f"🌤️ 正在获取 {city_data['name']} 的天气数据...")
                            weather_data = get_weather(token, loc_id, API_HOST)
                            if weather_data:
                                weather_data_list.append(weather_data)
                            else:
                                print(f"❌ 获取 {city_data['name']} 的天气数据失败")
                else:
                    print("❌ 无效选择，跳过当前城市")
    else:
        print("❌ 无效模式选择，返回主菜单")
        return
    
    # 如果找到了城市，显示结果
    if selected_cities:
        print(f"\n✅ 已查询 {len(selected_cities)} 个城市的天气数据")
        # 显示多城市天气对比
        display_multiple_weather(weather_data_list, selected_cities)
        
        # 询问用户是否查看温度热力图
        if len(selected_cities) >= 2:
            show_heatmap = input("\n是否查看温度热力图？(y/n): ").strip().lower()
            if show_heatmap == 'y':
                try:
                    print("正在生成温度热力图，请稍候...")
                    heatmap_file = map_visualization.create_temperature_heatmap(selected_cities, weather_data_list)
                    print(f"热力图已生成，正在打开浏览器...")
                    map_visualization.html_to_png(heatmap_file)
                except Exception as e:
                    print(f"生成热力图时出错: {e}")
    else:
        print("❌ 未选择任何城市，无法显示天气")


if __name__ == "__main__":
    main()
