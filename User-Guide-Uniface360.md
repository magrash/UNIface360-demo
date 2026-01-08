# Uniface360 User Guide

**Version 1.0**  
**June 1, 2025**

![Uniface360 Logo](static/logo6.png)

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Dashboard Overview](#dashboard-overview)
4. [Building Map](#building-map)
5. [People Directory](#people-directory)
6. [Live Stream](#live-stream)
7. [Attendance Management](#attendance-management)
8. [Emergency Status](#emergency-status)
9. [Reports and Analytics](#reports-and-analytics)
10. [User Management](#user-management)
11. [Support](#support)
12. [FAQ](#faq)

## Introduction

Welcome to Uniface360, the AI-powered building security and attendance management system. This guide will help you navigate the features and functionality of the Uniface360 platform.

Uniface360 combines facial recognition technology, multi-camera integration, and advanced analytics to provide real-time personnel tracking, space monitoring, and attendance management. The system is designed to enhance building security, streamline operations, and provide valuable insights into facility usage.

## Getting Started

### System Requirements
- Web browser: Chrome, Firefox, Safari, or Edge (latest versions)
- Screen resolution: Minimum 1366x768 (1920x1080 recommended)
- Internet connection: Broadband (1 Mbps+)

### Accessing the System
1. Open your web browser
2. Enter the URL provided by your administrator (typically https://[your-domain]/uniface360 or a local address)
3. You will be directed to the login page

### Logging In
1. Enter your username and password on the login screen
2. Click "Sign In"
3. If you've forgotten your password, click "Forgot Password" and follow the instructions

![Login Screen](static/login_screenshot.png)

### Navigation
The main navigation bar at the top of the screen provides access to all system modules:
- **Dashboard**: Overview of key metrics and system status
- **Map**: Interactive building map with occupancy data
- **People**: Personnel directory and individual tracking
- **Live Stream**: Real-time camera feeds
- **Reports**: Generate and export various reports
- **Support**: Access help and contact support
- **User Profile**: Access your profile and settings (top-right corner)

## Dashboard Overview

The dashboard provides at-a-glance information about building occupancy, recent events, and system status.

### Key Elements
1. **Occupancy Overview**: Visual representation of current building occupancy
2. **Floor Status**: Breakdown of occupancy by floor
3. **Recent Events**: Timeline of recent detection events
4. **System Status**: Health status of cameras and system components
5. **Quick Actions**: Shortcuts to commonly used functions

### Customizing Your Dashboard
1. Click the settings icon (⚙️) in the upper right corner of any widget
2. Select "Customize" to change the widget's display options
3. Use "Rearrange" mode to drag and drop widgets to your preferred layout
4. Click "Save Layout" when finished

## Building Map

The interactive building map provides a visual representation of your facility with real-time occupancy data.

### Viewing the Map
1. Click "Map" in the main navigation
2. The default view shows the ground floor (Floor 1)
3. Use the floor selector to switch between floors

### Map Features
- **Room Outlines**: Each room is displayed with its name
- **Person Indicators**: Blue dots represent detected individuals
- **Camera Icons**: Camera locations are marked with camera icons
- **Room Information**: Click on a room to view details
- **Camera Views**: Click on camera icons or use the "View Camera" button to access live feeds

### Interacting with the Map
1. **Viewing Room Details**: Click on any room to see its current occupancy, history, and details
2. **Accessing Camera Feeds**: Click on a camera icon or use the "View Camera" button in the room details panel
3. **Camera Controls**: When viewing a camera, use the controls to:
   - Toggle fullscreen view
   - Switch between cameras
   - Close the camera view

### Room Information Panel
When you click on a room, the information panel shows:
- Room name and number
- Current occupancy
- List of individuals present
- Historical occupancy graph
- Link to camera feed (if available)

## People Directory

The People Directory provides access to information about all individuals tracked by the system.

### Viewing the Directory
1. Click "People" in the main navigation
2. The default view shows a list of all registered individuals
3. Use the search box to find specific people

### Person Details
Click on any person's name to view their profile:
- **Photo**: Most recent image
- **Basic Information**: Name, ID, role
- **Current Status**: Present/absent, location if present
- **Attendance History**: Recent attendance records
- **Movement Timeline**: Chart of movements between floors
- **Logs**: Detailed list of all detection events

### Filtering the Directory
Use the filter options to narrow down the list:
- By status (present, absent)
- By floor location
- By time range
- By role or department (if configured)

## Live Stream

The Live Stream section provides access to all camera feeds in real-time.

### Accessing Live Streams
1. Click "Live Stream" in the main navigation
2. The default view shows all active camera feeds
3. Use the layout controls to adjust the display format

### Camera Controls
Each camera feed has the following controls:
- **Fullscreen**: Expand to fullscreen view
- **Camera Selector**: Switch to another camera
- **Floor Indicator**: Shows which floor the camera is monitoring
- **Status Indicator**: Shows if the camera is online/offline

### View Modes
- **Grid View**: See multiple cameras simultaneously
- **Single View**: Focus on one camera feed
- **Floor View**: Group cameras by floor

## Attendance Management

Uniface360 automatically tracks attendance based on facial recognition.

### Viewing Attendance Records
1. Navigate to "Reports" > "Attendance"
2. Set the date range for the report
3. Filter by individual or department if needed
4. View the attendance summary

### Attendance Dashboard
The attendance dashboard shows:
- Present/absent counts for the day
- Arrival time distribution chart
- Late arrival statistics
- Absence patterns
- Average time spent in the building

### Managing Excuses
For administrators and managers:
1. Navigate to "Excuses" in the Reports section
2. View pending excuse requests
3. Approve or deny requests
4. Add comments or notes

## Emergency Status

The Emergency Status screen provides critical information during emergency situations.

### Accessing Emergency Status
1. Click "Emergency Status" in the main navigation
2. Alternatively, click the emergency icon in the top bar

### Emergency Dashboard
The emergency status screen shows:
- Complete list of all personnel
- Last known location for each person
- Last seen timestamp
- Status indicator (safe, unaccounted for)
- Evidence images (if available)
- Links to detailed movement logs

### Filtering the Emergency List
Use the filters to:
- Show only unaccounted personnel
- Sort by floor or time last seen
- Search for specific individuals

## Reports and Analytics

Uniface360 offers comprehensive reporting and analytics capabilities.

### Available Reports
- **Attendance Summary**: Daily, weekly, or monthly attendance records
- **Person Logs**: Detailed movement logs for individuals
- **Occupancy Analysis**: Building and room usage patterns
- **Time Analysis**: Time spent by individuals in different areas
- **System Activity**: System usage and activity logs

### Generating Reports
1. Navigate to "Reports" in the main navigation
2. Select the report type
3. Configure parameters (date range, individuals, etc.)
4. Click "Generate Report"

### Exporting Reports
Reports can be exported in various formats:
- PDF
- CSV
- Excel

To export a report:
1. Generate the report
2. Click the "Export" button
3. Select your preferred format
4. Save the file to your computer

## User Management

This section is relevant for administrators responsible for managing system users.

### User Roles
Uniface360 supports the following user roles:
- **Administrator**: Full access to all system features
- **Manager**: Access to reports, personnel data, and limited settings
- **Viewer**: View-only access to dashboards and basic reports

### Adding New Users
1. Navigate to "Settings" > "Users"
2. Click "Add New User"
3. Fill in the required information:
   - Username
   - Email address
   - Role selection
   - Initial password
4. Click "Create User"
5. The new user will receive an email with login instructions

### Managing Existing Users
1. Navigate to "Settings" > "Users"
2. Click on a username to view/edit their profile
3. Options include:
   - Reset password
   - Change role
   - Disable/enable account
   - Delete user

## Support

Uniface360 offers multiple support options.

### Accessing Help
- Click "Support" in the main navigation
- Use the context-sensitive help icons (?) throughout the interface
- Access the documentation through the Help Center

### Contacting Support
To contact support:
1. Click "Support" in the main navigation
2. Click "Contact Support"
3. Fill out the support request form:
   - Subject
   - Issue description
   - Priority level
   - Screenshots (if applicable)
4. Click "Submit"
5. You will receive a confirmation email with your ticket number

### Common Support Topics
- Camera connectivity issues
- Face recognition troubleshooting
- Report generation problems
- Account access issues
- System performance concerns

## FAQ

### General Questions

**Q: How accurate is the facial recognition system?**  
A: Uniface360's facial recognition system achieves 98% accuracy under optimal lighting conditions. Factors that can affect accuracy include poor lighting, occlusion (partial face coverage), and extreme angles.

**Q: Is my facial data secure?**  
A: Yes. Uniface360 stores facial data as mathematical encodings, not actual images. These encodings cannot be reverse-engineered into facial images.

**Q: How many cameras can the system support?**  
A: The standard configuration supports up to 16 cameras. Enterprise installations can support 50+ cameras with appropriate hardware.

### Technical Questions

**Q: What happens if the internet connection is lost?**  
A: The core system continues to function locally, recording all detection events. Once connectivity is restored, any pending data is synchronized.

**Q: Can the system work with existing security cameras?**  
A: Yes, Uniface360 is compatible with most IP cameras that provide RTSP streams. USB webcams are also supported for smaller installations.

**Q: How long is data retained in the system?**  
A: By default, detection logs are retained for 90 days. Evidence images are stored for 30 days. These retention periods can be configured by administrators.

### Usage Questions

**Q: How do I add a new person to the recognition system?**  
A: Only system administrators can add new people. They must provide multiple reference photos of the individual and run the training script.

**Q: Can I receive alerts for specific events?**  
A: Yes. Navigate to "Settings" > "Notifications" to configure alert preferences for events such as first appearance, specific area access, or extended absences.

**Q: How do I generate a report for a specific time period?**  
A: In the Reports section, select the desired report type, then use the date/time pickers to specify the period before generating the report.

---

For additional assistance, please contact your system administrator or the Uniface360 support team at support@uniface360.com.

© 2025 PetroChoice®. All Rights Reserved.
