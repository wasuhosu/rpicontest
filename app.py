from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import pigpio
import time
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# ### ピンの設定 ###
# モーターA (左側) のピン
ENA = 10  # Enable A (PWM)
IN1 = 26  # Input 1
IN2 = 16  # Input 2

# モーターB (右側) のピン
ENB = 9   # Enable B (PWM)
IN3 = 7   # Input 3
IN4 = 8   # Input 4

# pigpioクライアントの初期化
pi = None
current_speed = 0
current_direction = 0
move_timer = None

def init_pigpio():
    """pigpioを初期化"""
    global pi
    try:
        pi = pigpio.pi()
        if not pi.connected:
            print("pigpioデーモンに接続できません")
            return False
        
        # 全てのピンを出力モードに設定
        pi.set_mode(ENA, pigpio.OUTPUT)
        pi.set_mode(IN1, pigpio.OUTPUT)
        pi.set_mode(IN2, pigpio.OUTPUT)
        pi.set_mode(ENB, pigpio.OUTPUT)
        pi.set_mode(IN3, pigpio.OUTPUT)
        pi.set_mode(IN4, pigpio.OUTPUT)
        
        # 初期状態で全てのピンをLOWに設定
        pi.write(IN1, 0)
        pi.write(IN2, 0)
        pi.write(IN3, 0)
        pi.write(IN4, 0)
        
        # PWMを0%で開始
        pi.set_PWM_dutycycle(ENA, 0)
        pi.set_PWM_dutycycle(ENB, 0)
        
        print("pigpio初期化完了")
        return True
    except Exception as e:
        print(f"pigpio初期化エラー: {e}")
        return False

def move_motors(speed, direction):
    """
    モーターを制御する関数
    speed: 0-100 (パーセンテージ)
    direction: 1=前進, -1=後進, 2=右旋回, -2=左旋回, 0=停止
    """
    global pi, current_speed, current_direction
    
    if pi is None or not pi.connected:
        print("pigpioが初期化されていません")
        return
    
    current_speed = speed
    current_direction = direction
    
    # 速度をPWMデューティサイクルに変換 (0-255)
    pwm_value = int(speed * 255 / 100)
    
    # PWM設定
    pi.set_PWM_dutycycle(ENA, pwm_value)
    pi.set_PWM_dutycycle(ENB, pwm_value)
    
    if direction == 1:  # 前進
        pi.write(IN1, 0)
        pi.write(IN2, 1)
        pi.write(IN3, 1)
        pi.write(IN4, 0)
        socketio.emit('status', {'action': '前進', 'speed': speed})
    elif direction == -1:  # 後進
        pi.write(IN1, 1)
        pi.write(IN2, 0)
        pi.write(IN3, 0)
        pi.write(IN4, 1)
        socketio.emit('status', {'action': '後進', 'speed': speed})
    elif direction == 2:  # 右旋回
        pi.write(IN1, 1)
        pi.write(IN2, 0)
        pi.write(IN3, 1)
        pi.write(IN4, 0)
        socketio.emit('status', {'action': '右旋回', 'speed': speed})
    elif direction == -2:  # 左旋回
        pi.write(IN1, 0)
        pi.write(IN2, 1)
        pi.write(IN3, 0)
        pi.write(IN4, 1)
        socketio.emit('status', {'action': '左旋回', 'speed': speed})
    else:  # 停止
        pi.write(IN1, 0)
        pi.write(IN2, 0)
        pi.write(IN3, 0)
        pi.write(IN4, 0)
        pi.set_PWM_dutycycle(ENA, 0)
        pi.set_PWM_dutycycle(ENB, 0)
        socketio.emit('status', {'action': '停止', 'speed': 0})

def stop_motors():
    """モーターを停止"""
    move_motors(0, 0)

def auto_stop():
    """自動停止タイマー"""
    global move_timer
    if move_timer:
        move_timer.cancel()
    stop_motors()

@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """クライアント接続時"""
    print('クライアントが接続しました')
    emit('status', {'action': '接続完了', 'speed': 0})

@socketio.on('disconnect')
def handle_disconnect():
    """クライアント切断時"""
    print('クライアントが切断しました')
    stop_motors()

@socketio.on('motor_control')
def handle_motor_control(data):
    """モーター制御コマンドを受信"""
    global move_timer
    
    action = data.get('action')
    speed = data.get('speed', 50)  # デフォルト速度50%
    duration = data.get('duration', 0)  # 継続時間（0=無制限）
    
    print(f"受信コマンド: {action}, 速度: {speed}%, 継続時間: {duration}秒")
    
    # 既存のタイマーをキャンセル
    if move_timer:
        move_timer.cancel()
    
    # アクションに応じてモーターを制御
    if action == 'forward':
        move_motors(speed, 1)
    elif action == 'backward':
        move_motors(speed, -1)
    elif action == 'left':
        move_motors(speed, -2)
    elif action == 'right':
        move_motors(speed, 2)
    elif action == 'stop':
        stop_motors()
    else:
        emit('error', {'message': f'未知のアクション: {action}'})
        return
    
    # 継続時間が指定されている場合、タイマーで自動停止
    if duration > 0:
        move_timer = threading.Timer(duration, auto_stop)
        move_timer.start()

@socketio.on('get_status')
def handle_get_status():
    """現在の状態を返す"""
    emit('status', {
        'speed': current_speed,
        'direction': current_direction,
        'connected': pi.connected if pi else False
    })

def cleanup():
    """終了処理"""
    global pi, move_timer
    if move_timer:
        move_timer.cancel()
    if pi:
        stop_motors()
        pi.stop()
        print("pigpio終了処理完了")

if __name__ == '__main__':
    try:
        # pigpio初期化
        if not init_pigpio():
            print("pigpioの初期化に失敗しました")
            exit(1)
        
        print("Flask-SocketIOサーバーを開始します...")
        print("ブラウザで http://localhost:5000 にアクセスしてください")
        
        # Flaskサーバー開始
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
        
    except KeyboardInterrupt:
        print("プログラムが中断されました")
    finally:
        cleanup()
