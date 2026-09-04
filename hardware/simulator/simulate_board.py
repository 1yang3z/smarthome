# -*- coding: utf-8 -*-
"""
模拟 Arduino 数据发送器
用于无硬件时测试网关
"""
import serial
import serial.tools.list_ports
import time
import random
import argparse
import sys


def generate_data(temp_base=25.0, humi_base=55.0, light_base=800):
    """生成模拟传感器数据"""
    temp = round(temp_base + random.uniform(-2.0, 2.0), 1)
    humi = round(humi_base + random.uniform(-8.0, 8.0), 1)
    temp = max(-10, min(50, temp))
    humi = max(0, min(100, humi))
    light = round(light_base + random.uniform(-200, 200))
    light = max(0, min(2000, light))

    alert = random.choice([0, 0, 0, 1])  # 10% 概率触发告警

    return temp, humi, light, alert


def main():
    parser = argparse.ArgumentParser(description="模拟 Arduino 数据发送器")
    parser.add_argument("--port", "-p", default="COM3", help="串口号")
    parser.add_argument("--baudrate", "-b", type=int, default=9600, help="波特率")
    parser.add_argument("--interval", "-i", type=float, default=3.0, help="发送间隔（秒）")
    args = parser.parse_args()

    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baudrate,
            timeout=1
        )
    except serial.SerialException as e:
        print(f"[错误] 无法打开串口 {args.port}: {e}")
        sys.exit(1)

    print(f"[串口] 已连接: {args.port} @ {args.baudrate} bps")
    print("[格式] T:温度,H:湿度,L:光照,AL:告警,LR:0,LG:0,LB:0,BZ:0")
    print("-" * 50)
    print("按 Ctrl+C 停止发送")

    seq = 0
    try:
        while True:
            temp, humi, light, alert = generate_data()

            # 格式: T:25.3,H:60.5,L:800,AL:0,LR:0,LG:0,LB:0,BZ:0
            line = f"T:{temp},H:{humi},L:{light},AL:{alert},LR:0,LG:0,LB:0,BZ:0\r\n"
            ser.write(line.encode("utf-8"))

            seq += 1
            print(f"[{seq}] 📤 {line.strip()}")
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[用户] 已终止发送")
    finally:
        ser.close()
        print(f"[串口] 已关闭，共发送 {seq} 条数据")


if __name__ == "__main__":
    main()