# 🏢 VMF Society Visitor App

A cloud‑hosted **visitor management system** built with **FastAPI**, **PostgreSQL**, and **Firebase OTP authentication**.  
This app helps housing societies manage visitor entries, security verification, and resident notifications.

---

## 🚀 Features
- **Visitor Registration**: Residents can log visitor details (name, phone, flat number, purpose).
- **Security Gate Interface**: Guards can check in/out visitors with timestamps.
- **Resident Notifications**: OTP verification via Firebase (with test numbers for development).
- **Admin Dashboard**: View daily/weekly visitor logs and reports.
- **Persistent Storage**: PostgreSQL database hosted on Render (free 1 GB tier).
- **Cloud Deployment**: Dockerized backend deployed on Render.

---

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL (Render free tier)
- **ORM**: SQLAlchemy + Alembic migrations
- **Authentication**: Firebase Phone OTP
- **Deployment**: Docker + Render
- **Frontend (optional)**: React / Vue (to be integrated)

---

## ⚙️ Setup Instructions

### 1. Clone the repo
```bash
git clone https://github.com/<your-username>
