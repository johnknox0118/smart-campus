# Smart Campus Management and Security System - REST API Reference

All requests to the backend APIs should be sent to the base URL: `http://localhost:5000/api`. 
Protected endpoints require a JWT header: `Authorization: Bearer <your_access_token>`.

---

## 1. Authentication Module (`/api/auth`)

### 1.1 Secure Login
- **Endpoint:** `POST /api/auth/login`
- **Auth required:** No
- **Request Body:**
  ```json
  {
    "username": "student",
    "password": "student123"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "message": "Login successful",
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "refresh_token": "eyJhbGciOiJIUzI1Ni...",
    "user": {
      "id": 2,
      "username": "student",
      "email": "student@prathyusha.edu.in",
      "role": "Student"
    }
  }
  ```

### 1.2 User Registration
- **Endpoint:** `POST /api/auth/register`
- **Auth required:** Yes (Admin role only)
- **Request Body:**
  ```json
  {
    "username": "new_student",
    "password": "Password123!",
    "email": "new_student@prathyusha.edu.in",
    "role": "Student",
    "department_name": "Computer Science & Engineering",
    "class_name": "CSE-A"
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "message": "User registered successfully",
    "user": {
      "id": 10,
      "username": "new_student",
      "email": "new_student@prathyusha.edu.in",
      "role": "Student"
    }
  }
  ```

---

## 2. GPS Tracking & Geofencing Module (`/api/gps`)

### 2.1 Emit Location Log
- **Endpoint:** `POST /api/gps/track`
- **Auth required:** Yes (Student, Staff, or Driver)
- **Request Body:**
  ```json
  {
    "latitude": 13.0848,
    "longitude": 79.9968,
    "speed": 0.0,
    "accuracy": 5.0,
    "battery": 90,
    "mocked": false
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "success",
    "geofence": "Library",
    "is_spoofed": false,
    "spoof_reason": null,
    "attendance_status": "Present",
    "timestamp": "2026-07-14 13:00:00"
  }
  ```

### 2.2 Get Location History
- **Endpoint:** `GET /api/gps/history/<int:user_id>`
- **Auth required:** Yes (Admin, Security, or Staff)
- **Response (200 OK):**
  ```json
  {
    "username": "student",
    "role": "Student",
    "history": [
      {
        "id": 150,
        "latitude": 13.0848,
        "longitude": 79.9968,
        "speed": 0.0,
        "accuracy": 5.0,
        "battery": 90,
        "geofence_name": "Library",
        "is_spoofed": false,
        "spoof_reason": null,
        "timestamp": "2026-07-14 13:00:00"
      }
    ]
  }
  ```

---

## 3. Bus Tracking Module (`/api/bus`)

### 3.1 Upload Bus Location
- **Endpoint:** `POST /api/bus/location`
- **Auth required:** Yes (Driver role only)
- **Request Body:**
  ```json
  {
    "latitude": 13.0450,
    "longitude": 80.0210,
    "speed": 45.0,
    "eta_mins": 15,
    "next_stop": "Poonamallee Junction"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "success",
    "message": "Bus location telemetry logged",
    "bus_number": "PEC-001"
  }
  ```

### 3.2 View Bus Transit List
- **Endpoint:** `GET /api/bus/status`
- **Auth required:** Yes
- **Response (200 OK):**
  ```json
  {
    "buses": [
      {
        "id": 1,
        "bus_number": "PEC-001",
        "route_name": "Poonamallee - Tiruvallur Road to PEC Campus",
        "driver_name": "driver",
        "capacity": 50,
        "status": "Active",
        "latitude": 13.0450,
        "longitude": 80.0210,
        "speed": 45.0,
        "eta_mins": 15,
        "next_stop": "Poonamallee Junction",
        "last_updated": "2026-07-14 13:01:00"
      }
    ]
  }
  ```

---

## 4. Leave Management Module (`/api/leave`)

### 4.1 Apply for Leave
- **Endpoint:** `POST /api/leave/request`
- **Auth required:** Yes (Student or Staff)
- **Request Body:**
  ```json
  {
    "start_date": "2026-07-20",
    "end_date": "2026-07-22",
    "reason": "Medical appointment"
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "message": "Leave request submitted successfully",
    "leave_id": 5
  }
  ```

### 4.2 Approve/Reject Leave Request
- **Endpoint:** `POST /api/leave/approve/<int:request_id>`
- **Auth required:** Yes (Admin or Staff)
- **Request Body:**
  ```json
  {
    "status": "Approved"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "message": "Leave request successfully marked as Approved",
    "leave_id": 5
  }
  ```

---

## 5. Emergency SOS Module (`/api/emergency`)

### 5.1 Trigger SOS Alarm
- **Endpoint:** `POST /api/emergency/sos`
- **Auth required:** Yes
- **Request Body:**
  ```json
  {
    "latitude": 13.0844,
    "longitude": 79.9972
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "status": "success",
    "message": "Emergency SOS triggered! Dispatching security response team.",
    "alert_id": 12
  }
  ```

### 5.2 Resolve Active SOS
- **Endpoint:** `POST /api/emergency/resolve/<int:alert_id>`
- **Auth required:** Yes (Admin or Security)
- **Response (200 OK):**
  ```json
  {
    "message": "Emergency SOS marked as resolved."
  }
  ```
