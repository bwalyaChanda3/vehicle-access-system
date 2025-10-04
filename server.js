const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const WebSocket = require('ws');
const http = require('http');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

// Middleware
app.use(express.json());
app.use(express.static('public'));

// Database setup
const db = new sqlite3.Database(process.env.DATABASE_URL || './vehicles.db', (err) => {
    if (err) {
        console.error('Error opening database:', err.message);
    } else {
        console.log('Connected to SQLite database.');
        
        // Create tables if they don't exist
        db.run(`CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            -- Owner Details
            fullName TEXT NOT NULL,
            nationalRegistrationCard TEXT NOT NULL,
            licenseNumber TEXT NOT NULL,
            placeOfResidence TEXT NOT NULL,
            phoneNumber TEXT NOT NULL,
            -- Vehicle Details
            licensePlateNumber TEXT UNIQUE NOT NULL,
            registrationMark TEXT NOT NULL,
            vinChassisNumber TEXT NOT NULL,
            engineNumber TEXT NOT NULL,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            modelNumber TEXT NOT NULL,
            color TEXT NOT NULL,
            vehicleCategory TEXT NOT NULL,
            propelledBy TEXT NOT NULL,
            netWeight TEXT NOT NULL,
            gvmKg TEXT NOT NULL,
            class TEXT NOT NULL,
            engineCapacity TEXT NOT NULL,
            seatingCapacity TEXT NOT NULL,
            registrationAuthority TEXT NOT NULL,
            yearOfMake TEXT NOT NULL,
            firstRegistrationDate TEXT NOT NULL,
            customsClearanceNumber TEXT NOT NULL,
            interpolNumber TEXT NOT NULL,
            -- System fields
            status TEXT DEFAULT 'pending',
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
        )`);
        
        db.run(`CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licensePlate TEXT NOT NULL,
            accessTime DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            details TEXT
        )`);
    }
});

// WebSocket connections for real-time updates
const clients = new Set();

wss.on('connection', (ws) => {
    clients.add(ws);
    console.log('New client connected');
    
    ws.on('close', () => {
        clients.remove(ws);
        console.log('Client disconnected');
    });
});

// Broadcast to all connected clients
function broadcast(data) {
    clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify(data));
        }
    });
}

// API Routes

// User registration
app.post('/api/register', (req, res) => {
    const {
        // Owner Details
        fullName, nationalRegistrationCard, licenseNumber, placeOfResidence, phoneNumber,
        // Vehicle Details
        licensePlateNumber, registrationMark, vinChassisNumber, engineNumber, make, model,
        modelNumber, color, vehicleCategory, propelledBy, netWeight, gvmKg, class: vehicleClass,
        engineCapacity, seatingCapacity, registrationAuthority, yearOfMake, firstRegistrationDate,
        customsClearanceNumber, interpolNumber
    } = req.body;
    
    // Validate required fields
    const requiredFields = [
        'fullName', 'nationalRegistrationCard', 'licenseNumber', 'placeOfResidence', 'phoneNumber',
        'licensePlateNumber', 'registrationMark', 'vinChassisNumber', 'engineNumber', 'make', 'model',
        'modelNumber', 'color', 'vehicleCategory', 'propelledBy', 'netWeight', 'gvmKg', 'vehicleClass',
        'engineCapacity', 'seatingCapacity', 'registrationAuthority', 'yearOfMake', 'firstRegistrationDate',
        'customsClearanceNumber', 'interpolNumber'
    ];
    
    const missingFields = requiredFields.filter(field => !req.body[field]);
    if (missingFields.length > 0) {
        return res.status(400).json({ 
            error: 'All fields are required', 
            missingFields: missingFields 
        });
    }
    
    const sql = `INSERT INTO registrations (
        fullName, nationalRegistrationCard, licenseNumber, placeOfResidence, phoneNumber,
        licensePlateNumber, registrationMark, vinChassisNumber, engineNumber, make, model,
        modelNumber, color, vehicleCategory, propelledBy, netWeight, gvmKg, class,
        engineCapacity, seatingCapacity, registrationAuthority, yearOfMake, firstRegistrationDate,
        customsClearanceNumber, interpolNumber
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`;
    
    const values = [
        fullName, nationalRegistrationCard, licenseNumber, placeOfResidence, phoneNumber,
        licensePlateNumber, registrationMark, vinChassisNumber, engineNumber, make, model,
        modelNumber, color, vehicleCategory, propelledBy, netWeight, gvmKg, vehicleClass,
        engineCapacity, seatingCapacity, registrationAuthority, yearOfMake, firstRegistrationDate,
        customsClearanceNumber, interpolNumber
    ];
    
    db.run(sql, values, function(err) {
        if (err) {
            if (err.message.includes('UNIQUE constraint failed')) {
                return res.status(400).json({ error: 'License plate already registered' });
            }
            return res.status(500).json({ error: 'Database error' });
        }
        
        res.json({ 
            success: true, 
            message: 'Registration submitted successfully',
            id: this.lastID 
        });
        
        // Notify admin dashboard of new registration
        broadcast({ type: 'new_registration', data: req.body });
    });
});

// Get all registrations (for admin)
app.get('/api/registrations', (req, res) => {
    db.all('SELECT * FROM registrations ORDER BY createdAt DESC', [], (err, rows) => {
        if (err) {
            return res.status(500).json({ error: 'Database error' });
        }
        res.json(rows);
    });
});

// Update registration status (approve/reject)
app.put('/api/registrations/:id', (req, res) => {
    const { id } = req.params;
    const { status } = req.body;
    
    if (!['approved', 'rejected'].includes(status)) {
        return res.status(400).json({ error: 'Invalid status' });
    }
    
    db.run('UPDATE registrations SET status = ? WHERE id = ?', [status, id], function(err) {
        if (err) {
            return res.status(500).json({ error: 'Database error' });
        }
        
        if (this.changes === 0) {
            return res.status(404).json({ error: 'Registration not found' });
        }
        
        res.json({ success: true, message: `Registration ${status}` });
        
        // Notify of status change
        broadcast({ type: 'registration_updated', id, status });
    });
});

// Log vehicle access
app.post('/api/access-log', (req, res) => {
    const { licensePlate, status, details } = req.body;
    
    if (!licensePlate || !status) {
        return res.status(400).json({ error: 'License plate and status are required' });
    }
    
    const sql = `INSERT INTO access_logs (licensePlate, status, details) VALUES (?, ?, ?)`;
    
    db.run(sql, [licensePlate, status, details || ''], function(err) {
        if (err) {
            return res.status(500).json({ error: 'Database error' });
        }
        
        res.json({ success: true, id: this.lastID });
        
        // Notify of new access log
        broadcast({ type: 'access_log', data: { licensePlate, status, details, accessTime: new Date() } });
    });
});

// Get access logs
app.get('/api/access-logs', (req, res) => {
    const limit = req.query.limit || 50;
    
    db.all(`SELECT * FROM access_logs ORDER BY accessTime DESC LIMIT ?`, [limit], (err, rows) => {
        if (err) {
            return res.status(500).json({ error: 'Database error' });
        }
        res.json(rows);
    });
});

// Check if a license plate is approved
app.get('/api/check-plate/:licensePlate', (req, res) => {
    const { licensePlate } = req.params;
    
    db.get('SELECT * FROM registrations WHERE licensePlateNumber = ? AND status = "approved"', [licensePlate], (err, row) => {
        if (err) {
            return res.status(500).json({ error: 'Database error' });
        }
        
        if (row) {
            res.json({ approved: true, vehicle: row });
        } else {
            res.json({ approved: false });
        }
    });
});

// Get weekly reports
app.get('/api/reports/weekly', (req, res) => {
    const { startDate, endDate } = req.query;
    
    if (!startDate || !endDate) {
        return res.status(400).json({ error: 'Start date and end date are required' });
    }
    
    // Get registrations for the week
    db.all(`
        SELECT * FROM registrations 
        WHERE date(createdAt) BETWEEN ? AND ? 
        ORDER BY createdAt DESC
    `, [startDate, endDate], (err, registrations) => {
        if (err) {
            return res.status(500).json({ error: 'Database error' });
        }
        
        // Get access logs for the week
        db.all(`
            SELECT * FROM access_logs 
            WHERE date(accessTime) BETWEEN ? AND ? 
            ORDER BY accessTime DESC
        `, [startDate, endDate], (err, accessLogs) => {
            if (err) {
                return res.status(500).json({ error: 'Database error' });
            }
            
            // Generate statistics
            const stats = {
                totalRegistrations: registrations.length,
                approvedRegistrations: registrations.filter(r => r.status === 'approved').length,
                pendingRegistrations: registrations.filter(r => r.status === 'pending').length,
                rejectedRegistrations: registrations.filter(r => r.status === 'rejected').length,
                totalAccessAttempts: accessLogs.length,
                successfulAccess: accessLogs.filter(l => l.status === 'approved').length,
                deniedAccess: accessLogs.filter(l => l.status === 'denied').length,
                registrations: registrations,
                accessLogs: accessLogs
            };
            
            res.json(stats);
        });
    });
});

// Serve admin page
app.get('/admin', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on port ${PORT}`);
    console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});