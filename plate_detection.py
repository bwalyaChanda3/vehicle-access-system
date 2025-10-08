# plate_detection.py
import cv2
import numpy as np
import imutils
import easyocr
import requests
import json
from datetime import datetime

class LicensePlateDetector:
    def __init__(self, server_url=None):
        self.server_url = server_url or os.getenv('SERVER_URL', 'http://your-domain.com:3000')
        self.reader = easyocr.Reader(['en'])

    def detect_from_camera(self):
        """For real-time camera detection"""
        cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if ret:
                # Save frame and process
                cv2.imwrite("temp_frame.jpg", frame)
                self.process_image("temp_frame.jpg")  # Fixed: added self.
            cv2.waitKey(1000)  # Process every second
        
    def detect_plate_from_image(self, image_path):
        """Detect license plate from image file"""
        try:
            # Read and process image
            img = cv2.imread(image_path)
            if img is None:
                return None, "Could not load image"
                
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply filter and find edges
            bfilter = cv2.bilateralFilter(gray, 11, 17, 17)
            edged = cv2.Canny(bfilter, 30, 200)
            
            # Find contours
            keypoints = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            contours = imutils.grab_contours(keypoints)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
            
            # Find license plate location
            location = None
            for contour in contours:
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                if len(approx) == 4:
                    location = approx
                    break
            
            if location is None:
                return None, "No license plate detected"
            
            # Extract and process plate region
            mask = np.zeros(gray.shape, np.uint8)
            new_image = cv2.drawContours(mask, [location], 0, 255, -1)
            new_image = cv2.bitwise_and(img, img, mask=mask)
            
            (x, y) = np.where(mask == 255)
            (x1, y1) = (np.min(x), np.min(y))
            (x2, y2) = (np.max(x), np.max(y))
            cropped_image = gray[x1:x2+1, y1:y2+1]
            
            # Extract text using EasyOCR
            result = self.reader.readtext(cropped_image)
            
            if result:
                plate_text = result[0][-2].strip().upper()
                confidence = result[0][-1]
                
                print(f"Detected License Plate: {plate_text}")
                print(f"Confidence: {confidence:.2f}")
                
                return plate_text, confidence
            else:
                return None, "No text detected on plate"
                
        except Exception as e:
            return None, f"Error processing image: {str(e)}"
    
    def check_plate_with_server(self, plate_text):
        """Check if plate is registered and get owner details"""
        try:
            # First, get all registrations
            response = requests.get(
                f"{self.server_url}/api/registrations",
                timeout=5
            )
            
            if response.status_code == 200:
                registrations = response.json()
                
                # Find the plate in registrations
                for vehicle in registrations:
                    if (vehicle.get('licensePlateNumber', '').upper() == plate_text.upper() and 
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
    
    def log_access_attempt(self, plate_text, status, details):
        """Log the access attempt to the server"""
        try:
            data = {
                "licensePlate": plate_text,
                "status": status,
                "details": details
            }
            
            response = requests.post(
                f"{self.server_url}/api/access-logs",  # Fixed: changed to access-logs
                json=data,
                timeout=5
            )
            
            return response.status_code == 200
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to log access: {str(e)}")
            return False
    
    def process_image(self, image_path):
        """Complete processing pipeline"""
        print(f"Processing image: {image_path}")
        print("-" * 50)
        
        # Step 1: Detect license plate
        plate_text, confidence = self.detect_plate_from_image(image_path)
        
        if plate_text is None:
            print(f"❌ Detection failed: {confidence}")
            return None, None
        
        # Step 2: Check with server
        print(f"🔍 Checking plate '{plate_text}' with server...")
        plate_info = self.check_plate_with_server(plate_text)
        
        # Step 3: Process result
        if plate_info.get("approved"):
            vehicle = plate_info.get("vehicle", {})
            owner_name = vehicle.get("fullName", "Unknown")
            vehicle_make = vehicle.get("make", "Unknown")
            vehicle_model = vehicle.get("model", "Unknown")
            
            print(f"✅ ACCESS GRANTED")
            print(f"   Owner: {owner_name}")
            print(f"   Vehicle: {vehicle_make} {vehicle_model}")
            print(f"   License Plate: {plate_text}")
            
            # Log successful access
            details = f"Approved vehicle - {owner_name} ({vehicle_make} {vehicle_model})"
            self.log_access_attempt(plate_text, "approved", details)
            
        else:
            print(f"❌ ACCESS DENIED")
            print(f"   License Plate: {plate_text}")
            print(f"   Reason: {plate_info.get('error', 'Vehicle not registered or not approved')}")
            
            # Log denied access
            details = "Vehicle not registered or not approved"
            self.log_access_attempt(plate_text, "denied", details)
        
        print("-" * 50)
        return plate_text, plate_info

# Usage example
if __name__ == "__main__":
    detector = LicensePlateDetector()
    
    # Process your image
    image_path = "C:\\Users\\Bwalya\\Downloads\\image6.webp"
    plate_text, result = detector.process_image(image_path)