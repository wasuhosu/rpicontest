from flask import Flask, render_template, Response
from flask_socketio import SocketIO, emit
import pigpio
import time
import threading
from rpi_ws281x import PixelStrip, Color
import io
import cv2
from picamera2 import Picamera2
from threading import Condition

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

# サーボモーター のピン
SERVO_PITCH = 18  # ピッチ制御（上下）
SERVO_YAW = 13    # ヨー制御（左右）

# NeoPixel LEDの設定
LED_COUNT = 6        # LEDの数
LED_PIN = 12         # LEDのデータピン
LED_FREQ_HZ = 800000 # LED信号周波数 (800khz)
LED_DMA = 10         # DMAチャンネル
LED_BRIGHTNESS = 255 # 明度 (0-255)
LED_INVERT = False   # 信号反転
LED_CHANNEL = 0      # GPIOチャンネル

# pigpioクライアントの初期化
pi = None
current_speed = 0
current_direction = 0
move_timer = None

# サーボモーターの状態
current_pitch = 90   # 初期角度（中央）
current_yaw = 90     # 初期角度（中央）
servo_min_pulse = 500   # 最小パルス幅（μs）
servo_max_pulse = 2500  # 最大パルス幅（μs）

# NeoPixel LEDの初期化
strip = None
led_brightness = 100  # 初期明度 (0-100%)
led_animation_timer = None

# カメラの設定
camera = None
output_frame = None
frame_lock = threading.Lock()

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
        pi.set_mode(SERVO_PITCH, pigpio.OUTPUT)
        pi.set_mode(SERVO_YAW, pigpio.OUTPUT)
        
        # 初期状態で全てのピンをLOWに設定
        pi.write(IN1, 0)
        pi.write(IN2, 0)
        pi.write(IN3, 0)
        pi.write(IN4, 0)
        
        # PWMを0%で開始
        pi.set_PWM_dutycycle(ENA, 0)
        pi.set_PWM_dutycycle(ENB, 0)
        
        # サーボモーターを中央位置に設定
        set_servo_angle(SERVO_PITCH, current_pitch)
        set_servo_angle(SERVO_YAW, current_yaw)
        
        print("pigpio初期化完了")
        return True
    except Exception as e:
        print(f"pigpio初期化エラー: {e}")
        return False

def init_neopixel():
    """NeoPixel LEDを初期化"""
    global strip
    try:
        strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        strip.begin()
        
        # 全てのLEDを消灯
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        
        print("NeoPixel LED初期化完了")
        return True
    except Exception as e:
        print(f"NeoPixel LED初期化エラー: {e}")
        return False

def init_camera():
    """カメラを初期化"""
    global camera
    try:
        camera = Picamera2()
        
        # カメラ設定
        config = camera.create_video_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        camera.configure(config)
        camera.start()
        
        print("カメラ初期化完了")
        return True
    except Exception as e:
        print(f"カメラ初期化エラー: {e}")
        return False

def capture_frames():
    """カメラからフレームを取得し続ける関数"""
    global output_frame, frame_lock
    
    while True:
        try:
            if camera is None:
                time.sleep(0.1)
                continue
                
            # フレームを取得
            frame = camera.capture_array()
            
            # フレームをJPEGエンコード
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            
            # グローバル変数に保存（スレッドセーフ）
            with frame_lock:
                output_frame = buffer.tobytes()
                
        except Exception as e:
            print(f"フレーム取得エラー: {e}")
            time.sleep(0.1)

def generate_video_stream():
    """ビデオストリーム用のジェネレータ"""
    global output_frame, frame_lock
    
    while True:
        # フレームが利用可能になるまで待機
        with frame_lock:
            if output_frame is None:
                continue
            frame = output_frame
        
        # HTTPレスポンス形式でフレームを返す
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def angle_to_pulse_width(angle):
    """
    角度をパルス幅に変換する関数
    angle: 0-180度
    return: パルス幅（μs）
    """
    return servo_min_pulse + (angle / 180.0) * (servo_max_pulse - servo_min_pulse)

def set_servo_angle(pin, angle):
    """
    サーボモーターの角度を設定する関数
    pin: GPIOピン番号
    angle: 0-180度
    """
    global pi
    if pi is None or not pi.connected:
        print("pigpioが初期化されていません")
        return
    
    # 角度を0-180度の範囲に制限
    angle = max(0, min(180, angle))
    
    # 角度をパルス幅に変換
    pulse_width = angle_to_pulse_width(angle)
    
    # サーボ信号を送信
    pi.set_servo_pulsewidth(pin, pulse_width)

def control_servo(servo_type, direction):
    """
    サーボモーターを制御する関数
    servo_type: 'pitch' または 'yaw'
    direction: 'up', 'down', 'left', 'right', 'center'
    """
    global current_pitch, current_yaw
    
    step = 5  # 1回の操作での角度変化量
    
    if servo_type == 'pitch':
        if direction == 'up':
            current_pitch = min(180, current_pitch + step)
        elif direction == 'down':
            current_pitch = max(0, current_pitch - step)
        elif direction == 'center':
            current_pitch = 90
        
        set_servo_angle(SERVO_PITCH, current_pitch)
        socketio.emit('servo_status', {
            'type': 'pitch', 
            'angle': current_pitch,
            'direction': direction
        })
        
    elif servo_type == 'yaw':
        if direction == 'left':
            current_yaw = min(180, current_yaw + step)
        elif direction == 'right':
            current_yaw = max(0, current_yaw - step)
        elif direction == 'center':
            current_yaw = 90
        
        set_servo_angle(SERVO_YAW, current_yaw)
        socketio.emit('servo_status', {
            'type': 'yaw',
            'angle': current_yaw,
            'direction': direction
        })

def set_led_color(led_index, r, g, b):
    """
    指定したLEDの色を設定
    led_index: LEDのインデックス (0-5、-1で全LED)
    r, g, b: RGB値 (0-255)
    """
    global strip, led_brightness
    if strip is None:
        print("NeoPixel LEDが初期化されていません")
        return
    
    # 明度を適用
    brightness_factor = led_brightness / 100.0
    r = int(r * brightness_factor)
    g = int(g * brightness_factor)
    b = int(b * brightness_factor)
    
    color = Color(r, g, b)
    
    if led_index == -1:  # 全てのLED
        for i in range(LED_COUNT):
            strip.setPixelColor(i, color)
    else:  # 指定したLED
        if 0 <= led_index < LED_COUNT:
            strip.setPixelColor(led_index, color)
    
    strip.show()

def set_led_brightness(brightness):
    """LED明度を設定 (0-100%)"""
    global led_brightness
    led_brightness = max(0, min(100, brightness))
    socketio.emit('led_status', {'brightness': led_brightness})

def led_animation_rainbow():
    """レインボーアニメーション"""
    global strip
    if strip is None:
        return
    
    import math
    
    for j in range(256):
        for i in range(LED_COUNT):
            pixel_index = (i * 256 // LED_COUNT) + j
            r = int((math.sin(pixel_index * 0.024) + 1) * 127)
            g = int((math.sin(pixel_index * 0.024 + 2) + 1) * 127)
            b = int((math.sin(pixel_index * 0.024 + 4) + 1) * 127)
            
            # 明度を適用
            brightness_factor = led_brightness / 100.0
            r = int(r * brightness_factor)
            g = int(g * brightness_factor)
            b = int(b * brightness_factor)
            
            strip.setPixelColor(i, Color(r, g, b))
        
        strip.show()
        time.sleep(0.02)

def led_animation_chase(r, g, b):
    """チェイスアニメーション"""
    global strip
    if strip is None:
        return
    
    brightness_factor = led_brightness / 100.0
    r = int(r * brightness_factor)
    g = int(g * brightness_factor)
    b = int(b * brightness_factor)
    
    for i in range(LED_COUNT):
        # 全て消灯
        for j in range(LED_COUNT):
            strip.setPixelColor(j, Color(0, 0, 0))
        
        # 現在のLEDを点灯
        strip.setPixelColor(i, Color(r, g, b))
        strip.show()
        time.sleep(0.2)

def stop_led_animation():
    """LEDアニメーションを停止"""
    global led_animation_timer
    if led_animation_timer:
        led_animation_timer.cancel()
        led_animation_timer = None

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

@app.route('/video_feed')
def video_feed():
    """ビデオストリーミング"""
    return Response(generate_video_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

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
    emit('servo_status', {
        'pitch': current_pitch,
        'yaw': current_yaw
    })

@socketio.on('servo_control')
def handle_servo_control(data):
    """サーボモーター制御コマンドを受信"""
    servo_type = data.get('type')  # 'pitch' または 'yaw'
    direction = data.get('direction')  # 'up', 'down', 'left', 'right', 'center'
    
    print(f"サーボ制御コマンド: {servo_type}, 方向: {direction}")
    
    if servo_type in ['pitch', 'yaw'] and direction in ['up', 'down', 'left', 'right', 'center']:
        control_servo(servo_type, direction)
    else:
        emit('error', {'message': f'未知のサーボコマンド: {servo_type}, {direction}'})

@socketio.on('servo_angle')
def handle_servo_angle(data):
    """サーボモーターの角度直接指定"""
    global current_pitch, current_yaw
    
    servo_type = data.get('type')  # 'pitch' または 'yaw'
    angle = data.get('angle', 90)  # 角度（0-180）
    
    print(f"サーボ角度設定: {servo_type}, 角度: {angle}度")
    
    # 角度を0-180度の範囲に制限
    angle = max(0, min(180, angle))
    
    if servo_type == 'pitch':
        current_pitch = angle
        set_servo_angle(SERVO_PITCH, current_pitch)
        socketio.emit('servo_status', {
            'type': 'pitch', 
            'angle': current_pitch,
            'direction': 'slider'
        })
    elif servo_type == 'yaw':
        current_yaw = angle
        set_servo_angle(SERVO_YAW, current_yaw)
        socketio.emit('servo_status', {
            'type': 'yaw',
            'angle': current_yaw,
            'direction': 'slider'
        })
    else:
        emit('error', {'message': f'未知のサーボタイプ: {servo_type}'})

@socketio.on('led_control')
def handle_led_control(data):
    """LED制御コマンドを受信"""
    action = data.get('action')
    
    print(f"LED制御コマンド: {action}")
    
    if action == 'set_color':
        led_index = data.get('led_index', -1)  # -1で全LED
        r = data.get('r', 0)
        g = data.get('g', 0)
        b = data.get('b', 0)
        set_led_color(led_index, r, g, b)
        socketio.emit('led_status', {
            'action': 'color_set',
            'led_index': led_index,
            'r': r, 'g': g, 'b': b
        })
        
    elif action == 'set_brightness':
        brightness = data.get('brightness', 100)
        set_led_brightness(brightness)
        
    elif action == 'animation_rainbow':
        stop_led_animation()
        threading.Thread(target=led_animation_rainbow, daemon=True).start()
        socketio.emit('led_status', {'action': 'animation_started', 'type': 'rainbow'})
        
    elif action == 'animation_chase':
        r = data.get('r', 255)
        g = data.get('g', 0)
        b = data.get('b', 0)
        stop_led_animation()
        threading.Thread(target=led_animation_chase, args=(r, g, b), daemon=True).start()
        socketio.emit('led_status', {'action': 'animation_started', 'type': 'chase'})
        
    elif action == 'off':
        stop_led_animation()
        set_led_color(-1, 0, 0, 0)  # 全LED消灯
        socketio.emit('led_status', {'action': 'off'})
        
    else:
        emit('error', {'message': f'未知のLEDコマンド: {action}'})

def cleanup():
    """終了時のクリーンアップ処理"""
    global pi, strip, camera
    
    if pi:
        # モーターを停止
        stop_motors()
        # サーボモーターを中央位置に戻す
        set_servo_angle(SERVO_PITCH, 90)
        set_servo_angle(SERVO_YAW, 90)
        time.sleep(0.5)  # サーボが動く時間を確保
        pi.stop()
        print("pigpio終了処理完了")
    if strip:
        # 全LEDを消灯
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        print("NeoPixel LED終了処理完了")
    if camera:
        camera.stop()
        camera.close()
        print("カメラ終了処理完了")

if __name__ == '__main__':
    try:
        # pigpio初期化
        if not init_pigpio():
            print("pigpioの初期化に失敗しました")
            exit(1)
        
        # NeoPixel LED初期化
        if not init_neopixel():
            print("NeoPixel LEDの初期化に失敗しました")
            exit(1)
        
        # カメラ初期化
        if not init_camera():
            print("カメラの初期化に失敗しました")
            exit(1)
        
        # カメラフレーム取得スレッドを開始
        camera_thread = threading.Thread(target=capture_frames, daemon=True)
        camera_thread.start()
        
        print("Flask-SocketIOサーバーを開始します...")
        print("ブラウザで http://localhost:5000 にアクセスしてください")
        
        # Flaskサーバー開始
        socketio.run(app, debug=False, host='0.0.0.0', port=5000)
        
    except KeyboardInterrupt:
        print("プログラムが中断されました")
    finally:
        cleanup()
