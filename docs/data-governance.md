# Data Governance and Privacy Considerations

Attendance information is personally identifiable student data. When sharing this tool with other Troy High School teachers, follow the guidelines below to comply with FERPA and district policy.

## Access Control
- Only district-employed teachers and approved staff may have accounts.
- Require strong, unique passwords and revoke credentials immediately when staff depart.
- Store passwords only as strong hashes (bcrypt with a cost factor of 12 or greater).
- Restrict API endpoints with authentication middleware so teachers can only see their own classes.

## Data Handling
- Host the server on district-managed infrastructure or an approved cloud provider with encryption at rest.
- Enforce HTTPS in production to encrypt traffic between browsers and the backend.
- Back up the SQLite database on a secure schedule and keep backups encrypted.
- Log access attempts and unexpected errors, but avoid logging full student records or passwords.

## Retention and Auditing
- Define how long attendance records must be kept for compliance and purge data past the retention window.
- Keep an audit trail of changes (who recorded or updated attendance) if required by district policy.
- Review access logs periodically to detect misuse.

## Incident Response
- Document a procedure for reporting suspected breaches to district leadership within 24 hours.
- Rotate JWT secrets and invalidate sessions if you suspect token leakage.
- Communicate remediation steps to affected teachers and families when necessary.

## Training and Usage
- Provide teachers with training on how to log in, maintain rosters, and report issues.
- Remind staff not to share screenshots of the tool on public channels.
- Keep a change log when updating the application so administrators understand functional differences.
