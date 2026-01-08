# Uniface360 - Technical Specification

**Version 1.0**  
**Last Updated: June 1, 2025**  
**Author: PetroChoice® Development Team**

## System Architecture

### Overview
Uniface360 is built on a multi-tiered architecture consisting of:

1. **Presentation Layer**: Flask web application
2. **Business Logic Layer**: Python modules for face recognition and data processing
3. **Data Layer**: SQLite databases for storage

### Component Diagram

```
┌──────────────────────┐      ┌──────────────────────┐
│                      │      │                      │
│    Web Interface     │◄────►│    Flask Server      │
│                      │      │                      │
└──────────────────────┘      └───────────┬──────────┘
                                          │
                                          │
                                          ▼
┌──────────────────────┐      ┌──────────────────────┐
│                      │      │                      │
│   Face Recognition   │◄────►│    Database Layer    │
│        Engine        │      │                      │
│                      │      │                      │
└─────────┬────────────┘      └──────────────────────┘
          │
          │
┌─────────▼────────────┐
│                      │
│   Camera Interfaces  │
│                      │
└──────────────────────┘
```

## Technology Stack

### Backend
- **Programming Language**: Python 3.9
- **Web Framework**: Flask 2.2.3
- **Database**: SQLite 3
- **Authentication**: Flask-Login
- **Face Recognition**: face_recognition library (based on dlib)
- **Image Processing**: OpenCV 4.7.0
- **PDF Generation**: ReportLab

### Frontend
- **HTML/CSS/JavaScript**
- **CSS Framework**: Bootstrap 5.3.2
- **Icons**: Bootstrap Icons, Font Awesome
- **Charting**: Chart.js
- **DOM Manipulation**: Vanilla JavaScript

## Module Descriptions

### 1. app_2.py (Main Application)

This is the core Flask application serving as the backbone of the system.

**Key Functions**:
- Web server initialization with Flask
- Route definitions for web pages
- User authentication and session management
- Database operations for user data
- Report generation with ReportLab
- Email notifications with Flask-Mail
- API endpoints for data exchange

**Dependencies**:
- Flask and its extensions
- SQLite3 for database operations
- ReportLab for PDF generation
- PIL for image manipulation
- OpenCV for camera feeds

**Initialization Process**:
1. Flask application setup
2. Database connections established
3. Login manager configuration
4. Mail service initialization
5. Route definitions

### 2. face_tracker.py

This module handles the core facial recognition functionality for a single camera.

**Key Functions**:
- Loading and managing facial encodings
- Processing video frames for face detection
- Matching detected faces to known individuals
- Recording detection events to the database
- Saving evidence images

**Algorithms**:
- Face detection using HOG (Histogram of Oriented Gradients)
- Face encoding using 128-dimensional vectors
- Face matching using L2 distance calculations

### 3. multi_camera_tracker.py

This module extends face_tracker.py to handle multiple camera inputs simultaneously.

**Key Functions**:
- Managing multiple video streams
- Associating cameras with physical locations
- Threading for parallel processing
- Debouncing detection events
- Database logging with location context

**Design Pattern**: Producer-Consumer pattern using a queue for database operations

### 4. train_faces.py

This utility script creates the facial encodings used for recognition.

**Key Functions**:
- Processing reference images from folder structure
- Creating facial encodings for each individual
- Averaging multiple encodings for better accuracy
- Saving encodings to a pickle file for production use

### 5. Database Structure

**tracking.db**:
- Main database for tracking detection events
- Contains logs table with person data, timestamps, and locations
- Stores paths to evidence images

**users.db**:
- Authentication database
- Stores user credentials and permissions
- Contains hashed passwords only (no plaintext storage)

## Security Implementation

### Authentication Flow
1. User submits login credentials
2. Password is verified against hashed value in database
3. On success, Flask-Login creates session
4. Session cookie is used for subsequent authentication

### Password Storage
- Passwords are hashed using Werkzeug's generate_password_hash
- Uses PBKDF2 algorithm with SHA-256
- Implements salting for enhanced security

### Authorization
- Role-based access control implemented
- Certain routes protected with @login_required decorator
- Admin functions restricted to admin users only

## Data Flow

### Person Detection Process
1. Camera captures frame
2. Face detection algorithm identifies faces in frame
3. Face encoding is calculated for each detected face
4. Encodings are compared against known encodings
5. If match found, person is identified
6. Detection event is logged to database with timestamp and location
7. If configured, evidence image is saved

### Reporting Process
1. User requests report with parameters
2. Application queries database for relevant records
3. Data is processed and formatted
4. PDF is generated using ReportLab
5. Document is served to user for download

## Performance Considerations

### Face Recognition Optimization
- Pre-computed encodings to minimize processing time
- Multi-threading for handling multiple cameras
- Debouncing to prevent duplicate database entries
- Asynchronous database writes

### Web Interface Optimization
- Minimal JavaScript dependencies
- Efficient DOM manipulation
- Responsive design for various screen sizes
- Lazy loading of images and resources

## Testing Procedures

### Unit Testing
- Individual module testing for core functions
- Mock objects for database and camera interfaces
- Function-level tests for recognition accuracy

### Integration Testing
- End-to-end testing of detection and recording workflow
- Database integrity verification
- Web interface functionality testing

### Performance Testing
- Load testing with multiple concurrent users
- Face recognition speed and accuracy benchmarking
- Database query performance analysis

## Deployment Guidelines

### System Requirements
- **CPU**: Quad-core processor, 2.5GHz or better
- **RAM**: Minimum 8GB, recommended 16GB
- **Storage**: 50GB available space
- **OS**: Windows 10/11 or Linux (Ubuntu 20.04 or newer)
- **Camera**: USB webcams or IP cameras (720p resolution or higher)
- **Networking**: Ethernet connection (for IP cameras)

### Installation Process
Detailed installation steps provided in main documentation.

### Production Recommendations
- Consider using a WSGI server like Gunicorn for Flask in production
- Implement regular database backups
- Use a production-grade database like PostgreSQL for large deployments
- Consider containerization with Docker for easier deployment
- Implement proper SSL encryption for production environments

## API Documentation

### Authentication Endpoints
- `POST /login`: Authenticate user
  - Parameters: username, password
  - Returns: Session cookie

- `GET /logout`: End session
  - Parameters: None
  - Returns: Redirect to login page

### Data Endpoints
- `GET /api/people`: List all registered individuals
  - Parameters: None
  - Returns: JSON array of person objects

- `GET /api/logs/<name>`: Get movement logs for an individual
  - Parameters: name (in URL)
  - Returns: JSON array of log entries

- `GET /api/occupancy`: Get current building occupancy
  - Parameters: floor (optional)
  - Returns: JSON object with occupancy data

### Report Endpoints
- `GET /api/report/attendance`: Generate attendance report
  - Parameters: start_date, end_date
  - Returns: JSON array of attendance records

- `GET /api/report/movements`: Generate movement report
  - Parameters: name, start_date, end_date
  - Returns: JSON array of movement records

- `GET /export/pdf/<report_type>`: Export report as PDF
  - Parameters: report_type (in URL), query parameters vary by report
  - Returns: PDF file download

## Appendix

### Dependencies List
A complete list of Python package dependencies:
- flask==2.2.3
- flask-login==0.6.2
- face-recognition==1.3.0
- opencv-python==4.7.0
- pillow==9.4.0
- reportlab==3.6.12
- flask-mail==0.9.1
- werkzeug==2.2.3
- numpy==1.24.2

### File Structure
```
Camera attendance - 2/
├── app_2.py                # Main Flask application
├── app.py                  # Legacy application file
├── face_tracker.py         # Single camera face tracking
├── multi_camera_tracker.py # Multi-camera tracking
├── train_faces.py          # Facial encoding training
├── face_encodings.pkl      # Saved facial encodings
├── tracking.db             # Detection log database
├── users.db                # User authentication database
├── static/                 # Static assets
│   ├── logo6.png           # Favicon and logo
│   ├── styles_2.css        # Main stylesheet
│   └── ...                 # Other assets
├── templates/              # HTML templates
│   ├── home.html           # Landing page
│   ├── dashboard_2.html    # Main dashboard
│   ├── map.html            # Interactive building map
│   └── ...                 # Other page templates
├── evidence/               # Captured evidence images
├── known_faces/            # Reference face images
│   ├── person1/            # Images for person 1
│   ├── person2/            # Images for person 2
│   └── ...                 # Other individuals
└── Documentation-Uniface360.md  # System documentation
```

### Error Codes
- 100-199: Authentication errors
- 200-299: Database errors
- 300-399: Camera/video errors
- 400-499: Face recognition errors
- 500-599: System errors

### Troubleshooting Checklist
1. Camera connection issues
   - Check USB connections
   - Verify camera IDs
   - Test with default camera app

2. Face recognition issues
   - Check lighting conditions
   - Verify facial encodings file
   - Retrain model if necessary

3. Database issues
   - Check file permissions
   - Verify database integrity
   - Backup and restore if corrupted

---

© 2025 PetroChoice®. All Rights Reserved.
