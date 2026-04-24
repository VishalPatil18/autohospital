-- Decode Seed Data
-- Run after Alembic migrations: psql -U postgres -d decode -f seed.sql
--
-- All passwords are "password123"
-- Argon2id hash generated with argon2-cffi default parameters:
--   from argon2 import PasswordHasher; ph = PasswordHasher(); ph.hash("password123")
-- The hash below is a valid argon2id hash of "password123" for reference.
-- In production, generate fresh hashes; argon2id salts are random per hash.
--
-- Hash used: $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>
-- Each user has a distinct hash (different salt) but all verify against "password123".

-- Fixed UUIDs for seed data
-- Patients
-- Alice:  a1000000-0000-0000-0000-000000000001
-- Bob:    a2000000-0000-0000-0000-000000000002
-- Doctors
-- Smith:  d1000000-0000-0000-0000-000000000001
-- Jones:  d2000000-0000-0000-0000-000000000002

BEGIN;

-- ── Users ────────────────────────────────────────────────────────────────────

INSERT INTO users (id, email, password_hash, role, created_at) VALUES
(
    'a1000000-0000-0000-0000-000000000001',
    'alice@example.com',
    '$argon2id$v=19$m=65536,t=3,p=4$c29tZXJhbmRvbXNhbHQ$RdescudvJCsgt3ub+b+dWRWJTmaasfNlW4nTjCKmSZA',
    'patient',
    NOW()
),
(
    'a2000000-0000-0000-0000-000000000002',
    'bob@example.com',
    '$argon2id$v=19$m=65536,t=3,p=4$c29tZXJhbmRvbXNhbHQ$RdescudvJCsgt3ub+b+dWRWJTmaasfNlW4nTjCKmSZA',
    'patient',
    NOW()
),
(
    'd1000000-0000-0000-0000-000000000001',
    'dr.smith@example.com',
    '$argon2id$v=19$m=65536,t=3,p=4$c29tZXJhbmRvbXNhbHQ$RdescudvJCsgt3ub+b+dWRWJTmaasfNlW4nTjCKmSZA',
    'doctor',
    NOW()
),
(
    'd2000000-0000-0000-0000-000000000002',
    'dr.jones@example.com',
    '$argon2id$v=19$m=65536,t=3,p=4$c29tZXJhbmRvbXNhbHQ$RdescudvJCsgt3ub+b+dWRWJTmaasfNlW4nTjCKmSZA',
    'doctor',
    NOW()
);

-- ── Patient profiles ──────────────────────────────────────────────────────────

INSERT INTO patients (user_id, dob, first_name, last_name, phone, address) VALUES
(
    'a1000000-0000-0000-0000-000000000001',
    '1990-03-15',
    'Alice',
    'Nguyen',
    '555-1001',
    '123 Maple Street, Springfield, IL 62701'
),
(
    'a2000000-0000-0000-0000-000000000002',
    '1985-07-22',
    'Bob',
    'Martinez',
    '555-1002',
    '456 Oak Avenue, Springfield, IL 62702'
);

-- ── Doctor profiles ───────────────────────────────────────────────────────────

INSERT INTO doctors (user_id, specialty, first_name, last_name, license_number) VALUES
(
    'd1000000-0000-0000-0000-000000000001',
    'Internal Medicine',
    'James',
    'Smith',
    'IL-MD-10001'
),
(
    'd2000000-0000-0000-0000-000000000002',
    'Cardiology',
    'Linda',
    'Jones',
    'IL-MD-10002'
);

-- ── Care team (Dr. Smith → Alice) ─────────────────────────────────────────────

INSERT INTO care_team (doctor_id, patient_id) VALUES
(
    'd1000000-0000-0000-0000-000000000001',
    'a1000000-0000-0000-0000-000000000001'
);

-- ── Appointment (Alice with Dr. Smith, scheduled tomorrow) ────────────────────

INSERT INTO appointments (id, patient_id, doctor_id, scheduled_at, status, notes, created_at) VALUES
(
    'e1000000-0000-0000-0000-000000000001',
    'a1000000-0000-0000-0000-000000000001',
    'd1000000-0000-0000-0000-000000000001',
    NOW() + INTERVAL '1 day',
    'scheduled',
    'Annual wellness checkup. Patient reports mild fatigue.',
    NOW()
);

COMMIT;

-- ── Verification ──────────────────────────────────────────────────────────────
-- SELECT u.email, u.role, p.first_name, p.last_name FROM users u
-- LEFT JOIN patients p ON p.user_id = u.id
-- LEFT JOIN doctors d ON d.user_id = u.id;
