const path = require('path');
const express = require('express');
const cookieParser = require('cookie-parser');
const cors = require('cors');
const dotenv = require('dotenv');
const { initDb } = require('./lib/db');
const authRouter = require('./routes/auth');
const classesRouter = require('./routes/classes');
const studentsRouter = require('./routes/students');
const attendanceRouter = require('./routes/attendance');
const { authenticate } = require('./middleware/authenticate');

dotenv.config({ path: path.resolve(__dirname, '..', '.env') });

const app = express();

const allowedOrigins = (process.env.CLIENT_ORIGIN || 'http://localhost:8080,http://localhost:5173,http://localhost:4173')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);
app.use(cors({
  origin: allowedOrigins,
  credentials: true
}));
app.use(express.json());
app.use(cookieParser());

app.use('/api/auth', authRouter);
app.use('/api/classes', authenticate, classesRouter);
app.use('/api/students', authenticate, studentsRouter);
app.use('/api/attendance', authenticate, attendanceRouter);

const publicDir = path.join(__dirname, '..', 'public');
app.use(express.static(publicDir));

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

const port = process.env.PORT || 8080;

async function start() {
  await initDb();
  app.listen(port, () => {
    console.log(`Attendance backend listening on port ${port}`);
  });
}

start().catch((error) => {
  console.error('Failed to start server', error);
  process.exit(1);
});

module.exports = app;
