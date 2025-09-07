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

// LED関連の要素
const ledIndicators = document.querySelectorAll('.led-indicator');
const colorPicker = document.getElementById('colorPicker');
const redSlider = document.getElementById('redSlider');
const greenSlider = document.getElementById('greenSlider');
const blueSlider = document.getElementById('blueSlider');
const redValue = document.getElementById('redValue');
const greenValue = document.getElementById('greenValue');
const blueValue = document.getElementById('blueValue');
const brightnessSlider = document.getElementById('brightnessSlider');
const brightnessValue = document.getElementById('brightnessValue');
const applyColorBtn = document.getElementById('applyColorBtn');
const rainbowBtn = document.getElementById('rainbowBtn');
const chaseBtn = document.getElementById('chaseBtn');
const ledOffBtn = document.getElementById('ledOffBtn');

let selectedLed = -1; // -1は全LED、0-5は個別LED

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
        statusValue.style.color = '#666';
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

// LED状態更新
socket.on('led_status', function(data) {
    if (data.action === 'color_set' && data.led_index !== undefined) {
        const color = `rgb(${data.r}, ${data.g}, ${data.b})`;
        if (data.led_index === -1) {
            // 全LED
            ledIndicators.forEach(led => {
                led.style.backgroundColor = color;
            });
        } else {
            // 個別LED
            const led = document.querySelector(`[data-led="${data.led_index}"]`);
            if (led) {
                led.style.backgroundColor = color;
            }
        }
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

// LED制御のイベントリスナー

// LED選択
ledIndicators.forEach((led, index) => {
    led.addEventListener('click', function() {
        // 選択状態をリセット
        ledIndicators.forEach(l => l.style.border = '3px solid #ddd');
        
        if (selectedLed === index) {
            // 同じLEDをクリックした場合は全LED選択
            selectedLed = -1;
        } else {
            // 個別LED選択
            selectedLed = index;
            this.style.border = '3px solid #4CAF50';
        }
    });
});

// カラーピッカー
colorPicker.addEventListener('input', function() {
    const hex = this.value;
    const r = parseInt(hex.substr(1, 2), 16);
    const g = parseInt(hex.substr(3, 2), 16);
    const b = parseInt(hex.substr(5, 2), 16);
    
    redSlider.value = r;
    greenSlider.value = g;
    blueSlider.value = b;
    redValue.textContent = r;
    greenValue.textContent = g;
    blueValue.textContent = b;
});

// RGB スライダー
redSlider.addEventListener('input', function() {
    redValue.textContent = this.value;
    updateColorPicker();
});

greenSlider.addEventListener('input', function() {
    greenValue.textContent = this.value;
    updateColorPicker();
});

blueSlider.addEventListener('input', function() {
    blueValue.textContent = this.value;
    updateColorPicker();
});

function updateColorPicker() {
    const r = parseInt(redSlider.value);
    const g = parseInt(greenSlider.value);
    const b = parseInt(blueSlider.value);
    const hex = '#' + 
        r.toString(16).padStart(2, '0') +
        g.toString(16).padStart(2, '0') +
        b.toString(16).padStart(2, '0');
    colorPicker.value = hex;
}

// 明度スライダー
brightnessSlider.addEventListener('input', function() {
    brightnessValue.textContent = this.value;
    socket.emit('led_control', {
        action: 'set_brightness',
        brightness: parseInt(this.value)
    });
});

// LED制御ボタン
applyColorBtn.addEventListener('click', function() {
    const r = parseInt(redSlider.value);
    const g = parseInt(greenSlider.value);
    const b = parseInt(blueSlider.value);
    
    socket.emit('led_control', {
        action: 'set_color',
        led_index: selectedLed,
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
    const r = parseInt(redSlider.value);
    const g = parseInt(greenSlider.value);
    const b = parseInt(blueSlider.value);
    
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

// モーター制御ボタンのイベントリスナー
controlButtons.forEach(button => {
    // マウス/タッチダウン時 - モーター開始
    button.addEventListener('mousedown', function(e) {
        e.preventDefault();
        const action = this.getAttribute('data-action');
        const speed = parseInt(speedSlider.value);
        
        socket.emit('motor_control', {
            action: action,
            speed: speed,
            duration: 0  // 継続時間は0（無制限）
        });
        
        // ボタンのフィードバック
        this.style.transform = 'scale(0.95)';
        this.style.opacity = '0.8';
    });
    
    // マウス/タッチアップ時 - モーター停止
    button.addEventListener('mouseup', function(e) {
        e.preventDefault();
        socket.emit('motor_control', {
            action: 'stop',
            speed: 0,
            duration: 0
        });
        
        this.style.transform = 'scale(1)';
        this.style.opacity = '1';
    });
    
    // マウスリーブ時 - モーター停止（ボタンから離れた場合）
    button.addEventListener('mouseleave', function(e) {
        socket.emit('motor_control', {
            action: 'stop',
            speed: 0,
            duration: 0
        });
        
        this.style.transform = 'scale(1)';
        this.style.opacity = '1';
    });
    
    // タッチ開始時 - モーター開始
    button.addEventListener('touchstart', function(e) {
        e.preventDefault();
        const action = this.getAttribute('data-action');
        const speed = parseInt(speedSlider.value);
        
        socket.emit('motor_control', {
            action: action,
            speed: speed,
            duration: 0
        });
        
        this.style.transform = 'scale(0.95)';
        this.style.opacity = '0.8';
    });
    
    // タッチ終了時 - モーター停止
    button.addEventListener('touchend', function(e) {
        e.preventDefault();
        socket.emit('motor_control', {
            action: 'stop',
            speed: 0,
            duration: 0
        });
        
        this.style.transform = 'scale(1)';
        this.style.opacity = '1';
    });
    
    // タッチキャンセル時 - モーター停止
    button.addEventListener('touchcancel', function(e) {
        e.preventDefault();
        socket.emit('motor_control', {
            action: 'stop',
            speed: 0,
            duration: 0
        });
        
        this.style.transform = 'scale(1)';
        this.style.opacity = '1';
    });
});

// サーボモーター制御ボタンのイベントリスナー
servoButtons.forEach(button => {
    button.addEventListener('click', function(e) {
        e.preventDefault();
        const servoType = this.getAttribute('data-servo');
        const direction = this.getAttribute('data-direction');
        
        socket.emit('servo_control', {
            type: servoType,
            direction: direction
        });
        
        // ボタンのフィードバック
        this.style.transform = 'scale(0.95)';
        setTimeout(() => {
            this.style.transform = 'scale(1)';
        }, 150);
    });
});

// キーボード操作
let pressedKeys = new Set();

document.addEventListener('keydown', function(event) {
    if (event.repeat) return; // キーリピートを無視
    
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
        // サーボモーター制御（I/J/K/Lキー）
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
            // サーボモーターを中央に
            socket.emit('servo_control', { type: 'pitch', direction: 'center' });
            socket.emit('servo_control', { type: 'yaw', direction: 'center' });
            event.preventDefault();
            return;
    }
    
    if (action) {
        socket.emit('motor_control', {
            action: action,
            speed: speed,
            duration: 0
        });
        
        // 対応するボタンのスタイルを更新
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
        // モーター停止
        socket.emit('motor_control', {
            action: 'stop',
            speed: 0,
            duration: 0
        });
        
        // 対応するボタンのスタイルをリセット
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
    const buttons = document.querySelectorAll('.control-btn');
    buttons.forEach(button => {
        button.style.transform = 'scale(1)';
        button.style.opacity = '1';
    });
    // キープレス状態をクリア
    pressedKeys.clear();
});
