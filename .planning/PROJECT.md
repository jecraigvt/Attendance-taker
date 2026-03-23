# Attendance Taker

## What This Is

A school attendance system that captures student sign-ins via tablet kiosks, stores them in Firebase, and syncs to Aeries (the official student information system). Currently a single-teacher tool hosted at rollcall.it.com. This milestone transforms it into a multi-tenant platform where any teacher can sign up, manage rosters, and have attendance automatically synced to Aeries — with self-healing automation that fixes itself when Aeries UI changes.

## Core Value

Every student who signs in must have their correct attendance status reflected in Aeries. The system must work reliably for multiple teachers without requiring technical support from the developer.

## Current Milestone: v2.0 Multi-Tenant SaaS

**Goal:** Transform from single-teacher tool to multi-tenant platform with cloud sync and self-healing automation

**Target features:**
- Firebase Auth with Google login, per-teacher data isolation
- Teacher dashboard (roster upload, sync status, Aeries credential management)
- Cloud-based Aeries sync on Railway (no longer runs on developer's PC)
- Self-healing Playwright automation using Gemini LLM (Flash first, Pro fallback)
- Hosted at rollcall.it.com (Firebase Hosting — already deployed)

## Requirements

### Validated

- ✓ Student sign-in via tablet kiosk — existing
- ✓ Firebase storage of attendance records — existing
- ✓ Sync to Aeries via Playwright automation with retry logic — v1.0
- ✓ Scheduled sync every 20 min during school hours — v1.0
- ✓ Audit logging and verification reports — v1.0
- ✓ Selector fallbacks for Aeries UI changes — v1.0
- ✓ Bell-schedule-based tardy logic — v1.0
- ✓ Firebase Hosting deployment at rollcall.it.com — v1.0

### Active

- [ ] Multi-tenant authentication (Google login per teacher)
- [ ] Per-teacher data isolation in Firestore
- [ ] Teacher dashboard with roster management and sync status
- [ ] Secure Aeries credential storage per teacher
- [ ] Cloud-based sync server on Railway
- [ ] Self-healing Playwright with Gemini LLM (selector auto-repair)
- [ ] Teacher onboarding flow (first-time setup)

### Out of Scope

- Aeries API integration — still requires district IT approval
- Mobile app — tablet kiosks and web app are sufficient
- Real-time sync — 20-min batch sync is sufficient
- Student-facing features — sign-in kiosk UI unchanged
- Multi-school support — single school district for now

## Context

**Current architecture:**
```
Student → Tablet kiosk → Firebase → Local sync script (Jeremy's PC) → Aeries
```

**Target architecture:**
```
Student → Tablet kiosk → Firebase (per-teacher) → Railway cloud sync → Aeries
                                                      ↓ (on failure)
                                                   Gemini LLM → patch selectors → retry
```

**Technical environment:**
- Frontend: Single HTML file with Tailwind CSS, Firebase SDK
- Backend: Python 3.x with firebase-admin, Playwright
- Database: Firebase Firestore (anonymous auth currently)
- Hosting: Firebase Hosting (rollcall.it.com)
- Sync: Currently runs on Windows Task Scheduler locally
- Target: Railway for cloud sync, Gemini API for self-healing

**Key context from v1.0:**
- Sync reliability improved from ~97% to near-100%
- Selector fallback strategy: data-attr → text-content → xpath
- 20-minute sync intervals during 08:00-15:45
- Bell-schedule-based tardy logic with 5-min grace period

## Constraints

- **Aeries access**: Push-only via browser automation; no API
- **Security**: Must encrypt teacher Aeries credentials at rest
- **Cost**: Railway free tier limits; Gemini Flash for cost control
- **Gemini API**: User has existing Gemini API key
- **Browser automation**: Playwright needs headless browser in cloud container
- **School year**: Teachers actively using the system; changes must not disrupt

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep browser automation | Aeries API not available without district IT approval | ✓ Good |
| Firebase Auth with Google | Teachers already have school Google accounts | — Pending |
| Railway for cloud sync | User already has Railway account; supports Docker containers | — Pending |
| Gemini Flash first, Pro fallback | Flash is 10-20x cheaper; sufficient for selector matching | — Pending |
| Selector config file over code patching | Safer than LLM rewriting Python; git-trackable changes | — Pending |
| Encrypted credential storage | Teacher passwords stored encrypted in Firestore | — Pending |

---
*Last updated: 2026-03-23 after milestone v2.0 initialization*
