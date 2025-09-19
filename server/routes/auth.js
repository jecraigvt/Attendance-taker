const express = require('express');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { OAuth2Client } = require('google-auth-library');
const crypto = require('crypto');
const { getDb } = require('../lib/db');

const router = express.Router();

let googleClient;

function getGoogleClient() {
  if (googleClient) {
    return googleClient;
  }
  const clientId = process.env.GOOGLE_CLIENT_ID;
  if (!clientId) {
    return null;
  }
  googleClient = new OAuth2Client(clientId);
  return googleClient;
}

function getAllowedGoogleDomain() {
  return (process.env.GOOGLE_ALLOWED_DOMAIN || 'fjuhsd.org').toLowerCase();
}

function issueAuthResponse(res, teacher) {
  const tokenPayload = { teacherId: teacher.id };
  const token = jwt.sign(tokenPayload, process.env.JWT_SECRET || 'change-me', { expiresIn: '8h' });

  res.cookie('token', token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 8 * 60 * 60 * 1000
  });

  res.json({
    token,
    teacher: {
      id: teacher.id,
      name: teacher.name,
      email: teacher.email
    }
  });
}

router.post('/login', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ message: 'Email and password are required' });
  }

  const db = getDb();
  const teacher = await db.get('SELECT id, name, email, password_hash FROM teachers WHERE email = ?', email);

  if (!teacher) {
    return res.status(401).json({ message: 'Invalid email or password' });
  }

  const passwordMatches = await bcrypt.compare(password, teacher.password_hash);
  if (!passwordMatches) {
    return res.status(401).json({ message: 'Invalid email or password' });
  }

  issueAuthResponse(res, teacher);
});

router.post('/logout', (req, res) => {
  res.clearCookie('token');
  res.status(204).end();
});

router.post('/register', async (req, res) => {
  const { name, email, password, registrationCode } = req.body;
  if (!name || !email || !password) {
    return res.status(400).json({ message: 'Name, email, and password are required' });
  }

  const expectedCode = process.env.REGISTRATION_CODE;
  if (expectedCode && registrationCode !== expectedCode) {
    return res.status(403).json({ message: 'Invalid registration code' });
  }

  const db = getDb();
  const existing = await db.get('SELECT id FROM teachers WHERE email = ?', email);
  if (existing) {
    return res.status(409).json({ message: 'A teacher with that email already exists' });
  }

  const passwordHash = await bcrypt.hash(password, 12);
  const result = await db.run(
    'INSERT INTO teachers (name, email, password_hash) VALUES (?, ?, ?)',
    name,
    email,
    passwordHash
  );

  res.status(201).json({
    id: result.lastID,
    name,
    email
  });
});

router.get('/config', (req, res) => {
  res.json({
    clientId: process.env.GOOGLE_CLIENT_ID || null,
    allowedDomain: getAllowedGoogleDomain()
  });
});

router.post('/google', async (req, res) => {
  const credential = req.body?.credential;
  if (!credential) {
    return res.status(400).json({ message: 'Google credential is required' });
  }

  const client = getGoogleClient();
  if (!client) {
    return res.status(500).json({ message: 'Google sign-in is not configured' });
  }

  try {
    const ticket = await client.verifyIdToken({
      idToken: credential,
      audience: process.env.GOOGLE_CLIENT_ID
    });

    const payload = ticket.getPayload();
    const email = payload?.email?.toLowerCase();
    if (!email) {
      return res.status(401).json({ message: 'Google account is missing an email address' });
    }

    if (!payload.email_verified) {
      return res.status(401).json({ message: 'Google email is not verified' });
    }

    const allowedDomain = getAllowedGoogleDomain();
    if (!email.endsWith(`@${allowedDomain}`)) {
      return res.status(403).json({ message: `Please use your ${allowedDomain} account` });
    }

    const db = getDb();
    let teacher = await db.get('SELECT id, name, email FROM teachers WHERE email = ?', email);
    const displayName = payload.name || [payload.given_name, payload.family_name].filter(Boolean).join(' ') || email;

    if (!teacher) {
      const placeholderSecret = payload.sub || crypto.randomBytes(32).toString('hex');
      const passwordHash = await bcrypt.hash(placeholderSecret, 12);
      const result = await db.run(
        'INSERT INTO teachers (name, email, password_hash) VALUES (?, ?, ?)',
        displayName,
        email,
        passwordHash
      );
      teacher = {
        id: result.lastID,
        name: displayName,
        email
      };
    } else if (displayName && teacher.name !== displayName) {
      await db.run('UPDATE teachers SET name = ? WHERE id = ?', displayName, teacher.id);
      teacher.name = displayName;
    }

    issueAuthResponse(res, teacher);
  } catch (error) {
    console.error('Google sign-in failed', error);
    res.status(401).json({ message: 'Google sign-in failed' });
  }
});

router.get('/me', async (req, res) => {
  const token = req.cookies?.token;
  if (!token) {
    return res.status(401).json({ message: 'Not authenticated' });
  }

  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET || 'change-me');
    const db = getDb();
    const teacher = await db.get('SELECT id, name, email FROM teachers WHERE id = ?', payload.teacherId);
    if (!teacher) {
      return res.status(401).json({ message: 'Not authenticated' });
    }
    res.json({ teacher });
  } catch (error) {
    res.status(401).json({ message: 'Not authenticated' });
  }
});

module.exports = router;
