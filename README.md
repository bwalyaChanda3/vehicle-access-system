# University of Zambia - Vehicle Access System

A comprehensive vehicle registration and monitoring system for the University of Zambia campus security.

## Features

### 🚗 Vehicle Registration System
- **Professional Registration Form** with University of Zambia branding
- **Comprehensive Owner Details**:
  - Full Name
  - National Registration Card Number
  - License Number
  - Place of Residence
  - Phone Number (+260 format)

- **Detailed Vehicle Information**:
  - License Plate Number
  - Registration Mark
  - VIN/Chassis Number
  - Engine Number
  - Make, Model, Model Number
  - Color(s)
  - Vehicle Category (Private, Commercial, Government, Diplomatic)
  - Propelled By (Petrol, Diesel, Electric, Hybrid, LPG)
  - Net Weight, GVM (kg)
  - Vehicle Class (A, B, C, D)
  - Engine Capacity (cc)
  - Seating Capacity
  - Registration Authority
  - Year of Make
  - First Registration Date
  - Customs Clearance Number
  - Interpol Number (xx/xxx format)

### 🔐 Admin Dashboard
- **Dashboard Overview** with real-time statistics
- **Registration Management**:
  - View all registration requests
  - Approve/Reject applications
  - View detailed vehicle information
  - Manage approved vehicles

- **Access Monitoring**:
  - Real-time access logs
  - Vehicle movement tracking
  - Access attempt history

- **Weekly Reports**:
  - Generate comprehensive weekly reports
  - Statistics on registrations and access attempts
  - Export capabilities for further analysis

### 🛡️ Security Features
- Real-time WebSocket connections for live updates
- Comprehensive logging of all access attempts
- Status tracking (Pending, Approved, Rejected)
- Detailed audit trail

## Technology Stack

- **Backend**: Node.js with Express.js
- **Database**: SQLite3
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Real-time**: WebSocket connections
- **Styling**: Custom CSS with responsive design

## Installation & Setup

1. **Prerequisites**:
   - Node.js (v14 or higher)
   - npm (Node Package Manager)

2. **Install Dependencies**:
   ```bash
   npm install
   ```

3. **Start the Server**:
   ```bash
   npm start
   ```

4. **Access the System**:
   - **Registration Portal**: http://localhost:3000
   - **Admin Dashboard**: http://localhost:3000/admin

## Usage

### For Vehicle Owners
1. Visit the registration portal
2. Fill in all required owner and vehicle details
3. Submit the registration form
4. Wait for admin approval
5. Receive notification once approved

### For Administrators
1. Access the admin dashboard
2. Review pending registration requests
3. Approve or reject applications
4. Monitor vehicle access in real-time
5. Generate weekly reports for analysis

## Database Schema

The system uses SQLite3 with the following main tables:

- **registrations**: Stores all vehicle registration data
- **access_logs**: Records all vehicle access attempts

## API Endpoints

- `POST /api/register` - Submit vehicle registration
- `GET /api/registrations` - Get all registrations (admin)
- `PUT /api/registrations/:id` - Update registration status
- `GET /api/access-logs` - Get access logs
- `POST /api/access-log` - Log vehicle access
- `GET /api/check-plate/:licensePlate` - Check if plate is approved
- `GET /api/reports/weekly` - Generate weekly reports

## Security Considerations

- All form inputs are validated server-side
- Phone numbers are formatted with +260 prefix
- License plates are automatically converted to uppercase
- Interpol numbers follow xx/xxx format
- Real-time monitoring prevents unauthorized access

## Future Enhancements

- Integration with camera systems for automatic plate detection
- SMS notifications for registration status updates
- Mobile app for easier access
- Advanced analytics and reporting
- Integration with campus security systems

## Support

For technical support or questions about the system, please contact the University of Zambia IT department.

---

**University of Zambia**  
*Vehicle Access Control System*  
*Version 2.0 - Professional Edition*