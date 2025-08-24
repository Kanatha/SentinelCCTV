import base64
import time
import threading
import io
import os

from flask import Flask, request, send_from_directory, render_template, jsonify
from flask_socketio import SocketIO
import cv2
import numpy as np

# If you plan to use eventlet/gevent, you can monkey-patch here.
try:
    import eventlet
    eventlet.monkey_patch()
except Exception:
    eventlet = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet' if eventlet else None, cors_allowed_origins='*')

# State
state = {
    'rtsp_url': 'rtsp:/192.168.1.20:554/mjpeg/1',
    'placeholder_path': os.path.join(os.path.dirname(__file__), 'static', 'placeholder.jpg'),
    'running': True,
}

state_lock = threading.Lock()

# Ensure static directory exists
os.makedirs(os.path.join(os.path.dirname(__file__), 'static'), exist_ok=True)

# load Haar cascade (bundled with OpenCV)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Worker thread that reads RTSP, runs detection, emits frames that contain faces

def stream_worker():
    last_url = None
    cap = None

    while state['running']:
        with state_lock:
            url = state['rtsp_url']

        if not url:
            # no RTSP configured; sleep briefly
            time.sleep(0.5)
            continue

        if url != last_url:
            # reconnect if URL changed
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None

            # Open capture
            cap = cv2.VideoCapture(url)
            last_url = url
            time.sleep(0.5)

        if cap is None or not cap.isOpened():
            # try to open again after a short pause
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            cap = cv2.VideoCapture(url)
            time.sleep(1.0)
            continue

        ret, frame = cap.read()
        if not ret or frame is None:
            # read failed; retry
            time.sleep(0.5)
            continue

        # Resize for speed (optional) - comment out if you want full resolution
        max_width = 800
        h, w = frame.shape[:2]
        if w > max_width:
            scale = max_width / float(w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        
        # draw rectangles
        for (x, y, fw, fh) in faces:
            cv2.rectangle(frame, (x, y), (x + fw, y + fh), (0, 255, 0), 2)

        # encode to JPEG and emit via Socket.IO
        _, jpeg = cv2.imencode('.jpg', frame)
        b64 = base64.b64encode(jpeg.tobytes()).decode('ascii')

        # emit the image and metadata
        socketio.emit('frame', {'image': b64, 'faces': len(faces)})

        # throttle loop slightly to avoid CPU spin
        time.sleep(0.03)

    # cleanup
    try:
        if cap is not None:
            cap.release()
    except Exception:
        pass


# Start the worker thread
worker_thread = threading.Thread(target=stream_worker, daemon=True)
worker_thread.start()


# Routes
@app.route('/')
def index():
    return render_template('./index.html')


@app.route('/set_stream', methods=['POST'])
def set_stream():
    data = request.get_json(force=True)
    url = data.get('rtsp_url')
    if not url:
        return jsonify({'ok': False, 'error': 'rtsp_url required'}), 400

    with state_lock:
        state['rtsp_url'] = url

    return jsonify({'ok': True, 'rtsp_url': url})


@app.route('/stop_stream', methods=['POST'])
def stop_stream():
    with state_lock:
        state['rtsp_url'] = None
    return jsonify({'ok': True})

@app.route('/status')
def status():
    with state_lock:
        url = state['rtsp_url']
    return jsonify({'rtsp_url': url})


@socketio.on('connect')
def on_connect():
    print('Client connected')


@socketio.on('disconnect')
def on_disconnect():
    print('Client disconnected')


if __name__ == '__main__':
    # Note: using eventlet (if available) is recommended for production-like websocket behavior.
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)