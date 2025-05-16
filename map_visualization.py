import os
import folium
from PIL import Image
from io import BytesIO
import base64
import tempfile

def create_weather_map(location_data, weather_data):
    """
    创建天气地图可视化
    
    :param location_data: 位置数据字典，包含lat和lon字段
    :param weather_data: 天气数据字典
    :return: HTML文件路径
    """
    # 从位置数据中提取经纬度
    lat = float(location_data.get("lat", 0))
    lon = float(location_data.get("lon", 0))
    
    # 创建地图，以位置为中心
    weather_map = folium.Map(location=[lat, lon], zoom_start=10)
    
    # 获取天气信息
    now = weather_data.get("now", {})
    weather_text = now.get("text", "未知")
    temp = now.get("temp", "N/A")
    
    # 构建弹出信息
    popup_text = f"""
        <div style="font-family: Arial; width: 160px;">
            <h4 style="margin-bottom: 5px;">{location_data.get('name', '未知位置')}</h4>
            <p style="margin: 2px 0;">🌡️ 温度: {temp}°C</p>
            <p style="margin: 2px 0;">☁️ 天气: {weather_text}</p>
            <p style="margin: 2px 0;">💨 风向: {now.get('windDir', 'N/A')} {now.get('windScale', 'N/A')}级</p>
            <p style="margin: 2px 0;">💧 湿度: {now.get('humidity', 'N/A')}%</p>
        </div>
    """
    
    # 添加标记点
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(popup_text, max_width=200),
        tooltip=f"{location_data.get('name', '位置')} - {weather_text}, {temp}°C",
        icon=folium.Icon(icon="cloud", prefix="fa"),
    ).add_to(weather_map)
    
    # 保存到临时文件
    temp_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    weather_map.save(temp_file.name)
    
    return temp_file.name

def create_temperature_heatmap(city_list, weather_data_list):
    """
    创建温度热力图
    
    :param city_list: 城市列表，包含多个城市的位置数据
    :param weather_data_list: 对应城市的天气数据列表
    :return: HTML文件路径
    """
    # 查找中心位置（使用第一个城市或默认值）
    center_lat = float(city_list[0].get("lat", 35)) if city_list else 35
    center_lon = float(city_list[0].get("lon", 105)) if city_list else 105
    
    # 创建地图
    heat_map = folium.Map(location=[center_lat, center_lon], zoom_start=5)
    
    # 准备热力图数据
    heat_data = []
    for i, city in enumerate(city_list):
        if i < len(weather_data_list):
            weather = weather_data_list[i].get("now", {})
            lat = float(city.get("lat", 0))
            lon = float(city.get("lon", 0))
            temp = float(weather.get("temp", 0))
            
            # 温度值加入热力图数据 [lat, lon, intensity]
            heat_data.append([lat, lon, temp])
            
            # 同时添加标记点
            folium.Marker(
                location=[lat, lon],
                popup=f"{city.get('name', '未知')}: {temp}°C",
                tooltip=f"{city.get('name', '未知')}: {temp}°C"
            ).add_to(heat_map)
    
    # 添加热力图层
    folium.plugins.HeatMap(heat_data).add_to(heat_map)
    
    # 保存到临时文件
    temp_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    heat_map.save(temp_file.name)
    
    return temp_file.name

def html_to_png(html_file):
    """
    将HTML地图转换为PNG图像（需要外部工具如wkhtmltopdf）
    
    :param html_file: HTML文件路径
    :return: PNG图像的BytesIO对象或None
    """
    try:
        import webbrowser
        # 此功能需要使用外部工具实现
        # 简单实现是打开浏览器让用户查看
        webbrowser.open('file://' + os.path.abspath(html_file))
        return None
    except Exception as e:
        print(f"转换HTML到PNG失败: {e}")
        return None

def get_static_map_url(lat, lon, zoom=10, width=600, height=400):
    """
    生成第三方静态地图URL（回退方案）
    
    :param lat: 纬度
    :param lon: 经度
    :param zoom: 缩放级别
    :param width: 图像宽度
    :param height: 图像高度
    :return: 静态地图URL
    """
    # 使用OpenStreetMap静态地图
    return f"https://static-maps.yandex.ru/1.x/?ll={lon},{lat}&size={width},{height}&z={zoom}&l=map" 