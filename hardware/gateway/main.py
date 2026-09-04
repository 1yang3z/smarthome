# -*- coding: utf-8 -*-
"""
硬件网关主入口
数据流: Arduino → 串口 → 解析 → MQTT → Flask 后端
"""
import time
import signal
import sys
from config import DEVICE_ID, SAMPLE_INTERVAL
from serial_reader import SerialReader
from data_parser import DataParser
from mqtt_client import MqttClient


class HardwareGateway:
    """硬件网关"""

    def __init__(self):
        self.reader = SerialReader()
        self.parser = DataParser()
        self.mqtt = MqttClient()
        self.running = False
        self.simulation_mode = False
        # ===== 设备状态跟踪 =====
        self.device_states = {
            "window": "closed",  # 窗户: open/closed
            "ac": "off",  # 空调: on/off
            "light": "off",  # 灯光: on/off
            "fan": "off",  # 风扇: on/off
            "humidifier": "off",  # 加湿器: on/off
            "alert": "off"  # 告警: on/off
        }

    def start(self):
        """启动网关"""
        print("=" * 60)
        print("  🏠 智能家居硬件网关 v2.0")
        print(f"  设备ID: {DEVICE_ID}")
        print("  数据流: Arduino → 串口 → MQTT → Flask")
        print("=" * 60)

        # 连接 MQTT
        if not self.mqtt.connect():
            print("[网关] ❌ MQTT 连接失败")
            return False

        self.mqtt.publish_status(online=True)
        print("[网关] ✅ 已发布上线状态")

        # 启动串口
        if not self.reader.start():
            print("[网关] ⚠️ 串口打开失败，切换到模拟模式")
            self.simulation_mode = True
        else:
            self.simulation_mode = False

        self.running = True
        return True

    def stop(self):
        """停止网关"""
        self.running = False
        if not self.simulation_mode:
            self.reader.stop()
        self.mqtt.publish_status(online=False)
        self.mqtt.disconnect()
        print("[网关] 已安全关闭")

    def _process_serial_data(self, line):
        """处理串口数据"""
        parsed = self.parser.parse(line)
        if not self.parser.validate(parsed):
            print(f"[串口] ⚠️ 数据不完整: {line}")
            return

        temperature = parsed.get("temperature")
        humidity = parsed.get("humidity")
        light = parsed.get("light")

        # 发布到 MQTT (Flask 后端)
        self.mqtt.publish_sensor_data(temperature, humidity, light)

    # main.py - 修改 _process_command 方法

    def _process_command(self, cmd):
        """处理 MQTT 控制指令"""
        command = cmd.get("command")
        device_id = cmd.get("device_id", "unknown")
        params = cmd.get("params", {})  # 获取额外参数

        print(f"[命令] 📨 目标: {device_id}, 指令: {command}, 参数: {params}")

        # 只处理本设备的指令，或者处理广播指令（device_id = "all"）
        if device_id != DEVICE_ID and device_id != "all":
            print(f"[命令] ⚠️ 目标设备不匹配，忽略")
            return

        # ---- 显示执行状态 ----
        status_map = {
            "open": "打开",
            "close": "关闭",
            "on": "开启",
            "off": "关闭",
            "alert_on": "开启告警",
            "alert_off": "关闭告警",
            "fan_on": "开启风扇",
            "fan_off": "关闭风扇",
            "light_on": "开启灯光",
            "light_off": "关闭灯光",
            "ac_on": "开启空调",
            "ac_off": "关闭空调"
        }
        status = status_map.get(command, command)
        print(f"[命令] 🎯 执行: {status}")

        # ---- 获取串口指令 ----
        serial_cmd = self.mqtt.send_control_to_arduino(command, params)

        if serial_cmd:
            if not self.simulation_mode:
                # 发送到 Arduino
                if self.reader.write(serial_cmd):
                    print(f"[命令] ✅ 已发送到 Arduino: {serial_cmd.strip()}")
                    self.mqtt.publish_command_ack(command, "ok", f"指令 {command} 已执行")

                    # 记录执行状态（用于前端反馈）
                    self.last_command = command
                    self.last_command_time = time.time()
                else:
                    print(f"[命令] ❌ 串口发送失败")
                    self.mqtt.publish_command_ack(command, "fail", "串口发送失败")
            else:
                # 模拟模式：更新模拟状态
                self._update_simulation_state(command)
                print(f"[模拟] ✅ 执行指令: {command}")
                self.mqtt.publish_command_ack(command, "ok", f"模拟执行: {command}")
        else:
            print(f"[命令] ⚠️ 未知指令: {command}")
            self.mqtt.publish_command_ack(command, "unknown", f"未知指令: {command}")

    def _update_simulation_state(self, command):
        """更新模拟状态（用于模拟模式）"""
        state_map = {
            "open": "窗户已打开",
            "close": "窗户已关闭",
            "on": "设备已开启",
            "off": "设备已关闭",
            "alert_on": "🚨 告警已触发",
            "alert_off": "🔕 告警已解除",
            "fan_on": "风扇已开启",
            "fan_off": "风扇已关闭",
            "light_on": "灯光已开启",
            "light_off": "灯光已关闭"
        }
        print(f"[模拟] 📟 设备状态: {state_map.get(command, command)}")

    def _simulate_data(self):
        """模拟生成数据（无硬件时使用）"""
        import random
        temperature = round(22.0 + random.uniform(-3, 3), 1)
        humidity = round(55.0 + random.uniform(-10, 10), 1)
        light = round(500 + random.uniform(-200, 200))

        print(f"[模拟] 🌡️ {temperature}°C, 💧 {humidity}%, 💡 {light}lux")
        self.mqtt.publish_sensor_data(temperature, humidity, light)

    def run(self):
        """主循环"""
        if not self.start():
            return

        last_heartbeat = 0
        heartbeat_interval = 30
        serial_idle_count = 0

        print("[网关] 开始采集循环...\n")

        try:
            while self.running:
                # ---- 处理串口数据 ----
                if not self.simulation_mode:
                    lines = self.reader.read_all()
                    if lines:
                        serial_idle_count = 0
                        for line in lines:
                            print(f"[串口] 📥 {line}")
                            self._process_serial_data(line)
                    else:
                        serial_idle_count += 1
                        # 60秒无数据自动切换到模拟模式
                        if serial_idle_count >= 30:  # 30 * 2s = 60s
                            print("[网关] ⚠️ 串口60秒无数据，切换到模拟模式")
                            self.simulation_mode = True
                else:
                    # 模拟模式
                    self._simulate_data()

                # ---- 处理控制指令 ----
                cmd = self.mqtt.get_pending_command()
                if cmd:
                    self._process_command(cmd)

                # ---- 心跳 ----
                current_time = time.time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    self.mqtt.publish_status(online=True)
                    last_heartbeat = current_time

                time.sleep(SAMPLE_INTERVAL)

        except KeyboardInterrupt:
            print("\n[网关] 收到终止信号")
        finally:
            self.stop()


def signal_handler(sig, frame):
    """处理 Ctrl+C"""
    print("\n[网关] 正在退出...")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    gateway = HardwareGateway()
    gateway.run()


if __name__ == "__main__":
    main()