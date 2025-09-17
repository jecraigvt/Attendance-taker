const express = require('express');
const { getDb } = require('../lib/db');

const router = express.Router();

router.get('/', async (req, res) => {
  const db = getDb();
  const classes = await db.all(
    'SELECT id, name, period, created_at FROM classes WHERE teacher_id = ? ORDER BY created_at DESC',
    req.teacher.id
  );
  res.json({ classes });
});

router.post('/', async (req, res) => {
  const { name, period } = req.body;
  if (!name) {
    return res.status(400).json({ message: 'Class name is required' });
  }

  const db = getDb();
  const result = await db.run(
    'INSERT INTO classes (teacher_id, name, period) VALUES (?, ?, ?)',
    req.teacher.id,
    name,
    period || null
  );

  res.status(201).json({
    id: result.lastID,
    name,
    period: period || null
  });
});

router.put('/:id', async (req, res) => {
  const { name, period } = req.body;
  const { id } = req.params;
  const db = getDb();

  const existing = await db.get(
    'SELECT id, name, period FROM classes WHERE id = ? AND teacher_id = ?',
    id,
    req.teacher.id
  );
  if (!existing) {
    return res.status(404).json({ message: 'Class not found' });
  }

  const nextName = name ? name : existing.name;
  const nextPeriod = period !== undefined ? period : existing.period;

  await db.run('UPDATE classes SET name = ?, period = ? WHERE id = ?', nextName, nextPeriod || null, id);

  res.json({
    id: Number(id),
    name: nextName,
    period: nextPeriod || null
  });
});

router.delete('/:id', async (req, res) => {
  const { id } = req.params;
  const db = getDb();
  const result = await db.run('DELETE FROM classes WHERE id = ? AND teacher_id = ?', id, req.teacher.id);
  if (result.changes === 0) {
    return res.status(404).json({ message: 'Class not found' });
  }
  res.status(204).end();
});

module.exports = router;
