"""
Ultra-Fast Person Detection (CPU Optimized)
============================================
Optimized for CPU-only systems using ONNX Runtime.

Usage:
    python realtime_person_detection.py
    
First run will convert the model to ONNX format.
Press 'q' to quit.
"""

import os
import cv2
import numpy as np
from threading import Thread
from argparse import ArgumentParser


def convert_to_onnx(weights_path, onnx_path, input_size=256):
    """Convert PyTorch model to ONNX for fast CPU inference."""
    import torch
    from nets import nn
    
    print("Converting model to ONNX (one-time setup)...")
    
    # Load model
    checkpoint = torch.load(weights_path, map_location='cpu')
    model = checkpoint['model'].float()
    model.fuse()
    model.eval()
    
    # Export
    dummy_input = torch.zeros(1, 3, input_size, input_size)
    torch.onnx.export(
        model, dummy_input, onnx_path,
        opset_version=12,
        input_names=['images'],
        output_names=['output'],
        dynamic_axes={'images': {0: 'batch'}, 'output': {0: 'batch', 2: 'anchors'}}
    )
    print(f"Saved ONNX model: {onnx_path}")


def xywh2xyxy(x):
    """Convert boxes from (cx,cy,w,h) to (x1,y1,x2,y2)."""
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def nms_numpy(boxes, scores, iou_threshold=0.5):
    """Pure NumPy NMS for speed."""
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        
        w = np.maximum(0, xx2 - xx1)
        h = np.maximum(0, yy2 - yy1)
        inter = w * h
        
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-7)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    
    return keep


class UltraFastDetector:
    """Ultra-fast detector using ONNX Runtime."""
    
    def __init__(self, onnx_path, input_size=256, conf=0.5, iou=0.5):
        import onnxruntime as ort
        
        self.input_size = input_size
        self.conf_threshold = conf
        self.iou_threshold = iou
        
        # ONNX Runtime with optimizations
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = 4
        
        self.session = ort.InferenceSession(onnx_path, opts, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        
        # Warm up
        dummy = np.zeros((1, 3, input_size, input_size), dtype=np.float32)
        self.session.run(None, {self.input_name: dummy})
        print("ONNX Runtime ready!")
    
    def detect(self, frame):
        h0, w0 = frame.shape[:2]
        
        # Fast letterbox resize
        scale = self.input_size / max(h0, w0)
        new_w, new_h = int(w0 * scale), int(h0 * scale)
        
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Pad
        pad_w = (self.input_size - new_w) // 2
        pad_h = (self.input_size - new_h) // 2
        
        padded = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        padded[pad_h:pad_h+new_h, pad_w:pad_w+new_w] = resized
        
        # Preprocess: HWC->CHW, BGR->RGB, normalize
        blob = padded[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        blob = blob[np.newaxis, ...]
        
        # Inference
        output = self.session.run(None, {self.input_name: blob})[0][0]
        
        # Post-process: output shape is (5, num_anchors) for 1 class
        output = output.T  # (num_anchors, 5)
        
        # Filter by confidence
        scores = output[:, 4]
        mask = scores > self.conf_threshold
        output = output[mask]
        scores = scores[mask]
        
        if len(output) == 0:
            return []
        
        # Convert boxes
        boxes = xywh2xyxy(output[:, :4])
        
        # NMS
        keep = nms_numpy(boxes, scores, self.iou_threshold)
        boxes = boxes[keep]
        scores = scores[keep]
        
        # Scale back to original image
        boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_w) / scale
        boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_h) / scale
        
        # Clip
        boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, w0)
        boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, h0)
        
        return [(int(b[0]), int(b[1]), int(b[2]), int(b[3]), s) for b, s in zip(boxes, scores)]


class VideoCaptureFast:
    """Threaded capture for zero-lag reading."""
    
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.frame = None
        self.stopped = False
        Thread(target=self._read, daemon=True).start()
    
    def _read(self):
        while not self.stopped:
            ret, self.frame = self.cap.read()
    
    def read(self):
        return self.frame.copy() if self.frame is not None else None
    
    def release(self):
        self.stopped = True
        self.cap.release()


def run_detection(source='0', input_size=256, conf=0.5, skip=2):
    """Run ultra-fast detection."""
    
    weights_path = './weights/best.pt'
    onnx_path = f'./weights/model_{input_size}.onnx'
    
    # Convert to ONNX if needed
    if not os.path.exists(onnx_path):
        convert_to_onnx(weights_path, onnx_path, input_size)
    
    # Initialize
    detector = UltraFastDetector(onnx_path, input_size, conf)
    
    src = int(source) if source.isdigit() else source
    cap = VideoCaptureFast(src)
    
    print(f"\nRunning (size={input_size}, skip={skip})")
    print("Press 'q' to quit\n")
    
    frame_count = 0
    detections = []
    prev_tick = cv2.getTickCount()
    
    while True:
        frame = cap.read()
        if frame is None:
            continue
        
        frame_count += 1
        
        # Detect every N frames
        if frame_count % skip == 0:
            detections = detector.detect(frame)
        
        # Draw enhanced detections
        for x1, y1, x2, y2, conf in detections:
            # Color based on confidence (green=high, yellow=medium, red=low)
            if conf >= 0.7:
                color = (0, 255, 0)  # Green - high confidence
            elif conf >= 0.5:
                color = (0, 255, 255)  # Yellow - medium
            else:
                color = (0, 165, 255)  # Orange - lower
            
            # Draw box with thickness based on confidence
            thickness = 2 if conf < 0.7 else 3
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Confidence percentage label
            percent = int(conf * 100)
            label = f"Person {percent}%"
            
            # Label background
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - lh - 10), (x1 + lw + 10, y1), color, -1)
            
            # Label text (white for contrast)
            cv2.putText(frame, label, (x1 + 5, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            cv2.putText(frame, label, (x1 + 5, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # FPS
        curr_tick = cv2.getTickCount()
        fps = cv2.getTickFrequency() / (curr_tick - prev_tick + 1)
        prev_tick = curr_tick
        
        # Info bar at top
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 40), (40, 40, 40), -1)
        cv2.putText(frame, f'Persons: {len(detections)}', (15, 28), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f'FPS: {int(fps)}', (w - 100, 28), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        cv2.imshow('Person Detection (Press Q to quit)', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('--source', default='0', help='Camera or video')
    parser.add_argument('--size', default=256, type=int, help='Input size (smaller=faster)')
    parser.add_argument('--conf', default=0.5, type=float, help='Confidence')
    parser.add_argument('--skip', default=2, type=int, help='Process every Nth frame')
    args = parser.parse_args()
    
    run_detection(args.source, args.size, args.conf, args.skip)
