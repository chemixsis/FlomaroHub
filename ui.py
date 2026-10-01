import calendar
from datetime import timedelta
from html import escape
import streamlit as st


def money(value):
    return f"{float(value or 0):,.2f} zł".replace(",", "X").replace(".", ",").replace("X", " ")


def minutes_to_text(minutes):
    if minutes is None:
        return "—"
    hours = int(minutes) // 60
    mins = int(minutes) % 60
    return f"{hours} h {mins:02d} min"


def status_label(status):
    return {
        "active": "W trakcie",
        "pending": "Do zatwierdzenia",
        "approved": "Zatwierdzona",
        "rejected": "Odrzucona",
        "created": "Do wypłaty",
        "sent": "Przelew wysłany",
        "received": "Otrzymano",
    }.get(status, status)


def status_icon(status):
    return {
        "active": "🟣",
        "pending": "🟡",
        "approved": "🟢",
        "rejected": "🔴",
        "created": "⚪",
        "sent": "🟡",
        "received": "🟢",
    }.get(status, "⚪")


def apply_styles():
    st.markdown("""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

      :root {
        --flomaro-navy: #0D2947;
        --flomaro-navy-2: #12385E;
        --flomaro-blue: #19476F;
        --flomaro-blue-soft: #2A587E;
        --flomaro-yellow: #E7B843;
        --flomaro-yellow-soft: #F3D98E;
        --flomaro-cream: #FFFFFF;
        --flomaro-text: #F7F4EE;
        --flomaro-muted: #C8D2DC;
        --flomaro-border: rgba(231,184,67,.20);
      }

      html, body, [class*="css"] {
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
      }

      .stApp {
        background:
          radial-gradient(circle at 12% 8%, rgba(42,88,126,.26), transparent 28%),
          linear-gradient(180deg, #0B2744 0%, var(--flomaro-navy) 52%, #0A223B 100%);
      }

      /* Lower the whole app so Streamlit's black top bar never covers the brand. */
      .block-container {
        max-width: 1340px;
        padding-top: 4.9rem;
        padding-bottom: 3.5rem;
      }

      [data-testid="InputInstructions"] {
        display: none !important;
      }

      .brand {
        font-family: "Outfit", "Segoe UI", sans-serif;
        font-size: 3.05rem;
        line-height: 1.06;
        font-weight: 700;
        letter-spacing: -0.045em;
        margin: .35rem 0 .25rem 0;
        color: var(--flomaro-yellow);
      }

      .brand-sub {
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
        color: var(--flomaro-muted);
        letter-spacing: .035em;
        font-size: .9rem;
        margin-bottom: 28px;
      }

      h1, h2, h3 {
        font-family: "Outfit", "Segoe UI", sans-serif;
        color: var(--flomaro-text);
        letter-spacing: -.015em;
      }

      h2 { font-size: 2rem !important; }
      h3 { font-size: 1.55rem !important; }

      p, label, .stCaption {
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
        color: var(--flomaro-muted);
      }


      .stApp, .stApp button, .stApp input, .stApp textarea,
      .stApp label, .stApp select {
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
      }

      /* Logowanie: zawsze białe pola i granatowy tekst — również po Enter. */
      div[data-testid="stForm"] div[data-baseweb="input"],
      div[data-testid="stForm"] div[data-baseweb="input"] > div,
      div[data-testid="stForm"] div[data-baseweb="base-input"],
      div[data-testid="stForm"] input,
      div[data-testid="stTextInput"] input,
      div[data-testid="stTextInput"] input:focus,
      div[data-testid="stTextInput"] input:active,
      div[data-testid="stTextInput"] input:hover {
        background: #FFFFFF !important;
        background-color: #FFFFFF !important;
        color: #12385E !important;
        -webkit-text-fill-color: #12385E !important;
        caret-color: #12385E !important;
      }

      .stApp input:-webkit-autofill,
      .stApp input:-webkit-autofill:hover,
      .stApp input:-webkit-autofill:focus,
      .stApp input:-webkit-autofill:active {
        -webkit-box-shadow: 0 0 0 1000px #FFFFFF inset !important;
        -webkit-text-fill-color: #12385E !important;
        caret-color: #12385E !important;
      }

      div[data-testid="stTextInput"] input::placeholder {
        color: #607993 !important;
        opacity: 1;
      }

      /* E-mail przy logowaniu: pogrubiona czcionka także podczas wpisywania. */
      div[class*="st-key-login_email"] input,
      div[class*="st-key-login_email"] input:focus,
      div[data-testid="stForm"]:has(input[aria-label="PIN"]) input[aria-label="E-mail"] {
        font-weight: 700 !important;
      }

      /* Kafelki z przyciskami: cały kwadrat jest klikalny. */
      div[class*="st-key-admin_nav_"] button {
        aspect-ratio: 1.12 / 1;
        width: 100%;
        min-height: 168px;
        padding: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        border-radius: 22px;
        background: linear-gradient(145deg, #24577C, #12385E);
        border: 1px solid rgba(231,184,67,.24);
        font-family: "Outfit", "Segoe UI", sans-serif;
        font-size: 1.5rem;
        font-weight: 600;
        letter-spacing: -.025em;
        color: #F7F4EE;
      }

      div[class*="st-key-admin_nav_"] button:hover {
        border-color: #E7B843;
        background: linear-gradient(145deg, #2D6286, #19476F);
        color: #F3D98E;
      }

      div[class*="st-key-admin_nav_"] button p {
        font-family: "Outfit", "Segoe UI", sans-serif;
        width: 100%;
        text-align: center;
        color: inherit;
        font-size: inherit;
        font-weight: inherit;
      }

      /* Nagłówek panelu szefa i ikonka ustawień obok nazwy. */
      .admin-panel-heading {
        font-family: "Outfit", "Segoe UI", sans-serif;
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -.02em;
        line-height: 1.2;
        color: var(--flomaro-text);
        white-space: nowrap;
      }

      div[class*="st-key-admin_settings_button"] button {
        min-height: 42px;
        width: 42px;
        padding: 0;
        border-radius: 12px;
        font-size: 1.55rem;
        color: var(--flomaro-yellow-soft);
      }

      /* Metrics / content cards */
      div[data-testid="stMetric"] {
        border: 1px solid var(--flomaro-border);
        border-radius: 20px;
        padding: 17px 18px;
        background: rgba(25,71,111,.74);
        box-shadow: 0 12px 28px rgba(0,0,0,.12);
      }

      div[data-testid="stMetric"] label {
        color: var(--flomaro-muted) !important;
      }

      div[data-testid="stMetric"] div {
        color: var(--flomaro-text) !important;
      }

      /* Standard buttons */
      div[data-testid="stButton"] > button,
      div[data-testid="stFormSubmitButton"] > button {
        border-radius: 13px;
        border: 1px solid rgba(231,184,67,.25);
        min-height: 45px;
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
        font-weight: 650;
        background: rgba(25,71,111,.82);
        color: var(--flomaro-text);
        transition: transform .12s ease, border-color .12s ease, background .12s ease;
      }

      div[data-testid="stButton"] > button:hover,
      div[data-testid="stFormSubmitButton"] > button:hover {
        border-color: var(--flomaro-yellow);
        color: var(--flomaro-yellow-soft);
        background: var(--flomaro-blue-soft);
        transform: translateY(-1px);
      }

      button[kind^="primary"],
      div[data-testid="stFormSubmitButton"] button[kind^="primary"] {
        background: var(--flomaro-yellow) !important;
        border-color: var(--flomaro-yellow) !important;
        color: var(--flomaro-navy) !important;
      }

      button[kind^="primary"]:hover,
      div[data-testid="stFormSubmitButton"] button[kind^="primary"]:hover {
        background: var(--flomaro-yellow-soft) !important;
        color: var(--flomaro-navy) !important;
      }

      /* Labels follow the button color, including nested Markdown text.
         Yellow buttons use navy; dark-blue button overrides stay white. */
      button[kind^="primary"],
      button[kind^="primary"] * {
        -webkit-text-fill-color: currentColor !important;
      }
      button[kind^="primary"] * {
        color: inherit !important;
      }

      /* Inputs - warm cream instead of bright white */
      div[data-baseweb="input"],
      div[data-baseweb="select"] > div,
      textarea,
      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input,
      div[data-testid="stDateInput"] input,
      div[data-testid="stTimeInput"] input {
        background: var(--flomaro-cream) !important;
        color: var(--flomaro-navy) !important;
        border-radius: 11px !important;
      }

      div[data-baseweb="input"]:focus-within {
        border-color: var(--flomaro-yellow) !important;
        box-shadow: 0 0 0 1px var(--flomaro-yellow) !important;
        background: #FFFFFF !important;
      }

      /* Forms / panels */
      div[data-testid="stForm"],
      div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(18,56,94,.80);
        border: 1px solid var(--flomaro-border) !important;
        border-radius: 22px !important;
        box-shadow: 0 16px 38px rgba(0,0,0,.10);
      }

      div[data-testid="stForm"] {
        padding: 20px;
      }

      div[data-testid="stForm"] label,
      div[data-testid="stForm"] p,
      div[data-testid="stForm"] span,
      div[data-testid="stVerticalBlockBorderWrapper"] p,
      div[data-testid="stVerticalBlockBorderWrapper"] label {
        color: var(--flomaro-muted);
      }

      /* Expanders / tabs */
      details,
      div[data-testid="stExpander"] {
        background: rgba(18,56,94,.72);
        border: 1px solid rgba(231,184,67,.14);
        border-radius: 16px;
      }

      div[data-testid="stExpander"] * {
        color: var(--flomaro-text);
      }

      div[data-baseweb="tab-list"] {
        background: rgba(18,56,94,.70);
        border-radius: 14px;
        padding: 4px;
      }

      div[data-baseweb="tab-list"] button {
        color: var(--flomaro-text) !important;
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
      }

      /* ADMIN HOME */
      .admin-home-intro {
        margin: 6px 0 18px 0;
      }

      .admin-home-title {
        font-family: "Outfit", "Segoe UI", sans-serif;
        color: var(--flomaro-text);
        font-size: 2.05rem;
        font-weight: 700;
        line-height: 1;
        margin-bottom: 6px;
      }

      .admin-home-subtitle {
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
        color: var(--flomaro-muted);
        font-size: .9rem;
      }

      .admin-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 16px;
        margin: 8px 0 24px 0;
      }

      .admin-tile {
        aspect-ratio: 1 / .88;
        min-height: 150px;
        display: flex;
        align-items: flex-end;
        justify-content: flex-start;
        padding: 20px;
        border-radius: 24px;
        border: 1px solid rgba(231,184,67,.18);
        background:
          linear-gradient(145deg, rgba(42,88,126,.92), rgba(18,56,94,.96));
        color: var(--flomaro-text) !important;
        text-decoration: none !important;
        box-shadow: 0 14px 34px rgba(0,0,0,.13);
        transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
      }

      .admin-tile:hover {
        transform: translateY(-4px);
        border-color: rgba(231,184,67,.70);
        box-shadow: 0 20px 42px rgba(0,0,0,.18);
      }

      .admin-tile span {
        font-family: "Outfit", "Segoe UI", sans-serif;
        font-size: 1.5rem;
        font-weight: 700;
        line-height: 1;
        color: var(--flomaro-text);
      }

      .admin-tile:hover span {
        color: var(--flomaro-yellow-soft);
      }

      .admin-page-top {
        display: flex;
        align-items: center;
        gap: 16px;
        margin: 2px 0 22px 0;
      }

      .admin-back {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 94px;
        min-height: 42px;
        padding: 0 14px;
        border-radius: 13px;
        border: 1px solid rgba(231,184,67,.28);
        background: rgba(25,71,111,.80);
        color: var(--flomaro-text) !important;
        text-decoration: none !important;
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
        font-size: .88rem;
        font-weight: 650;
      }

      .admin-back:hover {
        border-color: var(--flomaro-yellow);
        color: var(--flomaro-yellow-soft) !important;
      }

      .admin-page-name {
        font-family: "Outfit", "Segoe UI", sans-serif;
        color: var(--flomaro-yellow);
        font-size: 2.05rem;
        font-weight: 700;
        line-height: 1;
      }

      /* Calendar */

      /* Monthly work roster */
      .roster-calendar {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: 9px;
        margin: 12px 0 24px 0;
      }

      .roster-calendar-head {
        text-align: center;
        padding: 7px 4px;
        font-size: .79rem;
        font-weight: 750;
        color: var(--flomaro-yellow);
      }

      .roster-calendar-day {
        min-height: 160px;
        padding: 10px;
        border-radius: 15px;
        border: 1px solid rgba(246,198,46,.16);
        background: var(--flomaro-blue);
        overflow: hidden;
      }

      .roster-calendar-empty {
        opacity: .20;
        min-height: 160px;
      }

      .roster-date {
        font-size: 1rem;
        font-weight: 800;
        color: var(--flomaro-yellow);
        margin-bottom: 8px;
      }

      .roster-place {
        border-radius: 9px;
        padding: 7px 8px;
        margin-bottom: 7px;
        font-size: .74rem;
        line-height: 1.3;
        color: white;
      }

      .roster-place-label {
        font-weight: 800;
        font-size: .68rem;
        text-transform: uppercase;
        letter-spacing: .035em;
        margin-bottom: 3px;
      }

      .roster-warehouse {
        background: rgba(255,255,255,.09);
        border-left: 3px solid var(--flomaro-yellow);
      }

      .roster-local {
        background: rgba(220,232,244,.10);
        border-left: 3px solid #8FB7D8;
      }

      .roster-off {
        background: rgba(255,255,255,.05);
        border-left: 3px solid rgba(255,255,255,.38);
        opacity: .78;
      }

      .roster-no-work {
        color: rgba(255,255,255,.38);
        font-size: .73rem;
        padding-top: 8px;
      }

      @media (max-width: 900px) {
        .roster-calendar {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .roster-calendar-head {
          display: none;
        }

        .roster-calendar-empty {
          display: none;
        }

        .roster-calendar-day {
          min-height: 130px;
        }
      }

      .calendar {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: 9px;
        margin: 12px 0 18px;
      }

      .cal-head {
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
        font-size: .78rem;
        font-weight: 700;
        color: var(--flomaro-yellow-soft);
        padding: 7px 8px;
        text-align: center;
      }

      .cal-day {
        min-height: 118px;
        border: 1px solid rgba(231,184,67,.16);
        border-radius: 16px;
        padding: 10px;
        background: rgba(18,56,94,.72);
      }

      .cal-day.empty {
        opacity: .38;
      }

      .cal-date {
        font-size: .79rem;
        font-weight: 700;
        color: var(--flomaro-yellow-soft);
        margin-bottom: 7px;
      }

      .cal-event {
        border-left: 3px solid var(--flomaro-yellow);
        background: rgba(231,184,67,.095);
        color: var(--flomaro-text);
        border-radius: 8px;
        padding: 6px 7px;
        margin: 5px 0;
        font-size: .76rem;
        line-height: 1.3;
      }

      .week-day {
        min-height: 180px;
      }

      div[data-testid="stAlert"] {
        border-radius: 15px;
      }

      @media (max-width: 1100px) {
        .admin-grid {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
      }

      @media (max-width: 720px) {
        .block-container {
          padding-top: 4.4rem;
        }

        .brand {
          font-size: 2.75rem;
        }

        .admin-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .admin-tile {
          min-height: 130px;
        }
      }
      /* Kalendarz eventów: cały miesiąc i klikalne wydarzenia. */
      .employee-event-month-title {
        font-family: "Outfit", "Segoe UI", sans-serif;
        color: #F3D98E;
        font-size: 1.55rem;
        font-weight: 700;
        text-align: center;
        padding-top: .3rem;
      }
      .employee-event-weekday {
        color: #F3D98E;
        font-weight: 700;
        text-align: center;
        padding: .4rem 0 .7rem;
      }
      .employee-event-date {
        color: #F3D98E;
        font-weight: 700;
        font-size: 1.05rem;
        margin-bottom: .4rem;
      }
      /* Keep empty day slots the same size as days with events. */
      .employee-event-empty {
        height: 180px;
        box-sizing: border-box;
        border: 1px solid rgba(231,184,67,.10);
        border-radius: 15px;
        background: rgba(18,56,94,.22);
      }
      /* Long event names wrap instead of forcing the day wider. */
      div[class*="st-key-employee_event_"] button {
        max-width: 100%;
      }
      div[class*="st-key-employee_event_"] button {
        white-space: pre-line;
        overflow-wrap: anywhere;
        height: auto;
        min-height: 3.9rem;
        font-size: .85rem;
        padding: .5rem .3rem;
        border-color: #E7B843;
      }

      /* Pogrubione przyciski Poprzedni / Następny w kalendarzu eventów. */
      .st-key-warehouse_event_prev button,
      .st-key-warehouse_event_next button,
      div[class*="st-key-employee_event_prev"] button,
      div[class*="st-key-employee_event_next"] button {
        font-family: "Outfit", "Segoe UI", sans-serif !important;
        font-size: 1rem !important;
        font-weight: 800 !important;
        letter-spacing: -.01em;
      }
      .st-key-warehouse_event_prev button p,
      .st-key-warehouse_event_next button p,
      .st-key-warehouse_event_prev button span,
      .st-key-warehouse_event_next button span,
      div[class*="st-key-employee_event_prev"] button p,
      div[class*="st-key-employee_event_next"] button p,
      div[class*="st-key-employee_event_prev"] button span,
      div[class*="st-key-employee_event_next"] button span {
        font-family: inherit !important;
        font-size: inherit !important;
        font-weight: 800 !important;
        color: inherit;
      }

      /* Rejestracja zmiany pracownika: granatowe tło i pogrubiony tekst. */
      .st-key-employee_start_shift button,
      .st-key-employee_end_shift button,
      .st-key-employee_start_shift button:hover,
      .st-key-employee_end_shift button:hover,
      .st-key-employee_start_shift button:focus,
      .st-key-employee_end_shift button:focus {
        background: #12385E !important;
        background-color: #12385E !important;
        color: #FFFFFF !important;
        border-color: #E7B843 !important;
        font-weight: 800 !important;
      }
      .st-key-employee_start_shift button p,
      .st-key-employee_end_shift button p,
      .st-key-employee_start_shift button span,
      .st-key-employee_end_shift button span {
        color: inherit !important;
        font-weight: 800 !important;
      }

      /* Tylko eventowy formularz dni wolnych. */
      div[class*="st-key-event_only_day_off_save"] button,
      div[class*="st-key-event_only_day_off_save"] button[kind^="primary"],
      div[class*="st-key-event_only_day_off_save"] button:hover {
        background: #12385E !important;
        background-color: #12385E !important;
        color: #FFFFFF !important;
        border-color: #E7B843 !important;
      }
      div[class*="st-key-event_only_day_off_note"] input,
      div[class*="st-key-event_only_day_off_note"] input:focus,
      div[class*="st-key-event_only_day_off_note"] input:hover,
      div[class*="st-key-event_only_day_off_note"] div[data-baseweb="input"],
      div[class*="st-key-event_only_day_off_note"] div[data-baseweb="base-input"] {
        background: #12385E !important;
        background-color: #12385E !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        caret-color: #FFFFFF !important;
      }
      div[class*="st-key-event_only_day_off_note"] input::placeholder {
        color: #C8D2DC !important;
        -webkit-text-fill-color: #C8D2DC !important;
      }
      div[class*="st-key-event_only_day_off_note"] input:-webkit-autofill {
        -webkit-box-shadow: 0 0 0 1000px #12385E inset !important;
        -webkit-text-fill-color: #FFFFFF !important;
      }
      /* Formularz dni wolnych pracownika magazynu. */
      div[class*="st-key-warehouse_day_off_save"] button,
      div[class*="st-key-warehouse_day_off_save"] button[kind^="primary"],
      div[class*="st-key-warehouse_day_off_save"] button:hover {
        background: #12385E !important;
        background-color: #12385E !important;
        color: #FFFFFF !important;
        border-color: #E7B843 !important;
      }
      div[class*="st-key-warehouse_day_off_note"] input,
      div[class*="st-key-warehouse_day_off_note"] input:focus,
      div[class*="st-key-warehouse_day_off_note"] input:hover,
      div[class*="st-key-warehouse_day_off_note"] div[data-baseweb="input"],
      div[class*="st-key-warehouse_day_off_note"] div[data-baseweb="base-input"] {
        background: #12385E !important;
        background-color: #12385E !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        caret-color: #FFFFFF !important;
      }
      div[class*="st-key-warehouse_day_off_note"] input::placeholder {
        color: #C8D2DC !important;
        -webkit-text-fill-color: #C8D2DC !important;
      }
      div[class*="st-key-warehouse_day_off_note"] input:-webkit-autofill {
        -webkit-box-shadow: 0 0 0 1000px #12385E inset !important;
        -webkit-text-fill-color: #FFFFFF !important;
      }

      /* Keep label contrast explicit, including form-submit button variants. */
      button[kind^="primary"] {
        --button-label-color: #0D2947;
        color: var(--button-label-color) !important;
      }
      button[kind^="primary"] * {
        color: var(--button-label-color) !important;
        -webkit-text-fill-color: var(--button-label-color) !important;
      }
      .st-key-employee_start_shift button,
      .st-key-employee_end_shift button,
      .st-key-warehouse_day_off_save button,
      .st-key-event_only_day_off_save button {
        --button-label-color: #FFFFFF;
      }
      .st-key-employee_area_back button,
      .st-key-employee_area_back button * {
        font-weight: 800 !important;
      }
      .st-key-login_panel {
        width: 100%;
        max-width: 480px;
        margin-inline: auto;
      }
      .stApp [data-testid="stColumn"] { min-width: 0; }
      .stApp button { overflow-wrap: anywhere; }
      .stApp input, .stApp textarea { font-size: 16px !important; }
      [data-baseweb="tab-list"] {
        overflow-x: auto;
        flex-wrap: nowrap;
        max-width: 100%;
      }
      [data-baseweb="tab"] { flex-shrink: 0; }
      .st-key-event_calendar_grid,
      .st-key-regular_calendar_grid {
        overflow-x: auto;
        max-width: 100%;
        padding-bottom: 8px;
      }
      :is(.st-key-event_calendar_grid, .st-key-regular_calendar_grid) [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        min-width: 630px;
        gap: 8px;
      }
      :is(.st-key-event_calendar_grid, .st-key-regular_calendar_grid) [data-testid="stColumn"] {
        flex: 1 1 0 !important;
        min-width: 82px !important;
        width: 0 !important;
      }
      @media (max-width: 900px) {
        .block-container { padding-inline: 1.25rem; }
        .brand { font-size: 2.5rem; }
        .admin-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      }
      @media (max-width: 640px) {
        .block-container { padding: 4rem .75rem 2rem; }
        .brand { font-size: 2.1rem; }
        .brand-sub { font-size: .8rem; margin-bottom: 18px; }
        h2 { font-size: 1.6rem !important; }
        h3 { font-size: 1.25rem !important; }
        .stApp [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
        .stApp [data-testid="stColumn"] {
          flex: 1 1 100%; width: 100%; min-width: 0;
        }
        .stApp button { min-height: 44px; }
        .admin-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
        .admin-page-top { flex-wrap: wrap; }
        [data-testid="stMetricValue"] { font-size: 1.6rem; }
      }

      /* Prominent greeting and compact, persistent boss navigation. */
      .st-key-login_submit button,
      .st-key-login_submit button *,
      .st-key-employee_greeting h3,
      .st-key-employee_greeting h3 * {
        font-weight: 800 !important;
      }
      .st-key-employee_greeting h3 { color: #FFFFFF !important; }
      .st-key-admin_navbar div[class*="st-key-admin_nav_"] button {
        aspect-ratio: auto;
        min-height: 64px;
        padding: 12px 10px;
        border-radius: 14px;
        font-size: 1rem;
        font-weight: 750;
      }
      .st-key-admin_navbar button:disabled {
        opacity: 1;
        background: #E7B843 !important;
        color: #0D2947 !important;
      }
      .st-key-admin_navbar button:disabled * {
        color: #0D2947 !important;
        -webkit-text-fill-color: #0D2947 !important;
      }
      .st-key-admin_overview [data-testid="stMetric"] {
        height: 100%;
        padding: 18px;
        border-radius: 16px;
        border: 1px solid rgba(231,184,67,.25);
        background: #12385E;
      }
      .st-key-admin_overview [data-testid="stMetricLabel"] p { color: #FFFFFF; }
      .st-key-admin_overview [data-testid="stMetricValue"] {
        font-size: clamp(1.4rem, 2.2vw, 2rem);
        overflow-wrap: anywhere;
      }
      @media (max-width: 900px) {
        .st-key-admin_navbar [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
        .st-key-admin_navbar [data-testid="stColumn"] {
          flex: 1 1 calc(33.333% - 16px); min-width: 0; width: auto;
        }
      }
      @media (max-width: 640px) {
        .st-key-admin_navbar [data-testid="stColumn"] {
          flex: 1 1 calc(50% - 16px); min-width: 0; width: auto;
        }
        .st-key-admin_navbar div[class*="st-key-admin_nav_"] button { min-height: 52px; }
        .admin-panel-heading { white-space: normal; }
      }

      .roster-event { border-left: 3px solid #E7B843; background: rgba(231,184,67,.10); }
      .stApp .st-key-admin_event_editor [data-testid="stForm"] input,
      .stApp .st-key-admin_event_editor [data-testid="stForm"] textarea,
      .stApp .st-key-admin_event_editor [data-testid="stForm"] [data-baseweb="input"],
      .stApp .st-key-admin_event_editor [data-testid="stForm"] [data-baseweb="input"] > div,
      .stApp .st-key-admin_event_editor [data-testid="stForm"] [data-baseweb="base-input"],
      .stApp .st-key-admin_event_editor [data-testid="stForm"] [data-baseweb="select"] > div,
      .stApp .st-key-admin_event_editor [data-testid="stForm"] [data-testid="stFileUploaderDropzone"] {
        background: #12385E !important;
        background-color: #12385E !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        caret-color: #FFFFFF !important;
      }
      .stApp .st-key-admin_event_editor [data-testid="stForm"] [data-baseweb="select"] > div * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
      }
      .stApp .st-key-admin_event_editor [data-testid="stForm"] [data-baseweb="tag"] { background: #19476F !important; }
      .stApp .st-key-admin_event_editor [data-testid="stForm"] input:-webkit-autofill {
        -webkit-box-shadow: 0 0 0 1000px #12385E inset !important;
        -webkit-text-fill-color: #FFFFFF !important;
      }
    </style>
    """, unsafe_allow_html=True)



def header():
    st.markdown('<div class="brand">FlomaroHUB</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="brand-sub">Grafiki • Godziny • Eventy • Wypłaty</div>',
        unsafe_allow_html=True,
    )


def _event_html(row, show_name=True):
    name = ""
    if show_name:
        name = (
            f"<strong>{escape(row['first_name'])} "
            f"{escape(row['last_name'])}</strong>"
        )

    note = f"<br>{escape(row['note'])}" if row["note"] else ""

    # Grafik lokal/magazyn nie ma godzin.
    if not row["start_time"] and not row["end_time"]:
        return (
            '<div class="cal-event">'
            f'{name}{note}</div>'
        )

    time_part = (
        f"{escape(row['start_time'])}–{escape(row['end_time'])}"
    )
    separator = "<br>" if name else ""

    return (
        '<div class="cal-event">'
        f'{name}{separator}{time_part}{note}</div>'
    )


def render_roster_calendar(
    rows,
    users,
    anchor_date,
    days_off_rows=None,
    show_days_off=False,
    event_rows=None,
):
    """
    Monthly visual roster calendar.
    Each day shows employees grouped by workplace.
    """
    last_day = calendar.monthrange(
        anchor_date.year,
        anchor_date.month,
    )[1]

    assignments = {}
    for row in rows:
        key = row["work_date"]
        assignments.setdefault(
            key,
            {
                "warehouse": [],
                "local": [],
            },
        )

        if row["work_group"] in ("warehouse", "local"):
            assignments[key][row["work_group"]].append(
                f"{row['first_name']} {row['last_name']}"
            )

    events_by_day = {}
    for event in event_rows or []:
        events_by_day.setdefault(event["event_date"], []).append(event)

    days_off = {}
    if days_off_rows:
        for row in days_off_rows:
            days_off.setdefault(
                row["availability_date"],
                [],
            ).append(
                f"{row['first_name']} {row['last_name']}"
            )

    weekday_names = [
        "Pon",
        "Wt",
        "Śr",
        "Czw",
        "Pt",
        "Sob",
        "Nd",
    ]

    html = '<div class="roster-calendar">'

    for weekday in weekday_names:
        html += (
            '<div class="roster-calendar-head">'
            f'{weekday}'
            '</div>'
        )

    first_day = anchor_date.replace(day=1)
    empty_before = first_day.weekday()

    for _ in range(empty_before):
        html += (
            '<div class="roster-calendar-day '
            'roster-calendar-empty"></div>'
        )

    for day_number in range(1, last_day + 1):
        day = anchor_date.replace(day=day_number)
        date_key = day.isoformat()

        day_assignments = assignments.get(
            date_key,
            {
                "warehouse": [],
                "local": [],
            },
        )

        warehouse_people = day_assignments["warehouse"]
        local_people = day_assignments["local"]
        free_people = days_off.get(date_key, [])

        html += '<div class="roster-calendar-day">'
        html += (
            '<div class="roster-date">'
            f'{day_number}'
            '</div>'
        )

        if warehouse_people:
            html += (
                '<div class="roster-place roster-warehouse">'
                '<div class="roster-place-label">Magazyn</div>'
                f'<div>{escape(", ".join(warehouse_people))}</div>'
                '</div>'
            )

        if local_people:
            html += (
                '<div class="roster-place roster-local">'
                '<div class="roster-place-label">Lokal</div>'
                f'<div>{escape(", ".join(local_people))}</div>'
                '</div>'
            )

        if show_days_off and free_people:
            html += (
                '<div class="roster-place roster-off">'
                '<div class="roster-place-label">Wolne</div>'
                f'<div>{escape(", ".join(free_people))}</div>'
                '</div>'
            )

        for event in events_by_day.get(date_key, []):
            html += (
                '<div class="roster-place roster-event">'
                '<div class="roster-place-label">Eventy</div>'
                f'<strong>{escape(event["name"])}</strong>'
                f'<div>{escape(event["start_time"])}–{escape(event["end_time"])}</div>'
                f'<div>{escape(event["people"] or "Brak przypisanej obsady")}</div>'
                '</div>'
            )

        if not warehouse_people and not local_people and not events_by_day.get(date_key):
            html += (
                '<div class="roster-no-work">'
                'Brak obsady'
                '</div>'
            )

        html += '</div>'

    total_cells = empty_before + last_day
    empty_after = (7 - (total_cells % 7)) % 7

    for _ in range(empty_after):
        html += (
            '<div class="roster-calendar-day '
            'roster-calendar-empty"></div>'
        )

    html += '</div>'

    st.markdown(
        html,
        unsafe_allow_html=True,
    )



def render_week_calendar(rows, week_start, show_names=True):
    days = [week_start + timedelta(days=i) for i in range(7)]
    by_date = {}

    for row in rows:
        by_date.setdefault(row["work_date"], []).append(row)

    html = '<div class="calendar">'
    day_names = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]

    for name, day in zip(day_names, days):
        html += f'<div class="cal-head">{name}<br>{day.strftime("%d.%m")}</div>'

    for day in days:
        html += '<div class="cal-day week-day">'
        html += f'<div class="cal-date">{day.strftime("%d.%m.%Y")}</div>'

        for row in by_date.get(day.isoformat(), []):
            html += _event_html(row, show_names)

        html += '</div>'

    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_month_calendar(rows, anchor_date, show_names=True):
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(anchor_date.year, anchor_date.month)
    by_date = {}

    for row in rows:
        by_date.setdefault(row["work_date"], []).append(row)

    html = '<div class="calendar">'
    for name in ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]:
        html += f'<div class="cal-head">{name}</div>'

    for week in weeks:
        for day in week:
            extra = " empty" if day.month != anchor_date.month else ""
            html += f'<div class="cal-day{extra}">'
            html += f'<div class="cal-date">{day.day}</div>'

            for row in by_date.get(day.isoformat(), []):
                html += _event_html(row, show_names)

            html += '</div>'

    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def login_keyboard():
    """Local keyboard behavior: email Enter focuses PIN without submission."""
    st.html("""
    <script>
    (() => {
      if (window.flomaroLoginKeydown) {
        document.removeEventListener('keydown', window.flomaroLoginKeydown, true);
      }
      window.flomaroLoginKeydown = (event) => {
        if (event.key !== 'Enter' || event.isComposing) return;
        if (!event.target.matches('.st-key-login_email input')) return;
        const pin = document.querySelector('.st-key-login_pin input');
        if (!pin) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        pin.focus();
      };
      document.addEventListener('keydown', window.flomaroLoginKeydown, true);
      const email = document.querySelector('.st-key-login_email input');
      const pin = document.querySelector('.st-key-login_pin input');
      if (email) {
        email.setAttribute('enterkeyhint', 'next');
        email.setAttribute('inputmode', 'email');
        email.setAttribute('autocomplete', 'username');
      }
      if (pin) {
        pin.setAttribute('enterkeyhint', 'go');
        pin.setAttribute('inputmode', 'numeric');
        pin.setAttribute('autocomplete', 'current-password');
      }
    })();
    </script>
    """, unsafe_allow_javascript=True)
