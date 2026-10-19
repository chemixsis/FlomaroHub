
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            pin_hash TEXT NOT NULL,
            access_level TEXT NOT NULL DEFAULT 'employee',
            hourly_rate REAL NOT NULL DEFAULT 32,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS registration_requests (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS work_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_work_groups (
            user_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, group_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES work_groups(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            work_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            note TEXT,
            work_group TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT,
            note TEXT,
            manager_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS event_assignments (
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (event_id, user_id),
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS event_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            content BLOB NOT NULL,
            sha256 TEXT NOT NULL,
            uploaded_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(event_id, sha256)
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            period_from TEXT NOT NULL,
            period_to TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT,
            received_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS availabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            availability_date TEXT NOT NULL,
            availability_type TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            note TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, availability_date),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL DEFAULT 'info',
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_at TEXT NOT NULL,
            end_at TEXT,
            actual_minutes INTEGER,
            billable_hours DOUBLE PRECISION,
            hourly_rate REAL,
            amount REAL,
            approval_status TEXT NOT NULL DEFAULT 'active',
            approved_by INTEGER,
            approved_at TEXT,
            payment_id INTEGER,
            original_start_at TEXT,
            original_end_at TEXT,
            corrected_by INTEGER,
            corrected_at TEXT,
            correction_note TEXT,
            rejection_note TEXT,
            work_group TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (approved_by) REFERENCES users(id),
            FOREIGN KEY (corrected_by) REFERENCES users(id),
            FOREIGN KEY (payment_id) REFERENCES payments(id)
        );
        

CREATE TABLE IF NOT EXISTS recurring_schedules (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    starts_on TEXT NOT NULL,
    ends_on TEXT,
    work_group TEXT NOT NULL CHECK (work_group IN ('warehouse', 'local')),
    PRIMARY KEY (user_id, starts_on)
);
CREATE TABLE IF NOT EXISTS schedule_overrides (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    work_date TEXT NOT NULL,
    PRIMARY KEY (user_id, work_date)
);


CREATE TABLE IF NOT EXISTS delivery_outbox (
 id TEXT PRIMARY KEY, channel TEXT NOT NULL, recipient TEXT NOT NULL,
 subject TEXT NOT NULL, body TEXT NOT NULL, user_id INTEGER REFERENCES users(id),
 event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'queued', created_at BIGINT NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0, first_attempt BIGINT NOT NULL DEFAULT 0,
 next_attempt BIGINT NOT NULL DEFAULT 0, lease_until BIGINT NOT NULL DEFAULT 0,
 provider_id TEXT NOT NULL DEFAULT '', last_error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS delivery_queue_idx ON delivery_outbox(status,next_attempt);
CREATE TABLE IF NOT EXISTS support_tickets (
 id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),subject TEXT NOT NULL,
 description TEXT NOT NULL,page TEXT NOT NULL,created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY,applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payroll_migration_backup (
 shift_id INTEGER PRIMARY KEY, actual_minutes INTEGER, billable_hours DOUBLE PRECISION,
 amount DOUBLE PRECISION
);
