const jwt = require('jsonwebtoken');
const { getDb } = require('../lib/db');

function getTokenFromRequest(req) {
  const authHeader = req.get('Authorization');
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.slice(7);
  }
  if (req.cookies && req.cookies.token) {
    return req.cookies.token;
  }
  return null;
}

async function authenticate(req, res, next) {
  const token = getTokenFromRequest(req);

  if (!token) {
    return res.status(401).json({ message: 'Authentication required' });
  }

  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET || 'change-me');
    const db = getDb();
    const teacher = await db.get('SELECT id, name, email FROM teachers WHERE id = ?', payload.teacherId);
    if (!teacher) {
      return res.status(401).json({ message: 'Invalid authentication token' });
    }

    req.teacher = teacher;
    next();
  } catch (err) {
    console.error('Authentication error', err);
    res.status(401).json({ message: 'Invalid or expired authentication token' });
  }
}

module.exports = {
  authenticate
};
