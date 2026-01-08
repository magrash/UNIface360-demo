# Uniface360 Administrator Guide

**Version 1.0**  
**June 1, 2025**

## Table of Contents
1. [Introduction](#introduction)
2. [System Architecture](#system-architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [User Management](#user-management)
6. [Camera Setup](#camera-setup)
7. [Face Training](#face-training)
8. [Maintenance](#maintenance)
9. [Backup and Recovery](#backup-and-recovery)
10. [Troubleshooting](#troubleshooting)
11. [Security Best Practices](#security-best-practices)
12. [Performance Tuning](#performance-tuning)
13. [Advanced Configuration](#advanced-configuration)

## Introduction

This administrator guide provides detailed instructions for installing, configuring, and maintaining the Uniface360 AI Security System. This document is intended for system administrators and IT personnel responsible for the deployment and operation of the system.

### System Requirements

**Minimum Hardware Requirements:**
- CPU: Intel Core i5 (8th gen) or equivalent
- RAM: 8GB
- Storage: 50GB SSD
- Network: 100Mbps Ethernet
- Cameras: 720p resolution or higher

**Recommended Hardware Requirements:**
- CPU: Intel Core i7 (10th gen) or equivalent
- RAM: 16GB
- Storage: 250GB SSD
- Network: 1Gbps Ethernet
- Cameras: 1080p resolution

**Software Requirements:**
- Operating System: Windows 10/11 or Ubuntu 20.04 LTS or later
- Python 3.9 or higher
- Dependencies as listed in requirements.txt

## System Architecture

Uniface360 consists of several integrated components:

1. **Web Application (app_2.py)**: Flask-based web server providing user interface and API endpoints
2. **Face Recognition Engine**: Processes video feeds and identifies individuals
3. **Database**: Stores detection logs, user credentials, and system configuration
4. **Camera Integration**: Interfaces with USB and IP cameras

### Component Interactions

```
                ┌─────────────┐
                │   Cameras   │
                └──────┬──────┘
                       │
                       ▼
┌──────────────────────────────────┐
│                                  │
│      Face Recognition Engine     │
│                                  │
└──────────────────┬───────────────┘
                   │
                   ▼
┌──────────────────────────────────┐
│                                  │
│           Database               │
│                                  │
└──────────────────┬───────────────┘
                   │
                   ▼
┌──────────────────────────────────┐
│                                  │
│         Web Application          │
│                                  │
└──────────────────┬───────────────┘
                   │
                   ▼
┌──────────────────────────────────┐
│                                  │
│          Web Browser             │
│                                  │
└──────────────────────────────────┘
```

## Installation

### Prerequisites Installation

1. Install Python 3.9 or higher:
   ```
   # For Ubuntu
   sudo apt update
   sudo apt install python3.9 python3.9-dev python3.9-venv

   # For Windows
   # Download from https://www.python.org/downloads/
   ```

2. Install required system packages:
   ```
   # For Ubuntu
   sudo apt install build-essential cmake libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev
   
   # For Windows
   # Install Visual C++ Build Tools and CMake
   ```

### Application Installation

1. Clone or extract the application to your desired location:
   ```
   git clone https://github.com/petrochoice/uniface360.git
   cd uniface360
   ```

2. Create a virtual environment:
   ```
   # For Ubuntu
   python3 -m venv venv
   source venv/bin/activate
   
   # For Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Initialize the databases:
   ```
   python init_db.py
   ```

5. Set up the initial admin user:
   ```
   python create_admin.py
   ```

## Configuration

### Main Configuration File

The primary configuration is stored in `config.json`. Below is an explanation of the key settings:

```json
{
  "app": {
    "secret_key": "your-secret-key-here",
    "debug": false,
    "host": "0.0.0.0",
    "port": 5000
  },
  "database": {
    "tracking_db": "tracking.db",
    "users_db": "users.db"
  },
  "mail": {
    "server": "smtp.gmail.com",
    "port": 587,
    "use_tls": true,
    "username": "your-email@gmail.com",
    "password": "your-app-password",
    "default_sender": "Uniface360 <your-email@gmail.com>"
  },
  "cameras": {
    "floor1": 0,
    "floor2": 1,
    "floor3": 2
  },
  "face_recognition": {
    "encodings_file": "face_encodings.pkl",
    "tolerance": 0.6,
    "debounce_seconds": 5
  }
}
```

### Environment Variables

The application also supports configuration through environment variables, which take precedence over the config file:

- `FLASK_SECRET_KEY`: Secret key for Flask session security
- `MAIL_USERNAME`: Email username for notifications
- `MAIL_PASSWORD`: Email password for notifications
- `DATABASE_PATH`: Alternative path for database files
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Camera Configuration

Camera settings are managed in the `camera_config.json` file:

```json
{
  "cameras": [
    {
      "id": 0,
      "name": "Floor 1 Main",
      "location": "Floor 1",
      "type": "USB",
      "resolution": [640, 480],
      "fps": 15
    },
    {
      "id": 1,
      "name": "Floor 2 Main",
      "location": "Floor 2",
      "type": "USB",
      "resolution": [640, 480],
      "fps": 15
    },
    {
      "id": 2,
      "name": "Floor 3 Main",
      "location": "Floor 3",
      "type": "USB",
      "resolution": [640, 480],
      "fps": 15
    }
  ]
}
```

## User Management

### User Roles

Uniface360 implements role-based access control with the following predefined roles:

1. **Admin**: Full system access, including configuration
2. **Manager**: Access to reports and user management, but not system configuration
3. **Viewer**: Read-only access to dashboards and basic reports

### Managing Users

**Creating a New User:**
1. Log in with administrative credentials
2. Navigate to "Settings" > "Users"
3. Click "Add New User"
4. Fill in the required information:
   - Username
   - Email address
   - Role selection
   - Initial password
5. Click "Create User"

**Modifying a User:**
1. Navigate to "Settings" > "Users"
2. Click on the username you wish to modify
3. Update the desired fields
4. Click "Save Changes"

**Removing a User:**
1. Navigate to "Settings" > "Users"
2. Click on the username
3. Click "Delete User"
4. Confirm the deletion

**Password Reset:**
1. Navigate to "Settings" > "Users"
2. Click on the username
3. Click "Reset Password"
4. The system will generate a password reset link and send it to the user's email

### Default Credentials

The system is initialized with a default administrative account:
- Username: admin
- Password: admin

**Important:** Change the default password immediately after installation.

## Camera Setup

### Supported Camera Types

Uniface360 supports:
- **USB webcams**: Plug-and-play via USB ports
- **IP cameras**: Network cameras accessible via RTSP or HTTP streams
- **Built-in webcams**: Laptop or integrated cameras

### Adding a New Camera

**USB Camera:**
1. Connect the camera to an available USB port
2. Navigate to "Settings" > "Cameras"
3. Click "Detect Cameras"
4. Select the newly detected camera from the list
5. Configure the camera name and location
6. Click "Add Camera"

**IP Camera:**
1. Ensure the camera is connected to the network
2. Navigate to "Settings" > "Cameras"
3. Click "Add IP Camera"
4. Enter the required information:
   - Camera name
   - IP address
   - RTSP/HTTP URL
   - Authentication credentials (if required)
   - Location (floor/area)
5. Click "Test Connection" to verify
6. If successful, click "Add Camera"

### Camera Configuration

Each camera can be configured with:
- **Resolution**: Higher resolution improves recognition but requires more processing power
- **Frame Rate**: Lower frame rates reduce CPU usage
- **Detection Interval**: How often face detection is performed (in milliseconds)
- **Recognition Threshold**: Confidence threshold for positive identification

### Camera Troubleshooting

**Camera Not Detected:**
1. Verify the camera is properly connected
2. Check if the camera is being used by another application
3. Restart the camera service:
   ```
   python restart_camera_service.py
   ```

**Poor Recognition Rate:**
1. Check lighting conditions - ensure faces are well-illuminated
2. Adjust camera angle to capture frontal face views
3. Increase resolution if CPU resources permit
4. Consider retraining facial models with better quality images

## Face Training

### Preparing Training Data

For optimal face recognition, prepare training data as follows:

1. Create a directory structure with one subfolder per person:
   ```
   known_faces/
   ├── person1/
   │   ├── image1.jpg
   │   ├── image2.jpg
   │   └── ...
   ├── person2/
   │   ├── image1.jpg
   │   └── ...
   └── ...
   ```

2. Guidelines for optimal training images:
   - Use 3-5 images per person for best results
   - Ensure good lighting and clear visibility of the face
   - Include different angles and expressions
   - Use high-quality images (at least 640x480 resolution)
   - Ensure the face occupies a significant portion of the image

### Running the Training

Execute the training script to generate facial encodings:

```
python train_faces.py
```

This will:
1. Process all images in the `known_faces` directory
2. Generate facial encodings for each person
3. Save the encodings to `face_encodings.pkl`

### Updating Existing Models

To add new people or update existing encodings:

1. Add new photos to the appropriate folders in `known_faces/`
2. Run the training script with the update flag:
   ```
   python train_faces.py --update
   ```

### Verifying Training Results

To verify training success:
1. Navigate to "Settings" > "Face Recognition"
2. Click "Test Recognition"
3. The system will display all trained individuals with their recognition scores

## Maintenance

### Routine Maintenance Tasks

**Daily:**
- Check the system logs for errors
- Verify all cameras are operational
- Monitor disk space usage

**Weekly:**
- Review recognition accuracy metrics
- Clear temporary files
- Verify database integrity
- Check for software updates

**Monthly:**
- Perform database optimization
- Review and update user access permissions
- Clean up old evidence files (if not needed)
- Test backup and recovery procedures

### System Logs

Logs are stored in the `logs` directory with the following files:
- `application.log`: General application logs
- `recognition.log`: Face recognition specific logs
- `access.log`: User login and access attempts
- `error.log`: Error messages and exceptions

To change logging level:
1. Edit `config.json`
2. Update the `log_level` setting
3. Restart the application

### Monitoring System Health

The system health dashboard provides real-time metrics:
1. Navigate to "Settings" > "System Health"
2. Monitor key metrics:
   - CPU usage
   - Memory utilization
   - Disk space
   - Camera status
   - Face recognition performance
   - Database size

### Database Maintenance

To optimize database performance:
```
python manage.py optimize_db
```

To clean up old records:
```
python manage.py cleanup_logs --days 90
```

## Backup and Recovery

### Backup Strategy

Implement a regular backup schedule for:
- Database files (tracking.db, users.db)
- Facial encodings (face_encodings.pkl)
- Configuration files (config.json)
- Evidence images (if legally required to be preserved)

### Manual Backup

To perform a manual backup:
1. Navigate to "Settings" > "Backup"
2. Click "Create Backup"
3. The system will generate a timestamped backup file
4. Download the backup file to a secure location

### Automated Backup

Configure automated backups:
1. Navigate to "Settings" > "Backup"
2. Enable "Scheduled Backups"
3. Set the backup frequency and retention policy
4. Specify a backup location (local or network path)

### Backup Retention Policy

Recommended retention policies:
- Daily backups: Keep for 7 days
- Weekly backups: Keep for 4 weeks
- Monthly backups: Keep for 12 months

### Recovery Procedure

To restore from a backup:
1. Stop the Uniface360 service
2. Navigate to "Settings" > "Backup"
3. Click "Restore Backup"
4. Select the backup file
5. Confirm the restoration
6. The system will restore the data and restart

## Troubleshooting

### Common Issues and Solutions

**Web Interface Not Loading:**
1. Verify the Flask server is running
2. Check network connectivity
3. Review application logs for errors
4. Restart the web service:
   ```
   python restart_web_service.py
   ```

**Face Recognition Not Working:**
1. Verify the camera feeds are active
2. Check if facial encodings file exists
3. Review recognition logs for errors
4. Restart the recognition service:
   ```
   python restart_recognition_service.py
   ```

**Database Errors:**
1. Check database file permissions
2. Verify disk space availability
3. Run database integrity check:
   ```
   python manage.py check_db_integrity
   ```
4. Restore from backup if necessary

**Email Notifications Not Sending:**
1. Verify email configuration settings
2. Check network connectivity to SMTP server
3. Test email service:
   ```
   python test_email.py
   ```

### Diagnostic Tools

The system includes several diagnostic tools:

**System Check:**
```
python system_check.py
```
Performs a comprehensive check of all system components.

**Camera Test:**
```
python camera_test.py
```
Tests all configured cameras for accessibility and frame rate.

**Recognition Test:**
```
python recognition_test.py
```
Tests the face recognition system with sample images.

### Log Analysis

Key log patterns to watch for:

**Recognition Issues:**
```
WARN [FaceRecognition] Low confidence match: Person=John, Score=0.48
```
Indicates potential false positives or need for retraining.

**Camera Issues:**
```
ERROR [CameraManager] Failed to get frame from camera #2
```
Indicates camera connectivity or driver problems.

**Database Issues:**
```
ERROR [Database] SQLite error: database is locked
```
Indicates concurrent access problems or disk issues.

## Security Best Practices

### Access Control

1. Implement strong password policies:
   - Minimum 12 characters
   - Require complexity (uppercase, lowercase, numbers, symbols)
   - Regular password rotation (90 days recommended)

2. Use role-based access control:
   - Assign minimal necessary privileges
   - Review access permissions quarterly
   - Remove unused accounts promptly

3. Enable two-factor authentication for admin accounts

### Network Security

1. Run the system on an isolated network segment if possible
2. Implement HTTPS with a valid SSL certificate
3. Restrict access to the server by IP address when possible
4. Use VPN for remote administrative access

### Data Protection

1. Encrypt sensitive data (facial encodings, credentials)
2. Implement appropriate data retention policies
3. Secure backup files with encryption
4. Follow privacy regulations relevant to your jurisdiction

### System Hardening

1. Keep the operating system and dependencies updated
2. Disable unnecessary services
3. Use a firewall to restrict inbound connections
4. Regularly audit system security

## Performance Tuning

### Optimizing Recognition Performance

1. **Resolution vs. Processing Power**:
   - Lower camera resolution for faster processing
   - Find the optimal balance between recognition accuracy and performance

2. **Detection Frequency**:
   - Adjust detection interval based on CPU resources
   - Consider motion detection to trigger recognition

3. **Multi-threading Configuration**:
   - Modify `threading_config.json` to adjust thread allocation
   - Allocate more threads to busier cameras

### Database Optimization

1. **Indexing**:
   - Ensure proper indexes are created on frequently queried fields
   - Run the optimization script:
     ```
     python optimize_db.py
     ```

2. **Query Optimization**:
   - Modify `query_config.json` to adjust query parameters
   - Increase query cache size for better performance

### Memory Management

1. **Camera Buffer Settings**:
   - Adjust frame buffer sizes in `camera_config.json`
   - Reduce buffer size on memory-constrained systems

2. **Cache Settings**:
   - Modify cache expiration times in `cache_config.json`
   - Increase cache size for frequently accessed data

## Advanced Configuration

### Custom Face Recognition Parameters

Advanced recognition settings can be configured in `recognition_config.json`:

```json
{
  "detection_model": "hog",  // Options: "hog" (faster) or "cnn" (more accurate)
  "recognition_model": "large",  // Options: "small" or "large"
  "tolerance": 0.6,  // Lower = more strict matching
  "num_jitters": 1,  // Higher = more accurate but slower
  "detection_upsampling": 1,  // Higher = better detection for small faces
  "batch_size": 128  // Batch processing size for multiple faces
}
```

### Custom Database Configuration

For advanced database tuning, modify `database_config.json`:

```json
{
  "journal_mode": "WAL",  // WAL mode for better concurrency
  "synchronous": "NORMAL",  // FULL for more safety, NORMAL for better performance
  "temp_store": "MEMORY",  // Store temporary tables in memory
  "cache_size": 2000,  // Number of pages to cache in memory
  "page_size": 4096,  // Database page size
  "vacuum_threshold": 50  // Auto-vacuum when free space exceeds threshold
}
```

### API Configuration

To enable and configure the API for integration with other systems:

1. Edit `api_config.json`:
   ```json
   {
     "enabled": true,
     "require_token": true,
     "rate_limit": {
       "requests": 100,
       "per_minutes": 60
     },
     "allowed_origins": [
       "https://yourdomain.com",
       "https://anotherdomain.com"
     ]
   }
   ```

2. Generate API tokens:
   ```
   python generate_api_token.py --name "Integration Name"
   ```

### Custom Notification Rules

Configure advanced notification rules in `notification_config.json`:

```json
{
  "rules": [
    {
      "event": "new_person_detected",
      "recipients": ["security@company.com"],
      "delay": 0,
      "conditions": {
        "location": "restricted_area",
        "time": "outside_business_hours"
      }
    },
    {
      "event": "extended_absence",
      "recipients": ["hr@company.com"],
      "delay": 259200,  // 3 days in seconds
      "conditions": {
        "role": "employee"
      }
    }
  ]
}
```

---

## Support Resources

### Documentation

- Full system documentation is available at `/docs/index.html`
- API documentation is available at `/docs/api.html`

### Obtaining Support

For technical support:
- Email: support@uniface360.com
- Phone: +1-555-UNIFACE (555-864-3223)
- Web: https://support.uniface360.com

### Updates and Patches

Visit https://updates.uniface360.com for:
- Software updates
- Security patches
- Feature enhancements

Remember to back up your system before applying updates.

---

© 2025 PetroChoice®. All Rights Reserved.
