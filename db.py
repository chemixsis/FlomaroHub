import sqlite3
import hashlib
import re
from pathlib import Path
from datetime import datetime, timedelta, date

from postgres_backend import connect
from cloud_config import setting


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def init_db(seed=True):
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(73190421)")
        conn.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
        if seed:
            for code, name in (("event", "Eventy"), ("local", "Lokal"), ("warehouse", "Magazyn")):
                conn.execute("INSERT OR IGNORE INTO work_groups(code,name) VALUES(?,?)", (code, name))


def admin_exists():
    with connect() as conn:
        return conn.execute("""
            SELECT 1 FROM users
            WHERE access_level = 'admin' AND active = 1
            LIMIT 1
        """).fetchone() is not None


def add_user(first_name, last_name, email, phone, pin, registration_token=None):
    first_name = first_name.strip()
    last_name = last_name.strip()
    email = email.strip().lower()
    phone = phone.strip()

    if not first_name or not last_name:
        return False, "Podaj imię i nazwisko."
    if "@" not in email:
        return False, "Podaj poprawny adres e-mail."
    if not phone:
        return False, "Podaj numer telefonu."
    if not (pin.isdigit() and len(pin) == 4):
        return False, "PIN musi składać się dokładnie z 4 cyfr."

    try:
        with connect() as conn:
            # Serialize duplicate clicks and simultaneous first registrations.
            conn.execute("BEGIN IMMEDIATE")
            if registration_token and conn.execute(
                "SELECT 1 FROM registration_requests WHERE token = ?",
                (registration_token,),
            ).fetchone():
                return True, "Konto zostało już utworzone. Możesz się zalogować."
            if conn.execute(
                "SELECT 1 FROM users WHERE lower(trim(email)) = ?", (email,),
            ).fetchone():
                return False, "Konto z takim adresem e-mail już istnieje."
            access_level = "employee" if conn.execute(
                "SELECT 1 FROM users WHERE access_level = 'admin' AND active = 1 LIMIT 1"
            ).fetchone() else "admin"
            if access_level == "admin" and email != str(setting("BOOTSTRAP_EMAIL", "")).strip().lower():
                return False, "Pierwsze konto może utworzyć tylko wskazany właściciel aplikacji."
            cursor = conn.execute("""
                INSERT INTO users
                (first_name, last_name, email, phone, pin_hash, access_level, hourly_rate)
                VALUES (?, ?, ?, ?, ?, ?, 32)
            """, (
                first_name,
                last_name,
                email,
                phone,
                hash_pin(pin),
                access_level,
            ))
            if registration_token:
                conn.execute(
                    "INSERT INTO registration_requests (token, user_id) VALUES (?, ?)",
                    (registration_token, cursor.lastrowid),
                )
        if access_level == "admin":
            return True, "Konto szefa zostało utworzone."
        return True, "Konto zostało utworzone."
    except sqlite3.IntegrityError:
        return False, "Konto z takim adresem e-mail już istnieje."




def change_own_pin(user_id, current_pin, new_pin):
    if not (new_pin.isdigit() and len(new_pin) == 4):
        return False, "Nowy PIN musi składać się dokładnie z 4 cyfr."

    if not (current_pin.isdigit() and len(current_pin) == 4):
        return False, "Podaj poprawny obecny PIN."

    with connect() as conn:
        user = conn.execute("""
            SELECT pin_hash
            FROM users
            WHERE id = ?
              AND active = 1
        """, (user_id,)).fetchone()

        if not user:
            return False, "Nie znaleziono konta."

        if user["pin_hash"] != hash_pin(current_pin):
            return False, "Obecny PIN jest nieprawidłowy."

        conn.execute("""
            UPDATE users
            SET pin_hash = ?
            WHERE id = ?
        """, (
            hash_pin(new_pin),
            user_id,
        ))

    return True, "PIN został zmieniony."


def change_own_contact(user_id, current_pin, email, phone):
    email = email.strip().lower()
    phone = phone.strip()
    if not (current_pin.isascii() and current_pin.isdigit() and len(current_pin) == 4):
        return False, "Podaj obecny 4-cyfrowy PIN."
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return False, "Podaj poprawny adres e-mail."
    if not re.fullmatch(r"\+?[0-9 ()-]+", phone) or not 6 <= sum(c.isdigit() for c in phone) <= 15:
        return False, "Podaj poprawny numer telefonu (6–15 cyfr, opcjonalnie prefiks kraju)."
    try:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = conn.execute(
                "SELECT email, phone, pin_hash FROM users WHERE id = ? AND active = 1",
                (user_id,),
            ).fetchone()
            if not user:
                return False, "Nie znaleziono aktywnego konta."
            if user["pin_hash"] != hash_pin(current_pin):
                return False, "Obecny PIN jest nieprawidłowy."
            if conn.execute(
                "SELECT 1 FROM users WHERE lower(trim(email)) = ? AND id != ?",
                (email, user_id),
            ).fetchone():
                return False, "Ten adres e-mail jest już przypisany do innego konta."
            if user["email"] == email and user["phone"] == phone:
                return True, "Dane są już aktualne."
            conn.execute(
                "UPDATE users SET email = ?, phone = ? WHERE id = ?",
                (email, phone, user_id),
            )
        return True, "Dane zapisane. Przy kolejnym logowaniu użyj aktualnego adresu e-mail."
    except sqlite3.IntegrityError:
        return False, "Ten adres e-mail jest już przypisany do innego konta."


def admin_reset_pin(target_user_id, new_pin):
    if not (new_pin.isdigit() and len(new_pin) == 4):
        return False, "Nowy PIN musi składać się dokładnie z 4 cyfr."

    with connect() as conn:
        user = conn.execute("""
            SELECT id, first_name, last_name
            FROM users
            WHERE id = ?
              AND active = 1
        """, (target_user_id,)).fetchone()

        if not user:
            return False, "Nie znaleziono konta."

        conn.execute("""
            UPDATE users
            SET pin_hash = ?
            WHERE id = ?
        """, (
            hash_pin(new_pin),
            target_user_id,
        ))

        _create_notification(
            conn,
            target_user_id,
            "PIN został zresetowany",
            "Administrator ustawił nowy PIN do Twojego konta.",
            "pin_reset",
        )

    return True, "PIN został zresetowany."


def authenticate(email, pin):
    if not (pin.isdigit() and len(pin) == 4):
        return None

    with connect() as conn:
        return conn.execute("""
            SELECT *
            FROM users
            WHERE email = ?
              AND pin_hash = ?
              AND active = 1
        """, (email.strip().lower(), hash_pin(pin))).fetchone()


def get_user(user_id):
    with connect() as conn:
        return conn.execute("""
            SELECT * FROM users
            WHERE id = ? AND active = 1
        """, (user_id,)).fetchone()


def get_users():
    with connect() as conn:
        return conn.execute("""
            SELECT * FROM users
            WHERE active = 1
            ORDER BY last_name, first_name
        """).fetchall()


def get_user_groups(user_id):
    with connect() as conn:
        return conn.execute("""
            SELECT wg.code, wg.name
            FROM work_groups wg
            JOIN user_work_groups uwg ON uwg.group_id = wg.id
            WHERE uwg.user_id = ?
            ORDER BY wg.name
        """, (user_id,)).fetchall()



# ---------------- NOTIFICATIONS ----------------

def _create_notification(conn, user_id, title, message, notification_type="info"):
    conn.execute("""
        INSERT INTO notifications (
            user_id, notification_type, title, message, is_read
        )
        VALUES (?, ?, ?, ?, 0)
    """, (
        user_id,
        notification_type,
        title.strip(),
        message.strip(),
    ))


def create_notification(user_id, title, message, notification_type="info"):
    with connect() as conn:
        _create_notification(
            conn,
            user_id,
            title,
            message,
            notification_type,
        )


def get_notifications(user_id, limit=50):
    with connect() as conn:
        return conn.execute("""
            SELECT *
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, (user_id, int(limit))).fetchall()


def count_unread_notifications(user_id):
    with connect() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM notifications
            WHERE user_id = ?
              AND is_read = 0
        """, (user_id,)).fetchone()
        return int(row["cnt"] or 0)


def mark_notification_read(notification_id, user_id):
    with connect() as conn:
        conn.execute("""
            UPDATE notifications
            SET is_read = 1
            WHERE id = ?
              AND user_id = ?
        """, (notification_id, user_id))


def mark_all_notifications_read(user_id):
    with connect() as conn:
        conn.execute("""
            UPDATE notifications
            SET is_read = 1
            WHERE user_id = ?
        """, (user_id,))


def update_user_settings(user_id, access_level, rate, group_codes):
    if access_level not in ("admin", "employee"):
        return False, "Wybierz pozycję Szef lub Pracownik."
    try:
        hourly_rate = float(str(rate).replace(",", "."))
    except ValueError:
        return False, "Nieprawidłowa stawka."

    if hourly_rate < 0:
        return False, "Stawka nie może być ujemna."

    with connect() as conn:
        conn.execute("""
            UPDATE users
            SET access_level = ?, hourly_rate = ?
            WHERE id = ?
        """, (access_level, hourly_rate, user_id))

        conn.execute("DELETE FROM user_work_groups WHERE user_id = ?", (user_id,))

        for code in group_codes:
            group = conn.execute(
                "SELECT id FROM work_groups WHERE code = ?",
                (code,),
            ).fetchone()
            if group:
                conn.execute("""
                    INSERT INTO user_work_groups (user_id, group_id)
                    VALUES (?, ?)
                """, (user_id, group["id"]))

    return True, "Ustawienia zapisane."




# ---------------- AVAILABILITY ----------------

def set_availability(
    user_id,
    availability_date,
    availability_type,
    start_time=None,
    end_time=None,
    note="",
):
    allowed = {
        "available_all_day",
        "available_hours",
        "unavailable",
    }

    if availability_type not in allowed:
        return False, "Nieprawidłowy typ dostępności."

    start_value = None
    end_value = None

    if availability_type == "available_hours":
        if start_time is None or end_time is None:
            return False, "Podaj godziny dostępności."
        if end_time <= start_time:
            return False, "Koniec dostępności musi być później niż początek."
        start_value = start_time.strftime("%H:%M")
        end_value = end_time.strftime("%H:%M")

    with connect() as conn:
        conn.execute("""
            INSERT INTO availabilities (
                user_id,
                availability_date,
                availability_type,
                start_time,
                end_time,
                note,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, availability_date)
            DO UPDATE SET
                availability_type = excluded.availability_type,
                start_time = excluded.start_time,
                end_time = excluded.end_time,
                note = excluded.note,
                updated_at = excluded.updated_at
        """, (
            user_id,
            availability_date.isoformat(),
            availability_type,
            start_value,
            end_value,
            note.strip(),
            now_text(),
        ))

    return True, "Dostępność została zapisana."


def get_user_availability(user_id, date_from=None, date_to=None):
    sql = """
        SELECT *
        FROM availabilities
        WHERE user_id = ?
    """
    params = [user_id]

    if date_from is not None:
        sql += " AND availability_date >= ?"
        params.append(date_from.isoformat())

    if date_to is not None:
        sql += " AND availability_date <= ?"
        params.append(date_to.isoformat())

    sql += " ORDER BY availability_date"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def get_availability_for_users(user_ids, date_from=None, date_to=None):
    if not user_ids:
        return []

    placeholders = ",".join("?" for _ in user_ids)
    params = list(user_ids)

    sql = f"""
        SELECT
            a.*,
            u.first_name,
            u.last_name
        FROM availabilities a
        JOIN users u ON u.id = a.user_id
        WHERE a.user_id IN ({placeholders})
    """

    if date_from is not None:
        sql += " AND a.availability_date >= ?"
        params.append(date_from.isoformat())

    if date_to is not None:
        sql += " AND a.availability_date <= ?"
        params.append(date_to.isoformat())

    sql += " ORDER BY a.availability_date, u.last_name, u.first_name"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def delete_availability(availability_id, user_id):
    with connect() as conn:
        conn.execute("""
            DELETE FROM availabilities
            WHERE id = ?
              AND user_id = ?
        """, (availability_id, user_id))


def set_day_off(user_id, day_off_date, note=""):
    with connect() as conn:
        conn.execute("""
            INSERT INTO availabilities (
                user_id,
                availability_date,
                availability_type,
                start_time,
                end_time,
                note,
                updated_at
            )
            VALUES (?, ?, 'unavailable', NULL, NULL, ?, ?)
            ON CONFLICT(user_id, availability_date)
            DO UPDATE SET
                availability_type = 'unavailable',
                start_time = NULL,
                end_time = NULL,
                note = excluded.note,
                updated_at = excluded.updated_at
        """, (
            user_id,
            day_off_date.isoformat(),
            note.strip(),
            now_text(),
        ))

    return True, "Dzień wolny został zgłoszony."


def get_user_days_off(user_id, date_from=None, date_to=None):
    sql = """
        SELECT *
        FROM availabilities
        WHERE user_id = ?
          AND availability_type = 'unavailable'
    """
    params = [user_id]

    if date_from is not None:
        sql += " AND availability_date >= ?"
        params.append(date_from.isoformat())

    if date_to is not None:
        sql += " AND availability_date <= ?"
        params.append(date_to.isoformat())

    sql += " ORDER BY availability_date"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def get_days_off_for_users(user_ids, date_from=None, date_to=None):
    if not user_ids:
        return []

    placeholders = ",".join("?" for _ in user_ids)
    params = list(user_ids)

    sql = f"""
        SELECT
            a.*,
            u.first_name,
            u.last_name
        FROM availabilities a
        JOIN users u ON u.id = a.user_id
        WHERE a.user_id IN ({placeholders})
          AND a.availability_type = 'unavailable'
    """

    if date_from is not None:
        sql += " AND a.availability_date >= ?"
        params.append(date_from.isoformat())

    if date_to is not None:
        sql += " AND a.availability_date <= ?"
        params.append(date_to.isoformat())

    sql += " ORDER BY a.availability_date, u.last_name, u.first_name"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def is_day_off(user_id, work_date):
    date_value = (
        work_date.isoformat()
        if hasattr(work_date, "isoformat")
        else str(work_date)
    )

    with connect() as conn:
        row = conn.execute("""
            SELECT 1
            FROM availabilities
            WHERE user_id = ?
              AND availability_date = ?
              AND availability_type = 'unavailable'
            LIMIT 1
        """, (
            user_id,
            date_value,
        )).fetchone()

    return row is not None




# ---------------- SHIFT / POS ----------------

def get_active_shift(user_id):
    with connect() as conn:
        return conn.execute("""
            SELECT * FROM shifts
            WHERE user_id = ?
              AND approval_status = 'active'
              AND end_at IS NULL
            ORDER BY id DESC
            LIMIT 1
        """, (user_id,)).fetchone()


def _user_group_codes(user_id):
    return [row["code"] for row in get_user_groups(user_id)]


def start_shift(user_id, work_group):
    if get_active_shift(user_id):
        return False, "Masz już rozpoczętą zmianę."

    if work_group not in ("event", "local", "warehouse"):
        return False, "Wybierz prawidłowe stanowisko pracy."

    if work_group not in _user_group_codes(user_id):
        return False, "To stanowisko nie jest przypisane do Twojego konta."

    started = now_text()

    with connect() as conn:
        conn.execute("""
            INSERT INTO shifts (
                user_id,
                start_at,
                original_start_at,
                approval_status,
                work_group
            )
            VALUES (?, ?, ?, 'active', ?)
        """, (
            user_id,
            started,
            started,
            work_group,
        ))

    return True, "Zmiana rozpoczęta."


def temporary_round_hours(actual_minutes):
    hours = actual_minutes // 60
    remainder = actual_minutes % 60
    if remainder >= 30:
        hours += 1
    return hours


def recalc_shift_values(start_at, end_at, hourly_rate):
    start_dt = datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(end_at, "%Y-%m-%d %H:%M:%S")
    minutes = max(0, int((end_dt - start_dt).total_seconds() // 60))
    billable = temporary_round_hours(minutes)
    amount = round(billable * float(hourly_rate), 2)
    return minutes, billable, amount


def end_shift(user_id):
    active = get_active_shift(user_id)
    if not active:
        return False, "Nie masz rozpoczętej zmiany."

    ended = now_text()
    user = get_user(user_id)
    rate = float(user["hourly_rate"])
    minutes, billable, amount = recalc_shift_values(
        active["start_at"], ended, rate
    )

    with connect() as conn:
        conn.execute("""
            UPDATE shifts
            SET end_at = ?,
                original_end_at = ?,
                actual_minutes = ?,
                billable_hours = ?,
                hourly_rate = ?,
                amount = ?,
                approval_status = 'pending'
            WHERE id = ?
        """, (
            ended,
            ended,
            minutes,
            billable,
            rate,
            amount,
            active["id"],
        ))

    return True, "Zmiana zakończona i wysłana do zatwierdzenia."


def add_manual_shift(
    user_id,
    start_at,
    end_at,
    creator_id,
    work_group,
    note="",
    auto_approve=True,
):
    user = get_user(user_id)
    if not user:
        return False, "Nie znaleziono pracownika."

    if work_group not in ("event", "local", "warehouse"):
        return False, "Wybierz prawidłowe stanowisko."

    if work_group not in _user_group_codes(user_id):
        return False, "To stanowisko nie jest przypisane do tej osoby."

    if end_at <= start_at:
        return False, "Koniec zmiany musi być później niż początek."

    rate = float(user["hourly_rate"])
    minutes, billable, amount = recalc_shift_values(
        start_at, end_at, rate
    )

    status = "approved" if auto_approve else "pending"
    approved_by = creator_id if auto_approve else None
    approved_at = now_text() if auto_approve else None

    with connect() as conn:
        conn.execute("""
            INSERT INTO shifts (
                user_id,
                start_at,
                end_at,
                actual_minutes,
                billable_hours,
                hourly_rate,
                amount,
                approval_status,
                approved_by,
                approved_at,
                original_start_at,
                original_end_at,
                corrected_by,
                corrected_at,
                correction_note,
                work_group
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            start_at,
            end_at,
            minutes,
            billable,
            rate,
            amount,
            status,
            approved_by,
            approved_at,
            start_at,
            end_at,
            creator_id,
            now_text(),
            note.strip(),
            work_group,
        ))

        if not auto_approve:
            _create_notification(
                conn,
                user_id,
                "Godziny wpisane przez managera",
                f"Wpisano godziny {start_at[:10]} "
                f"{start_at[11:16]}–{end_at[11:16]}. "
                f"Oczekują na zatwierdzenie szefa.",
                "hours_entered",
            )

    return True, (
        "Ręczna zmiana została dodana i zatwierdzona."
        if auto_approve
        else "Godziny zostały wpisane i czekają na zatwierdzenie szefa."
    )


def get_user_shifts(user_id):
    with connect() as conn:
        return conn.execute("""
            SELECT s.*, p.status AS payment_status
            FROM shifts s
            LEFT JOIN payments p ON p.id = s.payment_id
            WHERE s.user_id = ?
            ORDER BY s.start_at DESC
        """, (user_id,)).fetchall()


def get_all_shifts():
    with connect() as conn:
        return conn.execute("""
            SELECT
                s.*,
                u.first_name,
                u.last_name,
                p.status AS payment_status
            FROM shifts s
            JOIN users u ON u.id = s.user_id
            LEFT JOIN payments p ON p.id = s.payment_id
            ORDER BY s.start_at DESC
        """).fetchall()


def get_pending_shifts():
    with connect() as conn:
        return conn.execute("""
            SELECT s.*, u.first_name, u.last_name
            FROM shifts s
            JOIN users u ON u.id = s.user_id
            WHERE s.approval_status = 'pending'
            ORDER BY s.start_at
        """).fetchall()


def get_shift(shift_id):
    with connect() as conn:
        return conn.execute("""
            SELECT s.*, u.first_name, u.last_name
            FROM shifts s
            JOIN users u ON u.id = s.user_id
            WHERE s.id = ?
        """, (shift_id,)).fetchone()


def correct_shift(shift_id, start_at, end_at, corrected_by, note=""):
    shift = get_shift(shift_id)
    if not shift:
        return False, "Nie znaleziono zmiany."
    if shift["approval_status"] not in ("pending", "rejected"):
        return False, "Można poprawiać tylko zmianę oczekującą lub odrzuconą."
    if not end_at > start_at:
        return False, "Koniec zmiany musi być później niż początek."

    rate = float(
        shift["hourly_rate"]
        or get_user(shift["user_id"])["hourly_rate"]
    )
    minutes, billable, amount = recalc_shift_values(
        start_at, end_at, rate
    )

    with connect() as conn:
        conn.execute("""
            UPDATE shifts
            SET start_at = ?,
                end_at = ?,
                actual_minutes = ?,
                billable_hours = ?,
                hourly_rate = ?,
                amount = ?,
                corrected_by = ?,
                corrected_at = ?,
                correction_note = ?,
                approval_status = 'pending'
            WHERE id = ?
        """, (
            start_at,
            end_at,
            minutes,
            billable,
            rate,
            amount,
            corrected_by,
            now_text(),
            note.strip(),
            shift_id,
        ))

    return True, "Godziny zostały poprawione."


def approve_shift(shift_id, approver_id):
    with connect() as conn:
        shift = conn.execute("""
            SELECT user_id, start_at
            FROM shifts
            WHERE id = ?
              AND approval_status = 'pending'
        """, (shift_id,)).fetchone()

        if not shift:
            return

        conn.execute("""
            UPDATE shifts
            SET approval_status = 'approved',
                approved_by = ?,
                approved_at = ?
            WHERE id = ?
              AND approval_status = 'pending'
        """, (
            approver_id,
            now_text(),
            shift_id,
        ))

        work_date = shift["start_at"][:10]
        _create_notification(
            conn,
            shift["user_id"],
            "Zmiana zatwierdzona",
            f"Twoja zmiana z {work_date} została zatwierdzona.",
            "shift_approved",
        )


def reject_shift(shift_id, approver_id, note=""):
    with connect() as conn:
        shift = conn.execute("""
            SELECT user_id, start_at
            FROM shifts
            WHERE id = ?
              AND approval_status = 'pending'
        """, (shift_id,)).fetchone()

        if not shift:
            return

        conn.execute("""
            UPDATE shifts
            SET approval_status = 'rejected',
                approved_by = ?,
                approved_at = ?,
                rejection_note = ?
            WHERE id = ?
              AND approval_status = 'pending'
        """, (
            approver_id,
            now_text(),
            note.strip(),
            shift_id,
        ))

        work_date = shift["start_at"][:10]
        extra = f" Powód: {note.strip()}" if note.strip() else ""
        _create_notification(
            conn,
            shift["user_id"],
            "Zmiana odrzucona",
            f"Twoja zmiana z {work_date} została odrzucona.{extra}",
            "shift_rejected",
        )


def delete_rejected_shift(shift_id, user_id):
    with connect() as conn:
        conn.execute("""
            DELETE FROM shifts
            WHERE id = ?
              AND user_id = ?
              AND approval_status = 'rejected'
              AND payment_id IS NULL
        """, (
            shift_id,
            user_id,
        ))


def get_schedule_for_user_date(user_id, work_date, work_group=None):
    sql = """
        SELECT * FROM schedules
        WHERE user_id = ?
          AND work_date = ?
    """
    params = [user_id, work_date]

    if work_group:
        sql += " AND work_group = ?"
        params.append(work_group)

    sql += " ORDER BY id"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


# ---------------- SCHEDULE ----------------

def get_day_schedule(work_date):
    date_value = (
        work_date.isoformat()
        if hasattr(work_date, "isoformat")
        else str(work_date)
    )

    with connect() as conn:
        return conn.execute("""
            SELECT
                s.*,
                u.first_name,
                u.last_name
            FROM schedules s
            JOIN users u ON u.id = s.user_id
            WHERE s.work_date = ?
              AND s.work_group IN ('warehouse', 'local')
              AND u.active = 1
            ORDER BY u.last_name, u.first_name
        """, (date_value,)).fetchall()


def set_day_schedule(work_date, assignments):
    """
    assignments: dict {user_id: 'warehouse'|'local'|None}
    """
    date_value = (
        work_date.isoformat()
        if hasattr(work_date, "isoformat")
        else str(work_date)
    )

    clean = {}
    blocked_names = []

    for raw_user_id, work_group in assignments.items():
        user_id = int(raw_user_id)

        if work_group not in (None, "warehouse", "local"):
            return False, "Nieprawidłowe miejsce pracy."

        if work_group is not None:
            if work_group not in _user_group_codes(user_id):
                user = get_user(user_id)
                name = (
                    f"{user['first_name']} {user['last_name']}"
                    if user else str(user_id)
                )
                return False, (
                    f"{name} nie jest przypisany/a do: "
                    f"{'Magazyn' if work_group == 'warehouse' else 'Lokal'}."
                )

            if is_day_off(user_id, date_value):
                user = get_user(user_id)
                if user:
                    blocked_names.append(
                        f"{user['first_name']} {user['last_name']}"
                    )

        clean[user_id] = work_group

    if blocked_names:
        return False, (
            "Nie można wpisać do grafiku osób, które zgłosiły wolne: "
            + ", ".join(blocked_names)
        )

    user_ids = list(clean.keys())
    if not user_ids:
        return True, "Brak zmian do zapisania."

    placeholders = ",".join("?" for _ in user_ids)

    with connect() as conn:
        old_rows = conn.execute(
            f"""
            SELECT user_id, work_group
            FROM schedules
            WHERE work_date = ?
              AND user_id IN ({placeholders})
              AND work_group IN ('warehouse', 'local')
            """,
            [date_value] + user_ids,
        ).fetchall()

        old_map = {
            int(row["user_id"]): row["work_group"]
            for row in old_rows
        }

        conn.execute(
            f"""
            DELETE FROM schedules
            WHERE work_date = ?
              AND user_id IN ({placeholders})
              AND work_group IN ('warehouse', 'local')
            """,
            [date_value] + user_ids,
        )

        for user_id, work_group in clean.items():
            if work_group is None:
                continue

            conn.execute("""
                INSERT INTO schedules (
                    user_id,
                    work_date,
                    start_time,
                    end_time,
                    note,
                    work_group
                )
                VALUES (?, ?, '', '', '', ?)
            """, (
                user_id,
                date_value,
                work_group,
            ))

        for user_id, new_group in clean.items():
            old_group = old_map.get(user_id)

            if old_group == new_group:
                continue

            old_label = (
                "Magazyn" if old_group == "warehouse"
                else "Lokal" if old_group == "local"
                else None
            )
            new_label = (
                "Magazyn" if new_group == "warehouse"
                else "Lokal" if new_group == "local"
                else None
            )

            if old_group is None and new_group is not None:
                _create_notification(
                    conn,
                    user_id,
                    "Nowy dzień w grafiku",
                    f"{date_value}: {new_label}.",
                    "schedule_added",
                )
            elif old_group is not None and new_group is None:
                _create_notification(
                    conn,
                    user_id,
                    "Zmiana w grafiku",
                    f"{date_value}: usunięto Cię z grafiku.",
                    "schedule_deleted",
                )
            elif old_group != new_group:
                _create_notification(
                    conn,
                    user_id,
                    "Grafik został zmieniony",
                    f"{date_value}: {old_label} → {new_label}.",
                    "schedule_updated",
                )

    return True, "Grafik na ten dzień został zapisany."


def add_schedule(
    user_id,
    work_date,
    start_time=None,
    end_time=None,
    work_group=None,
    note="",
):
    # Zachowane dla zgodności ze starszym kodem.
    if work_group not in ("local", "warehouse"):
        return False, "Grafik dotyczy Lokalu albo Magazynu."

    if work_group not in _user_group_codes(user_id):
        return False, "Ta osoba nie jest przypisana do wybranego obszaru."

    if is_day_off(user_id, work_date):
        return False, "Ta osoba zgłosiła wolne na ten dzień."

    date_value = work_date.isoformat()

    with connect() as conn:
        existing = conn.execute("""
            SELECT id
            FROM schedules
            WHERE user_id = ?
              AND work_date = ?
              AND work_group IN ('warehouse', 'local')
            LIMIT 1
        """, (
            user_id,
            date_value,
        )).fetchone()

        if existing:
            conn.execute("""
                UPDATE schedules
                SET work_group = ?,
                    start_time = '',
                    end_time = '',
                    note = ?
                WHERE id = ?
            """, (
                work_group,
                note.strip(),
                existing["id"],
            ))
        else:
            conn.execute("""
                INSERT INTO schedules (
                    user_id,
                    work_date,
                    start_time,
                    end_time,
                    note,
                    work_group
                )
                VALUES (?, ?, '', '', ?, ?)
            """, (
                user_id,
                date_value,
                note.strip(),
                work_group,
            ))

        label = "Magazyn" if work_group == "warehouse" else "Lokal"
        _create_notification(
            conn,
            user_id,
            "Nowy dzień w grafiku",
            f"{date_value}: {label}.",
            "schedule_added",
        )

    return True, "Dodano do grafiku."


def update_schedule(
    schedule_id,
    work_date,
    start_time=None,
    end_time=None,
    work_group=None,
    note="",
):
    if work_group not in ("local", "warehouse"):
        return False, "Grafik dotyczy Lokalu albo Magazynu."

    with connect() as conn:
        existing = conn.execute("""
            SELECT user_id
            FROM schedules
            WHERE id = ?
        """, (schedule_id,)).fetchone()

        if not existing:
            return False, "Nie znaleziono wpisu w grafiku."

        if work_group not in _user_group_codes(existing["user_id"]):
            return False, "Ta osoba nie jest przypisana do wybranego obszaru."

        if is_day_off(existing["user_id"], work_date):
            return False, "Ta osoba zgłosiła wolne na ten dzień."

        conn.execute("""
            UPDATE schedules
            SET work_date = ?,
                start_time = '',
                end_time = '',
                note = ?,
                work_group = ?
            WHERE id = ?
        """, (
            work_date.isoformat(),
            note.strip(),
            work_group,
            schedule_id,
        ))

    return True, "Grafik został zaktualizowany."


def get_user_schedule(user_id, work_group=None):
    sql = """
        SELECT * FROM schedules
        WHERE user_id = ?
    """
    params = [user_id]

    if work_group:
        sql += " AND work_group = ?"
        params.append(work_group)

    sql += " ORDER BY work_date, id"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def get_schedules_for_users(
    user_ids,
    date_from=None,
    date_to=None,
    work_group=None,
):
    if not user_ids:
        return []

    placeholders = ",".join("?" for _ in user_ids)
    params = list(user_ids)

    sql = f"""
        SELECT s.*, u.first_name, u.last_name
        FROM schedules s
        JOIN users u ON u.id = s.user_id
        WHERE s.user_id IN ({placeholders})
    """

    if date_from is not None:
        sql += " AND s.work_date >= ?"
        params.append(date_from.isoformat())

    if date_to is not None:
        sql += " AND s.work_date <= ?"
        params.append(date_to.isoformat())

    if work_group:
        sql += " AND s.work_group = ?"
        params.append(work_group)

    sql += " ORDER BY s.work_date, u.last_name, u.first_name"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def get_group_schedules(work_group, date_from=None, date_to=None):
    if work_group not in ("local", "warehouse"):
        return []

    params = [work_group]
    sql = """
        SELECT s.*, u.first_name, u.last_name
        FROM schedules s
        JOIN users u ON u.id = s.user_id
        WHERE s.work_group = ?
          AND u.active = 1
    """

    if date_from is not None:
        sql += " AND s.work_date >= ?"
        params.append(date_from.isoformat())

    if date_to is not None:
        sql += " AND s.work_date <= ?"
        params.append(date_to.isoformat())

    sql += " ORDER BY s.work_date, u.last_name, u.first_name"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def copy_schedule_week(
    user_ids,
    source_week_start,
    target_week_start,
    work_group=None,
):
    if not user_ids:
        return False, "Wybierz przynajmniej jednego pracownika."

    source_end = source_week_start + timedelta(days=6)
    day_delta = (target_week_start - source_week_start).days

    rows = get_schedules_for_users(
        user_ids,
        source_week_start,
        source_end,
        work_group,
    )

    copied = 0

    with connect() as conn:
        for row in rows:
            old_date = datetime.strptime(
                row["work_date"],
                "%Y-%m-%d",
            ).date()
            new_date = old_date + timedelta(days=day_delta)

            if is_day_off(row["user_id"], new_date):
                continue

            duplicate = conn.execute("""
                SELECT 1
                FROM schedules
                WHERE user_id = ?
                  AND work_date = ?
                  AND work_group IN ('warehouse', 'local')
                LIMIT 1
            """, (
                row["user_id"],
                new_date.isoformat(),
            )).fetchone()

            if duplicate:
                continue

            conn.execute("""
                INSERT INTO schedules (
                    user_id,
                    work_date,
                    start_time,
                    end_time,
                    note,
                    work_group
                )
                VALUES (?, ?, '', '', '', ?)
            """, (
                row["user_id"],
                new_date.isoformat(),
                row["work_group"],
            ))
            copied += 1

    return True, f"Skopiowano {copied} dni pracy."


def get_all_schedules():
    with connect() as conn:
        return conn.execute("""
            SELECT s.*, u.first_name, u.last_name
            FROM schedules s
            JOIN users u ON u.id = s.user_id
            ORDER BY s.work_date, u.last_name, u.first_name
        """).fetchall()


def get_schedule(schedule_id):
    with connect() as conn:
        return conn.execute("""
            SELECT s.*, u.first_name, u.last_name
            FROM schedules s
            JOIN users u ON u.id = s.user_id
            WHERE s.id = ?
        """, (schedule_id,)).fetchone()


def delete_schedule(schedule_id):
    with connect() as conn:
        existing = conn.execute("""
            SELECT
                user_id,
                work_date,
                work_group
            FROM schedules
            WHERE id = ?
        """, (schedule_id,)).fetchone()

        conn.execute(
            "DELETE FROM schedules WHERE id = ?",
            (schedule_id,),
        )

        if existing:
            _create_notification(
                conn,
                existing["user_id"],
                "Zmiana w grafiku",
                f"{existing['work_date']}: usunięto Cię z grafiku.",
                "schedule_deleted",
            )


# ---------------- EVENTS ----------------

def create_event(name, event_date, start_time, end_time, location, note, user_ids, manager_id=None):
    if not name.strip():
        return False, "Podaj nazwę eventu."

    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO events
            (name, event_date, start_time, end_time, location, note, manager_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name.strip(),
            event_date.isoformat(),
            start_time.strftime("%H:%M"),
            end_time.strftime("%H:%M"),
            location.strip(),
            note.strip(),
            manager_id,
        ))
        event_id = cur.lastrowid

        for user_id in user_ids:
            conn.execute("""
                INSERT OR IGNORE INTO event_assignments (event_id, user_id)
                VALUES (?, ?)
            """, (event_id, user_id))

            _create_notification(
                conn,
                user_id,
                "Nowy event",
                f"Przypisano Cię do eventu „{name.strip()}” "
                f"{event_date.isoformat()} "
                f"{start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')}.",
                "event_assigned",
            )

    return True, "Event został utworzony."


def get_user_events(user_id):
    with connect() as conn:
        return conn.execute("""
            SELECT
                e.*,
                m.first_name AS manager_first_name,
                m.last_name AS manager_last_name
            FROM events e
            JOIN event_assignments ea ON ea.event_id = e.id
            LEFT JOIN users m ON m.id = e.manager_id
            WHERE ea.user_id = ?
            ORDER BY e.event_date, e.start_time
        """, (user_id,)).fetchall()


def get_worker_event_details(user_id, event_id):
    """Only a worker assigned to the event may retrieve its details."""
    with connect() as conn:
        return conn.execute("""
            SELECT
                e.*,
                m.first_name AS manager_first_name,
                m.last_name AS manager_last_name,
                (
                    SELECT GROUP_CONCAT(u.first_name || ' ' || u.last_name, ', ')
                    FROM event_assignments crew
                    JOIN users u ON u.id = crew.user_id
                    WHERE crew.event_id = e.id
                ) AS crew_names
            FROM events e
            JOIN event_assignments ea ON ea.event_id = e.id
            LEFT JOIN users m ON m.id = e.manager_id
            WHERE ea.user_id = ?
              AND e.id = ?
            LIMIT 1
        """, (user_id, event_id)).fetchone()


def get_all_events():
    with connect() as conn:
        return conn.execute("""
            SELECT
                e.*,
                GROUP_CONCAT(u.first_name || ' ' || u.last_name, ', ') AS people,
                m.first_name AS manager_first_name,
                m.last_name AS manager_last_name
            FROM events e
            LEFT JOIN event_assignments ea ON ea.event_id = e.id
            LEFT JOIN users u ON u.id = ea.user_id
            LEFT JOIN users m ON m.id = e.manager_id
            GROUP BY e.id
            ORDER BY e.event_date, e.start_time
        """).fetchall()


# ---------------- PAYMENTS ----------------

def get_unpaid_approved_shifts(user_id, date_from, date_to):
    with connect() as conn:
        return conn.execute("""
            SELECT *
            FROM shifts
            WHERE user_id = ?
              AND approval_status = 'approved'
              AND payment_id IS NULL
              AND date(start_at) BETWEEN ? AND ?
            ORDER BY start_at
        """, (user_id, date_from.isoformat(), date_to.isoformat())).fetchall()


def create_payment(user_id, date_from, date_to):
    shifts = get_unpaid_approved_shifts(user_id, date_from, date_to)

    if not shifts:
        return False, "Brak zatwierdzonych, nierozliczonych zmian w tym okresie."

    total = round(sum(float(s["amount"] or 0) for s in shifts), 2)

    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO payments
            (user_id, period_from, period_to, amount, status)
            VALUES (?, ?, ?, ?, 'created')
        """, (
            user_id,
            date_from.isoformat(),
            date_to.isoformat(),
            total,
        ))
        payment_id = cur.lastrowid

        ids = [s["id"] for s in shifts]
        placeholders = ",".join("?" for _ in ids)
        conn.execute(
            f"UPDATE shifts SET payment_id = ? WHERE id IN ({placeholders})",
            [payment_id] + ids,
        )

    return True, total


def get_user_payments(user_id):
    with connect() as conn:
        return conn.execute("""
            SELECT * FROM payments
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
        """, (user_id,)).fetchall()


def get_all_payments(status=None):
    sql = """
        SELECT p.*, u.first_name, u.last_name
        FROM payments p
        JOIN users u ON u.id = p.user_id
    """
    params = []

    if status and status != "all":
        sql += " WHERE p.status = ?"
        params.append(status)

    sql += " ORDER BY p.created_at DESC, p.id DESC"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def mark_payment_sent(payment_id):
    with connect() as conn:
        payment = conn.execute("""
            SELECT user_id, amount, period_from, period_to
            FROM payments
            WHERE id = ?
              AND status = 'created'
        """, (payment_id,)).fetchone()

        if not payment:
            return

        conn.execute("""
            UPDATE payments
            SET status = 'sent',
                sent_at = ?
            WHERE id = ?
              AND status = 'created'
        """, (now_text(), payment_id))

        _create_notification(
            conn,
            payment["user_id"],
            "Przelew wysłany",
            f"Wysłano wypłatę {payment['amount']:.2f} zł "
            f"za okres {payment['period_from']}–{payment['period_to']}.",
            "payment_sent",
        )


def confirm_payment_received(payment_id, user_id):
    with connect() as conn:
        conn.execute("""
            UPDATE payments
            SET status = 'received',
                received_at = ?
            WHERE id = ?
              AND user_id = ?
              AND status = 'sent'
        """, (now_text(), payment_id, user_id))




# ---------------- REPORTS ----------------

def get_report_rows(date_from, date_to, user_ids=None):
    params = [
        date_from.isoformat(),
        date_to.isoformat(),
    ]

    sql = """
        SELECT
            s.id,
            s.user_id,
            u.first_name,
            u.last_name,
            date(s.start_at) AS work_date,
            s.start_at,
            s.end_at,
            s.actual_minutes,
            s.billable_hours,
            s.hourly_rate,
            s.amount,
            s.work_group,
            s.payment_id,
            p.status AS payment_status
        FROM shifts s
        JOIN users u ON u.id = s.user_id
        LEFT JOIN payments p ON p.id = s.payment_id
        WHERE s.approval_status = 'approved'
          AND date(s.start_at) BETWEEN ? AND ?
    """

    if user_ids:
        placeholders = ",".join("?" for _ in user_ids)
        sql += f" AND s.user_id IN ({placeholders})"
        params.extend(user_ids)

    sql += " ORDER BY s.start_at, u.last_name, u.first_name"

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


# ---------------- DASHBOARD / PROFILE ----------------

def get_today_active_shifts():
    with connect() as conn:
        return conn.execute("""
            SELECT s.*, u.first_name, u.last_name
            FROM shifts s
            JOIN users u ON u.id = s.user_id
            WHERE s.approval_status = 'active'
              AND s.end_at IS NULL
            ORDER BY s.start_at
        """).fetchall()


def get_today_schedule():
    today = date.today().isoformat()
    with connect() as conn:
        return conn.execute("""
            SELECT s.*, u.first_name, u.last_name
            FROM schedules s
            JOIN users u ON u.id = s.user_id
            WHERE s.work_date = ?
            ORDER BY s.start_time, u.last_name, u.first_name
        """, (today,)).fetchall()


def get_upcoming_events(limit=5):
    today = date.today().isoformat()
    with connect() as conn:
        return conn.execute("""
            SELECT
                e.*,
                m.first_name AS manager_first_name,
                m.last_name AS manager_last_name
            FROM events e
            LEFT JOIN users m ON m.id = e.manager_id
            WHERE e.event_date >= ?
            ORDER BY e.event_date, e.start_time
            LIMIT ?
        """, (today, int(limit))).fetchall()


def get_user_summary(user_id):
    shifts = get_user_shifts(user_id)
    payments = get_user_payments(user_id)

    return {
        "all_shifts": len([s for s in shifts if s["approval_status"] != "active"]),
        "approved_hours": sum(
            int(s["billable_hours"] or 0)
            for s in shifts
            if s["approval_status"] == "approved"
        ),
        "pending": sum(1 for s in shifts if s["approval_status"] == "pending"),
        "paid_total": sum(
            float(p["amount"] or 0)
            for p in payments
            if p["status"] == "received"
        ),
    }


def get_admin_event(actor_id, event_id):
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id=? AND active=1 AND access_level='admin'", (actor_id,)).fetchone():
            return None, []
        event = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        crew = conn.execute("SELECT u.* FROM users u JOIN event_assignments ea ON ea.user_id=u.id WHERE ea.event_id=? ORDER BY u.last_name,u.first_name,u.id", (event_id,)).fetchall()
        return event, crew


def save_event_details(actor_id, event_id, name, event_date, start_time, end_time, location, note, user_ids, manager_id=None, files=()):
    if not name.strip():
        return False, "Podaj nazwę eventu."
    if len(files) > 20:
        return False, "Dodaj maksymalnie 20 plików naraz."
    prepared = []
    for filename, content in files:
        clean_name = Path(filename.replace("\\", "/")).name
        clean_name = re.sub(r"[\x00-\x1f\x7f]", "", clean_name)
        if not clean_name or clean_name in (".", "..") or not content:
            return False, "Załącznik musi mieć nazwę i nie może być pusty."
        if len(content) > 10 * 1024 * 1024:
            return False, "Pojedynczy załącznik może mieć maksymalnie 10 MB."
        prepared.append((clean_name, content, hashlib.sha256(content).hexdigest()))
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM users WHERE id=? AND active=1 AND access_level='admin'", (actor_id,)).fetchone():
            return False, "Tylko szef może edytować eventy."
        old = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone() if event_id is not None else None
        if event_id is not None and old is None:
            return False, "Nie znaleziono eventu."
        user_ids = sorted(set(user_ids))
        for person_id in user_ids + ([manager_id] if manager_id is not None else []):
            if not conn.execute("SELECT 1 FROM users WHERE id=?", (person_id,)).fetchone():
                return False, "Nie znaleziono wybranej osoby."
        values = (name.strip(), event_date.isoformat(), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"), location.strip(), note.strip(), manager_id)
        if old is None:
            cursor = conn.execute("INSERT INTO events(name,event_date,start_time,end_time,location,note,manager_id) VALUES(?,?,?,?,?,?,?)", values)
            event_id = cursor.lastrowid
        else:
            conn.execute("UPDATE events SET name=?,event_date=?,start_time=?,end_time=?,location=?,note=?,manager_id=? WHERE id=?", values + (event_id,))
        old_ids = {r[0] for r in conn.execute("SELECT user_id FROM event_assignments WHERE event_id=?", (event_id,))}
        conn.execute("DELETE FROM event_assignments WHERE event_id=?", (event_id,))
        conn.executemany("INSERT INTO event_assignments(event_id,user_id) VALUES(?,?)", [(event_id, uid) for uid in user_ids])
        for filename, content, digest in prepared:
            conn.execute("INSERT OR IGNORE INTO event_attachments(event_id,name,content,sha256,uploaded_by) VALUES(?,?,?,?,?)", (event_id, filename, content, digest, actor_id))
        changed = old is None or values != tuple(old[k] for k in ("name","event_date","start_time","end_time","location","note","manager_id")) or old_ids != set(user_ids) or bool(prepared)
        if changed:
            for uid in set(user_ids) | old_ids:
                message = f"Zaktualizowano event „{name.strip()}” ({event_date.isoformat()})." if uid in user_ids else f"Usunięto Twoje przypisanie do eventu „{name.strip()}”."
                _create_notification(conn, uid, "Nowy event" if old is None else "Zmiana eventu", message, "event_updated")
    return True, "Event i załączniki zostały zapisane."


def _can_read_event(conn, viewer_id, event_id):
    return conn.execute("""SELECT 1 FROM users u WHERE u.id=? AND u.active=1
        AND (u.access_level='admin' OR EXISTS(SELECT 1 FROM event_assignments ea WHERE ea.user_id=u.id AND ea.event_id=?))""", (viewer_id, event_id)).fetchone() is not None


def get_event_attachments(viewer_id, event_id):
    with connect() as conn:
        if not _can_read_event(conn, viewer_id, event_id):
            return []
        return conn.execute("SELECT id,name,length(content) AS size,created_at FROM event_attachments WHERE event_id=? ORDER BY id", (event_id,)).fetchall()


def get_event_attachment(viewer_id, attachment_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM event_attachments WHERE id=?", (attachment_id,)).fetchone()
        if row is None or not _can_read_event(conn, viewer_id, row["event_id"]):
            return None
        return row
