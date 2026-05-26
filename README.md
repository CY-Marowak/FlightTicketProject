# Flight Ticket Tracker

An application that tracks the flight prices from time to time and notifies users when prices drop. <br>
There are three version (Desktop, Web and Mobile) for users.

## How it Works
### App Flow:
<a href="https://viewer.diagrams.net/?target=blank&highlight=0000ff&edit=_blank&layers=1&nav=1#Uhttps://github.com/CY-Marowak/FlightTicketProject/raw/refs/heads/master/diagram/App%20flow.svg">
  <img src="diagram/App%20flow.svg" alt="App flow" width="80%">
</a>

---

## Project Overview

### System Architecture:
<a href="https://viewer.diagrams.net/?target=blank&highlight=0000ff&edit=_blank&layers=1&nav=1#Uhttps://github.com/CY-Marowak/FlightTicketProject/raw/refs/heads/master/diagram/System%20Architecture.svg">
  <img src="diagram/System%20Architecture.svg" alt="System Architecture" width="100%">
</a>

---

### Business Logic Flow:
<a href="https://viewer.diagrams.net/?lightbox=1&ui=dark&?target=blank&highlight=0000ff&edit=_blank&layers=1&nav=1#Uhttps://github.com/CY-Marowak/FlightTicketProject/raw/refs/heads/master/diagram/Business%20Logic%20flow.svg">
  <img src="diagram/Business%20Logic%20flow.svg" alt="Business Logic flow" width="100%">
</a>

---

## Tech Stack & Technical Highlights
### Backend & Infrastructure
* **Flask & Python**: Built a RESTful API backend serving three distinct client platforms.
* **APScheduler & Automation**: Implemented a background cron-job running every 10 minutes to fetch live flight data via **RapidAPI**, drastically reducing manual tracking effort.
* **Database Optimization**: Designed a PostgreSQL schema leveraging `ON DELETE SET NULL` constraints to automatically clean up expired flight schedules while preserving users' historical price alert logs.
* **FCM & Real-time Sync**: Integrated **Firebase Cloud Messaging (FCM)** for mobile push notifications and **Socket.io** for real-time web UI updates.

### Frontend & Clients
* **Web (React & TypeScript)**: Built a responsive dashboard featuring historical price charts.
* **Mobile (React Native & Expo)**: Developed a cross-platform mobile app utilizing **Expo Secure Store (iOS Keychain / Android KeyStore)** for encrypted JWT token storage to ensure device-level security.
* **Desktop (PyQt5)**: Built a lightweight native desktop client, packaged into a standalone `.exe` via PyInstaller.

---
## Web version

https://flightticketwebproject.onrender.com/

## Desktop version Installation

1. Go to [GitHub Releases](https://github.com/CY-Marowak/FlightTicketProject/releases).
2. Click the latest "Desktop" Version.
3. Open assets and download "FlightTicketTracker.exe".
4. Click "FlightTicketTracker.exe" on your desktop to start.

## Mobile version Installation

1. Go to [GitHub Releases](https://github.com/CY-Marowak/FlightTicketProject/releases).
2. Click the latest "Mobile" Version.
3. Open the link and click install.
4. Scan the QR code and download the app.
5. Open "FlightTicketMobile" on your phone to start.
