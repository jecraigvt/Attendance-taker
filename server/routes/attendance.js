const express = require('express');
const { getDb } = require('../lib/db');

const router = express.Router();

router.get('/', async (req, res) => {
  const { classId, date } = req.query;
  if (!classId || !date) {
    return res.status(400).json({ message: 'classId and date query parameters are required' });
  }

  const db = getDb();
  const entries = await db.all(
    `SELECT attendance_entries.id, attendance_entries.student_id, attendance_entries.status, attendance_entries.note
     FROM attendance_entries
     INNER JOIN students ON students.id = attendance_entries.student_id
     WHERE attendance_entries.class_id = ?
       AND attendance_entries.attendance_date = ?
       AND attendance_entries.teacher_id = ?
     ORDER BY students.last_name ASC, students.first_name ASC`,
    classId,
    date,
    req.teacher.id
  );

  res.json({ entries });
});

router.post('/', async (req, res) => {
  const { classId, studentId, date, status, note } = req.body;
  if (!classId || !studentId || !date || !status) {
    return res.status(400).json({ message: 'classId, studentId, date, and status are required' });
  }

  const db = getDb();
  const classroom = await db.get('SELECT id FROM classes WHERE id = ? AND teacher_id = ?', classId, req.teacher.id);
  if (!classroom) {
    return res.status(404).json({ message: 'Class not found' });
  }

  const student = await db.get('SELECT id FROM students WHERE id = ? AND teacher_id = ?', studentId, req.teacher.id);
  if (!student) {
    return res.status(404).json({ message: 'Student not found' });
  }

  await db.run(
    `INSERT INTO attendance_entries (teacher_id, class_id, student_id, attendance_date, status, note)
     VALUES (?, ?, ?, ?, ?, ?)
     ON CONFLICT(class_id, student_id, attendance_date)
     DO UPDATE SET status = excluded.status, note = excluded.note, recorded_at = datetime('now')`,
    req.teacher.id,
    classId,
    studentId,
    date,
    status,
    note || null
  );

  res.status(201).json({ message: 'Attendance recorded' });
});

module.exports = router;
