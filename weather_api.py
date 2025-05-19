# weather_api.py - 天气查询功能模块
import requests
import os
from dotenv import load_dotenv
from tabulate import tabulate
load_dotenv()

def get_weather(token, location_id, api_host=os.environ.get("API_HOST")):
    """
    获取实时天气数据
    :param token: API密钥
    :param location_id: 城市ID
    :param api_host: API主机地址
    :return: 天气数据字典或None
    """
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{api_host}/v7/weather/now",
            headers=headers,
            params={"location": location_id},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()

        if data["code"] == "200":
            return data
        print(f"⚠️ 天气查询失败：{data.get('code', '未知错误')}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"🔌 请求异常：{e}")
        return None


def display_weather(weather_data, city_info=None):
    """
    显示天气信息
    :param weather_data: 天气数据字典
    :param city_info: 可选的城市信息
    """
    if city_info:
        print(f"\n🌆 城市：{city_info['name']} ({city_info['adm1']})")

    now = weather_data["now"]
    print(f"🕒 观测时间：{now['obsTime']}")
    print(f"🌡 温度：{now['temp']}℃ (体感 {now['feelsLike']}℃)")
    print(f"🌈 天气：{now['text']} ({now['icon']})")
    print(f"🌪 风力：{now['windDir']} {now['windScale']}级")
    print(f"💧 湿度：{now['humidity']}%")
    print(f"👁 能见度：{now['vis']}公里")
    print(f"📡 数据源：{' | '.join(weather_data['refer']['sources'])}")


def display_multiple_weather(weather_data_list, city_info_list):
    """
    以表格形式显示多个城市的天气对比
    :param weather_data_list: 多个城市的天气数据列表
    :param city_info_list: 多个城市的信息列表
    """
    if not weather_data_list or not city_info_list:
        print("❌ 没有可显示的天气数据")
        return
    
    # 表头
    headers = ["城市", "天气", "温度(℃)", "体感温度(℃)", "湿度(%)", "风向", "风力(级)", "能见度(km)"]
    table_data = []
    
    # 准备表格数据
    for i, weather_data in enumerate(weather_data_list):
        if i >= len(city_info_list):
            break
            
        city = city_info_list[i]
        city_name = f"{city['name']} ({city['adm1']})"
        
        now = weather_data["now"]
        row = [
            city_name,
            now['text'],
            now['temp'],
            now['feelsLike'],
            now['humidity'],
            now['windDir'],
            now['windScale'],
            now['vis']
        ]
        table_data.append(row)
    
    # 打印表格
    print("\n📊 多城市天气对比")
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # 显示观测时间
    if weather_data_list:
        print(f"\n🕒 观测时间：{weather_data_list[0]['now']['obsTime']}")
        print(f"📡 数据源：{' | '.join(weather_data_list[0]['refer']['sources'])}")


if __name__ == "__main__":
    # 单独测试天气查询功能
    TOKEN = "your_token"
    test_id = input("测试天气查询，请输入城市ID：")

    weather = get_weather(TOKEN, test_id)
    if weather:
        display_weather(weather)