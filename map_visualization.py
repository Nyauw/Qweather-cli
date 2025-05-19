import os
import folium
from folium import plugins  # 正确导入folium插件模块
from PIL import Image
from io import BytesIO
import base64
import tempfile
import importlib

# 检查plugins模块是否可用
HAS_PLUGINS = False
try:
    if hasattr(folium, 'plugins') or importlib.util.find_spec('folium.plugins'):
        HAS_PLUGINS = True
        if not hasattr(folium, 'plugins'):
            import folium.plugins
except:
    pass

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
    
    # 获取所有温度以便计算范围（仅用于标题显示）
    temps = []
    for i, city in enumerate(city_list):
        if i < len(weather_data_list):
            weather = weather_data_list[i].get("now", {})
            temp = float(weather.get("temp", 0))
            temps.append(temp)
    
    min_temp = min(temps) if temps else 0
    max_temp = max(temps) if temps else 0
    
    # 准备数据和标记
    for i, city in enumerate(city_list):
        if i < len(weather_data_list):
            weather = weather_data_list[i].get("now", {})
            lat = float(city.get("lat", 0))
            lon = float(city.get("lon", 0))
            temp = float(weather.get("temp", 0))
            
            # 获取更多天气数据
            weather_text = weather.get("text", "未知")
            humidity = weather.get("humidity", "未知")
            wind = f"{weather.get('windDir', '')} {weather.get('windScale', '')}级"
            
            # 构建详细的弹出信息
            popup_html = f"""
            <div style="width: 200px;">
                <h4 style="margin: 0 0 5px 0;">{city.get('name', '未知')} ({city.get('adm1', '')})</h4>
                <hr style="margin: 0 0 5px 0;">
                <p style="margin: 3px 0;"><b>🌡️ 温度:</b> {temp}°C</p>
                <p style="margin: 3px 0;"><b>☁️ 天气:</b> {weather_text}</p>
                <p style="margin: 3px 0;"><b>💧 湿度:</b> {humidity}%</p>
                <p style="margin: 3px 0;"><b>🌪️ 风力:</b> {wind}</p>
            </div>
            """
            
            # 根据绝对温度生成颜色
            color = get_color_for_temp(temp)
            
            # 使用带温度的标签
            tooltip = f"{city.get('name', '未知')}: {temp}°C"
            
            # 使用不同大小和颜色的圆圈表示温度
            folium.CircleMarker(
                location=[lat, lon],
                radius=8 + min(temp, 40)/5,  # 温度越高圆圈越大，但限制最大值
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=tooltip,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                weight=2
            ).add_to(heat_map)
            
            # 添加城市名称标签（显示城市名和温度）
            try:
                folium.map.Marker(
                    [lat, lon],
                    icon=folium.DivIcon(
                        icon_size=(150, 36),
                        icon_anchor=(75, 0),
                        html=f'<div style="font-size: 12px; font-weight: bold; text-shadow: 1px 1px 1px white; text-align: center; background: none; border: none;">{city.get("name")}<br/>{temp}°C</div>'
                    )
                ).add_to(heat_map)
            except Exception as e:
                print(f"添加城市标签失败: {e}")
    
    # 尝试使用plugins添加热力图（如果可用）
    if HAS_PLUGINS:
        try:
            heat_data = [[float(city.get("lat", 0)), float(city.get("lon", 0)), 
                        float(weather_data_list[i].get("now", {}).get("temp", 0))]
                        for i, city in enumerate(city_list) if i < len(weather_data_list)]
            
            # 使用绝对温度范围的渐变色
            gradient = {
                0.0: 'darkblue',  # <0°C
                0.1: 'blue',      # 0-10°C
                0.3: 'lightblue', # 10-18°C
                0.5: 'green',     # 18-25°C 
                0.7: 'orange',    # 25-32°C
                0.9: 'red'        # >32°C
            }
            
            if hasattr(folium, 'plugins'):
                folium.plugins.HeatMap(heat_data, radius=25, blur=15, 
                                    min_opacity=0.4, gradient=gradient).add_to(heat_map)
            else:
                folium.plugins.HeatMap(heat_data, radius=25, blur=15, 
                                    min_opacity=0.4, gradient=gradient).add_to(heat_map)
        except Exception as e:
            print(f"无法添加热力图层: {e}")
    
    # 添加图例
    add_temperature_legend(heat_map)
    
    # 添加地图标题
    title_html = f'''
    <div style="position: fixed; 
        top: 10px; left: 50px; right: 50px; 
        text-align: center;
        padding: 10px; 
        background-color: white; 
        border-radius: 5px;
        border: 2px solid grey;
        z-index: 9999;">
        <h3 style="margin: 0;">多城市温度对比图</h3>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">数据来源: 和风天气</p>
        <p style="margin: 0; font-size: 12px;">当前城市温度范围: {min_temp:.1f}°C ~ {max_temp:.1f}°C</p>
    </div>
    '''
    heat_map.get_root().html.add_child(folium.Element(title_html))
    
    # 保存到临时文件
    temp_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    heat_map.save(temp_file.name)
    
    return temp_file.name

def get_color_for_temp(temp):
    """
    根据绝对温度值生成颜色
    :param temp: 实际温度值（不是归一化的）
    :return: 对应的颜色
    """
    if temp < 0:
        return 'darkblue'  # 非常冷，零下温度
    elif temp < 10:
        return 'blue'     # 较冷 (0-10℃)
    elif temp < 18:
        return 'lightblue'  # 稍冷 (10-18℃)
    elif temp < 25:
        return 'green'    # 温和 (18-25℃)
    elif temp < 32:
        return 'orange'   # 较热 (25-32℃)
    else:
        return 'red'      # 非常热 (>32℃)

def add_temperature_legend(map_obj):
    """添加基于绝对温度的图例到地图"""
    legend_html = f'''
    <div style="position: fixed; 
        bottom: 50px; right: 50px; width: 180px; height: 180px; 
        border:2px solid grey; z-index:9999; font-size:14px;
        background-color: white; padding: 10px;
        border-radius: 5px;">
        <p style="margin-top: 0; margin-bottom: 5px;"><b>温度范围</b></p>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: darkblue; margin-right: 5px;"></div>
            <span>非常冷 (< 0°C)</span>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: blue; margin-right: 5px;"></div>
            <span>较冷 (0-10°C)</span>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: lightblue; margin-right: 5px;"></div>
            <span>稍冷 (10-18°C)</span>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: green; margin-right: 5px;"></div>
            <span>温和 (18-25°C)</span>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: orange; margin-right: 5px;"></div>
            <span>较热 (25-32°C)</span>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: red; margin-right: 5px;"></div>
            <span>非常热 (> 32°C)</span>
        </div>
    </div>
    '''
    map_obj.get_root().html.add_child(folium.Element(legend_html))

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