"""
智能家居监测控制系统 - MQTT 客户端
负责：连接 Broker、订阅传感器数据、发布控制指令
"""
import json
import logging
import paho.mqtt.client as mqtt
from datetime import datetime

logger = logging.getLogger('mqtt_client')


class MqttClient:
    """MQTT 客户端封装"""

    def __init__(self, broker, port, client_id, topics, on_sensor_data=None):
        """
        :param broker:       Broker 地址
        :param port:         端口
        :param client_id:    客户端 ID
        :param topics:       订阅主题列表
        :param on_sensor_data: 传感器数据回调函数
        """
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.topics = topics
        self.on_sensor_data = on_sensor_data  # 外部回调

        self.client = mqtt.Client(client_id=client_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self.connected = False

    # ==================== 回调函数 ====================

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"✅ MQTT 连接成功: {self.broker}:{self.port}")
            # 订阅所有主题
            for topic in self.topics:
                client.subscribe(topic)
                logger.info(f"   订阅主题: {topic}")
        else:
            logger.error(f"❌ MQTT 连接失败，返回码: {rc}")

    def _on_message(self, client, userdata, msg):
        """收到消息"""
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            logger.debug(f"📩 收到消息 [{msg.topic}]: {payload}")

            # 传感器数据 → 调用外部回调
            if msg.topic == "sensor/env" and self.on_sensor_data:
                self.on_sensor_data(payload)

            # 设备状态回执
            elif msg.topic == "device/status":
                logger.info(f"📟 设备状态回执: {payload}")

        except json.JSONDecodeError:
            logger.warning(f"⚠️ 无法解析的消息: {msg.payload}")
        except Exception as e:
            logger.error(f"消息处理异常: {e}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logger.warning(f"⚠️ MQTT 意外断开，返回码: {rc}")
        else:
            logger.info("MQTT 正常断开")

    # ==================== 公开方法 ====================

    def connect(self):
        """连接 Broker 并启动后台线程"""
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()  # 后台线程，自动处理收发
            return True
        except Exception as e:
            logger.error(f"MQTT 连接异常: {e}")
            return False

    def publish(self, topic, data):
        """发布消息到指定主题"""
        try:
            payload = json.dumps(data)
            result = self.client.publish(topic, payload, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"📤 发布成功 [{topic}]: {data}")
                return True
            else:
                logger.warning(f"发布失败 [{topic}], rc={result.rc}")
                return False
        except Exception as e:
            logger.error(f"发布异常: {e}")
            return False

    def send_control(self, command, device_id="gateway_001", mode="manual"):
        """发送控制指令"""
        data = {
            "device_id": device_id,
            "command": command,          # open / close / fan_on / fan_off
            "mode": mode,                # auto / manual
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return self.publish("device/control", data)

    def disconnect(self):
        """断开连接"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT 已断开")


# ==================== 测试 ====================
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    def handle_sensor(data):
        print(f"🌡️ 温度: {data.get('temperature')}°C | 💧 湿度: {data.get('humidity')}%")

    mqtt_client = MqttClient(
        broker="121.40.171.160",
        port=1883,
        client_id="test_client",
        topics=["sensor/env", "device/status", "device/control"],
        on_sensor_data=handle_sensor
    )

    mqtt_client.connect()

    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        mqtt_client.disconnect()