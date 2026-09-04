"""
智能家居监测控制系统 - 数据库模型
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    """用户表"""
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')          # admin / user
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<User {self.username}>'


class Device(db.Model):
    """设备表"""
    __tablename__ = 'device'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(50), unique=True, nullable=False)
    device_name = db.Column(db.String(100), nullable=False)
    device_type = db.Column(db.String(50))                    # sensor / actuator
    location = db.Column(db.String(100))                      # 安装位置
    status = db.Column(db.String(20), default='online')       # online / offline
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<Device {self.device_name}>'


class SensorData(db.Model):
    """传感器历史数据表"""
    __tablename__ = 'sensor_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(50), nullable=False)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    light = db.Column(db.Float)                               # 光照强度 (lux)
    timestamp = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'light': self.light,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }

    def __repr__(self):
        return f'<SensorData {self.device_id} @ {self.timestamp}>'


class Alert(db.Model):
    """告警记录表"""
    __tablename__ = 'alert'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(50))
    alert_type = db.Column(db.String(50))
    alert_level = db.Column(db.String(20), default='warning')    # 🆕 warning / critical / danger
    alert_message = db.Column(db.String(255))
    threshold_value = db.Column(db.Float)
    actual_value = db.Column(db.Float)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'alert_type': self.alert_type,
            'alert_level': self.alert_level,
            'alert_message': self.alert_message,
            'threshold_value': self.threshold_value,
            'actual_value': self.actual_value,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class ControlLog(db.Model):
    """控制指令日志表"""
    __tablename__ = 'control_log'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(50))
    command = db.Column(db.String(50))                        # open / close / fan_on / fan_off
    mode = db.Column(db.String(20))                           # auto / manual
    source = db.Column(db.String(50))                         # web / auto_rule
    success = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<ControlLog {self.command}>'
class SystemConfig(db.Model):
    """系统配置表 — 持久化阈值等配置"""
    __tablename__ = 'system_config'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_key = db.Column(db.String(50), unique=True, nullable=False)
    config_value = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now)