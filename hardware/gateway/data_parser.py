# -*- coding: utf-8 -*-
"""
数据解析模块
将 Arduino 发送的原始字符串解析为结构化数据
"""
import re
from config import PARSER_FIELD_MAP


class DataParser:
    """串口数据解析器"""

    def __init__(self, field_map=None):
        self.field_map = field_map or PARSER_FIELD_MAP

    def parse(self, raw_line: str) -> dict:
        """
        解析 Arduino 数据
        输入: "T:25.3,H:60.5,L:800,AL:0,LR:0,LG:0,LB:0,BZ:0"
        输出: {"temperature": 25.3, "humidity": 60.5, "light": 800, ...}
        """
        raw_line = raw_line.strip()
        result = {}

        # 按逗号分割各字段
        parts = raw_line.split(",")
        for part in parts:
            part = part.strip()
            match = re.match(r"([A-Za-z]+):([\-\d.]+)", part)
            if match:
                key = match.group(1)
                value = float(match.group(2))
                mapped_key = self.field_map.get(key, key)
                result[mapped_key] = value

        return result

    def validate(self, parsed: dict) -> bool:
        """验证解析结果是否有效"""
        # 至少要有温度和湿度
        return parsed.get("temperature") is not None and parsed.get("humidity") is not None

    def to_json_payload(self, parsed: dict, device_id: str) -> dict:
        """
        转换为 Flask 后端需要的 JSON 格式
        Flask 后端期望: {"device_id": "gateway_001", "temperature": 25.3, "humidity": 60.5, "light": 800}
        """
        payload = {
            "device_id": device_id,
            "temperature": parsed.get("temperature"),
            "humidity": parsed.get("humidity"),
            "light": parsed.get("light")
        }
        # 只保留非 None 的字段
        return {k: v for k, v in payload.items() if v is not None}


if __name__ == "__main__":
    parser = DataParser()
    test_cases = [
        "T:25.3,H:60.5,L:800,AL:0,LR:0,LG:0,LB:0,BZ:0",
        "T:30.0,H:55.2,L:1200,AL:1,LR:1,LG:0,LB:0,BZ:1",
        "T:18.5,H:70.1,L:300,AL:0,LR:0,LG:1,LB:0,BZ:0",
    ]
    for case in test_cases:
        result = parser.parse(case)
        payload = parser.to_json_payload(result, "gateway_001")
        print(f"原始: {case}")
        print(f"解析: {result}")
        print(f"JSON: {payload}")
        print("-" * 50)