"""
和风天气 API 服务
"""
import requests
import time
from datetime import datetime


class WeatherService:
    """和风天气服务"""

    API_KEY = "c81b799616ca402fa62993cebab5d3f4"
    BASE_URL = "https://mm36x8ayq8.re.qweatherapi.com/v7"

    def __init__(self, city_id="101031100"):
        self.city_id = city_id
        self.last_update = 0
        self.update_interval = 300
        self.cache = {}

    def get_current_weather(self):
        now = time.time()
        if now - self.last_update < self.update_interval and self.cache:
            return self.cache

        try:
            url = f"{self.BASE_URL}/weather/now"
            params = {
                "location": self.city_id,
                "key": self.API_KEY
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if data.get("code") == "200":
                now_data = data["now"]
                self.cache = {
                    "success": True,
                    "temperature": now_data["temp"],
                    "feels_like": now_data["feelsLike"],
                    "condition": now_data["text"],
                    "wind_dir": now_data["windDir"],
                    "wind_scale": now_data["windScale"],
                    "humidity": now_data["humidity"],
                    "icon": now_data["icon"],
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.last_update = now
            else:
                self.cache = {"success": False, "error": f"API错误: {data}"}

        except Exception as e:
            self.cache = {"success": False, "error": str(e)}

        return self.cache


CITY_IDS = {
    "天津": "101030100",
    "滨海新区": "101031100",
    "北京": "101010100",
    "上海": "101020100",
    "杭州": "101210101"
}