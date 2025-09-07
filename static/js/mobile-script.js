// Socket.IO接続
const socket = io();

// DOM要素の取得
const speedSlider = document.getElementById('speedSlider');
const speedValue = document.getElementById('speedValue');
const statusValue = document.getElementById('statusValue');
const connectionStatus = document.getElementById('connectionStatus');
const controlButtons = document.querySelectorAll('.control-btn');
const servoButtons = document.querySelectorAll('.servo-btn');
const pitchAngle = document.getElementById('pitchAngle');
const yawAngle = document.getElementById('yawAngle');
const pitchSlider = document.getElementById('pitchSlider');
const yawSlider = document.getElementById('yawSlider');

// LED関連の要素（簡略化）
const colorPicker = document.getElementById('colorPicker');
const brightnessSlider = document.getElementById('brightnessSlider');
const brightnessValue = document.getElementById('brightnessValue');
const applyColorBtn = document.getElementById('applyColorBtn');
const rainbowBtn = document.getElementById('rainbowBtn');
const chaseBtn = document.getElementById('chaseBtn');
const ledOffBtn = document.getElementById('ledOffBtn');

let selectedLed = -1; // 常に全LED制御

// タッチイベントのための変数
let touchStartTime = 0;
let isLongPress = false;

// 接続状態の更新
socket.on('connect', function() {
    console.log('サーバーに接続しました');
    connectionStatus.className = 'connection-status connected';
    statusValue.textContent = 'サーバーに接続しました';
});

socket.on('disconnect', function() {
    console.log('サーバーから切断されました');
    connectionStatus.className = 'connection-status disconnected';
    statusValue.textContent = 'サーバーから切断されました';
});

// ステータス更新
socket.on('status', function(data) {
    statusValue.textContent = `動作: ${data.action}, 速度: ${data.speed}%`;
});

// エラーメッセージ
socket.on('error', function(data) {
    statusValue.textContent = `エラー: ${data.message}`;
    statusValue.style.color = 'red';
    setTimeout(() => {
        statusValue.style.color = 'white';
    }, 3000);
});

// サーボモーター状態更新
socket.on('servo_status', function(data) {
    if (data.type === 'pitch') {
        pitchAngle.textContent = data.angle;
        pitchSlider.value = data.angle;
    } else if (data.type === 'yaw') {
        yawAngle.textContent = data.angle;
        yawSlider.value = data.angle;
    } else if (data.pitch !== undefined && data.yaw !== undefined) {
        // 初期状態の場合
        pitchAngle.textContent = data.pitch;
        yawAngle.textContent = data.yaw;
        pitchSlider.value = data.pitch;
        yawSlider.value = data.yaw;
    }
});

// 速度スライダーの更新
speedSlider.addEventListener('input', function() {
    speedValue.textContent = this.value;
});

// サーボスライダーの更新
pitchSlider.addEventListener('input', function() {
    const angle = parseInt(this.value);
    pitchAngle.textContent = angle;
    socket.emit('servo_angle', {
        type: 'pitch',
        angle: angle
    });
});

yawSlider.addEventListener('input', function() {
    const angle = parseInt(this.value);
    yawAngle.textContent = angle;
    socket.emit('servo_angle', {
        type: 'yaw',
        angle: angle
    });
});

// 明度スライダー
brightnessSlider.addEventListener('input', function() {
    brightnessValue.textContent = this.value;
    socket.emit('led_control', {
        action: 'set_brightness',
        brightness: parseInt(this.value)
    });
});

// LED制御ボタン（簡略化）
applyColorBtn.addEventListener('click', function() {
    const hex = colorPicker.value;
    const r = parseInt(hex.substr(1, 2), 16);
    const g = parseInt(hex.substr(3, 2), 16);
    const b = parseInt(hex.substr(5, 2), 16);
    
    socket.emit('led_control', {
        action: 'set_color',
        led_index: -1, // 常に全LED
        r: r,
        g: g,
        b: b
    });
});

rainbowBtn.addEventListener('click', function() {
    socket.emit('led_control', {
        action: 'animation_rainbow'
    });
});

chaseBtn.addEventListener('click', function() {
    const hex = colorPicker.value;
    const r = parseInt(hex.substr(1, 2), 16);
    const g = parseInt(hex.substr(3, 2), 16);
    const b = parseInt(hex.substr(5, 2), 16);
    
    socket.emit('led_control', {
        action: 'animation_chase',
        r: r,
        g: g,
        b: b
    });
});

ledOffBtn.addEventListener('click', function() {
    socket.emit('led_control', {
        action: 'off'
    });
});

// モーター制御ボタンのイベントリスナー（タッチ対応）
controlButtons.forEach(button => {
    let touchTimer = null;
    let isPressed = false;
    
    // 共通の開始処理
    function startAction() {
        if (isPressed) return;
        isPressed = true;
        
        const action = button.getAttribute('data-action');
        const speed = parseInt(speedSlider.value);
        
        socket.emit('motor_control', {
            action: action,
            speed: speed,
            duration: 0
        });
        
        // ボタンのフィードバック
        button.style.transform = 'scale(0.95)';
        button.style.opacity = '0.8';
    }
    
    // 共通の終了処理
    function endAction() {
        if (!isPressed) return;
        isPressed = false;
        
        socket.emit('motor_control', {
            action: 'stop',
            speed: 0,
            duration: 0
        });
        
        button.style.transform = 'scale(1)';
        button.style.opacity = '1';
        
        if (touchTimer) {
            clearTimeout(touchTimer);
            touchTimer = null;
        }
    }
    
    // タッチイベント
    button.addEventListener('touchstart', function(e) {
        e.preventDefault();
        startAction();
    });
    
    button.addEventListener('touchend', function(e) {
        e.preventDefault();
        endAction();
    });
    
    button.addEventListener('touchcancel', function(e) {
        e.preventDefault();
        endAction();
    });
    
    // マウスイベント（デスクトップ用）
    button.addEventListener('mousedown', function(e) {
        e.preventDefault();
        startAction();
    });
    
    button.addEventListener('mouseup', function(e) {
        e.preventDefault();
        endAction();
    });
    
    button.addEventListener('mouseleave', function(e) {
        endAction();
    });
});

// サーボモーター制御ボタンのイベントリスナー
servoButtons.forEach(button => {
    button.addEventListener('click', function(e) {
        e.preventDefault();
        const servoType = this.getAttribute('data-servo');
        const direction = this.getAttribute('data-direction');
        
        // 両方のサーボを中央に戻す処理
        if (servoType === 'both' && direction === 'center') {
            socket.emit('servo_control', { type: 'pitch', direction: 'center' });
            socket.emit('servo_control', { type: 'yaw', direction: 'center' });
        } else {
            socket.emit('servo_control', {
                type: servoType,
                direction: direction
            });
        }
        
        // ボタンのフィードバック
        this.style.transform = 'scale(0.95)';
        setTimeout(() => {
            this.style.transform = 'scale(1)';
        }, 150);
    });
});

// キーボード操作（デスクトップ用）
let pressedKeys = new Set();

document.addEventListener('keydown', function(event) {
    if (event.repeat) return;
    
    const speed = parseInt(speedSlider.value);
    let action = null;
    let servoAction = null;
    
    switch(event.key) {
        case 'ArrowUp':
        case 'w':
        case 'W':
            if (!pressedKeys.has('forward')) {
                action = 'forward';
                pressedKeys.add('forward');
            }
            break;
        case 'ArrowDown':
        case 's':
        case 'S':
            if (!pressedKeys.has('backward')) {
                action = 'backward';
                pressedKeys.add('backward');
            }
            break;
        case 'ArrowLeft':
        case 'a':
        case 'A':
            if (!pressedKeys.has('left')) {
                action = 'left';
                pressedKeys.add('left');
            }
            break;
        case 'ArrowRight':
        case 'd':
        case 'D':
            if (!pressedKeys.has('right')) {
                action = 'right';
                pressedKeys.add('right');
            }
            break;
        case 'i':
        case 'I':
            servoAction = { type: 'pitch', direction: 'up' };
            break;
        case 'k':
        case 'K':
            servoAction = { type: 'pitch', direction: 'down' };
            break;
        case 'j':
        case 'J':
            servoAction = { type: 'yaw', direction: 'left' };
            break;
        case 'l':
        case 'L':
            servoAction = { type: 'yaw', direction: 'right' };
            break;
        case 'c':
        case 'C':
            socket.emit('servo_control', { type: 'pitch', direction: 'center' });
            socket.emit('servo_control', { type: 'yaw', direction: 'center' });
            event.preventDefault();
            return;
        case ' ': // スペースキーで停止
            socket.emit('motor_control', { action: 'stop', speed: 0, duration: 0 });
            event.preventDefault();
            return;
    }
    
    if (action) {
        socket.emit('motor_control', {
            action: action,
            speed: speed,
            duration: 0
        });
        
        const button = document.querySelector(`[data-action="${action}"]`);
        if (button) {
            button.style.transform = 'scale(0.95)';
            button.style.opacity = '0.8';
        }
        
        event.preventDefault();
    }
    
    if (servoAction) {
        socket.emit('servo_control', servoAction);
        event.preventDefault();
    }
});

document.addEventListener('keyup', function(event) {
    let action = null;
    
    switch(event.key) {
        case 'ArrowUp':
        case 'w':
        case 'W':
            action = 'forward';
            pressedKeys.delete('forward');
            break;
        case 'ArrowDown':
        case 's':
        case 'S':
            action = 'backward';
            pressedKeys.delete('backward');
            break;
        case 'ArrowLeft':
        case 'a':
        case 'A':
            action = 'left';
            pressedKeys.delete('left');
            break;
        case 'ArrowRight':
        case 'd':
        case 'D':
            action = 'right';
            pressedKeys.delete('right');
            break;
    }
    
    if (action) {
        socket.emit('motor_control', {
            action: 'stop',
            speed: 0,
            duration: 0
        });
        
        const button = document.querySelector(`[data-action="${action}"]`);
        if (button) {
            button.style.transform = 'scale(1)';
            button.style.opacity = '1';
        }
    }
});

// ページロード時にステータスを取得
window.addEventListener('load', function() {
    socket.emit('get_status');
});

// ページから離れる時やフォーカスを失った時にモーターを停止
window.addEventListener('beforeunload', function() {
    socket.emit('motor_control', { action: 'stop', speed: 0, duration: 0 });
});

window.addEventListener('blur', function() {
    socket.emit('motor_control', { action: 'stop', speed: 0, duration: 0 });
    
    // 全てのボタンスタイルをリセット
    controlButtons.forEach(button => {
        button.style.transform = 'scale(1)';
        button.style.opacity = '1';
    });
    
    pressedKeys.clear();
});

// デバイスの向き変更時の処理
window.addEventListener('orientationchange', function() {
    setTimeout(() => {
        // 画面の再計算
        window.scrollTo(0, 0);
    }, 100);
});

// タッチイベントでのスクロール防止（ゲームパッド部分）
document.querySelectorAll('.control-btn, .servo-btn').forEach(button => {
    button.addEventListener('touchmove', function(e) {
        e.preventDefault();
    });
});

// バイブレーション（対応デバイスのみ）
function vibrate(duration = 50) {
    if (navigator.vibrate) {
        navigator.vibrate(duration);
    }
}

// ボタン押下時のバイブレーション
controlButtons.forEach(button => {
    button.addEventListener('touchstart', () => vibrate(30));
});

servoButtons.forEach(button => {
    button.addEventListener('click', () => vibrate(20));
});
