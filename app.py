from datetime import date, time, datetime, timedelta
import calendar
import csv
import io
from uuid import uuid4
import streamlit as st

from db import (
    init_db, add_user, authenticate, get_user, get_users,
    change_own_pin, change_own_contact, admin_reset_pin,
    get_all_user_groups, update_user_settings,
    set_availability, get_user_availability, get_availability_for_users, delete_availability,
    set_day_off, get_user_days_off, get_days_off_for_users, is_day_off,
    get_notifications, count_unread_notifications, mark_notification_read, mark_all_notifications_read,
    get_active_shift, start_shift, end_shift, add_manual_shift,
    get_user_shifts, get_all_shifts, get_pending_shifts, get_shift,
    correct_shift, approve_shift, reject_shift, delete_rejected_shift,
    get_schedule_for_user_date, get_day_schedule, set_day_schedule,
    add_schedule, update_schedule, get_user_schedule,
    get_schedules_for_users, get_group_schedules, get_all_schedules, get_schedule, delete_schedule,
    copy_schedule_week,
    create_event, get_user_events, get_worker_event_details, get_all_events,
    get_admin_event, save_event_details, get_event_attachments, get_event_attachment,
    get_unpaid_approved_shifts, create_payment,
    get_user_payments, get_all_payments,
    mark_payment_sent, confirm_payment_received,
    get_today_active_shifts, get_today_schedule,
    get_upcoming_events, get_user_summary, get_report_rows,
)
from ui import (
    apply_styles, login_keyboard, header, money, minutes_to_text,
    status_label, status_icon,
    render_week_calendar, render_month_calendar, render_roster_calendar,
)

st.set_page_config(
    page_title="FlomaroHUB",
    page_icon="🟣",
    layout="wide",
)

apply_styles()
header()

from cloud_gate import require_access
from cloud_config import setting
require_access()
if setting("DATA_READY", False) is not True:
    st.info("Trwa przygotowanie danych aplikacji. Właściciel musi dokończyć konfigurację.")
    st.stop()

@st.cache_resource
def initialize_database():
    init_db()
    return True

try:
    initialize_database()
except Exception:
    st.error("Nie można połączyć się z bazą. Sprawdź konfigurację i stan projektu Supabase.")
    st.stop()



# This snapshot belongs to this script run only: the next interaction reads anew.
_render_groups = None


def get_render_user_groups(user_id):
    global _render_groups
    if _render_groups is None:
        _render_groups = get_all_user_groups()
    return _render_groups.get(user_id, [])


def logout():
    st.session_state.clear()
    st.rerun()



WORK_GROUP_LABELS = {
    "event": "Eventy",
    "warehouse": "Magazyn",
    "local": "Lokal",
    None: "—",
}


def work_group_label(code):
    return WORK_GROUP_LABELS.get(code, code or "—")


def event_month_calendar(user_id, key_prefix):
    """Whole month, Monday-first; only assigned events are shown."""
    key = f"{key_prefix}_event_month"
    if key not in st.session_state:
        st.session_state[key] = date.today().replace(day=1).isoformat()

    month = date.fromisoformat(st.session_state[key]).replace(day=1)
    previous_month = (month - timedelta(days=1)).replace(day=1)
    next_month = (
        date(month.year + 1, 1, 1) if month.month == 12
        else date(month.year, month.month + 1, 1)
    )

    left, middle, right = st.columns([1, 3, 1], gap="small")
    with left:
        if st.button(
            "← Poprzedni", key=f"{key_prefix}_event_prev",
            use_container_width=True,
        ):
            st.session_state[key] = previous_month.isoformat()
            st.rerun()
    with middle:
        month_names = [
            "", "Styczeń", "Luty", "Marzec", "Kwiecień",
            "Maj", "Czerwiec", "Lipiec", "Sierpień",
            "Wrzesień", "Październik", "Listopad", "Grudzień",
        ]
        st.markdown(
            f'<div class="employee-event-month-title">'
            f'{month_names[month.month]} {month.year}</div>',
            unsafe_allow_html=True,
        )
    with right:
        if st.button(
            "Następny →", key=f"{key_prefix}_event_next",
            use_container_width=True,
        ):
            st.session_state[key] = next_month.isoformat()
            st.rerun()

    by_day = {}
    for row in get_user_events(user_id):
        if row["event_date"][:7] == month.strftime("%Y-%m"):
            by_day.setdefault(int(row["event_date"][8:10]), []).append(row)

    with st.container(key="event_calendar_grid"):
        weekday_names = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]
        for col, name in zip(st.columns(7, gap="small"), weekday_names):
            with col:
                st.markdown(
                    f'<div class="employee-event-weekday">{name}</div>',
                    unsafe_allow_html=True,
                )

        for week_number, week in enumerate(calendar.monthcalendar(month.year, month.month)):
            cols = st.columns(7, gap="small")
            for weekday, (col, day) in enumerate(zip(cols, week)):
                with col:
                    if day == 0:
                        st.markdown(
                            '<div class="employee-event-empty"></div>',
                            unsafe_allow_html=True,
                        )
                        continue
                    # Fixed height: extra event buttons scroll inside this day,
                    # rather than making the calendar row grow.
                    with st.container(height=180, border=True):
                        st.markdown(
                            f'<div class="employee-event-date">{day}</div>',
                            unsafe_allow_html=True,
                        )
                        today_events = by_day.get(day, [])
                        for event in today_events:
                            if st.button(
                                f"{event['name']}\n{event['start_time']}–{event['end_time']}",
                                key=f"{key_prefix}_event_{event['id']}",
                                use_container_width=True,
                                help="Otwórz szczegóły eventu",
                            ):
                                st.session_state["employee_event_detail_id"] = event["id"]
                                st.rerun()
                        if not today_events:
                            st.caption("—")


def regular_month_calendar(user_id, team_ids=None, work_group=None):
    """Warehouse/local team or personal schedule in the event month layout."""
    key_prefix = "warehouse"
    key = f"{key_prefix}_event_month"
    if key not in st.session_state:
        st.session_state[key] = date.today().replace(day=1).isoformat()

    month = date.fromisoformat(st.session_state[key]).replace(day=1)
    previous_month = (month - timedelta(days=1)).replace(day=1)
    next_month = (
        date(month.year + 1, 1, 1) if month.month == 12
        else date(month.year, month.month + 1, 1)
    )

    left, middle, right = st.columns([1, 3, 1], gap="small")
    with left:
        if st.button(
            "← Poprzedni", key=f"{key_prefix}_event_prev",
            use_container_width=True,
        ):
            st.session_state[key] = previous_month.isoformat()
            st.rerun()
    with middle:
        month_names = [
            "", "Styczeń", "Luty", "Marzec", "Kwiecień",
            "Maj", "Czerwiec", "Lipiec", "Sierpień",
            "Wrzesień", "Październik", "Listopad", "Grudzień",
        ]
        st.markdown(
            f'<div class="employee-event-month-title">'
            f'{month_names[month.month]} {month.year}</div>',
            unsafe_allow_html=True,
        )
    with right:
        if st.button(
            "Następny →", key=f"{key_prefix}_event_next",
            use_container_width=True,
        ):
            st.session_state[key] = next_month.isoformat()
            st.rerun()

    month_start, month_end = month_range(month)
    by_day = {}
    for row in get_schedules_for_users(
        [user_id] if team_ids is None else team_ids,
        month_start, month_end, work_group=work_group,
    ):
        if row["work_group"] not in ("warehouse", "local"):
            continue
        by_day.setdefault(int(row["work_date"][8:10]), []).append(row)
    days_off = {} if team_ids is not None else {
        int(row["availability_date"][8:10]): row
        for row in get_user_days_off(user_id, month_start, month_end)
    }

    with st.container(key="regular_calendar_grid"):
        weekday_names = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]
        for col, name in zip(st.columns(7, gap="small"), weekday_names):
            with col:
                st.markdown(
                    f'<div class="employee-event-weekday">{name}</div>',
                    unsafe_allow_html=True,
                )

        for week_number, week in enumerate(calendar.monthcalendar(month.year, month.month)):
            cols = st.columns(7, gap="small")
            for weekday, (col, day) in enumerate(zip(cols, week)):
                with col:
                    if day == 0:
                        st.markdown(
                            '<div class="employee-event-empty"></div>',
                            unsafe_allow_html=True,
                        )
                        continue
                    # Fixed height: extra event buttons scroll inside this day,
                    # rather than making the calendar row grow.
                    with st.container(height=180, border=True):
                        st.markdown(
                            f'<div class="employee-event-date">{day}</div>',
                            unsafe_allow_html=True,
                        )
                        day_off = days_off.get(day)
                        if day_off is not None:
                            st.markdown("**Dzień wolny**")
                            if day_off["note"]:
                                st.text(day_off["note"])
                        shifts = by_day.get(day, [])
                        for shift in shifts:
                            st.text(f"{shift['first_name']} {shift['last_name']}")
                            st.caption(work_group_label(shift["work_group"]))
                            if shift["start_time"] or shift["end_time"]:
                                st.write(
                                    f"{shift['start_time'] or '—'}–"
                                    f"{shift['end_time'] or '—'}"
                                )
                            if shift["note"]:
                                st.text(shift["note"])
                        if not shifts and day_off is None:
                            st.caption("—")



def employee_event_details(user):
    """A separate internal view; no URL navigation or lost Streamlit session."""
    event_id = st.session_state.get("employee_event_detail_id")
    event = get_worker_event_details(user["id"], event_id)
    if not event:
        st.session_state.pop("employee_event_detail_id", None)
        st.warning("Ten event nie jest przypisany do Twojego konta.")
        if st.button("← Kalendarz eventów", key="employee_event_back_missing"):
            st.rerun()
        return

    if st.button("← Kalendarz eventów", key="employee_event_back"):
        st.session_state.pop("employee_event_detail_id", None)
        st.rerun()

    st.markdown(f"## {event['name']}")
    st.markdown(f"**Data:** {event['event_date']}")
    st.markdown(f"**Godziny:** {event['start_time']}–{event['end_time']}")
    st.markdown(f"**Miejsce:** {event['location'] or 'Nie podano'}")
    if event["manager_first_name"]:
        st.markdown(
            f"**Osoba odpowiedzialna:** {event['manager_first_name']} "
            f"{event['manager_last_name']}"
        )
    if event["crew_names"]:
        st.markdown(f"**Obsada:** {event['crew_names']}")
    st.markdown("### Informacje o evencie")
    st.write(event["note"] or "Brak dodatkowych informacji.")
    st.markdown("### Załączniki")
    event_attachment_downloads(user["id"], event["id"])


def month_range(anchor):
    month_start = anchor.replace(day=1)

    if anchor.month == 12:
        next_month = anchor.replace(
            year=anchor.year + 1,
            month=1,
            day=1,
        )
    else:
        next_month = anchor.replace(
            month=anchor.month + 1,
            day=1,
        )

    return month_start, next_month - timedelta(days=1)


def regular_schedule_users(users):
    result = []

    for person in users:
        if person["access_level"] == "admin":
            continue

        codes = [
            g["code"]
            for g in get_render_user_groups(person["id"])
        ]

        if "warehouse" in codes or "local" in codes:
            result.append(person)

    return result



def employee_schedule_calendar(user, groups):
    if not any(code in groups for code in ("warehouse", "local")):
        return

    view_mode = st.radio(
        "Widok",
        ["Grafik zespołu", "Tylko mój grafik"],
        horizontal=True,
        key="employee_regular_schedule_scope",
    )
    selected_group = st.radio(
        "Miejsce pracy",
        ["all", "warehouse", "local"],
        format_func=lambda code: "Magazyn i Lokal" if code == "all" else work_group_label(code),
        horizontal=True,
        key="employee_regular_schedule_place",
    )
    team_ids = None
    if view_mode == "Grafik zespołu":
        team_ids = [
            person["id"] for person in get_users()
            if person["access_level"] != "admin"
            and any(
                group["code"] in ("warehouse", "local")
                for group in get_render_user_groups(person["id"])
            )
        ]
    regular_month_calendar(
        user["id"], team_ids=team_ids,
        work_group=None if selected_group == "all" else selected_group,
    )


def shift_summary(row):
    start = datetime.strptime(row["start_at"], "%Y-%m-%d %H:%M:%S")
    end = (
        datetime.strptime(row["end_at"], "%Y-%m-%d %H:%M:%S")
        if row["end_at"] else None
    )
    return {
        "Data": start.strftime("%Y-%m-%d"),
        "Start": start.strftime("%H:%M"),
        "Koniec": end.strftime("%H:%M") if end else "—",
        "Rzeczywisty czas": minutes_to_text(row["actual_minutes"]),
        "Rozliczenie": (
            f"{row['billable_hours']} h"
            if row["billable_hours"] is not None else "—"
        ),
        "Stanowisko": work_group_label(row["work_group"]),
        "Kwota": money(row["amount"]),
        "Status": status_label(row["approval_status"]),
    }


def scheduled_vs_actual(shift):
    work_date = datetime.strptime(
        shift["start_at"],
        "%Y-%m-%d %H:%M:%S",
    ).date().isoformat()

    planned = get_schedule_for_user_date(
        shift["user_id"],
        work_date,
        shift["work_group"],
    )

    if planned:
        return "Pracownik był wpisany do grafiku na ten dzień."

    return "Brak wpisu w grafiku na ten dzień."



def correction_form(shift, approver_id, key_prefix):
    current_start = datetime.strptime(
        shift["start_at"], "%Y-%m-%d %H:%M:%S"
    )
    current_end = datetime.strptime(
        shift["end_at"], "%Y-%m-%d %H:%M:%S"
    )

    with st.expander("Popraw godziny przed zatwierdzeniem"):
        c1, c2 = st.columns(2)

        with c1:
            corr_date = st.date_input(
                "Data rozpoczęcia",
                value=current_start.date(),
                key=f"{key_prefix}_date_{shift['id']}",
            )
            corr_start = st.time_input(
                "Start",
                value=current_start.time().replace(second=0),
                step=300,
                key=f"{key_prefix}_start_{shift['id']}",
            )

        with c2:
            corr_end_date = st.date_input(
                "Data zakończenia",
                value=current_end.date(),
                key=f"{key_prefix}_end_date_{shift['id']}",
            )
            corr_end = st.time_input(
                "Koniec",
                value=current_end.time().replace(second=0),
                step=300,
                key=f"{key_prefix}_end_{shift['id']}",
            )

        note = st.text_input(
            "Powód / uwaga do korekty",
            key=f"{key_prefix}_note_{shift['id']}",
        )

        if st.button(
            "Zapisz korektę",
            key=f"{key_prefix}_save_{shift['id']}",
            use_container_width=True,
        ):
            start_dt = datetime.combine(
                corr_date, corr_start
            ).strftime("%Y-%m-%d %H:%M:%S")
            end_dt = datetime.combine(
                corr_end_date, corr_end
            ).strftime("%Y-%m-%d %H:%M:%S")

            ok, msg = correct_shift(
                shift["id"],
                start_dt,
                end_dt,
                approver_id,
                note,
            )

            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


def login_screen():
    with st.container(key="login_panel"):
        st.subheader("Zaloguj się")

        # Enter in email moves to PIN; Enter in PIN submits the form.
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "E-mail",
                key="login_email",
            )
            pin = st.text_input(
                "PIN",
                type="password",
                max_chars=4,
                key="login_pin",
            )

            submitted = st.form_submit_button(
                "Hej",
                key="login_submit",
                type="primary",
                use_container_width=True,
            )

        login_keyboard()

        if submitted:
            user = authenticate(email, pin)

            if user:
                st.session_state["user_id"] = user["id"]
                st.rerun()
            else:
                st.error("Nieprawidłowy e-mail lub PIN.")

        st.divider()

        with st.expander("Nie masz konta? Utwórz konto"):
            if st.session_state.get("registration_complete"):
                st.success("Konto zostało utworzone. Zaloguj się powyżej.")
                return
            if "registration_token" not in st.session_state:
                st.session_state["registration_token"] = str(uuid4())
            with st.form(
                "registration_form",
                clear_on_submit=False,
            ):
                first_name = st.text_input(
                    "Imię",
                    key="reg_first",
                )
                last_name = st.text_input(
                    "Nazwisko",
                    key="reg_last",
                )
                reg_email = st.text_input(
                    "E-mail",
                    key="reg_email",
                )
                phone = st.text_input(
                    "Numer telefonu",
                    key="reg_phone",
                )
                reg_pin = st.text_input(
                    "Ustaw 4-cyfrowy PIN",
                    type="password",
                    max_chars=4,
                    key="reg_pin",
                )

                register_submitted = st.form_submit_button(
                    "Utwórz konto",
                    use_container_width=True,
                )

            if register_submitted:
                ok, msg = add_user(
                    first_name,
                    last_name,
                    reg_email,
                    phone,
                    reg_pin,
                    registration_token=st.session_state["registration_token"],
                )
                if ok:
                    st.session_state["registration_complete"] = True
                    st.rerun()
                else:
                    st.error(msg)

def employee_schedule_tab(user):
    rows = get_user_schedule(user["id"])

    if not rows:
        st.info("Nie masz jeszcze wpisanego grafiku.")
        return

    anchor = st.date_input(
        "Pokaż tydzień zawierający",
        value=date.today(),
        key="employee_calendar_anchor",
    )
    week_start = anchor - timedelta(days=anchor.weekday())

    visible = [
        dict(r, first_name=user["first_name"], last_name=user["last_name"])
        for r in rows
        if week_start.isoformat()
        <= r["work_date"]
        <= (week_start + timedelta(days=6)).isoformat()
    ]

    render_week_calendar(
        visible,
        week_start,
        show_names=False,
    )






def own_contact_change_panel(user, key_prefix):
    prefix = f"{key_prefix}_contact_{user['id']}"
    if st.session_state.pop(f"{prefix}_reset", False):
        for field in ("email", "phone", "pin"):
            st.session_state.pop(f"{prefix}_{field}", None)
    message = st.session_state.pop(f"{prefix}_success", None)
    if message:
        st.success(message)
    st.markdown("### E-mail i telefon")
    st.caption("Zmień e-mail lub telefon i zatwierdź aktualnym PIN-em. Nowy e-mail będzie służył do logowania.")
    with st.form(f"{prefix}_form"):
        email = st.text_input("E-mail", value=user["email"], key=f"{prefix}_email")
        phone = st.text_input("Numer telefonu", value=user["phone"], key=f"{prefix}_phone")
        current_pin = st.text_input(
            "Potwierdź aktualnym PIN-em", type="password", max_chars=4,
            key=f"{prefix}_pin",
        )
        submitted = st.form_submit_button(
            "Zapisz dane kontaktowe", type="primary", use_container_width=True,
        )
    if submitted:
        ok, message = change_own_contact(user["id"], current_pin, email, phone)
        if ok:
            st.session_state[f"{prefix}_success"] = message
            st.session_state[f"{prefix}_reset"] = True
            st.rerun()
        else:
            st.error(message)


def own_pin_change_panel(user, key_prefix):
    own_contact_change_panel(user, key_prefix)
    st.divider()
    st.markdown("### Zmień PIN")
    st.caption(
        "PIN musi mieć dokładnie 4 cyfry."
    )

    current_pin = st.text_input(
        "Obecny PIN",
        type="password",
        max_chars=4,
        key=f"{key_prefix}_current_pin",
    )
    new_pin = st.text_input(
        "Nowy PIN",
        type="password",
        max_chars=4,
        key=f"{key_prefix}_new_pin",
    )
    new_pin_repeat = st.text_input(
        "Powtórz nowy PIN",
        type="password",
        max_chars=4,
        key=f"{key_prefix}_new_pin_repeat",
    )

    if st.button(
        "Zmień PIN",
        type="primary",
        use_container_width=True,
        key=f"{key_prefix}_change_pin_btn",
    ):
        if new_pin != new_pin_repeat:
            st.error("Nowe PIN-y nie są takie same.")
        else:
            ok, msg = change_own_pin(
                user["id"],
                current_pin,
                new_pin,
            )
            if ok:
                st.success(msg)
            else:
                st.error(msg)


def availability_label(kind, start_time=None, end_time=None):
    if kind == "available_all_day":
        return "Dostępna/y cały dzień"
    if kind == "available_hours":
        return f"Dostępna/y {start_time}–{end_time}"
    if kind == "unavailable":
        return "Niedostępna/y"
    return kind


def own_availability_panel(user, key_prefix):
    st.markdown("### Dni wolne")
    st.caption(
        "Zaznacz dni, w które nie możesz pracować. "
        "Szef zobaczy je podczas układania grafiku."
    )

    c1, c2 = st.columns(2)

    with c1:
        day_off_date = st.date_input(
            "Dzień wolny",
            value=date.today() + timedelta(days=1),
            key=f"{key_prefix}_day_off_date",
        )

    with c2:
        day_off_note = st.text_input(
            "Uwagi (opcjonalnie)",
            key=f"{key_prefix}_day_off_note",
        )

    if st.button(
        "Zgłoś dzień wolny",
        type="primary",
        use_container_width=True,
        key=f"{key_prefix}_day_off_save",
    ):
        ok, msg = set_day_off(
            user["id"],
            day_off_date,
            day_off_note,
        )
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    rows = get_user_days_off(
        user["id"],
        date.today(),
        date.today() + timedelta(days=120),
    )

    st.markdown("### Zgłoszone dni wolne")

    if not rows:
        st.info("Nie masz zgłoszonych dni wolnych.")
        return

    st.dataframe(
        [{
            "Data": row["availability_date"],
            "Uwagi": row["note"] or "",
        } for row in rows],
        use_container_width=True,
        hide_index=True,
    )

    options = {
        f"{row['availability_date']}"
        + (f" — {row['note']}" if row["note"] else ""): row["id"]
        for row in rows
    }

    selected = st.selectbox(
        "Anuluj dzień wolny",
        list(options.keys()),
        key=f"{key_prefix}_day_off_delete_choice",
    )

    if st.button(
        "Usuń zgłoszenie dnia wolnego",
        key=f"{key_prefix}_day_off_delete",
    ):
        delete_availability(
            options[selected],
            user["id"],
        )
        st.rerun()



def notification_panel(user, key_prefix):
    unread = count_unread_notifications(user["id"])
    st.markdown(f"### Powiadomienia — nieprzeczytane: {unread}")

    rows = get_notifications(user["id"])

    if not rows:
        st.info("Brak powiadomień.")
        return

    if unread:
        if st.button(
            "Oznacz wszystkie jako przeczytane",
            key=f"{key_prefix}_mark_all_read",
        ):
            mark_all_notifications_read(user["id"])
            st.rerun()

    for row in rows:
        icon = "🔵" if not row["is_read"] else "⚪"
        st.markdown(f"#### {icon} {row['title']}")
        st.write(row["message"])
        st.caption(row["created_at"])

        if not row["is_read"]:
            if st.button(
                "Oznacz jako przeczytane",
                key=f"{key_prefix}_read_{row['id']}",
            ):
                mark_notification_read(
                    row["id"],
                    user["id"],
                )
                st.rerun()

        st.divider()


def event_home_notifications(user):
    """Latest notifications on the event worker home page."""
    unread = count_unread_notifications(user["id"])
    st.markdown("### Powiadomienia")
    rows = get_notifications(user["id"], limit=50)

    if not rows:
        st.caption("Nie masz nowych powiadomień.")
        return

    if unread and st.button(
        f"Oznacz wszystkie jako przeczytane ({unread})",
        key="event_home_mark_all_read",
    ):
        mark_all_notifications_read(user["id"])
        st.rerun()

    def show_row(row):
        prefix = "● " if not row["is_read"] else ""
        with st.container(border=True):
            st.markdown(f"**{prefix}{row['title']}**")
            st.write(row["message"])
            st.caption(row["created_at"])
            if not row["is_read"] and st.button(
                "Oznacz jako przeczytane",
                key=f"event_home_read_{row['id']}",
            ):
                mark_notification_read(row["id"], user["id"])
                st.rerun()

    for row in rows[:4]:
        show_row(row)

    if len(rows) > 4:
        with st.expander(f"Starsze powiadomienia ({len(rows) - 4})"):
            for row in rows[4:]:
                show_row(row)



def employee_area_choice(user, groups):
    """Validate the chosen area against current account assignments."""
    available = [code for code in ("event", "warehouse", "local") if code in groups]
    if len(available) <= 1:
        if not available or available[0] != "event":
            st.session_state.pop("employee_event_detail_id", None)
        return available[0] if available else None

    key = f"employee_area_{user['id']}"
    selected = st.session_state.get(key)
    if selected not in available:
        st.session_state.pop(key, None)
        st.session_state.pop("employee_event_detail_id", None)
        with st.container(key="employee_greeting"):
            st.subheader(f"Hej, {user['first_name']} 👋")
        st.markdown("### Wybierz miejsce pracy:")
        for col, code in zip(st.columns(len(available)), available):
            with col:
                if st.button(
                    work_group_label(code), key=f"employee_area_choose_{code}",
                    use_container_width=True, type="primary",
                ):
                    st.session_state[key] = code
                    st.rerun()
        if st.button("Wyloguj się", key="employee_area_logout", use_container_width=True):
            logout()
        return None

    if st.button("← Zmień miejsce pracy", key="employee_area_back"):
        st.session_state.pop(key, None)
        st.session_state.pop("employee_event_detail_id", None)
        st.rerun()
    st.caption(work_group_label(selected))
    return selected


def employee_panel(user):
    groups = [g["code"] for g in get_render_user_groups(user["id"])]
    selected_area = employee_area_choice(user, groups)
    if groups and selected_area is None:
        return
    groups = [selected_area] if selected_area else []
    shifts = get_user_shifts(user["id"])
    payments = get_user_payments(user["id"])

    event_only = selected_area == "event"
    regular_area = selected_area in ("warehouse", "local")
    if event_only and st.session_state.get("employee_event_detail_id") is not None:
        employee_event_details(user)
        return

    with st.container(key="employee_greeting"):
        st.subheader(f"Hej, {user['first_name']} 👋")

    clock_groups = (
        ["event"] if event_only
        else [code for code in ("warehouse", "local") if code in groups]
    )

    # Event-only workers can clock in/out, just like warehouse/local workers.
    if clock_groups:
        st.markdown("### Rejestracja zmiany")
        active = get_active_shift(user["id"])

        if active:
            start_dt = datetime.strptime(
                active["start_at"],
                "%Y-%m-%d %H:%M:%S",
            )
            st.success(
                f"{work_group_label(active['work_group'])}: "
                f"zmiana trwa od {start_dt.strftime('%H:%M')} "
                f"({start_dt.strftime('%d.%m.%Y')})"
            )

            if st.button(
                "Zakończ zmianę",
                type="primary",
                use_container_width=True,
                key="employee_end_shift",
            ):
                ok, msg = end_shift(user["id"])
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            if event_only:
                selected_clock_group = "event"
            elif regular_area:
                selected_clock_group = selected_area
            else:
                selected_clock_group = st.selectbox(
                    "Gdzie teraz pracujesz?",
                    clock_groups,
                    format_func=work_group_label,
                    key="employee_clock_group",
                )

            if st.button(
                "Rozpocznij zmianę",
                type="primary",
                use_container_width=True,
                key="employee_start_shift",
            ):
                ok, msg = start_shift(
                    user["id"],
                    selected_clock_group,
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    elif not groups:
        st.warning(
            "Nie masz jeszcze przypisanego obszaru pracy. "
            "Szef musi ustawić Eventy, Magazyn lub Lokal."
        )

    pending_count = sum(
        1 for s in shifts
        if s["approval_status"] == "pending"
    )
    approved_unpaid = [
        s for s in shifts
        if s["approval_status"] == "approved"
        and s["payment_id"] is None
    ]

    c1, c2, c3 = st.columns(3)
    c1.metric("Do zatwierdzenia", pending_count)
    c2.metric(
        "Zatwierdzone godziny",
        f"{sum(int(s['billable_hours'] or 0) for s in approved_unpaid)} h",
    )
    c3.metric(
        "Do rozliczenia",
        f"{sum(float(s['amount'] or 0) for s in approved_unpaid):,.0f} zł".replace(",", " "),
    )

    tab_names = []

    if "event" in groups:
        tab_names.append("Eventy")

    if clock_groups and not event_only:
        tab_names.append("Grafik pracy")

    unread = count_unread_notifications(user["id"])
    notification_tab_name = (
        f"Powiadomienia ({unread})"
        if unread
        else "Powiadomienia"
    )

    if event_only:
        event_home_notifications(user)

    if not event_only:
        tab_names.append("Dni wolne")

    tab_names += [
        "Moje godziny",
        "Moje wypłaty",
    ]
    if not event_only and not regular_area:
        tab_names.append(notification_tab_name)
    tab_names.append("Ustawienia konta")

    tabs = st.tabs(tab_names)
    tab_map = dict(zip(tab_names, tabs))

    if "Eventy" in tab_map:
        with tab_map["Eventy"]:
            st.markdown("### Mój kalendarz eventów")
            event_month_calendar(user["id"], "employee")

    if "Grafik pracy" in tab_map:
        with tab_map["Grafik pracy"]:
            employee_schedule_calendar(
                user,
                groups,
            )

    if "Dni wolne" in tab_map:
        with tab_map["Dni wolne"]:
            own_availability_panel(
                user, "warehouse" if regular_area else "employee",
            )

    with tab_map["Moje godziny"]:
        visible = [
            s for s in shifts
            if s["approval_status"] != "active"
        ]

        if not visible:
            st.info("Nie masz jeszcze zapisanych godzin.")
        else:
            st.dataframe(
                [shift_summary(s) for s in visible],
                use_container_width=True,
                hide_index=True,
            )

            for s in visible:
                if (
                    s["approval_status"] == "rejected"
                    and s["rejection_note"]
                ):
                    st.error(
                        f"Odrzucona zmiana {s['start_at'][:10]}: "
                        f"{s['rejection_note']}"
                    )

            rejected = [
                s for s in visible
                if s["approval_status"] == "rejected"
                and s["payment_id"] is None
            ]

            if rejected:
                options = {
                    f"{s['start_at'][:16]} — "
                    f"{work_group_label(s['work_group'])}": s["id"]
                    for s in rejected
                }
                selected = st.selectbox(
                    "Usuń odrzuconą zmianę",
                    list(options.keys()),
                )

                if st.button("Usuń odrzuconą zmianę"):
                    delete_rejected_shift(
                        options[selected],
                        user["id"],
                    )
                    st.rerun()

    with tab_map["Moje wypłaty"]:
        if not payments:
            st.info("Nie masz jeszcze wypłat.")
        else:
            for payment in payments:
                st.markdown(
                    f"### {status_icon(payment['status'])} "
                    f"{status_label(payment['status'])} — "
                    f"{money(payment['amount'])}"
                )
                st.write(
                    f"Okres: **{payment['period_from']} – "
                    f"{payment['period_to']}**"
                )

                if payment["status"] == "sent":
                    if st.button(
                        "Potwierdzam otrzymanie przelewu",
                        key=f"confirm_{payment['id']}",
                        type="primary",
                    ):
                        confirm_payment_received(
                            payment["id"],
                            user["id"],
                        )
                        st.rerun()

                elif payment["status"] == "received":
                    st.success("Przelew potwierdzony ✅")

                st.divider()

    if notification_tab_name in tab_map:
        with tab_map[notification_tab_name]:
            notification_panel(
                user,
                "employee",
            )

    with tab_map["Ustawienia konta"]:
        own_pin_change_panel(
            user,
            "employee",
        )

    if st.button(
        "Wyloguj się",
        use_container_width=True,
        key="employee_logout",
    ):
        logout()

def approval_list(user, prefix, show_money):
    pending = get_pending_shifts()

    if not pending:
        st.success("Brak zmian oczekujących na zatwierdzenie.")
        return

    for shift in pending:
        st.markdown(
            f"### {shift['first_name']} {shift['last_name']}"
        )
        st.caption(
            f"{work_group_label(shift['work_group'])} • "
            f"{scheduled_vs_actual(shift)}"
        )
        st.write(
            f"Rzeczywisty czas: **{minutes_to_text(shift['actual_minutes'])}**  |  "
            f"Rozliczenie: **{shift['billable_hours']} h**"
        )

        if show_money:
            st.write(
                f"Stawka: **{money(shift['hourly_rate'])}/h**  |  "
                f"Kwota: **{money(shift['amount'])}**"
            )

        if shift["correction_note"]:
            st.info(
                f"Korekta: {shift['correction_note']}"
            )

        correction_form(
            shift,
            user["id"],
            prefix,
        )

        rejection_note = st.text_input(
            "Powód odrzucenia (opcjonalnie)",
            key=f"{prefix}_reject_note_{shift['id']}",
        )

        c1, c2 = st.columns(2)

        with c1:
            if st.button(
                "Zatwierdź",
                key=f"{prefix}_approve_{shift['id']}",
                type="primary",
                use_container_width=True,
            ):
                approve_shift(shift["id"], user["id"])
                st.rerun()

        with c2:
            if st.button(
                "Odrzuć",
                key=f"{prefix}_reject_{shift['id']}",
                use_container_width=True,
            ):
                reject_shift(
                    shift["id"],
                    user["id"],
                    rejection_note,
                )
                st.rerun()

        st.divider()


def manager_panel(user):
    groups = [g["code"] for g in get_render_user_groups(user["id"])]

    st.subheader(f"Panel managera — {user['first_name']}")

    unread = count_unread_notifications(user["id"])
    notification_tab_name = (
        f"Powiadomienia ({unread})"
        if unread
        else "Powiadomienia"
    )

    tabs = st.tabs([
        "Moje godziny",
        "Pracownicy",
        "Godziny zespołu",
        "Grafiki",
        "Eventy",
        "Dni wolne",
        "Wypłaty — podgląd",
        "Do zatwierdzenia",
        notification_tab_name,
        "Ustawienia konta",
    ])

    with tabs[0]:
        st.markdown("### Rejestracja mojej zmiany")
        active = get_active_shift(user["id"])

        if active:
            start_dt = datetime.strptime(
                active["start_at"],
                "%Y-%m-%d %H:%M:%S",
            )
            st.success(
                f"{work_group_label(active['work_group'])}: "
                f"zmiana trwa od {start_dt.strftime('%H:%M')}"
            )

            if st.button(
                "Zakończ moją zmianę",
                type="primary",
                use_container_width=True,
                key="manager_end_shift",
            ):
                ok, msg = end_shift(user["id"])
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            manager_groups = [
                code for code in ("event", "warehouse", "local")
                if code in groups
            ]

            if not manager_groups:
                st.warning(
                    "Szef musi przypisać managerowi obszary pracy."
                )
            else:
                selected_group = st.selectbox(
                    "Stanowisko",
                    manager_groups,
                    format_func=work_group_label,
                    key="manager_own_work_group",
                )

                if st.button(
                    "Rozpocznij moją zmianę",
                    type="primary",
                    use_container_width=True,
                    key="manager_start_shift",
                ):
                    ok, msg = start_shift(
                        user["id"],
                        selected_group,
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        own_rows = [
            s for s in get_user_shifts(user["id"])
            if s["approval_status"] != "active"
        ]
        if own_rows:
            st.dataframe(
                [shift_summary(s) for s in own_rows],
                use_container_width=True,
                hide_index=True,
            )

    with tabs[1]:
        users = get_users()
        rows = []
        for person in users:
            if person["access_level"] == "admin":
                continue
            person_groups = ", ".join(
                work_group_label(g["code"])
                for g in get_render_user_groups(person["id"])
            ) or "—"
            rows.append({
                "Pracownik": f"{person['first_name']} {person['last_name']}",
                "Status": (
                    "MANAGER"
                    if person["access_level"] == "manager"
                    else "PRACOWNIK"
                ),
                "Obszary": person_groups,
                "E-mail": person["email"],
                "Telefon": person["phone"],
            })

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

    with tabs[2]:
        st.markdown("### Wszystkie godziny zespołu")
        all_shifts = [
            row for row in get_all_shifts()
            if get_user(row["user_id"])["access_level"] != "admin"
        ]

        if all_shifts:
            st.dataframe(
                [{
                    "Pracownik": f"{r['first_name']} {r['last_name']}",
                    "Stanowisko": work_group_label(r["work_group"]),
                    **shift_summary(r),
                } for r in all_shifts],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Brak godzin.")

        st.divider()
        st.markdown("### Wpisz godziny pracownika")
        st.caption(
            "Godziny wpisane przez managera trafiają do zatwierdzenia szefa."
        )

        eligible = [
            u for u in get_users()
            if u["access_level"] != "admin"
            and u["id"] != user["id"]
        ]

        if eligible:
            employee_map = {
                f"{u['first_name']} {u['last_name']}": u
                for u in eligible
            }
            employee_name = st.selectbox(
                "Pracownik",
                list(employee_map.keys()),
                key="manager_manual_employee",
            )
            employee = employee_map[employee_name]
            employee_groups = [
                g["code"]
                for g in get_render_user_groups(employee["id"])
            ]

            if employee_groups:
                manual_group = st.selectbox(
                    "Stanowisko",
                    employee_groups,
                    format_func=work_group_label,
                    key="manager_manual_group",
                )

                c1, c2 = st.columns(2)
                with c1:
                    manual_date = st.date_input(
                        "Data",
                        value=date.today(),
                        key="manager_manual_date",
                    )
                    manual_start = st.time_input(
                        "Start",
                        value=time(10, 0),
                        step=300,
                        key="manager_manual_start",
                    )
                with c2:
                    manual_end = st.time_input(
                        "Koniec",
                        value=time(18, 0),
                        step=300,
                        key="manager_manual_end",
                    )
                    manual_note = st.text_input(
                        "Uwagi",
                        key="manager_manual_note",
                    )

                if st.button(
                    "Wpisz godziny",
                    type="primary",
                    use_container_width=True,
                    key="manager_add_manual_hours",
                ):
                    start_dt = datetime.combine(
                        manual_date,
                        manual_start,
                    ).strftime("%Y-%m-%d %H:%M:%S")
                    end_dt = datetime.combine(
                        manual_date,
                        manual_end,
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    ok, msg = add_manual_shift(
                        employee["id"],
                        start_dt,
                        end_dt,
                        user["id"],
                        manual_group,
                        manual_note,
                        auto_approve=False,
                    )

                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.warning(
                    "Ta osoba nie ma przypisanego obszaru pracy."
                )

    with tabs[3]:
        st.markdown("### Grafik zespołu")

        anchor = st.date_input(
            "Miesiąc",
            value=date.today().replace(day=1),
            key="manager_schedule_month",
        )
        month_start, month_end = month_range(anchor)

        schedule_users = regular_schedule_users(
            get_users()
        )
        schedule_ids = [
            person["id"]
            for person in schedule_users
        ]

        rows = get_schedules_for_users(
            schedule_ids,
            month_start,
            month_end,
        )

        render_roster_calendar(
            rows,
            schedule_users,
            anchor,
        )

    with tabs[4]:
        rows = get_all_events()
        if not rows:
            st.info("Brak eventów.")
        else:
            st.dataframe(
                [{
                    "Event": r["name"],
                    "Data": r["event_date"],
                    "Godziny": f"{r['start_time']}–{r['end_time']}",
                    "Miejsce": r["location"] or "",
                    "Pracownicy": r["people"] or "",
                    "Osoba odpowiedzialna": (
                        f"{r['manager_first_name']} {r['manager_last_name']}"
                        if r["manager_first_name"]
                        else "—"
                    ),
                } for r in rows],
                use_container_width=True,
                hide_index=True,
            )

    with tabs[5]:
        admin_availability(
            get_users(),
        )

    with tabs[6]:
        st.markdown("### Wypłaty — tylko podgląd")
        st.caption(
            "Manager widzi statusy i kwoty, ale nie może tworzyć ani wysyłać wypłat."
        )

        payments = get_all_payments()
        if not payments:
            st.info("Brak wypłat.")
        else:
            st.dataframe(
                [{
                    "Pracownik": f"{p['first_name']} {p['last_name']}",
                    "Okres": f"{p['period_from']}–{p['period_to']}",
                    "Kwota": money(p["amount"]),
                    "Status": status_label(p["status"]),
                } for p in payments],
                use_container_width=True,
                hide_index=True,
            )

    with tabs[7]:
        approval_list(
            user,
            "manager",
            show_money=False,
        )

    with tabs[8]:
        notification_panel(
            user,
            "manager",
        )

    with tabs[9]:
        own_pin_change_panel(
            user,
            "manager",
        )

    if st.button(
        "Wyloguj się",
        use_container_width=True,
        key="manager_logout",
    ):
        logout()

def admin_overview(users):
    """Read-only snapshot; outstanding shifts and prepared payments stay separate."""
    active = get_today_active_shifts()
    pending = get_pending_shifts()
    payments = get_all_payments()
    unpaid = [
        row for row in get_all_shifts()
        if row["approval_status"] == "approved" and row["payment_id"] is None
    ]
    schedule = get_today_schedule()
    days_off = get_days_off_for_users(
        [u["id"] for u in users], date.today(), date.today(),
    )
    off_ids = {row["user_id"] for row in days_off}
    return {
        "active": active,
        "pending": pending,
        "created": [p for p in payments if p["status"] == "created"],
        "sent": [p for p in payments if p["status"] == "sent"],
        "unpaid": unpaid,
        "schedule": schedule,
        "days_off": days_off,
        "conflicts": [row for row in schedule if row["user_id"] in off_ids],
        "unassigned": [
            u for u in users
            if u["access_level"] != "admin" and not get_render_user_groups(u["id"])
        ],
        "overnight": [row for row in active if row["start_at"][:10] < date.today().isoformat()],
        "events": [event for event in get_all_events() if event["event_date"] >= date.today().isoformat()][:5],
    }


def admin_dashboard(users, user):
    overview = admin_overview(users)
    with st.container(key="admin_overview"):
        with st.container(key="employee_greeting"):
            st.subheader(f"Hej, {user['first_name']} 👋")
        st.caption(f"Przegląd sytuacji • {date.today().strftime('%d.%m.%Y')}")
        if st.button("Odśwież dane", key="admin_refresh"):
            st.rerun()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Teraz pracują", len({row["user_id"] for row in overview["active"]}))
        c2.metric("Zmiany do zatwierdzenia", len(overview["pending"]))
        c3.metric("Do rozliczenia", money(sum(float(r["amount"] or 0) for r in overview["unpaid"])))
        c4.metric("Przelewy do wysłania", money(sum(float(p["amount"] or 0) for p in overview["created"])))
        st.caption("Do rozliczenia: zatwierdzone zmiany bez wypłaty. Do wysłania: już przygotowane wypłaty.")

        st.markdown("### Do sprawdzenia")
        actions = []
        if overview["pending"]:
            actions.append(("approvals", f"Zatwierdź godziny · {len(overview['pending'])}", None))
        if overview["unpaid"]:
            actions.append(("payments", f"Przygotuj wypłaty · {len(overview['unpaid'])} zmian", "transfers"))
        if overview["created"]:
            actions.append(("payments", f"Sprawdź przelewy · {len(overview['created'])}", "transfers"))
        if overview["unassigned"]:
            actions.append(("employees", f"Przypisz obszar pracy · {len(overview['unassigned'])} osób", None))
        if not actions:
            st.success("Brak zaległych zatwierdzeń, wypłat i kont do przypisania.")
        for index, (page, label, section) in enumerate(actions):
            if st.button(label, key=f"admin_action_{index}", use_container_width=True, type="primary"):
                if section:
                    st.session_state["admin_payments_view"] = section
                set_admin_page(page)
        if overview["conflicts"]:
            names = sorted({f"{r['first_name']} {r['last_name']}" for r in overview["conflicts"]})
            st.warning("Osoby wpisane w dzisiejszy grafik mimo zgłoszonego wolnego: " + ", ".join(names))
            if st.button("Sprawdź dzisiejszy grafik", key="admin_conflict_schedule"):
                st.session_state["admin_schedule_month"] = date.today().replace(day=1)
                st.session_state["admin_schedule_edit_date"] = date.today()
                set_admin_page("schedule")
        if overview["overnight"]:
            st.info(f"Otwarte zmiany rozpoczęte przed dzisiaj: {len(overview['overnight'])}. Są widoczne poniżej z datą rozpoczęcia.")

        st.markdown("### Dzisiaj")
        active_tab, schedule_tab, off_tab = st.tabs(["Trwające zmiany", "Planowana obsada", "Dni wolne"])
        with active_tab:
            if overview["active"]:
                st.dataframe([{
                    "Pracownik": f"{r['first_name']} {r['last_name']}",
                    "Miejsce": work_group_label(r["work_group"]),
                    "Rozpoczęcie": r["start_at"],
                } for r in overview["active"]], use_container_width=True, hide_index=True)
            else:
                st.info("Nikt nie ma obecnie rozpoczętej zmiany.")
        with schedule_tab:
            st.caption("Grafik Magazynu i Lokalu. Dzisiejsze eventy znajdują się w sekcji poniżej.")
            if overview["schedule"]:
                st.dataframe([{
                    "Pracownik": f"{r['first_name']} {r['last_name']}",
                    "Miejsce": work_group_label(r["work_group"]),
                    "Godziny": f"{r['start_time'] or '—'}–{r['end_time'] or '—'}",
                    "Uwagi": r["note"] or "",
                } for r in overview["schedule"]], use_container_width=True, hide_index=True)
            else:
                st.info("Na dzisiaj nie wpisano obsady Magazynu ani Lokalu.")
        with off_tab:
            if overview["days_off"]:
                st.dataframe([{
                    "Pracownik": f"{r['first_name']} {r['last_name']}",
                    "Uwagi": r["note"] or "",
                } for r in overview["days_off"]], use_container_width=True, hide_index=True)
            else:
                st.info("Brak zgłoszonych dni wolnych na dzisiaj.")

        st.markdown("### Najbliższe eventy")
        st.caption("Do pięciu najbliższych eventów. Pełna lista jest w sekcji Eventy.")
        if not overview["events"]:
            st.info("Brak nadchodzących eventów.")
        for event in overview["events"]:
            with st.container(border=True):
                st.write(f"**{event['name']}**")
                st.caption(f"{event['event_date']} • {event['start_time']}–{event['end_time']} • {event['location'] or 'Bez podanej lokalizacji'}")
                responsible = f"{event['manager_first_name']} {event['manager_last_name']}" if event["manager_first_name"] else "Nie przypisano"
                st.write(f"Osoba odpowiedzialna: {responsible}")
                st.write(f"Obsada: {event['people'] or 'Nie przypisano pracowników'}")
        if st.button("Otwórz eventy", key="admin_overview_events", use_container_width=True):
            set_admin_page("events")

        with st.expander(f"Wysłane wypłaty bez potwierdzenia · {len(overview['sent'])}"):
            if overview["sent"]:
                st.dataframe([{
                    "Pracownik": f"{p['first_name']} {p['last_name']}",
                    "Kwota": money(p["amount"]),
                    "Okres": f"{p['period_from']}–{p['period_to']}",
                } for p in overview["sent"]], use_container_width=True, hide_index=True)
            else:
                st.caption("Brak wypłat oczekujących na potwierdzenie.")


def admin_calendar(users):
    st.markdown("### Grafik")
    st.caption(
        "Grafik miesięczny pokazuje Magazyn, Lokal, eventy i zgłoszone dni wolne."
    )

    schedule_users = regular_schedule_users(users)

    anchor = st.date_input(
        "Miesiąc grafiku",
        value=date.today().replace(day=1),
        key="admin_schedule_month",
    )
    month_start, month_end = month_range(anchor)

    schedule_ids = [
        person["id"]
        for person in schedule_users
    ]

    rows = get_schedules_for_users(
        schedule_ids,
        month_start,
        month_end,
    )

    month_days_off = get_days_off_for_users(
        schedule_ids,
        month_start,
        month_end,
    )

    render_roster_calendar(
        rows,
        schedule_users,
        anchor,
        days_off_rows=month_days_off,
        show_days_off=True,
        event_rows=[e for e in get_all_events() if month_start.isoformat() <= e["event_date"] <= month_end.isoformat()],
    )

    if not schedule_users:
        st.info("Brak pracowników Magazynu lub Lokalu do wpisania w grafik. Eventy edytujesz w sekcji Eventy.")
        return

    st.divider()
    st.markdown("### Ustaw grafik na konkretny dzień")

    schedule_date = st.date_input(
        "Dzień",
        value=anchor,
        key="admin_schedule_edit_date",
    )

    current_rows = get_day_schedule(
        schedule_date
    )
    current_map = {
        int(row["user_id"]): row["work_group"]
        for row in current_rows
    }

    day_off_rows = get_days_off_for_users(
        schedule_ids,
        schedule_date,
        schedule_date,
    )
    day_off_map = {
        int(row["user_id"]): row
        for row in day_off_rows
    }

    if day_off_rows:
        names = ", ".join(
            f"{row['first_name']} {row['last_name']}"
            for row in day_off_rows
        )
        st.info(
            f"Wolne zgłoszone na {schedule_date.strftime('%d.%m.%Y')}: "
            f"{names}"
        )

    assignments = {}

    for row_start in range(
        0,
        len(schedule_users),
        3,
    ):
        cols = st.columns(3)

        for col, person in zip(
            cols,
            schedule_users[row_start:row_start + 3],
        ):
            with col:
                st.markdown(
                    f"**{person['first_name']} "
                    f"{person['last_name']}**"
                )

                if person["id"] in day_off_map:
                    note = (
                        day_off_map[person["id"]]["note"]
                        or ""
                    )
                    st.caption(
                        "WOLNE"
                        + (f" — {note}" if note else "")
                    )
                    assignments[person["id"]] = None
                    continue

                person_groups = [
                    g["code"]
                    for g in get_render_user_groups(person["id"])
                ]

                options = [None]

                if "warehouse" in person_groups:
                    options.append("warehouse")

                if "local" in person_groups:
                    options.append("local")

                current = current_map.get(
                    person["id"]
                )

                if current not in options:
                    current = None

                selected = st.selectbox(
                    "Praca",
                    options,
                    index=options.index(current),
                    format_func=lambda code: {
                        None: "x",
                        "warehouse": "Magazyn",
                        "local": "Lokal",
                    }[code],
                    key=(
                        f"schedule_day_{schedule_date.isoformat()}_"
                        f"{person['id']}"
                    ),
                    label_visibility="collapsed",
                )

                assignments[person["id"]] = selected

    if st.button(
        "Zapisz grafik na ten dzień",
        type="primary",
        use_container_width=True,
        key="admin_schedule_day_save",
    ):
        ok, msg = set_day_schedule(
            schedule_date,
            assignments,
        )

        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)



def admin_availability(users):
    st.markdown("### Dni wolne pracowników")
    st.caption(
        "Tu widzisz dni, które pracownicy zgłosili jako wolne."
    )

    employee_users = [
        person
        for person in users
        if person["access_level"] != "admin"
    ]

    if not employee_users:
        st.info("Brak pracowników.")
        return

    labels = {
        f"{person['first_name']} {person['last_name']}": person
        for person in employee_users
    }

    selected_names = st.multiselect(
        "Pokaż osoby",
        list(labels.keys()),
        default=list(labels.keys()),
        key="admin_days_off_people",
    )

    c1, c2 = st.columns(2)

    with c1:
        date_from = st.date_input(
            "Od",
            value=date.today(),
            key="admin_days_off_from",
        )

    with c2:
        date_to = st.date_input(
            "Do",
            value=date.today() + timedelta(days=31),
            key="admin_days_off_to",
        )

    selected_ids = [
        labels[name]["id"]
        for name in selected_names
    ]

    rows = get_days_off_for_users(
        selected_ids,
        date_from,
        date_to,
    )

    if not rows:
        st.info(
            "Brak zgłoszonych dni wolnych w wybranym okresie."
        )
        return

    st.dataframe(
        [{
            "Data": row["availability_date"],
            "Pracownik": (
                f"{row['first_name']} "
                f"{row['last_name']}"
            ),
            "Uwagi": row["note"] or "",
        } for row in rows],
        use_container_width=True,
        hide_index=True,
    )



def admin_reports(users):
    st.markdown("### Raporty")
    st.caption(
        "Raport obejmuje zatwierdzone zmiany w wybranym okresie."
    )

    employee_users = [
        u for u in users
        if u["access_level"] != "admin"
    ]

    labels = {
        f"{u['first_name']} {u['last_name']}": u
        for u in employee_users
    }

    c1, c2 = st.columns(2)

    with c1:
        date_from = st.date_input(
            "Raport od",
            value=date.today().replace(day=1),
            key="report_from",
        )

    with c2:
        date_to = st.date_input(
            "Raport do",
            value=date.today(),
            key="report_to",
        )

    selected_names = st.multiselect(
        "Pracownicy",
        list(labels.keys()),
        default=list(labels.keys()),
        key="report_people",
    )

    selected_ids = [
        labels[name]["id"]
        for name in selected_names
    ]

    rows = get_report_rows(
        date_from,
        date_to,
        selected_ids,
    )

    if not rows:
        st.info("Brak zatwierdzonych zmian w tym okresie.")
        return

    total_actual_minutes = sum(
        int(r["actual_minutes"] or 0)
        for r in rows
    )
    total_billable = sum(
        int(r["billable_hours"] or 0)
        for r in rows
    )
    total_amount = sum(
        float(r["amount"] or 0)
        for r in rows
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Zmiany", len(rows))
    m2.metric(
        "Rzeczywisty czas",
        minutes_to_text(total_actual_minutes),
    )
    m3.metric("Godziny rozliczeniowe", f"{total_billable} h")
    m4.metric("Koszt", money(total_amount))

    table_rows = []

    for r in rows:
        start_dt = datetime.strptime(
            r["start_at"],
            "%Y-%m-%d %H:%M:%S",
        )
        end_dt = datetime.strptime(
            r["end_at"],
            "%Y-%m-%d %H:%M:%S",
        )

        table_rows.append({
            "Pracownik": f"{r['first_name']} {r['last_name']}",
            "Stanowisko": work_group_label(r["work_group"]),
            "Data": r["work_date"],
            "Start": start_dt.strftime("%H:%M"),
            "Koniec": end_dt.strftime("%H:%M"),
            "Rzeczywisty czas": minutes_to_text(r["actual_minutes"]),
            "Godziny rozliczeniowe": r["billable_hours"],
            "Stawka": money(r["hourly_rate"]),
            "Kwota": money(r["amount"]),
            "Wypłata": status_label(r["payment_status"]) if r["payment_status"] else "Nierozliczona",
        })

    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
    )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=list(table_rows[0].keys()),
    )
    writer.writeheader()
    writer.writerows(table_rows)

    st.download_button(
        "Pobierz raport CSV",
        data=output.getvalue().encode("utf-8-sig"),
        file_name=(
            f"flomarohub_raport_{date_from.isoformat()}_"
            f"{date_to.isoformat()}.csv"
        ),
        mime="text/csv",
        use_container_width=True,
    )


def admin_profiles(users, employee=None, show_identity=True):
    if employee is None:
        labels = {f"{u['first_name']} {u['last_name']} — {u['email']}": u for u in users}
        if not labels:
            st.info("Brak pracowników.")
            return
        selected_name = st.selectbox("Pracownik", list(labels), key="profile_employee")
        employee = labels[selected_name]
    summary = get_user_summary(employee["id"])
    groups = ", ".join(
        g["name"]
        for g in get_render_user_groups(employee["id"])
    ) or "—"

    if show_identity:
        st.markdown(
            f"## {employee['first_name']} {employee['last_name']}"
        )
        st.write(
            f"**E-mail:** {employee['email']}  \n"
            f"**Telefon:** {employee['phone']}  \n"
            f"**Obszar:** {groups}  \n"
            f"**Stawka:** {money(employee['hourly_rate'])}/h"
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Zmiany", summary["all_shifts"])
    c2.metric("Zatwierdzone godziny", f"{summary['approved_hours']} h")
    c3.metric("Do zatwierdzenia", summary["pending"])
    c4.metric("Potwierdzone wypłaty", money(summary["paid_total"]))

    tabs = st.tabs(["Zmiany", "Wypłaty", "Grafik", "Eventy", "Dni wolne"])

    with tabs[0]:
        shifts = get_user_shifts(employee["id"])
        if not shifts:
            st.info("Brak zmian.")
        else:
            st.dataframe(
                [shift_summary(s) for s in shifts if s["approval_status"] != "active"],
                use_container_width=True,
                hide_index=True,
            )

    with tabs[1]:
        payments = get_user_payments(employee["id"])
        if not payments:
            st.info("Brak wypłat.")
        else:
            st.dataframe(
                [{
                    "Okres od": p["period_from"],
                    "Okres do": p["period_to"],
                    "Kwota": money(p["amount"]),
                    "Status": status_label(p["status"]),
                } for p in payments],
                use_container_width=True,
                hide_index=True,
            )

    with tabs[2]:
        schedule = get_user_schedule(employee["id"])
        if not schedule:
            st.info("Brak grafiku.")
        else:
            st.dataframe(
                [{
                    "Data": s["work_date"],
                    "Miejsce": work_group_label(s["work_group"]),
                    "Uwagi": s["note"] or "",
                } for s in schedule],
                use_container_width=True,
                hide_index=True,
            )

    with tabs[3]:
        events = get_user_events(employee["id"])
        if events:
            st.dataframe([{"Event": e["name"], "Data": e["event_date"], "Godziny": f"{e['start_time']}–{e['end_time']}", "Miejsce": e["location"] or ""} for e in events], use_container_width=True, hide_index=True)
        else:
            st.info("Brak przypisanych eventów.")
    with tabs[4]:
        days = get_user_days_off(employee["id"])
        if days:
            st.dataframe([{"Data": r["availability_date"], "Uwagi": r["note"] or ""} for r in days], use_container_width=True, hide_index=True)
        else:
            st.info("Brak zgłoszonych dni wolnych.")



ADMIN_PAGES = [
    ("employees", "Pracownicy"),
    ("schedule", "Grafik"),
    ("events", "Eventy"),
    ("approvals", "Zatwierdź godziny"),
    ("payments", "Wypłaty"),
]

def set_admin_page(page):
    st.session_state["admin_page"] = page
    st.rerun()


def admin_navigation():
    with st.container(key="admin_navbar"):
        cols = st.columns(len(ADMIN_PAGES), gap="small")

        for col, (page_key, title) in zip(cols, ADMIN_PAGES):
            with col:
                if st.button(
                    title,
                    key=f"admin_nav_{page_key}",
                    use_container_width=True,
                    disabled=st.session_state.get("admin_page") == page_key,
                ):
                    set_admin_page(page_key)


def admin_page_header(page):
    if st.button("← Panel", key=f"back_from_{page}"):
        set_admin_page(None)


def table_selected_index(event):
    selected = event.selection
    if selected.rows:
        return selected.rows[0]
    cells = selected.get("cells", [])
    return cells[0][0] if cells else None


def back_to_admin_list(state_key, epoch_key):
    st.session_state.pop(state_key, None)
    st.session_state[epoch_key] = st.session_state.get(epoch_key, 0) + 1
    st.rerun()


def admin_employee_accounts(users):
    selected_id = st.session_state.get("admin_employee_detail_id")
    selected = next((u for u in users if u["id"] == selected_id), None)
    if selected is None:
        st.session_state.pop("admin_employee_detail_id", None)
        st.caption("Kliknij osobę w tabeli, aby otworzyć jej dane i ustawienia.")
        rows = [{
            "Imię i nazwisko": f"{u['first_name']} {u['last_name']}",
            "E-mail": u["email"], "Telefon": u["phone"],
            "Pozycja": "SZEF" if u["access_level"] == "admin" else "PRACOWNIK",
            "Obszar": ", ".join(g["name"] for g in get_render_user_groups(u["id"])) or "—",
            "Stawka": money(u["hourly_rate"]),
        } for u in users]
        if not rows:
            st.info("Brak kont.")
            return
        selection = st.dataframe(
            rows, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode=["single-row", "single-cell"],
            key=f"admin_people_table_{st.session_state.get('admin_people_epoch', 0)}",
        )
        index = table_selected_index(selection)
        if index is not None and 0 <= index < len(users):
            st.session_state["admin_employee_detail_id"] = users[index]["id"]
            st.rerun()
        return

    if st.button("← Wszyscy pracownicy", key="admin_employee_back"):
        back_to_admin_list("admin_employee_detail_id", "admin_people_epoch")
    st.subheader(f"{selected['first_name']} {selected['last_name']}")
    st.write(f"E-mail: {selected['email']}")
    st.write(f"Telefon: {selected['phone']}")
    current_groups = [g["code"] for g in get_render_user_groups(selected["id"])]
    with st.form(f"employee_settings_{selected['id']}"):
        access = st.selectbox(
            "Pozycja", ["employee", "admin"],
            index=1 if selected["access_level"] == "admin" else 0,
            format_func=lambda value: "SZEF" if value == "admin" else "PRACOWNIK",
        )
        rate = st.text_input("Stawka godzinowa [zł]", value=str(selected["hourly_rate"]).replace(".", ","))
        groups = st.multiselect("Obszar pracy", ["event", "warehouse", "local"], default=current_groups, format_func=work_group_label)
        save = st.form_submit_button("Zapisz ustawienia", type="primary", use_container_width=True)
    if save:
        ok, message = update_user_settings(selected["id"], access, rate, groups)
        if ok:
            st.session_state["employee_saved"] = message
            st.rerun()
        else:
            st.error(message)
    if st.session_state.get("employee_saved"):
        st.success(st.session_state.pop("employee_saved"))
    admin_profiles(users, employee=selected, show_identity=False)
    st.divider()
    st.markdown("### Reset PIN-u")
    st.caption(
        "Starego PIN-u nie można podejrzeć. "
        "Możesz ustawić nowy 4-cyfrowy PIN i przekazać go pracownikowi."
    )

    reset_pin = st.text_input(
        "Nowy PIN dla wybranego konta",
        type="password",
        max_chars=4,
        key=f"admin_reset_pin_{selected['id']}",
    )
    reset_pin_repeat = st.text_input(
        "Powtórz nowy PIN",
        type="password",
        max_chars=4,
        key=f"admin_reset_pin_repeat_{selected['id']}",
    )

    if st.button(
        "Zresetuj PIN",
        use_container_width=True,
        key=f"admin_reset_pin_btn_{selected['id']}",
    ):
        if reset_pin != reset_pin_repeat:
            st.error("PIN-y nie są takie same.")
        else:
            ok, msg = admin_reset_pin(
                selected["id"],
                reset_pin,
            )
            if ok:
                st.success(
                    msg + " Przekaż nowy PIN tej osobie."
                )
            else:
                st.error(msg)



def event_attachment_downloads(viewer_id, event_id):
    attachments = get_event_attachments(viewer_id, event_id)
    if not attachments:
        st.caption("Brak załączników.")
        return
    for item in attachments:
        data = get_event_attachment(viewer_id, item["id"])
        if data is not None:
            st.download_button(
                f"Pobierz: {item['name']} ({item['size'] / 1024:.0f} KB)",
                data=bytes(data["content"]), file_name=item["name"],
                mime="application/octet-stream", key=f"event_file_{item['id']}",
                use_container_width=True,
            )


def admin_events_section(users):
    actor_id = st.session_state["user_id"]
    selected_id = st.session_state.get("admin_event_detail_id")
    if st.session_state.get("admin_event_saved"):
        st.success(st.session_state.pop("admin_event_saved"))
    if selected_id is None:
        if st.button("+ Nowy event", type="primary", key="admin_event_new"):
            st.session_state["admin_event_detail_id"] = "new"
            st.rerun()
        rows = get_all_events()
        if not rows:
            st.info("Brak eventów. Dodaj pierwszy event.")
            return
        st.caption("Kliknij event w tabeli, aby poprawić dane, zmienić obsadę lub dodać załączniki.")
        selection = st.dataframe([{
            "Event": r["name"], "Data": r["event_date"],
            "Godziny": f"{r['start_time']}–{r['end_time']}",
            "Miejsce": r["location"] or "", "Pracownicy": r["people"] or "",
            "Uwagi": r["note"] or "",
            "Osoba odpowiedzialna": f"{r['manager_first_name']} {r['manager_last_name']}" if r["manager_first_name"] else "—",
        } for r in rows], use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode=["single-row", "single-cell"],
            key=f"admin_events_table_{st.session_state.get('admin_events_epoch', 0)}")
        index = table_selected_index(selection)
        if index is not None and 0 <= index < len(rows):
            st.session_state["admin_event_detail_id"] = rows[index]["id"]
            st.rerun()
        return

    if st.button("← Wszystkie eventy", key="admin_event_back"):
        back_to_admin_list("admin_event_detail_id", "admin_events_epoch")
    event, crew = (None, []) if selected_id == "new" else get_admin_event(actor_id, selected_id)
    if selected_id != "new" and event is None:
        st.error("Event nie istnieje lub nie masz do niego dostępu.")
        return
    current_ids = [u["id"] for u in crew]
    candidates = {u["id"]: u for u in users if any(g["code"] == "event" for g in get_render_user_groups(u["id"]))}
    candidates.update({u["id"]: u for u in crew})
    responsible = {u["id"]: u for u in users}
    if event is not None and event["manager_id"] is not None and event["manager_id"] not in responsible:
        # Preserve a historical responsible person even if the account is inactive.
        responsible[event["manager_id"]] = {"first_name": "Dotychczasowa osoba", "last_name": f"(ID {event['manager_id']})"}
    label = lambda uid: f"{candidates[uid]['first_name']} {candidates[uid]['last_name']} — {candidates[uid]['email']}"
    with st.container(key="admin_event_editor"):
        st.subheader("Nowy event" if event is None else event["name"])
        with st.form(f"event_edit_{selected_id}_{st.session_state.get('admin_events_epoch', 0)}"):
            name = st.text_input("Nazwa eventu", value=event["name"] if event is not None else "")
            c1, c2 = st.columns(2)
            with c1:
                event_date = st.date_input("Data", value=date.fromisoformat(event["event_date"]) if event is not None else date.today())
                start = st.time_input("Od", value=time.fromisoformat(event["start_time"]) if event is not None else time(10), step=60)
            with c2:
                location = st.text_input("Miejsce", value=(event["location"] or "") if event is not None else "")
                end = st.time_input("Do", value=time.fromisoformat(event["end_time"]) if event is not None else time(20), step=60)
            manager_options = [None] + list(responsible)
            manager_id = st.selectbox("Osoba odpowiedzialna", manager_options,
                index=manager_options.index(event["manager_id"]) if event is not None else 0,
                format_func=lambda uid: "Brak" if uid is None else f"{responsible[uid]['first_name']} {responsible[uid]['last_name']} (ID {uid})")
            people = st.multiselect("Pracownicy", list(candidates), default=current_ids, format_func=label)
            note = st.text_area("Uwagi i dodatkowe informacje", value=(event["note"] or "") if event is not None else "", height=160)
            files = st.file_uploader("Dodaj załączniki", accept_multiple_files=True, help="Maksymalnie 10 MB na plik i 20 plików naraz. Pliki będą dostępne szefowi i przypisanym pracownikom.")
            submitted = st.form_submit_button("Utwórz event" if event is None else "Zapisz zmiany", type="primary", use_container_width=True)
        if submitted:
            if len(files) > 20 or any(f.size > 10 * 1024 * 1024 for f in files):
                st.error("Dodaj maksymalnie 20 plików, każdy do 10 MB.")
            else:
                ok, message = save_event_details(actor_id, None if event is None else event["id"], name, event_date, start, end, location, note, people, manager_id, [(f.name, f.getvalue()) for f in files])
                if ok:
                    st.session_state["admin_event_saved"] = message
                    back_to_admin_list("admin_event_detail_id", "admin_events_epoch")
                else:
                    st.error(message)
        if event is not None:
            st.markdown("### Załączniki")
            event_attachment_downloads(actor_id, event["id"])


def admin_hours_section(users, user):
    st.markdown("### Dodaj zmianę ręcznie")
    st.caption(
        "Przydatne, gdy pracownik zapomniał rozpocząć lub zakończyć zmianę."
    )

    manual_users = [
        u for u in users
        if u["access_level"] != "admin"
    ]

    if manual_users:
        manual_map = {
            f"{u['first_name']} {u['last_name']} — {u['email']}": u
            for u in manual_users
        }

        manual_name = st.selectbox(
            "Pracownik",
            list(manual_map.keys()),
            key="manual_shift_employee",
        )
        manual_employee = manual_map[manual_name]
        manual_groups = [
            g["code"]
            for g in get_render_user_groups(manual_employee["id"])
        ]

        if manual_groups:
            manual_group = st.selectbox(
                "Stanowisko",
                manual_groups,
                format_func=work_group_label,
                key="admin_manual_work_group",
            )

            mc1, mc2 = st.columns(2)

            with mc1:
                manual_date = st.date_input(
                    "Data",
                    value=date.today(),
                    key="manual_shift_date",
                )
                manual_start = st.time_input(
                    "Start",
                    value=time(10, 0),
                    step=300,
                    key="manual_shift_start",
                )

            with mc2:
                manual_end = st.time_input(
                    "Koniec",
                    value=time(18, 0),
                    step=300,
                    key="manual_shift_end",
                )
                manual_note = st.text_input(
                    "Uwagi / powód ręcznego wpisu",
                    key="manual_shift_note",
                )

            if st.button(
                "Dodaj i zatwierdź zmianę",
                type="primary",
                use_container_width=True,
                key="manual_shift_add",
            ):
                start_dt = datetime.combine(
                    manual_date,
                    manual_start,
                ).strftime("%Y-%m-%d %H:%M:%S")
                end_dt = datetime.combine(
                    manual_date,
                    manual_end,
                ).strftime("%Y-%m-%d %H:%M:%S")

                ok, msg = add_manual_shift(
                    manual_employee["id"],
                    start_dt,
                    end_dt,
                    user["id"],
                    manual_group,
                    manual_note,
                    auto_approve=True,
                )

                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.warning(
                "Ta osoba nie ma przypisanego obszaru pracy."
            )

    st.divider()
    st.markdown("### Wszystkie zmiany")

    rows = get_all_shifts()

    if not rows:
        st.info("Brak zmian.")
    else:
        status_filter = st.multiselect(
            "Status",
            ["active", "pending", "approved", "rejected"],
            default=["pending", "approved"],
            format_func=status_label,
        )

        visible = [
            r for r in rows
            if r["approval_status"] in status_filter
        ]

        data = []

        for r in visible:
            summary = shift_summary(r)
            summary["Pracownik"] = (
                f"{r['first_name']} {r['last_name']}"
            )
            summary["Stawka"] = money(r["hourly_rate"])
            data.append(summary)

        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True,
        )


def admin_payments_section(users):
    employee_users = [
        u for u in users
        if u["access_level"] != "admin"
    ]

    if not employee_users:
        st.info("Brak pracowników do rozliczenia.")
    else:
        labels = {
            f"{u['first_name']} {u['last_name']} — {u['email']}": u
            for u in employee_users
        }

        selected_label = st.selectbox(
            "Pracownik",
            list(labels.keys()),
            key="payment_employee",
        )
        selected = labels[selected_label]

        c1, c2 = st.columns(2)

        with c1:
            date_from = st.date_input(
                "Okres od",
                value=date.today().replace(day=1),
                key="payment_from",
            )

        with c2:
            date_to = st.date_input(
                "Okres do",
                value=date.today(),
                key="payment_to",
            )

        unpaid = get_unpaid_approved_shifts(
            selected["id"],
            date_from,
            date_to,
        )

        total_hours = sum(
            int(s["billable_hours"] or 0)
            for s in unpaid
        )
        total_amount = sum(
            float(s["amount"] or 0)
            for s in unpaid
        )

        m1, m2, m3 = st.columns(3)
        m1.metric("Zmiany", len(unpaid))
        m2.metric("Godziny", f"{total_hours} h")
        m3.metric("Kwota", money(total_amount))

        if st.button(
            "Utwórz wypłatę",
            type="primary",
            use_container_width=True,
            disabled=not unpaid,
        ):
            ok, result = create_payment(
                selected["id"],
                date_from,
                date_to,
            )

            if ok:
                st.success(
                    f"Utworzono wypłatę: {money(result)}"
                )
                st.rerun()
            else:
                st.error(result)

        st.divider()

        history_filter = st.selectbox(
            "Pokaż wypłaty",
            ["all", "created", "sent", "received"],
            format_func=lambda x: {
                "all": "Wszystkie",
                "created": "Do wypłaty",
                "sent": "Wysłane",
                "received": "Potwierdzone",
            }[x],
        )

        payments = get_all_payments(history_filter)

        if not payments:
            st.info("Brak wypłat.")
        else:
            for payment in payments:
                st.markdown(
                    f"### {status_icon(payment['status'])} "
                    f"{payment['first_name']} {payment['last_name']} — "
                    f"{money(payment['amount'])}"
                )
                st.write(
                    f"Okres: **{payment['period_from']} – "
                    f"{payment['period_to']}**"
                )
                st.write(
                    f"Status: **{status_label(payment['status'])}**"
                )

                if payment["status"] == "created":
                    if st.button(
                        "Oznacz przelew jako wysłany",
                        key=f"send_{payment['id']}",
                        type="primary",
                    ):
                        mark_payment_sent(payment["id"])
                        st.rerun()

                elif payment["status"] == "sent":
                    st.warning(
                        "Oczekuje na potwierdzenie pracownika."
                    )

                elif payment["status"] == "received":
                    st.success(
                        "Pracownik potwierdził otrzymanie."
                    )

                st.divider()


def admin_panel(user):
    users = get_users()
    page = st.session_state.get("admin_page")
    valid = {key for key, _ in ADMIN_PAGES} | {"settings"}

    if page not in valid:
        page = None
        st.session_state["admin_page"] = None

    title_col, settings_col = st.columns(
        [6, 1],
        gap="small",
        vertical_alignment="center",
    )
    with title_col:
        st.markdown('<div class="admin-panel-heading">Panel szefa</div>',
                    unsafe_allow_html=True)
    with settings_col:
        if st.button(
            "⚙",
            key="admin_settings_button",
            help="Ustawienia mojego konta",
            disabled=page == "settings",
        ):
            st.session_state["admin_page"] = "settings"
            st.rerun()

    admin_navigation()

    if page is None:
        admin_dashboard(users, user)

        if st.button(
            "Wyloguj się",
            use_container_width=True,
            key="admin_logout_home",
        ):
            logout()
        return

    admin_page_header(page)

    if page == "settings":
        own_pin_change_panel(user, "admin")

    elif page == "employees":
        admin_employee_accounts(users)

    elif page == "schedule":
        admin_calendar(users)
        with st.expander("Lista zgłoszonych dni wolnych"):
            admin_availability(users)

    elif page == "events":
        admin_events_section(users)

    elif page == "approvals":
        approval_list(user, "admin", show_money=True)

    elif page == "payments":
        section = st.radio(
            "Rozliczenia",
            ["transfers", "hours", "reports"],
            format_func=lambda value: {"transfers": "Wypłaty", "hours": "Godziny", "reports": "Raporty"}[value],
            horizontal=True,
            key="admin_payments_view",
        )
        if section == "hours":
            admin_hours_section(users, user)
        elif section == "transfers":
            admin_payments_section(users)
        else:
            admin_reports(users)

    st.divider()
    if st.button(
        "Wyloguj się",
        use_container_width=True,
        key=f"admin_logout_{page}",
    ):
        logout()


if "user_id" not in st.session_state:
    login_screen()

else:
    current_user = get_user(st.session_state["user_id"])

    if not current_user:
        logout()

    elif current_user["access_level"] == "admin":
        admin_panel(current_user)

    else:
        employee_panel(current_user)
