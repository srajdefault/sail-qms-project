# 🏢 SAIL Quarter Management System (SAIL QMS)

A robust, enterprise-grade Django web application engineered to streamline quarterly inspections, operator tracking, supervisor reviews, and automated OTP authentication for SAIL quarters.

---

### 📍 Highlight Feature: Location-Verified Inspections

To enforce strict field-data integrity during quarter inspections, the platform incorporates real-time **Geofenced Location Verification**:

1. **GPS Spatial Check**: When an operator initiates an inspection, the frontend captures live browser GPS coordinates (latitude/longitude).
2. **Radius Validation**: The backend checks operator coordinates against the defined center point and `allowed_radius_meters` of the assigned Sector using the Haversine formula.
3. **Automated Rejection**: Submissions outside the permitted radius are automatically flagged or blocked, preventing off-site fraud.
4. **Photo Evidence Tracking**: Every report pairs validated location data with uploaded visual proof (`/media/inspection_photos/`).

---

## 🔒 Role-Based Access Control (RBAC)

The system uses custom decorators and profile roles to strictly isolate permissions across three tiers:

- **👷 Operator**:
  - Accesses location-verified field inspection forms.
  - Uploads mandatory photo evidence for quarter audits.
  - Receives real-time feedback on sector radius compliance.

- **👨‍💼 Supervisor**:
  - Accesses the **Supervisor Dashboard** (`/supervisor_dashboard/`).
  - Monitors and verifies incoming inspection submissions from assigned field operators.
  - Tracks compliance metrics and resolves flagged audits.

- **📊 Manager**:
  - Accesses system-wide analytics via **Manager Overview** (`/manager_overview/`).
  - Audits sector boundaries, operator activity, and overall quarters status.

---

## 🔑 Key Capabilities

- **Mobile-Friendly OTP Authentication**: Passwordless login workflow utilizing phone/email OTP verification.
- **Dynamic Sector Management**: Configurable sector center coordinates and geo-radius tolerances in meters.
- **Evidence Storage Pipeline**: Secure local media handling for audit photos and evidence records.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.13, Django 5.x
- **Frontend**: HTML5, CSS3, JavaScript (Django Templates)
- **Database**: SQLite (Development) / PostgreSQL (Production ready)
- **HTTP/API Utilities**: Python `requests` library

---

## ⚙️ Local Setup & Installation Instructions

### 1. Clone the Repository
```bash
git clone [https://github.com/srajdefault/sail-qms-project.git](https://github.com/srajdefault/sail-qms-project.git)
cd sail-qms-project
