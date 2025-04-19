# geo_api.py - 城市搜索功能模块
import requests
import os
from dotenv import load_dotenv
load_dotenv()

def search_city(token, keyword, api_host=os.environ.get("API_HOST"), adm=None, number=5):
    """
    城市搜索API封装
    :param token: API密钥
    :param keyword: 搜索关键词
    :param api_host: API主机地址
    :param adm: 上级行政区划过滤
    :param number: 返回结果数量
    :return: 城市列表或None
    """
    params = {
        "location": keyword,
        "adm": adm,
        "number": number,
        "lang": "zh"
    }

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{api_host}/geo/v2/city/lookup",
            headers=headers,
            params=params,
            timeout=5
        )
        response.raise_for_status()
        data = response.json()

        if data["code"] == "200" and data.get("location"):
            return data["location"]
        print(f"⚠️ 城市搜索失败：{data.get('code', '未知错误')}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"🔌 请求异常：{e}")
        return None


def display_city_info(cities):
    """
    显示城市信息列表
    :param cities: 城市数据列表
    """
    print("\n🔍 找到以下城市：")
    for idx, city in enumerate(cities, 1):
        admin_info = f"{city['adm1']}/{city['adm2']}" if city['adm1'] != city['adm2'] else city['adm1']
        print(f"{idx}. {city['name']} ({admin_info}), {city['country']}")


def select_city(cities):
    """
    用户选择城市
    :param cities: 城市数据列表
    :return: 选择的城市ID或None
    """
    while True:
        try:
            choice = input(f"请选择城市编号 (1-{len(cities)}) 或输入q退出: ").strip()
            if choice.lower() == 'q':
                return None

            choice = int(choice)
            if 1 <= choice <= len(cities):
                return cities[choice - 1]["id"]
            print("输入超出范围，请重新选择")

        except ValueError:
            print("请输入有效数字")


if __name__ == "__main__":
    # 单独测试城市搜索功能
    TOKEN = "your_token"
    test_city = input("测试城市搜索，请输入城市名称：")

    result = search_city(TOKEN, test_city)
    if result:
        display_city_info(result)
        city_id = select_city(result)
        print(f"选中的城市ID: {city_id}")