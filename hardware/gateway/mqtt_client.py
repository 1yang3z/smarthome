# -*- coding: utf-8 -*-
"""
MQTT 客户端模块
发布数据到 Flask 后端订阅的 MQTT Broker
"""
import json
import time
import paho.mqtt.client as mqtt
from queue import Queue
from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE,
    MQTT_TOPIC_SENSOR, MQTT_TOPIC_CONTROL, MQTT_TOPIC_STATUS,
    DEVICE_ID
)


class MqttClient:
    """MQTT 客户端"""

    def __init__(self, broker=MQTT_BROKER, port=MQTT_PORT, keepalive=MQTT_KEEPALIVE):
        self.broker = broker
        self.port = port
        self.keepalive = keepalive
        self.client_id = f"hw_gateway_{DEVICE_ID}_{int(time.time())}"
        self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.connected = False
        self.command_queue = Queue()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print(f"[MQTT] ✅ 已连接到 Broker: {self.broker}:{self.port}")
            # 订阅控制主题 (接收 Flask 后端下发的指令)
            self.client.subscribe(MQTT_TOPIC_CONTROL)
            print(f"[MQTT] 📡 订阅主题: {MQTT_TOPIC_CONTROL}")
        else:
            print(f"[MQTT] ❌ 连接失败，返回码: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            print(f"[MQTT] ⚠️ 意外断开，将自动重连")

    def _on_message(self, client, userdata, msg):
        """收到 MQTT 消息"""
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            print(f"[MQTT] 📩 收到消息 [{topic}]: {payload}")

            # 控制指令放入队列
            if topic == MQTT_TOPIC_CONTROL:
                self.command_queue.put(payload)
        except Exception as e:
            print(f"[MQTT] 消息解析失败: {e}")

    def connect(self):
        """连接 MQTT Broker"""
        try:
            self.client.connect(self.broker, self.port, self.keepalive)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"[MQTT] 连接异常: {e}")
            return False

    def disconnect(self):
        """断开 MQTT 连接"""
        self.client.loop_stop()
        self.client.disconnect()
        print("[MQTT] 已断开连接")

    def publish_sensor_data(self, temperature, humidity, light=None, device_id=None):
        """
        发布传感器数据到 Flask 后端
        主题: sensor/env
        格式: {"device_id": "gateway_001", "temperature": 25.3, "humidity": 60.5, "light": 800}
        """
        payload = {
            "device_id": device_id or DEVICE_ID,
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1)
        }
        if light is not None:
            payload["light"] = int(light)

        json_payload = json.dumps(payload, ensure_ascii=False)
        result = self.client.publish(MQTT_TOPIC_SENSOR, json_payload, qos=1)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT] 📤 发布成功 [{MQTT_TOPIC_SENSOR}]: temp={temperature}°C, humi={humidity}%")
        else:
            print(f"[MQTT] ❌ 发布失败, rc={result.rc}")
        return result.rc

    def publish_status(self, online=True, device_id=None):
        """发布设备状态"""
        payload = {
            "device_id": device_id or DEVICE_ID,
            "online": online,
            "timestamp": int(time.time())
        }
        json_payload = json.dumps(payload)
        self.client.publish(MQTT_TOPIC_STATUS, json_payload, qos=1, retain=True)
        print(f"[MQTT] 📡 状态更新: online={online}")

    def publish_command_ack(self, command, result="ok", message=""):
        """发布命令应答"""
        payload = {
            "device_id": DEVICE_ID,
            "command": command,
            "result": result,
            "message": message,
            "timestamp": int(time.time())
        }
        json_payload = json.dumps(payload, ensure_ascii=False)
        topic = f"{MQTT_TOPIC_CONTROL}/ack"
        self.client.publish(topic, json_payload, qos=1)
        print(f"[MQTT] 📤 命令应答: {command} -> {result}")

    def get_pending_command(self):
        """获取待处理的命令（非阻塞）"""
        try:
            return self.command_queue.get_nowait()
        except:
            return None

    # mqtt_client.py - 修改 send_control_to_arduino 方法

    def send_control_to_arduino(self, command, params=None):
        """
        将 MQTT 控制指令转换为串口指令发送给 Arduino
        """
        cmd_map = {
            # 窗户控制 → 绿色LED (LG)
            "open": "CMD:LG:255\r\n",
            "close": "CMD:LG:0\r\n",

            # 空调控制 → 红色LED (LR)
            "ac_on": "CMD:LR:255\r\n",
            "ac_off": "CMD:LR:0\r\n",

            # 除湿器/风扇 → 蓝色LED (LB)
            "fan_on": "CMD:LB:255\r\n",
            "fan_off": "CMD:LB:0\r\n",

            # 告警控制 → 红色LED + 蜂鸣器
            "alert_on": "CMD:LR:255,AL:1,BZ:255\r\n",
            "alert_off": "CMD:LR:0,AL:0,BZ:0\r\n",

            # 通用开/关
            "on": "CMD:LG:255\r\n",
            "off": "CMD:LG:0\r\n",
        }
        return cmd_map.get(command)

        # 如果命令包含设备ID，可以进一步细化
        if params and params.get("device_type"):
            device_type = params.get("device_type")
            if device_type == "light":
                return cmd_map.get(f"light_{command}")
            elif device_type == "ac":
                return cmd_map.get(f"ac_{command}")
            elif device_type == "humidifier":
                return cmd_map.get(f"humidifier_{command}")
            elif device_type == "fan":
                return cmd_map.get(f"fan_{command}")

        return cmd_map.get(command)


if __name__ == "__main__":
    # 测试 MQTT 连接
    mqtt = MqttClient()
    if mqtt.connect():
        mqtt.publish_status(online=True)
        mqtt.publish_sensor_data(25.3, 60.5, 800)
        time.sleep(1)
        mqtt.disconnect()
    else:
        print("MQTT 连接失败")