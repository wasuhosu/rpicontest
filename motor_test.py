import RPi.GPIO as GPIO
import time

# ### ピンの設定 ###
# BCMモードを使用
GPIO.setmode(GPIO.BCM)

# モーターA (左側) のピン
ENA = 10  # Enable A (PWM)
IN1 = 26  # Input 1
IN2 = 16  # Input 2

# モーターB (右側) のピン
ENB = 9  # Enable B (PWM)
IN3 = 7  # Input 3
IN4 = 8  # Input 4

# 全ての制御ピンを出力モードに設定
GPIO.setup(ENA, GPIO.OUT)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(ENB, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

# ### PWMの設定 ###
# PWMオブジェクトの作成 (ピン, 周波数100Hz)
pwm_a = GPIO.PWM(ENA, 100)
pwm_b = GPIO.PWM(ENB, 100)

# PWMを開始。デューティー比0%で開始
pwm_a.start(0)
pwm_b.start(0)

# ### 動作をまとめた関数 ###
def move(speed, direction, duration):
    """
    基本的な動作を制御する関数
    direction: 1=前進, -1=後進, 2=左旋回, -2=右旋回, 0=停止
    """
    # 速度をデューティー比に設定
    pwm_a.ChangeDutyCycle(speed)
    pwm_b.ChangeDutyCycle(speed)
    
    if direction == 1: # 前進
        GPIO.output(IN1, GPIO.LOW); GPIO.output(IN2, GPIO.HIGH)
        GPIO.output(IN3, GPIO.HIGH); GPIO.output(IN4, GPIO.LOW)
    elif direction == -1: # 後進
        GPIO.output(IN1, GPIO.HIGH); GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.LOW); GPIO.output(IN4, GPIO.HIGH) 
    elif direction == 2: # 右旋回 (その場で回転)
        GPIO.output(IN1, GPIO.HIGH); GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.HIGH); GPIO.output(IN4, GPIO.LOW)
    elif direction == -2: # 左旋回 (その場で回転)
        GPIO.output(IN1, GPIO.LOW); GPIO.output(IN2, GPIO.HIGH)
        GPIO.output(IN3, GPIO.LOW); GPIO.output(IN4, GPIO.HIGH)
    else: # 停止
        print("停止")
        GPIO.output(IN1, GPIO.LOW); GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.LOW); GPIO.output(IN4, GPIO.LOW)
        
    time.sleep(duration)

# ### メインの処理 ###
try:
    print("2モーターテストを開始します。")

    # 1. 前進 (速度70%) で2秒間
    move(70, 1, 5)
 

    print("テストが完了しました。")

except KeyboardInterrupt:
    print("プログラムが中断されました。")

finally:
    # プログラム終了時には必ずGPIOをクリーンアップする
    print("GPIOをクリーンアップします。")
    pwm_a.stop()
    pwm_b.stop()
    GPIO.cleanup()