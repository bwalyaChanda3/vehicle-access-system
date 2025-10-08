const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Database - Use SQLite (works on Render)
const db = new sqlite3.Database('./vehicle_registration.db', (err) => {
    if (err) {
        console.error('Error opening database:', err.message);
    } else {
        console.log('Connected to SQLite database.');
        initializeDatabase();
    }
});

// Create tables if they don't exist
function initializeDatabase() {
    db.run(`CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullName TEXT NOT NULL,
        nationalRegistrationCard TEXT NOT NULL,
        licenseNumber TEXT NOT NULL,
        placeOfResidence TEXT NOT NULL,
        phoneNumber TEXT NOT NULL,
        licensePlateNumber TEXT NOT NULL UNIQUE,
        registrationMark TEXT NOT NULL,
        vinChassisNumber TEXT NOT NULL,
        engineNumber TEXT NOT NULL,
        make TEXT NOT NULL,
        model TEXT NOT NULL,
        modelNumber TEXT NOT NULL,
        color TEXT NOT NULL,
        vehicleCategory TEXT NOT NULL,
        propelledBy TEXT NOT NULL,
        netWeight INTEGER NOT NULL,
        gvmKg INTEGER NOT NULL,
        vehicleClass TEXT NOT NULL,
        engineCapacity INTEGER NOT NULL,
        seatingCapacity INTEGER NOT NULL,
        registrationAuthority TEXT NOT NULL,
        yearOfMake INTEGER NOT NULL,
        firstRegistrationDate TEXT NOT NULL,
        customsClearanceNumber TEXT NOT NULL,
        interpolNumber TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);

    db.run(`CREATE TABLE IF NOT EXISTS access_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        licensePlate TEXT NOT NULL,
        status TEXT NOT NULL,
        details TEXT,
        accessTime DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
}

// API Routes

// Submit registration
app.post('/api/register', (req, res) => {
    const {
        fullName, nationalRegistrationCard, licenseNumber, placeOfResidence, phoneNumber,
        licensePlateNumber, registrationMark, vinChassisNumber, engineNumber, make, model,
        modelNumber, color, vehicleCategory, propelledBy, netWeight, gvmKg, vehicleClass,
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
            error: 'Missing required fields', 
            missingFields 
        });
    }

    const sql = `INSERT INTO registrations (
        fullName, nationalRegistrationCard, licenseNumber, placeOfResidence, phoneNumber,
        licensePlateNumber, registrationMark, vinChassisNumber, engineNumber, make, model,
        modelNumber, color, vehicleCategory, propelledBy, netWeight, gvmKg, vehicleClass,
        engineCapacity, seatingCapacity, registrationAuthority, yearOfMake, firstRegistrationDate,
        customsClearanceNumber, interpolNumber
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`;

    const params = [
        fullName, nationalRegistrationCard, licenseNumber, placeOfResidence, phoneNumber,
        licensePlateNumber, registrationMark, vinChassisNumber, engineNumber, make, model,
        modelNumber, color, vehicleCategory, propelledBy, netWeight, gvmKg, vehicleClass,
        engineCapacity, seatingCapacity, registrationAuthority, yearOfMake, firstRegistrationDate,
        customsClearanceNumber, interpolNumber
    ];

    db.run(sql, params, function(err) {
        if (err) {
            if (err.message.includes('UNIQUE constraint failed')) {
                return res.status(400).json({ 
                    error: 'License plate number already registered' 
                });
            }
            console.error('Database error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
        
        res.json({ 
            success: true, 
            message: 'Registration submitted successfully',
            id: this.lastID 
        });
    });
});

// Get all registrations
app.get('/api/registrations', (req, res) => {
    db.all('SELECT * FROM registrations ORDER BY createdAt DESC', (err, rows) => {
        if (err) {
            console.error('Database error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
        res.json(rows);
    });
});

// Update registration status
app.put('/api/registrations/:id', (req, res) => {
    const { id } = req.params;
    const { status } = req.body;

    if (!['pending', 'approved', 'rejected'].includes(status)) {
        return res.status(400).json({ error: 'Invalid status' });
    }

    db.run('UPDATE registrations SET status = ? WHERE id = ?', [status, id], function(err) {
        if (err) {
            console.error('Database error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
        
        if (this.changes === 0) {
            return res.status(404).json({ error: 'Registration not found' });
        }

        res.json({ success: true, message: 'Status updated successfully' });
    });
});

// Get access logs
app.get('/api/access-logs', (req, res) => {
    const limit = req.query.limit || 100;
    
    db.all('SELECT * FROM access_logs ORDER BY accessTime DESC LIMIT ?', [limit], (err, rows) => {
        if (err) {
            console.error('Database error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
        res.json(rows);
    });
});

// Add access log (for testing)
app.post('/api/access-logs', (req, res) => {
    const { licensePlate, status, details } = req.body;

    db.run('INSERT INTO access_logs (licensePlate, status, details) VALUES (?, ?, ?)', 
        [licensePlate, status, details], function(err) {
        if (err) {
            console.error('Database error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
        res.json({ success: true, id: this.lastID });
    });
});

// Weekly reports
app.get('/api/reports/weekly', (req, res) => {
    const { startDate, endDate } = req.query;

    // Get registrations in date range
    db.all(`SELECT * FROM registrations WHERE date(createdAt) BETWEEN ? AND ?`, 
        [startDate, endDate], (err, registrations) => {
        if (err) {
            console.error('Database error:', err);
            return res.status(500).json({ error: 'Database error' });
        }

        // Get access logs in date range
        db.all(`SELECT * FROM access_logs WHERE date(accessTime) BETWEEN ? AND ?`, 
            [startDate, endDate], (err, accessLogs) => {
            if (err) {
                console.error('Database error:', err);
                return res.status(500).json({ error: 'Database error' });
            }

            const report = {
                totalRegistrations: registrations.length,
                approvedRegistrations: registrations.filter(r => r.status === 'approved').length,
                pendingRegistrations: registrations.filter(r => r.status === 'pending').length,
                rejectedRegistrations: registrations.filter(r => r.status === 'rejected').length,
                totalAccessAttempts: accessLogs.length,
                successfulAccess: accessLogs.filter(log => log.status === 'approved').length,
                registrations: registrations,
                accessLogs: accessLogs
            };

            res.json(report);
        });
    });
});

// Serve HTML files from public folder
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/admin', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

// Start server
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});