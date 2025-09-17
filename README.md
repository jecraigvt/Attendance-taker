# Troy High Shared Attendance Tool

This repository now contains a lightweight full-stack prototype that lets multiple Troy High School teachers share class rosters and record attendance collaboratively. The legacy Firebase page can continue operating separately while this project evolves toward a production-ready rollout.

## Project Structure

```
├── public/              # Static front-end served by the Express backend
│   └── index.html       # Login, roster management, and attendance UI
├── server/
│   ├── index.js         # Express entry point with REST API and static hosting
│   ├── lib/db.js        # SQLite database initialisation and migrations
│   ├── middleware/      # Authentication middleware
│   ├── routes/          # Auth, class, student, and attendance endpoints
│   └── scripts/         # Maintenance utilities (seed teacher, setup check)
├── docs/
│   └── data-governance.md
├── .env.example         # Environment variable template
└── README.md
```

## Getting Started

1. **Install dependencies**
   ```bash
   cd server
   npm install
   ```

2. **Create an environment file**
   ```bash
   cp ../.env.example ../.env
   # Edit ../.env to set JWT_SECRET and (optionally) REGISTRATION_CODE
   ```

3. **Run the setup check** (ensures the data directory exists)
   ```bash
   npm test
   ```

4. **Seed your first teacher account**
   ```bash
   node scripts/seed-teacher.js "Teacher Name" "teacher@troyhigh.edu" "strong-password"
   ```

5. **Start the backend**
   ```bash
   npm start
   ```
   The Express server listens on the port defined in `.env` (defaults to `8080`) and serves the front end at `http://localhost:8080/`.

## API Overview

All API routes live under `/api` and require authentication except for the login and registration endpoints.

- `POST /api/auth/login` — Obtain a JWT-backed session cookie.
- `POST /api/auth/logout` — Clear the session cookie.
- `POST /api/auth/register` — Create a teacher account (optionally gated by `REGISTRATION_CODE`).
- `GET /api/classes` — List the authenticated teacher's classes.
- `POST /api/classes` — Create a new class.
- `PUT /api/classes/:id` — Update an existing class.
- `DELETE /api/classes/:id` — Remove a class and related students/attendance.
- `GET /api/students?classId=ID` — List students for a class.
- `POST /api/students` — Add a student to the current teacher's class.
- `DELETE /api/students/:id` — Remove a student (and their attendance records).
- `GET /api/attendance?classId=ID&date=YYYY-MM-DD` — Fetch attendance entries.
- `POST /api/attendance` — Upsert attendance for a student on a specific date.

## Privacy and Compliance

Review the guidance in [`docs/data-governance.md`](docs/data-governance.md) before deploying the shared system. The document summarizes FERPA-related expectations, access policies, and incident-response procedures.

## Next Steps

- Integrate the backend with a production-ready database (e.g., PostgreSQL) once requirements solidify.
- Connect to the district's SSO provider or Google Workspace for centralized teacher accounts.
- Expand reporting (weekly summaries, exports) and audit logging before launching to staff.
