# Uniface360 - AI-Powered Building Security System
**Documentation**

**Date: June 1, 2025**

## Table of Contents
1. [Introduction](#introduction)
2. [System Overview](#system-overview)
3. [Architecture](#architecture)
4. [Features](#features)
5. [Technical Components](#technical-components)
6. [Installation Guide](#installation-guide)
7. [User Guide](#user-guide)
8. [API Reference](#api-reference)
9. [Database Schema](#database-schema)
10. [Security Considerations](#security-considerations)
11. [Troubleshooting](#troubleshooting)
12. [Future Enhancements](#future-enhancements)

## Introduction

Uniface360 is an advanced AI-powered building security system that provides real-time personnel tracking, space monitoring, and attendance management. It leverages facial recognition technology to identify individuals within a building and track their movements across multiple floors through a network of cameras.

This system is designed to enhance building security, automate attendance records, optimize space utilization, and provide comprehensive monitoring capabilities for facilities management.

**Developed by:** PetroChoice®

## System Overview

Uniface360 integrates multiple technologies to create a comprehensive security ecosystem:

- **AI-Powered Facial Recognition:** Identifies individuals using pre-trained facial encodings
- **Multi-Camera Integration:** Monitors different floors and areas simultaneously
- **Real-Time Tracking:** Records and displays personnel movement throughout the building
- **Interactive Building Map:** Visualizes occupancy and allows camera access
- **Attendance Management:** Automatically logs entry/exit times and generates reports
- **Emergency Status Monitoring:** Tracks individuals during emergency situations

The system consists of a web application built on Flask, a database for storing detection logs, and camera integration components for processing video feeds.

## Architecture

The Uniface360 system is built on a modular architecture consisting of the following components:

### Client-Side Components:
- Web interface for monitoring and management
- Interactive building map with real-time occupancy visualization
- Dashboard for analytics and reporting

### Server-Side Components:
- Flask web application (app_2.py)
- Authentication system
- Face recognition processing engine
- Database management
- Email notification system

### External Components:
- Multiple cameras (USB and laptop cameras)
- Database (SQLite)
- Facial encoding storage

### Data Flow:
1. Cameras capture video feeds
2. Face recognition system identifies individuals
3. Detection data is stored in the database
4. Web interface displays real-time information
5. Reports are generated based on collected data

## Features

### Personnel Tracking
- Real-time monitoring of all personnel movements
- Historical tracking of individual's locations
- Last known position identification
- Comprehensive logs of movements

### Space Monitoring
- Real-time room occupancy tracking
- Interactive building map with occupancy data
- Camera view access from map interface
- Floor-level monitoring

### Attendance System
- Automated check-in/check-out logging
- Attendance reports generation
- PDF export functionality
- Absence and lateness tracking

### AI-Powered Dashboard
- Analytics on building usage
- Attendance statistics
- Visual representation of data
- Custom filtering options

### Security Features
- User authentication and authorization
- Access control based on user roles
- Secure password management
- Email notifications for security events

### Emergency Management
- Status monitoring during emergencies
- Last known location tracking
- Evidence capture with timestamps
- Detailed person logs

## Technical Components

### Face Recognition System
The core of Uniface360 is its facial recognition capability implemented through multiple Python scripts:

#### train_faces.py
This script creates facial encodings from reference images stored in the `known_faces` directory. It:
- Processes images of individuals
- Creates mathematical encodings of facial features
- Stores these encodings in a pickle file for quick access during recognition

#### face_tracker.py
This module handles single-camera facial recognition:
- Loads pre-computed facial encodings
- Processes video frames to identify faces
- Matches detected faces against known encodings
- Records identifications in the database

#### multi_camera_tracker.py
This script extends face_tracker.py to handle multiple camera feeds:
- Processes feeds from different cameras simultaneously
- Maps cameras to specific floors/locations
- Uses threading to manage multiple video streams
- Implements debouncing to prevent duplicate detections
- Records identifications with location data

### Web Application (app_2.py)
The Flask web application provides the interface and business logic:
- User authentication and session management
- Dashboard views for monitoring
- Interactive building map
- Report generation
- Email notifications
- API endpoints for data access

### Database System
The system uses SQLite databases:
- `tracking.db`: Stores detection logs with timestamps and locations
- `users.db`: Manages user credentials and permissions

## Installation Guide

### Prerequisites
- Python 3.9 or higher
- OpenCV
- Face Recognition library
- Flask and related extensions
- SQLite
- ReportLab (for PDF generation)

### Installation Steps

1. **Clone the repository or extract the files**
   ```
   git clone https://github.com/petrochoice/uniface360.git
   cd uniface360
   ```

2. **Install required Python packages**
   ```
   pip install -r requirements.txt
   ```

3. **Train facial recognition models**
   - Place reference images in the `known_faces` directory
   - Each person should have their own subfolder named after them
   - Run the training script:
     ```
     python train_faces.py
     ```

4. **Configure camera settings**
   - Update the camera IDs in `multi_camera_tracker.py` based on your setup
   - Adjust the `CAMERA_FLOORS` mapping to match your building configuration

5. **Initialize the database**
   - The application will create necessary database tables on first run

6. **Configure email settings**
   - Update the email configuration in `app_2.py` with your SMTP server details

7. **Start the application**
   ```
   python app_2.py
   ```

## User Guide

### Accessing the System
1. Open a web browser and navigate to `http://localhost:5000`
2. Log in using your credentials (default admin: admin/admin)

### Dashboard
The dashboard provides an overview of:
- Current building occupancy
- Recent entry/exit events
- Attendance statistics
- System status

### Building Map
The interactive map shows:
- Room layouts for each floor
- Current occupancy with person indicators
- Camera locations
- Click on rooms to view camera feeds
- Use the "View Camera" button to see live feeds

### People Directory
Manage and view personnel information:
- Search for individuals
- View attendance history
- Generate attendance reports
- Export data to PDF

### Live Stream
View all camera feeds simultaneously:
- Switch between floors
- View multiple cameras on a single page
- Toggle fullscreen for individual feeds

### Emergency Status
During emergencies, this page shows:
- List of all personnel
- Last known location
- Last seen timestamp
- Evidence images (if available)
- Links to detailed logs

### Reporting
Generate and export various reports:
- Attendance summaries
- Person movement logs
- Building occupancy reports
- Customize date ranges and filters

### Support
Access help and support:
- Submit support tickets
- View system documentation
- Contact administrators

## API Reference

Uniface360 provides several API endpoints for integration:

### Authentication
- `POST /login`: Authenticate user and create session
- `GET /logout`: End user session

### Data Access
- `GET /api/people`: List all registered individuals
- `GET /api/logs/<name>`: Get movement logs for an individual
- `GET /api/occupancy`: Get current building occupancy

### Reporting
- `GET /api/report/attendance`: Generate attendance report
- `GET /api/report/movements`: Generate movement report
- `GET /export/pdf/<report_type>`: Export report as PDF

## Database Schema

### tracking.db
The main database for tracking data:

#### logs Table
- `id`: Integer primary key
- `name`: Text, person's name
- `time`: Text, timestamp of detection
- `floor`: Text, location of detection
- `image_path`: Text, path to captured image evidence (optional)

### users.db
The authentication database:

#### users Table
- `id`: Integer primary key
- `username`: Text, username for login
- `password`: Text, hashed password
- `role`: Text, user role (admin, viewer)

## Security Considerations

### Authentication Security
- Passwords are hashed using Werkzeug's security functions
- Session management through Flask-Login
- Role-based access control

### Data Security
- No plaintext passwords stored in the database
- Limited exposure of sensitive information through the web interface
- API endpoints require authentication

### Physical Security
- The system enhances physical security through continuous monitoring
- Unauthorized access attempts are logged
- Evidence images are captured and stored securely

### Privacy Considerations
- Facial data is stored as mathematical encodings, not actual images
- Access to historical data is restricted to authorized users
- System complies with privacy best practices

## Troubleshooting

### Camera Connectivity Issues
- Ensure camera devices are properly connected
- Verify camera IDs in the configuration
- Check if other applications are using the cameras

### Face Recognition Problems
- Ensure adequate lighting for optimal recognition
- Add multiple reference images for each person
- Retrain models if recognition accuracy decreases

### Database Issues
- Check file permissions for database files
- Backup databases regularly using the built-in tools
- Use the database maintenance options in the admin panel

### Web Interface Problems
- Clear browser cache if the interface behaves unexpectedly
- Ensure you're using a supported browser (Chrome, Firefox, Safari)
- Check server logs for error messages

## Future Enhancements

### Planned Features
- Mobile application for remote monitoring
- Integration with access control systems
- Advanced analytics for occupancy patterns
- Mask detection and enforcement
- Thermal camera integration for health screening
- Visitor management system
- Automatic scheduling based on occupancy patterns

### In Development
- Machine learning for behavioral analysis
- Predictive occupancy modeling
- Integration with building management systems
- Voice command interface
- Expanded reporting capabilities

---

© 2025 PetroChoice®. All Rights Reserved.
