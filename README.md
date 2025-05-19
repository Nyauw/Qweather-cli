# QWeather CLI Tool

A command-line weather query tool based on QWeather API that supports real-time weather information retrieval by city name.

[中文文档](README_CN.md) | English

## Features

- 🔍 Fuzzy city search (supporting Chinese/Pinyin)
- 🌦️ Real-time weather data retrieval
- 🔐 Automatic JWT Token generation (EdDSA algorithm)
- 🗺️ Multi-level administrative division display (Province/City)
- 📍 Weather map visualization (CLI interface only, based on folium/Leaflet)
- 🌡️ Temperature heatmap generation (CLI interface only)
- 📊 Multi-city weather data comparison
- ⚡ 5-minute Token auto-refresh

## File Structure

```
Qweather-cli/
├── main.py                # Main program entry
├── geo_api.py             # City search module
├── weather_api.py         # Weather query module
├── jwt_token.py           # JWT generation module
├── map_visualization.py   # Map visualization module 
├── weather_assistant_bot.py # Weather bot module
└── requirements.txt       # Dependencies list
```

## Quick Start

### Prerequisites

1. Register a QWeather account: [Developer Console](https://dev.qweather.com/)
2. Generate Ed25519 key pair:
```bash
openssl genpkey -algorithm ED25519 -out ed25519-private.pem \
&& openssl pkey -pubout -in ed25519-private.pem > ed25519-public.pem
```
3. Create a project and upload `ed25519-public.pem` to obtain:
   - Project ID (`sub` claim)
   - Credential ID (`kid` header)

### Installation Steps

1. Clone the repository
   ```bash
   git clone https://github.com/Au403/Qweather-cli.git
   cd Qweather-cli
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Configure private key
   ```bash
   # Place your generated private key in the project root directory
   cp /path/to/ed25519-private.pem ./
   ```

4. Modify configuration
   (Edit `.env` file)

### Usage Examples

```bash
# Start the program
python main.py

# Single city query example
Select function (1/2/q): 1
Enter city name (b to return): Beijing

🔍 Cities found:
1. Beijing (Beijing/Beijing), China
2. Dongcheng (Beijing/Beijing), China
3. Xicheng (Beijing/Beijing), China
4. Chaoyang (Beijing/Beijing), China
5. Haidian (Beijing/Beijing), China

Select city number (1-5): 1

🌆 City: Beijing (Beijing)
🕒 Observation time: 2025-04-08T20:50+08:00
🌡 Temperature: 18°C (feels like 16°C)
🌈 Weather: Sunny (0)
🌪 Wind: Northwest 3
💧 Humidity: 35%
👁 Visibility: 25km
📡 Data source: QWeather

View weather map? (y/n): y
Generating weather map, please wait...
Map generated, opening in browser...
```

```bash
# Multi-city comparison example
Select function (1/2/q): 2
Enter multiple city names, separated by commas (b to return): Beijing,Shanghai,Guangzhou

🔍 Searching city: Beijing
🔍 Cities found:
1. Beijing (Beijing/Beijing), China
2. Dongcheng (Beijing/Beijing), China
3. Xicheng (Beijing/Beijing), China
4. Chaoyang (Beijing/Beijing), China
5. Haidian (Beijing/Beijing), China
Select city number (1-5) or enter q to exit: 1

...

📊 Multi-city Weather Comparison
+---------------+--------+-------------+-------------+------------+---------------+---------+---------------+
| City          | Weather| Temp(°C)    | Feels like(°C)| Humidity(%)| Wind          | Level  | Visibility(km)|
+---------------+--------+-------------+-------------+------------+---------------+---------+---------------+
| Beijing       | Sunny  | 18          | 16          | 35         | Northwest     | 3      | 25            |
| Shanghai      | Cloudy | 22          | 24          | 65         | Southeast     | 2      | 20            |
| Guangzhou     | Showers| 26          | 28          | 80         | East          | 1      | 12            |
+---------------+--------+-------------+-------------+------------+---------------+---------+---------------+

🕒 Observation time: 2025-04-08T20:50+08:00
📡 Data source: QWeather

View temperature heatmap? (y/n): y
Generating temperature heatmap, please wait...
Heatmap generated, opening in browser...
```

```bash
# Telegram bot usage example
/start - Start using the bot
/setcity Beijing - Set your city
/weather - Get current weather information
/compare Beijing,Shanghai,Guangzhou - Compare multiple cities' weather
```

## Dependencies

- Python
- requests
- PyJWT
- cryptography
- folium
- tabulate

## License

This project is released under the [MIT License](LICENSE). When using the API data, please comply with the [QWeather Developer Agreement](https://dev.qweather.com/docs/terms/).

## Resources

- [QWeather Developer Documentation](https://dev.qweather.com/docs/)
- [JWT Generation Guide](https://dev.qweather.com/docs/configuration/authentication/)
- [API Error Code Reference](https://dev.qweather.com/docs/resource/error-code/)