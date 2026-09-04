# -*- coding: utf-8 -*-
"""
硬件网关配置文件
适配 Flask 后端: sensor/env 主题
"""

# ========== 串口配置 ==========
# Arduino 通过 USB 连接后，在设备管理器中查看 COM 口
# 虚拟串口测试: COM3↔COM4
SERIAL_PORT = "COM5"              # Windows: COMx, Linux: /dev/ttyUSB0
SERIAL_BAUDRATE = 9600            # 必须与 Arduino 代码一致
SERIAL_TIMEOUT = 1.0              # 读取超时（秒）

# ========== MQTT 配置 ==========
# 与 Flask 后端 config.py 中的 MQTT 配置一致
MQTT_BROKER = "121.40.171.160"    # 你的云服务器IP
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# MQTT 主题 (与 Flask 后端匹配)
MQTT_TOPIC_SENSOR = "sensor/env"      # 传感器数据上报
MQTT_TOPIC_CONTROL = "device/control" # 控制指令订阅
MQTT_TOPIC_STATUS = "device/status"   # 设备状态

# ========== 设备信息 ==========
DEVICE_ID = "gateway_001"              # 与 Flask config.py 一致

# ========== 数据采集 ==========
SAMPLE_INTERVAL = 2                    # 采样间隔（秒）
SERIAL_ENCODING = "utf-8"

# ========== 串口数据解析映射 ==========
# Arduino 发送格式: T:25.3,H:60.5,L:800,AL:0,LR:0,LG:0,LB:0,BZ:0
# 映射到 Flask 后端需要的字段
PARSER_FIELD_MAP = {
    "T": "temperature",    # 温度
    "H": "humidity",       # 湿度
    "L": "light",          # 光照
    "AL": "alert",         # 告警状态
    "LR": "led_red",       # 红色LED
    "LG": "led_green",     # 绿色LED
    "LB": "led_blue",    # 黄色LED (除湿器)  ← 新增
    "BZ": "buzzer"         # 蜂鸣器
}