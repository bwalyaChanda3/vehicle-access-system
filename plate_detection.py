# plate_detection.py
import cv2
import numpy as np
import imutils
import easyocr
import requests
import os
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import threading

app = Flask(__name__)

# Configuration
SERVER_URL = os.getenv('SERVER_URL', 'https://vehicle-access-system.onrender.com')  # ⚠️ UPDATE THIS
print(f"🎯 Target Server: {SERVER_URL}")

class LicensePlateDetector:
    def __init__(self):
        self.reader = easyocr.Reader(['en'])
        self.last_detection_time = 0
        self.detection_cooldown = 5
        self.cap = None
        self.is_detecting = False
        
    def start_detection(self):
        """Start webcam detection"""
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("❌ Cannot open webcam")
                return False
            
            self.is_detecting = True
            print("✅ Webcam started - Beginning detection loop")
            
            # Start detection in background thread
            thread = threading.Thread(target=self._detection_loop)
            thread.daemon = True
            thread.start()
            return True
            
        except Exception as e:
            print(f"❌ Error starting detection: {e}")
            return False
    
    def _detection_loop(self):
        """Main detection loop"""
        while self.is_detecting and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if not ret:
                    continue
                
                # Process frame for license plate
                plate_text, confidence = self._detect_plate(frame)
                
                if plate_text:
                    print(f"🚗 DETECTED: {plate_text} (Confidence: {confidence:.2f})")
                    
                    # Check with server and send real-time update
                    self._process_detection(plate_text, confidence)
                
                # Add delay to prevent overwhelming the system
                time.sleep(2)
                
            except Exception as e:
                print(f"⚠️ Detection loop error: {e}")
                time.sleep(1)
    
    def _detect_plate(self, frame):
        """Detect license plate in frame"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            bfilter = cv2.bilateralFilter(gray, 11, 17, 17)
            edged = cv2.Canny(bfilter, 30, 200)
            
            contours = imutils.grab_contours(
                cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            )
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
            
            location = None
            for contour in contours:
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                if len(approx) == 4:
                    location = approx
                    break
            
            if location is None:
                return None, 0
            
            # Extract plate region
            mask = np.zeros(gray.shape, np.uint8)
            cv2.drawContours(mask, [location], 0, 255, -1)
            new_image = cv2.bitwise_and(frame, frame, mask=mask)
            
            (x, y) = np.where(mask == 255)
            if len(x) == 0 or len(y) == 0:
                return None, 0
                
            x1, y1, x2, y2 = np.min(x), np.min(y), np.max(x), np.max(y)
            cropped_image = gray[x1:x2+1, y1:y2+1]
            
            # OCR the plate
            result = self.reader.readtext(cropped_image)
            if result:
                plate_text = result[0][-2].strip().upper()
                plate_text = ''.join(filter(str.isalnum, plate_text))
                confidence = result[0][-1]
                return plate_text, confidence
                
            return None, 0
            
        except Exception as e:
            print(f"Detection error: {e}")
            return None, 0
    
    def _process_detection(self, plate_text, confidence):
        """Process detected plate and send to server"""
        try:
            # Check cooldown
            current_time = time.time()
            if current_time - self.last_detection_time < self.detection_cooldown:
                return
            
            self.last_detection_time = current_time
            
            print(f"🔍 Checking plate '{plate_text}' with server...")
            
            # 1. Check if plate is approved
            plate_info = self._check_plate_with_server(plate_text)
            
            # 2. Send real-time update
            if plate_info.get("approved"):
                vehicle = plate_info.get("vehicle", {})
                print(f"✅ APPROVED: {vehicle.get('fullName', 'Unknown')}")
                
                self._send_realtime_update(
                    plate_text, "approved", 
                    {
                        "ownerName": vehicle.get('fullName', 'Unknown'),
                        "vehicleMake": vehicle.get('make', 'Unknown'),
                        "vehicleModel": vehicle.get('model', 'Unknown')
                    },
                    confidence
                )
            else:
                print(f"❌ DENIED: {plate_info.get('error', 'Unknown reason')}")
                self._send_realtime_update(plate_text, "denied", None, confidence)
                
        except Exception as e:
            print(f"❌ Error processing detection: {e}")
    
    def _check_plate_with_server(self, plate_text):
        """Check plate registration status"""
        try:
            response = requests.get(f"{SERVER_URL}/api/registrations", timeout=10)
            
            if response.status_code == 200:
                registrations = response.json()
                
                for vehicle in registrations:
                    vehicle_plate = vehicle.get('licensePlateNumber', '').upper()
                    vehicle_plate_clean = ''.join(filter(str.isalnum, vehicle_plate))
                    
                    if (vehicle_plate_clean == plate_text and 
                        vehicle.get('status') == 'approved'):
                        return {"approved": True, "vehicle": vehicle}
                
                return {"approved": False, "error": "Not registered or not approved"}
            else:
                return {"approved": False, "error": f"Server error: {response.status_code}"}
                
        except Exception as e:
            return {"approved": False, "error": f"Connection error: {e}"}
    
    def _send_realtime_update(self, plate_text, status, vehicle_info, confidence):
        """Send real-time update to admin dashboard"""
        try:
            data = {
                "licensePlate": plate_text,
                "status": status,
                "vehicleInfo": vehicle_info,
                "timestamp": datetime.now().isoformat(),
                "confidence": confidence
            }
            
            response = requests.post(
                f"{SERVER_URL}/api/realtime-access",
                json=data,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"📡 Real-time update SENT: {plate_text} - {status}")
            else:
                print(f"❌ Failed to send update: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error sending real-time update: {e}")
    
    def stop_detection(self):
        """Stop detection"""
        self.is_detecting = False
        if self.cap:
            self.cap.release()
        print("🛑 Detection stopped")

# Global detector instance
detector = LicensePlateDetector()

# Simple web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>UNZA Plate Detection</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
        h1 { color: #228B22; text-align: center; }
        .status { padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; font-weight: bold; }
        .ready { background: #d4edda; color: #155724; }
        .active { background: #cce5ff; color: #004085; }
        .error { background: #f8d7da; color: #721c24; }
        button { background: #228B22; color: white; padding: 15px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin: 10px; }
        .stop { background: #dc3545; }
    </style>
</head>
<body>
    <div class="container">
        <h1>UNZA Plate Detection</h1>
        <div id="status" class="status ready">🟢 Ready to start detection</div>
        
        <div style="text-align: center;">
            <button onclick="startDetection()">🚗 Start Detection</button>
            <button class="stop" onclick="stopDetection()">⏹️ Stop</button>
        </div>
        
        <div id="logs" style="margin-top: 20px; height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background: #fafafa;">
            <div>🔍 Detection logs will appear here...</div>
        </div>
    </div>

    <script>
        function addLog(message) {
            const logs = document.getElementById('logs');
            const logEntry = document.createElement('div');
            logEntry.textContent = '[' + new Date().toLocaleTimeString() + '] ' + message;
            logs.appendChild(logEntry);
            logs.scrollTop = logs.scrollHeight;
        }

        async function startDetection() {
            document.getElementById('status').className = 'status active';
            document.getElementById('status').textContent = '🔍 Starting detection...';
            addLog('Starting plate detection...');
            
            try {
                const response = await fetch('/start', { method: 'POST' });
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('status').className = 'status active';
                    document.getElementById('status').textContent = '✅ Detection active - Show license plates to camera';
                    addLog('Detection started successfully');
                } else {
                    document.getElementById('status').className = 'status error';
                    document.getElementById('status').textContent = '❌ ' + result.error;
                    addLog('Error: ' + result.error);
                }
            } catch (error) {
                document.getElementById('status').className = 'status error';
                document.getElementById('status').textContent = '❌ Connection error';
                addLog('Connection error: ' + error);
            }
        }

        async function stopDetection() {
            try {
                await fetch('/stop', { method: 'POST' });
                document.getElementById('status').className = 'status ready';
                document.getElementById('status').textContent = '🛑 Detection stopped';
                addLog('Detection stopped');
            } catch (error) {
                addLog('Error stopping detection: ' + error);
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/start', methods=['POST'])
def start_detection():
    try:
        success = detector.start_detection()
        return jsonify({"success": success, "message": "Detection started" if success else "Failed to start"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stop', methods=['POST'])
def stop_detection():
    try:
        detector.stop_detection()
        return jsonify({"success": True, "message": "Detection stopped"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "service": "plate_detection",
        "server_url": SERVER_URL,
        "detecting": detector.is_detecting
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 UNZA Plate Detection starting on port {port}")
    print(f"🎯 Main server: {SERVER_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)