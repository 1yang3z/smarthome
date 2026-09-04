# -*- coding: utf-8 -*-
"""
串口读取模块
从 Arduino 读取原始数据
"""
import serial
import serial.tools.list_ports
import time
import threading
from queue import Queue
from config import SERIAL_PORT, SERIAL_BAUDRATE, SERIAL_TIMEOUT, SERIAL_ENCODING


class SerialReader:
    """串口读取器，运行在独立线程中"""

    def __init__(self, port=SERIAL_PORT, baudrate=SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.running = False
        self.data_queue = Queue()
        self._thread = None

    @staticmethod
    def list_ports():
        """列出所有可用串口"""
        ports = serial.tools.list_ports.comports()
        return [{"device": p.device, "description": p.description} for p in ports]

    def open(self):
        """打开串口"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            if self.ser.is_open:
                print(f"[串口] ✅ 已连接: {self.port} @ {self.baudrate} bps")
                return True
        except serial.SerialException as e:
            print(f"[串口] ❌ 连接失败 {self.port}: {e}")
        return False

    def close(self):
        """关闭串口"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[串口] 已关闭")

    def _read_loop(self):
        """串口读取循环（运行在独立线程）"""
        buffer = ""
        while self.running:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    raw = self.ser.read(self.ser.in_waiting)
                    try:
                        text = raw.decode(SERIAL_ENCODING)
                    except UnicodeDecodeError:
                        text = raw.decode("utf-8", errors="replace")
                    buffer += text
                    # 按换行符分割
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip().strip('\r')
                        if line:
                            self.data_queue.put(line)
                else:
                    time.sleep(0.05)
            except serial.SerialException as e:
                print(f"[串口] 读取错误: {e}")
                time.sleep(1)
            except Exception as e:
                print(f"[串口] 未知错误: {e}")
                time.sleep(1)

    def start(self):
        """启动串口读取线程"""
        if not self.ser or not self.ser.is_open:
            if not self.open():
                return False
        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        print("[串口] 读取线程已启动")
        return True

    def stop(self):
        """停止串口读取线程"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        self.close()
        print("[串口] 读取线程已停止")

    def get_data(self, timeout=1.0):
        """获取一条数据（阻塞）"""
        try:
            return self.data_queue.get(timeout=timeout)
        except:
            return None

    def read_all(self):
        """获取所有待处理数据"""
        lines = []
        while not self.data_queue.empty():
            lines.append(self.data_queue.get_nowait())
        return lines

    def write(self, data):
        """向串口发送数据"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(data.encode('utf-8'))
                return True
            except Exception as e:
                print(f"[串口] 写入失败: {e}")
        return False


if __name__ == "__main__":
    print("可用串口:")
    for p in SerialReader.list_ports():
        print(f"  {p['device']}: {p['description']}")