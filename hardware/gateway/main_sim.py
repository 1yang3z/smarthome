# -*- coding: utf-8 -*-
"""
硬件网关 - 纯模拟模式（无需任何串口）
直接生成模拟数据发送到 MQTT
"""
import time
import random
import json
import paho.mqtt.client as mqtt

# ========== 配置 ==========
MQTT_BROKER = "121.40.171.160"
MQTT_PORT = 1883
MQTT_TOPIC_SENSOR = "sensor/env"
MQTT_TOPIC_CONTROL = "device/control"
DEVICE_ID = "gateway_001"


class SimMqttClient:
    def __init__(self):
        self.client = mqtt.Client(client_id=f"sim_gateway_{int(time.time())}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.connected = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print(f"✅ MQTT 连接成功: {MQTT_BROKER}:{MQTT_PORT}")
            self.client.subscribe(MQTT_TOPIC_CONTROL)
            print(f"📡 订阅主题: {MQTT_TOPIC_CONTROL}")
        else:
            print(f"❌ MQTT 连接失败, rc={rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            print(f"📩 收到控制指令: {payload}")
            command = payload.get('command')
            device_id = payload.get('device_id')
            if device_id == DEVICE_ID:
                print(f"🎯 执行指令: {command}")
                if command == 'open':
                    print("   ✅ 开窗 (模拟)")
                elif command == 'close':
                    print("   ✅ 关窗 (模拟)")
                elif command == 'alert_on':
                    print("   🚨 开启告警 (模拟)")
                elif command == 'alert_off':
                    print("   🔕 关闭告警 (模拟)")
        except Exception as e:
            print(f"消息处理异常: {e}")

    def connect(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"连接异常: {e}")
            return False

    def publish_sensor(self, temp, humid, light):
        payload = {
            "device_id": DEVICE_ID,
            "temperature": temp,
            "humidity": humid,
            "light": light
        }
        self.client.publish(MQTT_TOPIC_SENSOR, json.dumps(payload), qos=1)
        print(f"📤 发布: temp={temp}°C, humid={humid}%, light={light}lux")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()


def main():
    print("=" * 60)
    print("  🏠 智能家居硬件网关 - 纯模拟模式")
    print(f"  设备ID: {DEVICE_ID}")
    print("  数据流: 模拟生成 → MQTT → Flask")
    print("=" * 60)

    mqtt_client = SimMqttClient()
    if not mqtt_client.connect():
        print("❌ MQTT 连接失败，退出")
        return

    print("\n开始模拟数据采集... (按 Ctrl+C 退出)\n")

    try:
        count = 0
        while True:
            # 生成模拟数据（模拟真实环境变化）
            temp = round(22.0 + random.uniform(-3, 3), 1)
            humid = round(55.0 + random.uniform(-10, 10), 1)
            light = round(500 + random.uniform(-200, 200))

            mqtt_client.publish_sensor(temp, humid, light)
            count += 1

            time.sleep(3)  # 3秒一次

    except KeyboardInterrupt:
        print(f"\n🛑 已停止，共发送 {count} 条数据")
    finally:
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()