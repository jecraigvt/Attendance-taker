const express = require('express');
const { getDb } = require('../lib/db');

const router = express.Router();

router.get('/', async (req, res) => {
  const { classId } = req.query;
  if (!classId) {
    return res.status(400).json({ message: 'classId query parameter is required' });
  }

  const db = getDb();
  const students = await db.all(
    'SELECT id, first_name, last_name FROM students WHERE class_id = ? AND teacher_id = ? ORDER BY last_name ASC, first_name ASC',
    classId,
    req.teacher.id
  );

  res.json({ students });
});

router.post('/', async (req, res) => {
  const { classId, firstName, lastName } = req.body;
  if (!classId || !firstName || !lastName) {
    return res.status(400).json({ message: 'classId, firstName, and lastName are required' });
  }

  const db = getDb();
  const classroom = await db.get('SELECT id FROM classes WHERE id = ? AND teacher_id = ?', classId, req.teacher.id);
  if (!classroom) {
    return res.status(404).json({ message: 'Class not found' });
  }

  const result = await db.run(
    'INSERT INTO students (class_id, teacher_id, first_name, last_name) VALUES (?, ?, ?, ?)',
    classId,
    req.teacher.id,
    firstName,
    lastName
  );

  res.status(201).json({
    id: result.lastID,
    firstName,
    lastName
  });
});

router.delete('/:id', async (req, res) => {
  const { id } = req.params;
  const db = getDb();
  const result = await db.run('DELETE FROM students WHERE id = ? AND teacher_id = ?', id, req.teacher.id);
  if (result.changes === 0) {
    return res.status(404).json({ message: 'Student not found' });
  }
  res.status(204).end();
});

module.exports = router;
