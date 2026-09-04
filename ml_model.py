"""
智能家居监测控制系统 - 机器学习预测模块
使用随机森林//回归模型预测未来温湿度趋势
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib
import os

from config import Config

logger = logging.getLogger('ml_model')


def get_training_data():
    """从数据库获取训练数据"""
    from models import SensorData
    from app import db, app

    with app.app_context():
        records = SensorData.query \
            .order_by(SensorData.timestamp.asc()) \
            .limit(1000).all()

        if len(records) < 50:
            logger.warning(f"⚠️ 训练数据不足（仅 {len(records)} 条），生成模拟数据")
            return _generate_mock_data()

        data = []
        for r in records:
            data.append({
                'timestamp': r.timestamp,
                'temperature': r.temperature,
                'humidity': r.humidity
            })

        df = pd.DataFrame(data)
        logger.info(f"📊 获取到 {len(df)} 条训练数据")
        return df


def _generate_mock_data():
    """生成模拟训练数据（数据不足时使用）"""
    np.random.seed(42)
    hours = 200
    base_time = datetime.now() - timedelta(hours=hours)

    data = []
    for i in range(hours):
        t = base_time + timedelta(hours=i)
        # 模拟一天内的温度变化（早晨低，中午高）
        hour_of_day = t.hour
        base_temp = 22 + 8 * np.sin(np.pi * (hour_of_day - 6) / 12)
        temp = base_temp + np.random.normal(0, 1)

        # 模拟湿度变化（与温度大致相反）
        base_humidity = 60 - 15 * np.sin(np.pi * (hour_of_day - 6) / 12)
        humidity = base_humidity + np.random.normal(0, 3)
        humidity = np.clip(humidity, 30, 90)

        data.append({
            'timestamp': t,
            'temperature': round(temp, 1),
            'humidity': round(humidity, 1)
        })

    logger.info(f"📊 生成 {len(data)} 条模拟训练数据")
    return pd.DataFrame(data)


def build_features(df):
    """
    特征工程：从时间序列构建特征
    输入: DataFrame with columns [timestamp, temperature, humidity]
    输出: 特征矩阵 X_temp, X_humid, 目标 y_temp, y_humid
    """
    df = df.copy()

    # 时间特征
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['month'] = df['timestamp'].dt.month

    # 滞后特征（前1、2、3个时间点的值）
    for lag in [1, 2, 3]:
        df[f'temp_lag_{lag}'] = df['temperature'].shift(lag)
        df[f'humid_lag_{lag}'] = df['humidity'].shift(lag)

    # 滚动统计特征
    df['temp_rolling_mean_3'] = df['temperature'].rolling(3).mean()
    df['humid_rolling_mean_3'] = df['humidity'].rolling(3).mean()

    # 删除 NaN 行
    df = df.dropna()

    # 特征列
    feature_cols = ['hour', 'day_of_week', 'month',
                    'temp_lag_1', 'temp_lag_2', 'temp_lag_3',
                    'humid_lag_1', 'humid_lag_2', 'humid_lag_3',
                    'temp_rolling_mean_3', 'humid_rolling_mean_3']

    X = df[feature_cols]
    y_temp = df['temperature']
    y_humid = df['humidity']

    return X, y_temp, y_humid, feature_cols


from sklearn.linear_model import LinearRegression

def train_model():
    logger.info("🤖 开始训练预测模型...")
    df = get_training_data()
    X, y_temp, y_humid, feature_cols = build_features(df)

    X_train, X_test, y_temp_train, y_temp_test = train_test_split(X, y_temp, test_size=0.2, random_state=42)
    _, _, y_humid_train, y_humid_test = train_test_split(X, y_humid, test_size=0.2, random_state=42)

    results = {}  # 存储对比结果

    # ===== 模型1: 随机森林 =====
    model_temp_rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    model_temp_rf.fit(X_train, y_temp_train)
    temp_pred_rf = model_temp_rf.predict(X_test)
    temp_mae_rf = mean_absolute_error(y_temp_test, temp_pred_rf)
    logger.info(f"   🌲 随机森林 - 温度 MAE: {temp_mae_rf:.2f}°C")

    model_humid_rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    model_humid_rf.fit(X_train, y_humid_train)
    humid_pred_rf = model_humid_rf.predict(X_test)
    humid_mae_rf = mean_absolute_error(y_humid_test, humid_pred_rf)
    logger.info(f"   🌲 随机森林 - 湿度 MAE: {humid_mae_rf:.2f}%")

    results['rf'] = {'temp_mae': temp_mae_rf, 'humid_mae': humid_mae_rf}

    # ===== 模型2: 线性回归 =====
    model_temp_lr = LinearRegression()
    model_temp_lr.fit(X_train, y_temp_train)
    temp_pred_lr = model_temp_lr.predict(X_test)
    temp_mae_lr = mean_absolute_error(y_temp_test, temp_pred_lr)
    logger.info(f"   📈 线性回归 - 温度 MAE: {temp_mae_lr:.2f}°C")

    model_humid_lr = LinearRegression()
    model_humid_lr.fit(X_train, y_humid_train)
    humid_pred_lr = model_humid_lr.predict(X_test)
    humid_mae_lr = mean_absolute_error(y_humid_test, humid_pred_lr)
    logger.info(f"   📈 线性回归 - 湿度 MAE: {humid_mae_lr:.2f}%")

    results['lr'] = {'temp_mae': temp_mae_lr, 'humid_mae': humid_mae_lr}

    # 选择较优模型（MAE 更小的）
    best_model_temp = model_temp_rf if temp_mae_rf <= temp_mae_lr else model_temp_lr
    best_model_humid = model_humid_rf if humid_mae_rf <= humid_mae_lr else model_humid_lr
    best_temp_name = "随机森林" if temp_mae_rf <= temp_mae_lr else "线性回归"
    best_humid_name = "随机森林" if humid_mae_rf <= humid_mae_lr else "线性回归"
    logger.info(f"   ⭐ 温度模型选用: {best_temp_name} (MAE={min(temp_mae_rf, temp_mae_lr):.2f})")
    logger.info(f"   ⭐ 湿度模型选用: {best_humid_name} (MAE={min(humid_mae_rf, humid_mae_lr):.2f})")

    # 保存所有模型 + 对比结果
    os.makedirs('model', exist_ok=True)
    joblib.dump({
        'model_temp': best_model_temp,
        'model_humid': best_model_humid,
        'model_temp_rf': model_temp_rf,
        'model_humid_rf': model_humid_rf,
        'model_temp_lr': model_temp_lr,
        'model_humid_lr': model_humid_lr,
        'feature_cols': feature_cols,
        'results': results,
        'best_temp': best_temp_name,
        'best_humid': best_humid_name
    }, Config.MODEL_PATH)
    logger.info(f"✅ 模型已保存到 {Config.MODEL_PATH}")
    return best_model_temp, best_model_humid, feature_cols


def load_model():
    """加载已训练的模型"""
    if not os.path.exists(Config.MODEL_PATH):
        logger.warning("模型文件不存在，开始训练...")
        return train_model()

    model_data = joblib.load(Config.MODEL_PATH)
    logger.info(f"📦 模型已加载（温度MAE:{model_data['temp_mae']:.2f}°C, 湿度MAE:{model_data['humid_mae']:.2f}%）")
    return model_data['model_temp'], model_data['model_humid'], model_data['feature_cols']


def predict_temp_humidity(hours=6):
    """
    预测未来 N 小时的温湿度
    返回格式: {
        'timestamps': [...],
        'temperature': [...],
        'humidity': [...]
    }
    """
    # 加载模型
    model_temp, model_humid, feature_cols = load_model()

    # 获取最近数据作为预测起点
    from models import SensorData
    from app import db, app

    with app.app_context():
        recent = SensorData.query \
            .order_by(SensorData.timestamp.desc()) \
            .limit(10).all()

        if len(recent) < 5:
            logger.warning("历史数据不足，无法预测")
            return _generate_mock_prediction(hours)

        recent = list(reversed(recent))  # 按时间正序

    # 构建初始特征
    now = datetime.now()
    timestamps = []
    temp_predictions = []
    humid_predictions = []

    # 准备滑动窗口数据
    temp_window = [r.temperature for r in recent[-3:]]
    humid_window = [r.humidity for r in recent[-3:]]

    for i in range(hours):
        future_time = now + timedelta(hours=i + 1)

        # 构建当前特征
        features = {
            'hour': future_time.hour,
            'day_of_week': future_time.weekday(),
            'month': future_time.month,
            'temp_lag_1': temp_window[-1] if len(temp_window) >= 1 else temp_window[-1],
            'temp_lag_2': temp_window[-2] if len(temp_window) >= 2 else temp_window[-1],
            'temp_lag_3': temp_window[-3] if len(temp_window) >= 3 else temp_window[-1],
            'humid_lag_1': humid_window[-1] if len(humid_window) >= 1 else humid_window[-1],
            'humid_lag_2': humid_window[-2] if len(humid_window) >= 2 else humid_window[-1],
            'humid_lag_3': humid_window[-3] if len(humid_window) >= 3 else humid_window[-1],
            'temp_rolling_mean_3': np.mean(temp_window[-3:]),
            'humid_rolling_mean_3': np.mean(humid_window[-3:])
        }

        X_pred = pd.DataFrame([features])[feature_cols]

        # 预测
        pred_temp = model_temp.predict(X_pred)[0]
        pred_humid = model_humid.predict(X_pred)[0]

        # 限制合理范围
        pred_temp = np.clip(pred_temp, -10, 50)
        pred_humid = np.clip(pred_humid, 10, 95)

        timestamps.append(future_time.strftime('%Y-%m-%d %H:%M:%S'))
        temp_predictions.append(round(pred_temp, 1))
        humid_predictions.append(round(pred_humid, 1))

        # 更新滑动窗口
        temp_window.append(pred_temp)
        humid_window.append(pred_humid)
        temp_window = temp_window[-3:]
        humid_window = humid_window[-3:]

    return {
        'timestamps': timestamps,
        'temperature': temp_predictions,
        'humidity': humid_predictions
    }


def _generate_mock_prediction(hours=6):
    """生成模拟预测数据（模型不可用时）"""
    now = datetime.now()
    timestamps = []
    temp_list = []
    humid_list = []

    for i in range(hours):
        t = now + timedelta(hours=i + 1)
        hour_of_day = t.hour
        base_temp = 22 + 8 * np.sin(np.pi * (hour_of_day - 6) / 12)
        base_humid = 60 - 15 * np.sin(np.pi * (hour_of_day - 6) / 12)

        timestamps.append(t.strftime('%Y-%m-%d %H:%M:%S'))
        temp_list.append(round(base_temp + np.random.normal(0, 0.5), 1))
        humid_list.append(round(np.clip(base_humid + np.random.normal(0, 2), 30, 90), 1))

    return {
        'timestamps': timestamps,
        'temperature': temp_list,
        'humidity': humid_list
    }

def predict_both_models(hours=6):
    """同时用随机森林和线性回归预测，返回对比数据"""
    if not os.path.exists(Config.MODEL_PATH):
        train_model()

    data = joblib.load(Config.MODEL_PATH)
    model_temp_rf = data['model_temp_rf']
    model_temp_lr = data['model_temp_lr']
    model_humid_rf = data['model_humid_rf']
    model_humid_lr = data['model_humid_lr']
    feature_cols = data['feature_cols']

    from models import SensorData
    from app import db, app
    with app.app_context():
        recent = SensorData.query.order_by(SensorData.timestamp.desc()).limit(10).all()
        if len(recent) < 5:
            return _generate_mock_prediction(hours)
        recent = list(reversed(recent))

    now = datetime.now()
    timestamps, temp_rf, temp_lr, humid_rf, humid_lr = [], [], [], [], []

    temp_window = [r.temperature for r in recent[-3:]]
    humid_window = [r.humidity for r in recent[-3:]]

    for i in range(hours):
        future_time = now + timedelta(hours=i + 1)
        features = {
            'hour': future_time.hour,
            'day_of_week': future_time.weekday(),
            'month': future_time.month,
            'temp_lag_1': temp_window[-1],
            'temp_lag_2': temp_window[-2] if len(temp_window)>=2 else temp_window[-1],
            'temp_lag_3': temp_window[-3] if len(temp_window)>=3 else temp_window[-1],
            'humid_lag_1': humid_window[-1],
            'humid_lag_2': humid_window[-2] if len(humid_window)>=2 else humid_window[-1],
            'humid_lag_3': humid_window[-3] if len(humid_window)>=3 else humid_window[-1],
            'temp_rolling_mean_3': np.mean(temp_window[-3:]),
            'humid_rolling_mean_3': np.mean(humid_window[-3:])
        }
        X_pred = pd.DataFrame([features])[feature_cols]

        pred_temp_rf = np.clip(model_temp_rf.predict(X_pred)[0], -10, 50)
        pred_temp_lr = np.clip(model_temp_lr.predict(X_pred)[0], -10, 50)
        pred_humid_rf = np.clip(model_humid_rf.predict(X_pred)[0], 10, 95)
        pred_humid_lr = np.clip(model_humid_lr.predict(X_pred)[0], 10, 95)

        timestamps.append(future_time.strftime('%Y-%m-%d %H:%M:%S'))
        temp_rf.append(round(pred_temp_rf, 1))
        temp_lr.append(round(pred_temp_lr, 1))
        humid_rf.append(round(pred_humid_rf, 1))
        humid_lr.append(round(pred_humid_lr, 1))

        temp_window.append(pred_temp_rf)
        humid_window.append(pred_humid_rf)
        temp_window = temp_window[-3:]
        humid_window = humid_window[-3:]

    return {
        'timestamps': timestamps,
        'temperature_rf': temp_rf,
        'temperature_lr': temp_lr,
        'humidity_rf': humid_rf,
        'humidity_lr': humid_lr,
        'best_temp': data.get('best_temp', '随机森林'),
        'best_humid': data.get('best_humid', '随机森林'),
        'rf': data['results']['rf'],
        'lr': data['results']['lr']
    }

# ==================== 测试 ====================
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    result = predict_temp_humidity(6)
    print("\n📈 预测结果:")
    for i in range(len(result['timestamps'])):
        print(f"  {result['timestamps'][i]} → 温度:{result['temperature'][i]}°C  湿度:{result['humidity'][i]}%")