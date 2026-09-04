"""
智能家居监测控制系统 - 全局配置
"""
import urllib.parse


class Config:
    # ==================== MQTT 配置 ====================
    MQTT_BROKER = "121.40.171.160"
    MQTT_BROKER = os.environ.get('MQTT_BROKER', '127.0.0.1')
    MQTT_PORT = int(os.environ.get('MQTT_PORT', 1883))
    MQTT_TOPIC_SENSOR = "sensor/env"
    MQTT_TOPIC_CONTROL = "device/control"
    MQTT_TOPIC_STATUS = "device/status"
    MQTT_CLIENT_ID = os.environ.get('MQTT_CLIENT_ID', 'flask_server')

    # ==================== MySQL 配置 ====================
    DB_HOST = "121.40.171.160"
    DB_PORT = 3306
    DB_USER = "smarthome"
    DB_PASSWORD = "SmartDB@2026"
    DB_NAME = "smart_home"

    # URL 编码密码（处理 @ 等特殊字符）
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{urllib.parse.quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # ==================== Flask 配置 ====================
    SECRET_KEY = "smart-home-secret-key-2026"
    DEBUG = True

    # ==================== 设备配置 ====================
    DEVICE_ID = "gateway_001"

    # ==================== 阈值配置 ====================
    TEMP_HIGH = 30.0
    TEMP_LOW = 20.0
    HUMIDITY_HIGH = 75.0
    HUMIDITY_LOW = 40.0
    LIGHT_HIGH = 1000.0  # 🆕 光照过强
    LIGHT_LOW = 200.0  # 🆕 光照过弱
    # ==================== 告警等级说明 ====================
    ALERT_LEVELS = {
        "danger": "严重告警 — 自动触发设备控制",
        "critical": "重要告警 — 建议处理",
        "warning": "提醒告警 — 仅记录"
    }

    # ==================== 设备控制映射 ====================
    # 严重告警 → 自动控制设备
    DEVICE_AUTO_RULES = {
        "temp_high_danger": ("air_conditioner", "on"),  # 温度严重过高 → 开空调
        "temp_low_danger": ("air_conditioner", "on"),  # 温度严重过低 → 开空调(制热)
        "humidity_high_danger": ("dehumidifier", "on"),  # 湿度严重过高 → 开除湿器
        "light_high_danger": ("window", "close"),  # 光照过强 → 关窗
        "light_low_danger": ("window", "open")  # 光照过弱 → 开窗
    }
    # ==================== 预测模型配置 ====================
    MODEL_PATH = "model/temp_humidity_model.pkl"
    PREDICT_HOURS = 6