# plate_detection.py
import cv2
import numpy as np
import imutils
import easyocr
import requests
import json
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import base64
import io
from PIL import Image
import threading
import time

app = Flask(__name__)

class LicensePlateDetector:
    def __init__(self, server_url=None):
        self.server_url = server_url or os.getenv('SERVER_URL', 'https://vehicle-access-system.onrender.com')
        print(f"Connecting to server: {self.server_url}")
        self.reader = easyocr.Reader(['en'])
        self.last_detection_time = 0
        self.detection_cooldown = 5  # seconds between detections of same plate
        self.cap = None
        self.is_camera_active = False
        
    def start_camera(self):
        """Start webcam capture"""
        try:
            self.cap = cv2.VideoCapture(0)  # 0 = default camera
            if not self.cap.isOpened():
                print("❌ Error: Could not open webcam")
                return False
            
            # Set camera resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.is_camera_active = True
            print("✅ Webcam started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error starting camera: {str(e)}")
            return False
    
    def stop_camera(self):
        """Stop webcam capture"""
        if self.cap:
            self.cap.release()
            self.is_camera_active = False
            print("🛑 Webcam stopped")
    
    def capture_frame(self):
        """Capture a frame from webcam"""
        if not self.cap or not self.is_camera_active:
            return None
            
        ret, frame = self.cap.read()
        if ret:
            return frame
        return None
    
    def detect_plate_from_frame(self, frame):
        """Detect license plate from camera frame"""
        try:
            if frame is None:
                return None, "No frame captured"
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            bfilter = cv2.bilateralFilter(gray, 11, 17, 17)
            edged = cv2.Canny(bfilter, 30, 200)
            
            keypoints = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            contours = imutils.grab_contours(keypoints)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
            
            location = None
            for contour in contours:
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                if len(approx) == 4:
                    location = approx
                    break
            
            if location is None:
                return None, "No license plate detected"
            
            mask = np.zeros(gray.shape, np.uint8)
            new_image = cv2.drawContours(mask, [location], 0, 255, -1)
            new_image = cv2.bitwise_and(frame, frame, mask=mask)
            
            (x, y) = np.where(mask == 255)
            (x1, y1) = (np.min(x), np.min(y))
            (x2, y2) = (np.max(x), np.max(y))
            cropped_image = gray[x1:x2+1, y1:y2+1]
            
            result = self.reader.readtext(cropped_image)
            
            if result:
                plate_text = result[0][-2].strip().upper()
                plate_text = ''.join(filter(str.isalnum, plate_text))
                confidence = result[0][-1]
                
                print(f"🚗 Detected License Plate: {plate_text}")
                print(f"📊 Confidence: {confidence:.2f}")
                
                return plate_text, confidence
            else:
                return None, "No text detected on plate"
                
        except Exception as e:
            return None, f"Error processing frame: {str(e)}"
    
    def check_plate_with_server(self, plate_text):
        """Check if plate is registered and get owner details"""
        try:
            response = requests.get(
                f"{self.server_url}/api/registrations",
                timeout=10
            )
            
            if response.status_code == 200:
                registrations = response.json()
                
                for vehicle in registrations:
                    vehicle_plate = vehicle.get('licensePlateNumber', '').upper()
                    vehicle_plate_clean = ''.join(filter(str.isalnum, vehicle_plate))
                    
                    if (vehicle_plate_clean == plate_text and 
                        vehicle.get('status') == 'approved'):
                        return {
                            "approved": True,
                            "vehicle": vehicle
                        }
                
                return {"approved": False, "error": "Vehicle not found or not approved"}
            else:
                return {"approved": False, "error": f"Server error: {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            return {"approved": False, "error": f"Connection error: {str(e)}"}
    
    def send_realtime_update(self, plate_text, status, vehicle_info=None, confidence=0):
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
                f"{self.server_url}/api/realtime-access",
                json=data,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"📡 Real-time update sent: {plate_text} - {status}")
            else:
                print(f"❌ Failed to send real-time update: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending real-time update: {str(e)}")
    
    def process_frame(self, frame):
        """Process a single frame from webcam"""
        plate_text, confidence = self.detect_plate_from_frame(frame)
        
        if plate_text is None:
            return None, {"error": confidence, "approved": False}
        
        # Check if we recently detected this plate (cooldown)
        current_time = time.time()
        if current_time - self.last_detection_time < self.detection_cooldown:
            print("⏳ Skipping duplicate detection (cooldown)")
            return plate_text, {"approved": False, "error": "Duplicate detection"}
        
        self.last_detection_time = current_time
        
        print(f"🔍 Checking plate '{plate_text}' with server...")
        plate_info = self.check_plate_with_server(plate_text)
        
        # Send real-time update to admin dashboard
        if plate_info.get("approved"):
            vehicle = plate_info.get("vehicle", {})
            owner_name = vehicle.get("fullName", "Unknown")
            vehicle_make = vehicle.get("make", "Unknown")
            vehicle_model = vehicle.get("model", "Unknown")
            
            print(f"✅ ACCESS GRANTED")
            print(f"   👤 Owner: {owner_name}")
            print(f"   🚙 Vehicle: {vehicle_make} {vehicle_model}")
            print(f"   🚗 License Plate: {plate_text}")
            
            # Send real-time update
            self.send_realtime_update(
                plate_text, 
                "approved", 
                {
                    "ownerName": owner_name,
                    "vehicleMake": vehicle_make,
                    "vehicleModel": vehicle_model,
                    "fullInfo": vehicle
                },
                confidence
            )
            
            # Log to access logs
            details = f"Approved vehicle - {owner_name} ({vehicle_make} {vehicle_model})"
            self.log_access_attempt(plate_text, "approved", details)
            
        else:
            print(f"❌ ACCESS DENIED")
            print(f"   🚗 License Plate: {plate_text}")
            print(f"   📋 Reason: {plate_info.get('error', 'Vehicle not registered or not approved')}")
            
            # Send real-time update
            self.send_realtime_update(plate_text, "denied", None, confidence)
            
            # Log to access logs
            details = "Vehicle not registered or not approved"
            self.log_access_attempt(plate_text, "denied", details)
        
        return plate_text, plate_info
    
    def log_access_attempt(self, plate_text, status, details):
        """Log the access attempt to the server"""
        try:
            data = {
                "licensePlate": plate_text,
                "status": status,
                "details": details
            }
            
            response = requests.post(
                f"{self.server_url}/api/access-logs",
                json=data,
                timeout=10
            )
            
            return response.status_code == 200
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to log access: {str(e)}")
            return False

    def start_continuous_detection(self):
        """Start continuous plate detection from webcam"""
        if not self.start_camera():
            return False
        
        def detection_loop():
            print("🔄 Starting continuous plate detection...")
            while self.is_camera_active:
                try:
                    frame = self.capture_frame()
                    if frame is not None:
                        # Process the frame
                        plate_text, result = self.process_frame(frame)
                        
                        # Display frame with results (optional)
                        if plate_text:
                            cv2.putText(frame, f"Plate: {plate_text}", (10, 30), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        
                        # Show the frame (comment out if running on server without display)
                        cv2.imshow('UNZA Plate Detection', frame)
                        
                        # Break on 'q' key press
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                            
                    time.sleep(0.1)  # Small delay between frames
                    
                except Exception as e:
                    print(f"Error in detection loop: {str(e)}")
                    break
            
            # Cleanup
            self.stop_camera()
            cv2.destroyAllWindows()
        
        # Start detection in a separate thread
        detection_thread = threading.Thread(target=detection_loop)
        detection_thread.daemon = True
        detection_thread.start()
        return True

# Initialize detector
detector = LicensePlateDetector()

# Simple HTML template for web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>UNZA Plate Detection</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #228B22; text-align: center; }
        .button { background: #228B22; color: white; padding: 15px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin: 10px; }
        .button.stop { background: #dc3545; }
        .status { padding: 15px; border-radius: 5px; margin: 10px 0; text-align: center; font-weight: bold; }
        .ready { background: #d4edda; color: #155724; }
        .scanning { background: #fff3cd; color: #856404; }
        .error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <h1>UNIVERSITY OF ZAMBIA</h1>
        <h2>Real-time Plate Detection</h2>
        
        <div id="status" class="status ready">
            🟢 Ready to start plate detection
        </div>
        
        <div style="text-align: center;">
            <button class="button" onclick="startDetection()">🚗 Start Plate Detection</button>
            <button class="button stop" onclick="stopDetection()">⏹️ Stop Detection</button>
        </div>
        
        <div id="results" style="margin-top: 20px;"></div>
    </div>

    <script>
        function startDetection() {
            document.getElementById('status').className = 'status scanning';
            document.getElementById('status').textContent = '🔍 Starting camera and detection...';
            
            fetch('/start-detection', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('status').className = 'status ready';
                    document.getElementById('status').textContent = '✅ Camera started - Scanning for license plates...';
                    updateResults();
                } else {
                    document.getElementById('status').className = 'status error';
                    document.getElementById('status').textContent = '❌ ' + data.error;
                }
            })
            .catch(error => {
                document.getElementById('status').className = 'status error';
                document.getElementById('status').textContent = '❌ Error starting detection';
            });
        }

        function stopDetection() {
            fetch('/stop-detection', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                document.getElementById('status').className = 'status ready';
                document.getElementById('status').textContent = '🛑 Detection stopped';
            });
        }

        function updateResults() {
            // This would be updated via WebSocket in a real implementation
            // For now, we'll just show a message
            document.getElementById('results').innerHTML = 
                '<div style="text-align: center; color: #666; margin: 20px;">' +
                '🔍 Camera is active. Show a license plate to the webcam.<br>' +
                'Detections will appear in the Admin Dashboard in real-time!' +
                '</div>';
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/start-detection', methods=['POST'])
def start_detection():
    """Start continuous plate detection"""
    try:
        success = detector.start_continuous_detection()
        if success:
            return jsonify({"success": True, "message": "Plate detection started"})
        else:
            return jsonify({"success": False, "error": "Could not start camera"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stop-detection', methods=['POST'])
def stop_detection():
    """Stop plate detection"""
    try:
        detector.stop_camera()
        return jsonify({"success": True, "message": "Plate detection stopped"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/detect', methods=['POST'])
def detect_plate():
    """API endpoint for single image detection"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({"error": "No image selected"}), 400
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_path = f"temp_{timestamp}.jpg"
        image_file.save(image_path)
        
        # Use the existing image processing method
        plate_text, result = detector.process_image(image_path)
        
        if os.path.exists(image_path):
            os.remove(image_path)
        
        if plate_text is None:
            return jsonify({"error": result.get("error", "Detection failed")})
        
        return jsonify({
            "plate_text": plate_text,
            "result": result
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "plate_detection"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting UNZA Plate Detection System on port {port}")
    print(f"📷 Webcam will be accessible when you visit the website")
    app.run(host='0.0.0.0', port=port, debug=False)