# 和风天气命令行查询工具

基于和风天气API开发的命令行天气查询工具，支持通过城市名称查询实时天气信息。

## 功能特性

- 🔍 模糊城市搜索（支持中文/拼音）
- 🌦️ 实时天气数据获取
- 🔐 自动JWT Token生成（EdDSA算法）
- 🗺️ 多级行政区划显示（省/市/）
- ⚡ 5分钟Token自动刷新

## 文件结构

```
Qweather-cli/
├── main.py          # 主程序入口
├── geo_api.py       # 城市搜索模块
├── weather_api.py   # 天气查询模块
├── jwt_token.py     # JWT生成模块
└── requirements.txt # 依赖列表
```

## 快速开始

### 前置要求

1. 注册和风天气账号：[开发者控制台](https://dev.qweather.com/)
2. 生成Ed25519密钥对：
```bash
openssl genpkey -algorithm ED25519 -out ed25519-private.pem \
&& openssl pkey -pubout -in ed25519-private.pem > ed25519-public.pem
```
3. 创建项目并上传`ed25519-public.pem`获取：
   - 项目ID (`sub` claim)
   - 凭据 ID (`kid` header)

### 安装步骤

1. 克隆仓库
   ```bash
   git clone https://github.com/Au403/Qweather-cli.git
   cd Qweather-cli
   ```

2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

3. 配置密钥
   ```bash
   # 将生成的私钥文件放入项目根目录
   cp /path/to/ed25519-private.pem ./
   ```

4. 修改配置
（编辑`.env`）


### 使用示例

```bash
# 启动程序
python main.py

# 交互示例
请输入城市名称 (q退出): 杭州

🔍 找到以下城市：
1. 杭州 (浙江省/杭州), 中国
2. 萧山 (浙江省/杭州), 中国
3. 桐庐 (浙江省/杭州), 中国
4. 淳安 (浙江省/杭州), 中国
5. 建德 (浙江省/杭州), 中国

请选择城市编号（1-5）: 1

🌆 城市：杭州 (浙江省)
🕒 观测时间：2025-04-08T20:50+08:00
🌡 温度：23℃ (体感 23℃)
🌈 天气：多云 (151)
🌪 风力：东南风 1级
💧 湿度：40%
👁 能见度：15公里
📡 数据源：QWeather
```

## 依赖项

- Python
- requests
- PyJWT
- cryptography


## 授权许可

本项目基于 [MIT License](LICENSE) 发布，使用API数据请遵守[和风天气开发者协议](https://dev.qweather.com/docs/terms/)。

## 相关资源

- [和风天气开发文档](https://dev.qweather.com/docs/)
- [JWT生成指南](https://dev.qweather.com/docs/configuration/authentication/)
- [API错误码说明](https://dev.qweather.com/docs/resource/error-code/)