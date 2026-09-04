"""
智能家居监测控制系统 - Flask 主程序（完整版 v2）
"""
import json
import logging
from datetime import datetime, timedelta

from weather_service import WeatherService, CITY_IDS

weather_service = WeatherService("101031100")
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from config import Config
from models import db, User, Device, SensorData, Alert, ControlLog, SystemConfig
from mqtt_client import MqttClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('app')

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

# ==================== 配置读写 ====================

def _get_config(key, default):
    cfg = SystemConfig.query.filter_by(config_key=key).first()
    return float(cfg.config_value) if cfg else default

def _set_config(key, value):
    cfg = SystemConfig.query.filter_by(config_key=key).first()
    if cfg:
        cfg.config_value = str(value)
        cfg.updated_at = datetime.now()
    else:
        cfg = SystemConfig(config_key=key, config_value=str(value))
        db.session.add(cfg)
    db.session.commit()

# ==================== 设备状态存储（内存） ====================

device_status = {
    "air_conditioner": "off",   # LED1
    "dehumidifier": "off",      # LED2
    "window": "closed"          # LED3
}

auto_mode = True  # 自动控制开关

# ==================== MQTT 回调 ====================

def on_sensor_data(payload):
    try:
        device_id = payload.get('device_id', 'gateway_001')
        temperature = payload.get('temperature')
        humidity = payload.get('humidity')
        light = payload.get('light')

        with app.app_context():
            record = SensorData(device_id=device_id, temperature=temperature, humidity=humidity, light=light)
            db.session.add(record)
            check_and_create_alert(device_id, temperature, humidity, light)
            db.session.commit()
            logger.info(f"💾 数据已入库: {device_id} | 温度:{temperature}°C 湿度:{humidity}% 光照:{light}")
    except Exception as e:
        logger.error(f"处理传感器数据异常: {e}")

def check_and_create_alert(device_id, temperature, humidity, light):
    temp_high = _get_config('temp_high', Config.TEMP_HIGH)
    temp_low = _get_config('temp_low', Config.TEMP_LOW)
    humidity_high = _get_config('humidity_high', Config.HUMIDITY_HIGH)
    humidity_low = _get_config('humidity_low', Config.HUMIDITY_LOW)
    light_high = _get_config('light_high', Config.LIGHT_HIGH)
    light_low = _get_config('light_low', Config.LIGHT_LOW)

    alerts = []

    # 温度
    if temperature is not None:
        if temperature >= temp_high + 5:
            alerts.append(Alert(device_id=device_id, alert_type='temp_high', alert_level='danger',
                alert_message=f'温度严重过高: {temperature}°C >= {temp_high+5}°C', threshold_value=temp_high+5, actual_value=temperature))
        elif temperature > temp_high:
            alerts.append(Alert(device_id=device_id, alert_type='temp_high', alert_level='critical',
                alert_message=f'温度过高: {temperature}°C > {temp_high}°C', threshold_value=temp_high, actual_value=temperature))
        elif temperature <= temp_low - 5:
            alerts.append(Alert(device_id=device_id, alert_type='temp_low', alert_level='danger',
                alert_message=f'温度严重过低: {temperature}°C <= {temp_low-5}°C', threshold_value=temp_low-5, actual_value=temperature))
        elif temperature < temp_low:
            alerts.append(Alert(device_id=device_id, alert_type='temp_low', alert_level='critical',
                alert_message=f'温度过低: {temperature}°C < {temp_low}°C', threshold_value=temp_low, actual_value=temperature))

    # 湿度
    if humidity is not None:
        if humidity >= humidity_high + 10:
            alerts.append(Alert(device_id=device_id, alert_type='humidity_high', alert_level='danger',
                alert_message=f'湿度严重过高: {humidity}% >= {humidity_high+10}%', threshold_value=humidity_high+10, actual_value=humidity))
        elif humidity > humidity_high:
            alerts.append(Alert(device_id=device_id, alert_type='humidity_high', alert_level='critical',
                alert_message=f'湿度过高: {humidity}% > {humidity_high}%', threshold_value=humidity_high, actual_value=humidity))
        elif humidity <= humidity_low - 10:
            alerts.append(Alert(device_id=device_id, alert_type='humidity_low', alert_level='danger',
                alert_message=f'湿度严重过低: {humidity}% <= {humidity_low-10}%', threshold_value=humidity_low-10, actual_value=humidity))
        elif humidity < humidity_low:
            alerts.append(Alert(device_id=device_id, alert_type='humidity_low', alert_level='critical',
                alert_message=f'湿度过低: {humidity}% < {humidity_low}%', threshold_value=humidity_low, actual_value=humidity))

    # 光照
    if light is not None:
        if light >= light_high:
            alerts.append(Alert(device_id=device_id, alert_type='light_high', alert_level='danger',
                alert_message=f'光照过强: {light}lux >= {light_high}lux', threshold_value=light_high, actual_value=light))
        elif light <= light_low:
            alerts.append(Alert(device_id=device_id, alert_type='light_low', alert_level='danger',
                alert_message=f'光照过弱: {light}lux <= {light_low}lux', threshold_value=light_low, actual_value=light))

    for alert in alerts:
        db.session.add(alert)
        logger.warning(f"🚨 告警 [{alert.alert_level}]: {alert.alert_message}")
        # 自动控制
        if alert.alert_level == 'danger' and auto_mode:
            auto_control_device(alert.alert_type, 'danger')

def auto_control_device(alert_type, level):
    key = f"{alert_type}_{level}"
    rule = Config.DEVICE_AUTO_RULES.get(key)
    if rule:
        dev, action = rule
        device_status[dev] = "on" if action == "on" else "open" if action == "open" else "closed" if action == "close" else action
        logger.info(f"🤖 自动控制: {dev} → {device_status[dev]}")
        # TODO: 发送 MQTT 指令给硬件
        # mqtt_client.publish("device/control", {"device": dev, "action": action})

# ==================== MQTT 客户端 ====================

mqtt_client = MqttClient(
    broker=Config.MQTT_BROKER, port=Config.MQTT_PORT, client_id=Config.MQTT_CLIENT_ID,
    topics=[Config.MQTT_TOPIC_SENSOR, Config.MQTT_TOPIC_STATUS], on_sensor_data=on_sensor_data
)

# ==================== 页面路由 ====================

@app.route('/')
def index(): return render_template('index.html')
@app.route('/devices')
def devices_page(): return render_template('devices.html')
@app.route('/monitor')
def monitor_page(): return render_template('monitor.html')
@app.route('/history')
def history_page(): return render_template('history.html')
@app.route('/alerts')
def alerts_page(): return render_template('alerts.html')
@app.route('/predict')
def predict_page(): return render_template('predict.html')

# ==================== 系统状态 ====================

@app.route('/api/status')
def api_status():
    return jsonify({'success': True, 'mqtt_connected': mqtt_client.connected,
        'mqtt_broker': f"{Config.MQTT_BROKER}:{Config.MQTT_PORT}",
        'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

# ==================== 设备管理 ====================

@app.route('/api/devices', methods=['GET'])
def get_devices():
    devices = Device.query.all()
    return jsonify({'success': True, 'data': [{'id': d.id, 'device_id': d.device_id,
        'device_name': d.device_name, 'device_type': d.device_type, 'location': d.location, 'status': d.status} for d in devices]})

@app.route('/api/devices/status')
def get_device_status():
    return jsonify({'success': True, 'data': device_status, 'auto_mode': auto_mode})


@app.route('/api/devices/control', methods=['POST'])
def manual_control():
    global auto_mode
    data = request.get_json()
    device = data.get('device')
    action = data.get('action')
    force = data.get('force', False)

    if device not in device_status:
        return jsonify({'success': False, 'message': '设备不存在'}), 400

    if force:
        auto_mode = False

    device_status[device] = action
    logger.info(f"🕹️ 手动控制: {device} → {action}")

    # ===== 新增：通过 MQTT 下发控制指令 =====
    # 将设备名映射到命令
    device_command_map = {
        "window": {
            "open": "open",
            "close": "close"
        },
        "air_conditioner": {
            "on": "ac_on",
            "off": "ac_off"
        },
        "dehumidifier": {
            "on": "fan_on",
            "off": "fan_off"
        }
    }

    # 获取对应的MQTT命令
    command_map = device_command_map.get(device, {})
    mqtt_command = command_map.get(action)

    if mqtt_command:
        # 通过 MQTT 下发
        success = mqtt_client.send_control(mqtt_command, Config.DEVICE_ID, "manual")
        logger.info(f"📤 MQTT 指令下发: {mqtt_command} → {'成功' if success else '失败'}")

        # 记录控制日志
        log = ControlLog(
            device_id=Config.DEVICE_ID,
            command=mqtt_command,
            mode='manual',
            source='web',
            success=success
        )
        db.session.add(log)
        db.session.commit()
    else:
        logger.warning(f"⚠️ 未知设备/动作: {device}/{action}")

    return jsonify({'success': True, 'data': device_status, 'auto_mode': auto_mode})

@app.route('/api/devices/auto', methods=['POST'])
def toggle_auto():
    global auto_mode
    data = request.get_json()
    auto_mode = data.get('auto_mode', True)
    return jsonify({'success': True, 'auto_mode': auto_mode})

# ==================== 传感器数据 ====================

@app.route('/api/sensor/latest')
def get_latest_data():
    data = SensorData.query.order_by(SensorData.timestamp.desc()).first()
    return jsonify({'success': True, 'data': data.to_dict() if data else None})

@app.route('/api/sensor/history')
def get_history():
    hours = request.args.get('hours', 24, type=int)
    limit = request.args.get('limit', 100, type=int)
    since = datetime.now() - timedelta(hours=hours)
    records = SensorData.query.filter(SensorData.timestamp >= since).order_by(SensorData.timestamp.asc()).limit(limit).all()
    return jsonify({'success': True, 'data': [r.to_dict() for r in records], 'count': len(records)})

# ==================== 告警管理 ====================

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    limit = request.args.get('limit', 100, type=int)
    level = request.args.get('level', '')
    query = Alert.query
    if level: query = query.filter(Alert.alert_level == level)
    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    return jsonify({'success': True, 'data': [a.to_dict() for a in alerts], 'count': len(alerts)})

@app.route('/api/alerts/stats')
def get_alert_stats():
    total = Alert.query.count()
    by_level = {
        'danger': Alert.query.filter(Alert.alert_level == 'danger').count(),
        'critical': Alert.query.filter(Alert.alert_level == 'critical').count(),
        'warning': Alert.query.filter(Alert.alert_level == 'warning').count()
    }
    unread = Alert.query.filter(Alert.is_read == False).count()
    by_type = {t: Alert.query.filter(Alert.alert_type == t).count() for t in ['temp_high', 'temp_low', 'humidity_high', 'humidity_low', 'light_high', 'light_low']}
    return jsonify({'success': True, 'data': {'total': total, 'unread': unread, 'by_level': by_level, 'by_type': by_type}})

@app.route('/api/alerts/<int:alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    alert = Alert.query.get(alert_id)
    if alert: alert.is_read = True; db.session.commit(); return jsonify({'success': True})
    return jsonify({'success': False}), 404

# ==================== 阈值配置（持久化）====================

@app.route('/api/thresholds', methods=['GET'])
def get_thresholds():
    return jsonify({'success': True, 'data': {
        'temp_high': _get_config('temp_high', Config.TEMP_HIGH),
        'temp_low': _get_config('temp_low', Config.TEMP_LOW),
        'humidity_high': _get_config('humidity_high', Config.HUMIDITY_HIGH),
        'humidity_low': _get_config('humidity_low', Config.HUMIDITY_LOW),
        'light_high': _get_config('light_high', Config.LIGHT_HIGH),
        'light_low': _get_config('light_low', Config.LIGHT_LOW)
    }})

@app.route('/api/thresholds', methods=['POST'])
def update_thresholds():
    data = request.get_json()
    for key in ['temp_high', 'temp_low', 'humidity_high', 'humidity_low', 'light_high', 'light_low']:
        if key in data:
            _set_config(key, data[key])
    return jsonify({'success': True, 'message': '阈值已保存',
        'data': {'temp_high': _get_config('temp_high', Config.TEMP_HIGH),
                 'temp_low': _get_config('temp_low', Config.TEMP_LOW),
                 'humidity_high': _get_config('humidity_high', Config.HUMIDITY_HIGH),
                 'humidity_low': _get_config('humidity_low', Config.HUMIDITY_LOW),
                 'light_high': _get_config('light_high', Config.LIGHT_HIGH),
                 'light_low': _get_config('light_low', Config.LIGHT_LOW)}})

# ==================== 预测 ====================

@app.route('/api/predict')
def get_prediction():
    try:
        from ml_model import predict_both_models
        result = predict_both_models(hours=Config.PREDICT_HOURS)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"预测失败: {e}")
        return jsonify({'success': False, 'message': '预测功能暂不可用'}), 500

 #-------------------- 天气 API --------------------

@app.route('/api/weather')
def get_weather():
    return jsonify({'success': True, 'data': weather_service.get_current_weather()})

@app.route('/api/weather/cities')
def get_weather_cities():
    return jsonify({'success': True, 'data': CITY_IDS})

@app.route('/api/weather/set_city', methods=['POST'])
def set_weather_city():
    data = request.get_json()
    city_id = data.get('city_id', '101031100')
    weather_service.city_id = city_id
    weather_service.last_update = 0  # 立即刷新
    return jsonify({'success': True, 'message': '城市已切换'})

#--------------硬件控制命令下发---------------
@app.route('/api/control', methods=['POST'])
def send_control():
    """手动下发控制指令"""
    data = request.get_json()
    command = data.get('command')
    device_id = data.get('device_id', Config.DEVICE_ID)
    mode = data.get('mode', 'manual')

    if command not in ['open', 'close', 'alert_on', 'alert_off', 'on', 'off']:
        return jsonify({'success': False, 'message': '无效指令'}), 400

    # 通过 MQTT 下发
    success = mqtt_client.send_control(command, device_id, mode)

    # 记录日志
    log = ControlLog(
        device_id=device_id,
        command=command,
        mode=mode,
        source='web',
        success=success
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'success': success,
        'message': f'指令 {command} 已{"下发" if success else "失败"}'
    })
#---------------两模型-----------------
@app.route('/api/predict/compare')
def get_model_comparison():
    """返回两个模型的性能对比"""
    try:
        import joblib
        data = joblib.load(Config.MODEL_PATH)
        return jsonify({
            'success': True,
            'data': {
                'rf': {
                    'name': '随机森林',
                    'temp_mae': round(data['results']['rf']['temp_mae'], 2),
                    'humid_mae': round(data['results']['rf']['humid_mae'], 2)
                },
                'lr': {
                    'name': '线性回归',
                    'temp_mae': round(data['results']['lr']['temp_mae'], 2),
                    'humid_mae': round(data['results']['lr']['humid_mae'], 2)
                },
                'best_temp': data.get('best_temp', '随机森林'),
                'best_humid': data.get('best_humid', '随机森林')
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== 初始化 ====================

def init_db():
    with app.app_context():
        db.create_all()
        if Device.query.count() == 0:
            default_devices = [
                Device(device_id='gateway_001', device_name='智能网关', device_type='gateway', location='客厅'),
                Device(device_id='sensor_dht11_01', device_name='DHT11温湿度传感器', device_type='sensor', location='卧室'),
                Device(device_id='sensor_light_01', device_name='光照传感器', device_type='sensor', location='阳台'),
                Device(device_id='air_conditioner', device_name='空调 (LED1)', device_type='actuator', location='卧室'),
                Device(device_id='dehumidifier', device_name='除湿器 (LED2)', device_type='actuator', location='客厅'),
                Device(device_id='window', device_name='窗户 (LED3)', device_type='actuator', location='阳台'),
            ]
            db.session.add_all(default_devices)
            db.session.commit()
            logger.info("✅ 默认设备已创建")

if __name__ == '__main__':
    init_db()
    mqtt_client.connect()
    logger.info("=" * 50)
    logger.info("🚀 智能家居监测控制系统启动")
    logger.info(f"   MQTT Broker: {Config.MQTT_BROKER}:{Config.MQTT_PORT}")
    logger.info(f"   数据库: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    logger.info("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)