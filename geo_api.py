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


def get_selected_city_data(cities, location_id):
    """
    获取选中城市的完整数据
    :param cities: 城市数据列表
    :param location_id: 选中的城市ID
    :return: 完整城市数据字典
    """
    for city in cities:
        if city["id"] == location_id:
            return city
    return None


def select_multiple_cities(cities):
    """
    用户选择多个城市
    :param cities: 城市数据列表
    :return: 选择的城市ID列表
    """
    selected_ids = []
    print(f"请选择城市编号(1-{len(cities)})，多个城市用逗号分隔，输入完成后按回车:")
    print("输入 'a' 选择所有城市，输入 'q' 退出选择")
    
    while True:
        choice = input("你的选择: ").strip().lower()
        
        if choice == 'q':
            return [] if not selected_ids else selected_ids
        
        if choice == 'a':
            return [city["id"] for city in cities]
        
        try:
            # 处理逗号分隔的多个选择
            selections = [int(num.strip()) for num in choice.split(",")]
            valid_selections = []
            
            for sel in selections:
                if 1 <= sel <= len(cities):
                    city_id = cities[sel - 1]["id"]
                    if city_id not in selected_ids:
                        selected_ids.append(city_id)
                        valid_selections.append(sel)
                else:
                    print(f"忽略无效选择: {sel}")
            
            if valid_selections:
                city_names = ", ".join([cities[i-1]["name"] for i in valid_selections])
                print(f"已选择: {city_names}")
                
                add_more = input("是否继续添加更多城市? (y/n): ").strip().lower()
                if add_more != 'y':
                    return selected_ids
            else:
                print("未做有效选择，请重试")
                
        except ValueError:
            print("输入格式错误，请输入数字或用逗号分隔多个数字")


if __name__ == "__main__":
    # 单独测试城市搜索功能
    TOKEN = "your_token"
    test_city = input("测试城市搜索，请输入城市名称：")

    result = search_city(TOKEN, test_city)
    if result:
        display_city_info(result)
        city_id = select_city(result)
        print(f"选中的城市ID: {city_id}")
        
        # 测试获取完整城市数据
        if city_id:
            city_data = get_selected_city_data(result, city_id)
            print(f"城市经纬度: {city_data.get('lat')}, {city_data.get('lon')}")