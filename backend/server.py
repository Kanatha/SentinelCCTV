#!/usr/bin/env python3

try:
    import eventlet
    eventlet.monkey_patch()
    async_mode = 'eventlet'
except Exception:
    eventlet = None
    async_mode = None

import os
import time
import base64
import threading
import subprocess
import numpy as np
from pathlib import Path
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import cv2
import onnxruntime as ort

# --- CONFIGURATION ---
MODEL_DIR = Path("./models")
MODEL_PATH = MODEL_DIR / "yolov5s.onnx"
NAMES_PATH = MODEL_DIR / "coco.names"

DETECT_EVERY_N_FRAMES = 5   # run detection every 5 frames
INFER_SIZE = 640            # YOLO input size (square)
CONF_THRESHOLD = 0.3
NMS_THRESHOLD = 0.45
MAX_WIDTH = 1280            # resize long edge before detection for speed

app = Flask(__name__)
socketio = SocketIO(app, async_mode=async_mode, cors_allowed_origins='*')

# --- load class names ---
if not MODEL_PATH.exists() or not NAMES_PATH.exists():
    raise RuntimeError(f"Model or names not found in {MODEL_DIR}. Put yolov5s.onnx and coco.names there.")

with open(NAMES_PATH, 'r') as f:
    CLASSES = [l.strip() for l in f if l.strip()]

print(f"Loaded {len(CLASSES)} classes from {NAMES_PATH}")

# --- ONNX Runtime session ---
ort_session = ort.InferenceSession(
    str(MODEL_PATH),
    providers=["CPUExecutionProvider"]
)

# --- utilities ---
def letterbox(image, new_shape=(INFER_SIZE, INFER_SIZE), color=(114, 114, 114)):
    shape = image.shape[:2]  # h, w
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
    dw = new_shape[1] - new_unpad[0]
    dh = new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    resized = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    padded = cv2.copyMakeBorder(resized, top, bottom, left, right,
                                cv2.BORDER_CONSTANT, value=color)
    return padded, r, (left, top)


def xywh2xyxy(xywh, r, pad, orig_w, orig_h):
    cx, cy, w, h = xywh
    left, top = pad
    x1 = (cx - w / 2 - left) / r
    y1 = (cy - h / 2 - top) / r
    x2 = (cx + w / 2 - left) / r
    y2 = (cy + h / 2 - top) / r
    x1 = max(0, min(orig_w - 1, int(round(x1))))
    y1 = max(0, min(orig_h - 1, int(round(y1))))
    x2 = max(0, min(orig_w - 1, int(round(x2))))
    y2 = max(0, min(orig_h - 1, int(round(y2))))
    return x1, y1, x2, y2

# --- FFmpeg reader: yields BGR frames at full FPS ---
def ffmpeg_frame_generator(rtsp_url):
    args = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "-"
    ]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**7)
    buf = b''
    SOI = b'\xff\xd8'
    EOI = b'\xff\xd9'
    try:
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            while True:
                start = buf.find(SOI)
                if start == -1:
                    if len(buf) > 10**6:
                        buf = b''
                    break
                end = buf.find(EOI, start)
                if end == -1:
                    if start > 0:
                        buf = buf[start:]
                    break
                jpg = buf[start:end+2]
                buf = buf[end+2:]
                arr = np.frombuffer(jpg, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    yield frame
    finally:
        try:
            proc.kill()
        except Exception:
            pass

# --- Detection using ONNX Runtime (YOLOv5) ---
def detect_yolo(frame):
    orig_h, orig_w = frame.shape[:2]
    long_edge = max(orig_w, orig_h)
    if long_edge > MAX_WIDTH:
        scale = MAX_WIDTH / float(long_edge)
        frame_small = cv2.resize(frame, (int(orig_w * scale), int(orig_h * scale)))
        orig_h, orig_w = frame_small.shape[:2]
    else:
        frame_small = frame

    img, ratio, pad = letterbox(frame_small, new_shape=(INFER_SIZE, INFER_SIZE))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    img = np.transpose(img, (2, 0, 1))[None]  # NCHW

    outputs = ort_session.run(None, {ort_session.get_inputs()[0].name: img})
    preds = outputs[0]
    if preds.ndim == 3:
        preds = preds[0]

    boxes, confidences, class_ids = [], [], []
    for row in preds:
        cx, cy, w, h = row[0:4]
        objness = float(row[4])
        class_scores = row[5:]
        if class_scores.size == 0:
            continue
        class_id = int(np.argmax(class_scores))
        cls_score = float(class_scores[class_id])
        score = objness * cls_score
        if score < CONF_THRESHOLD:
            continue
        x1, y1, x2, y2 = xywh2xyxy((cx, cy, w, h), ratio, pad, orig_w, orig_h)
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        confidences.append(score)
        class_ids.append(class_id)

    detections = []
    if boxes:
        indices = cv2.dnn.NMSBoxes(boxes, confidences, CONF_THRESHOLD, NMS_THRESHOLD)
        if len(indices) > 0:
            for i in indices.flatten():
                x, y, w, h = boxes[i]
                detections.append({
                    'label': CLASSES[class_ids[i]] if class_ids[i] < len(CLASSES) else str(class_ids[i]),
                    'score': confidences[i],
                    'box': (int(x), int(y), int(x + w), int(y + h))
                })
    return detections

# --- Stream Processor ---
class StreamProcessor(threading.Thread):
    def __init__(self, stream_id, rtsp_url):
        super().__init__(daemon=True)
        self.stream_id = str(stream_id)
        self.url = rtsp_url
        self.running = True
        self.last_detections = []
        self.frame_count = 0

    def run(self):
        print(f"[{self.stream_id}] starting stream: {self.url}")
        gen = ffmpeg_frame_generator(self.url)
        for frame in gen:
            if not self.running:
                break

            self.frame_count += 1

            # run detection every N frames
            if self.frame_count % DETECT_EVERY_N_FRAMES == 0:
                try:
                    self.last_detections = detect_yolo(frame)
                except Exception as e:
                    print(f"[{self.stream_id}] detection error:", e)
                    self.last_detections = []

            # draw latest detections
            for d in self.last_detections:
                x1, y1, x2, y2 = d['box']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{d['label']} {d['score']:.2f}"
                cv2.putText(frame, label, (x1, max(15, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            # emit every frame
            try:
                _, jpeg = cv2.imencode('.jpg', frame)
                b64 = base64.b64encode(jpeg.tobytes()).decode('ascii')
                payload = {
                    'stream_id': self.stream_id,
                    'image': b64,
                    'detections': self.last_detections,
                    'frame_num': self.frame_count,
                    'timestamp': time.time()
                }
                socketio.emit('frame', payload)
            except Exception as e:
                print(f"[{self.stream_id}] emit error:", e)

        print(f"[{self.stream_id}] stream ended")

    def stop(self):
        self.running = False

# --- Example streams ---
streams = [
    {"id": "cam1", "url": "rtsp://192.168.1.15/mjpeg/1"},
]

processors = {}
for s in streams:
    p = StreamProcessor(s['id'], s['url'])
    processors[s['id']] = p
    p.start()

# --- Flask endpoints ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/streams')
def list_streams():
    return jsonify([{'id': s['id'], 'url': s['url']} for s in streams])

@socketio.on('connect')
def on_connect():
    print('client connected')

@socketio.on('disconnect')
def on_disconnect():
    print('client disconnected')

if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
    finally:
        for p in processors.values():
            p.stop()
