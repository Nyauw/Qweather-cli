# weather_api.py - 天气查询功能模块
import requests


def get_weather(token, location_id, api_host="https://your_api_host"):
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


if __name__ == "__main__":
    # 单独测试天气查询功能
    TOKEN = "your_token"
    test_id = input("测试天气查询，请输入城市ID：")

    weather = get_weather(TOKEN, test_id)
    if weather:
        display_weather(weather)