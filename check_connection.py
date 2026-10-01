"""Read-only checks against the configured Supabase database; no employee data printed."""
from datetime import date, timedelta
import db
from postgres_backend import connect


def main():
    try:
        with connect() as conn:
            conn.execute('SELECT 1').fetchone()
        db.get_users()
        db.get_all_events()
        db.get_all_schedules()
        db.get_all_shifts()
        db.get_all_payments()
        db.get_today_active_shifts()
        db.get_today_schedule()
        db.get_upcoming_events()
        db.get_report_rows(date.today() - timedelta(days=31), date.today())
    except Exception as exc:
        print('Sprawdzenie nie powiodło się. Typ błędu:', type(exc).__name__)
        print('Sprawdź sekrety, import danych i aktywność projektu Supabase.')
        raise SystemExit(1)
    print('OK: połączenie, pracownicy, eventy, grafiki, zmiany, wypłaty i raporty.')
    print('Dane nie były zmieniane. Przed udostępnieniem wykonaj testy w aplikacji według README.')


if __name__ == '__main__':
    main()
