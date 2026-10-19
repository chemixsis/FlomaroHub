"""Small shared UI panels; database work is deferred until interaction."""
from datetime import date
from uuid import uuid4
import streamlit as st
from cloud_config import setting
from delivery import DeliveryWorker, configured, delivery_status, submit_problem
from payroll import weekly_breakdown
from ui import money, minutes_to_text


def delivery_config():
    return {key:setting(key,'') for key in ('RESEND_API_KEY','EMAIL_FROM','SMSAPI_TOKEN','SMSAPI_SENDER')}


@st.cache_resource
def start_delivery_worker():
    config=delivery_config()
    if setting('DELIVERY_ENABLED',False) is not True: return None
    if not any(configured(c,config) for c in ('email','sms')): return None
    return DeliveryWorker(config)


def report_problem_panel(user):
    with st.expander('Zgłoś problem'):
        st.caption('Zgłoszenie trafi do Ariny: arinametluk@gmail.com. Opisz, co się stało; nie wpisuj PIN-u ani haseł.')
        if 'support_token' not in st.session_state: st.session_state['support_token']=str(uuid4())
        with st.form('report_problem_form',clear_on_submit=True):
            subject=st.text_input('Temat problemu',max_chars=120)
            description=st.text_area('Co się stało?',max_chars=5000,height=140)
            submitted=st.form_submit_button('Wyślij zgłoszenie',type='primary')
        if submitted:
            page=str(st.session_state.get('admin_page') or st.session_state.get('employee_area') or 'konto pracownika')
            ok,message=submit_problem(user['id'],subject,description,page,st.session_state['support_token'])
            if ok:
                st.session_state['support_token']=str(uuid4())
                st.success(message)
                if setting('DELIVERY_ENABLED',False) is not True or not configured('email',delivery_config()):
                    st.warning('Zgłoszenie jest zapisane, ale wysyłka e-mail czeka na konfigurację właściciela.')
                worker=start_delivery_worker()
                if worker: worker.wake.set()
            else: st.error(message)


def weekly_panel(shifts,summary):
    st.markdown('### Rozliczenia tygodniowe')
    st.caption('Poniedziałek–niedziela. Liczymy pełne przepracowane minuty × stawkę / 60. Kwotę wypłaty ustalamy do grosza po zsumowaniu tygodnia. Data rozpoczęcia zmiany wyznacza tydzień.')
    for week in weekly_breakdown(shifts):
        label=f"{week['start']:%d.%m.%Y}–{week['end']:%d.%m.%Y} · do rozliczenia {money(week['amount'])}"
        with st.expander(label):
            st.write(f"Czas (bez odrzuconych): **{minutes_to_text(week['minutes'])}**")
            if week['pending']: st.info(f"Dodatkowo oczekuje na zatwierdzenie: {money(week['pending_amount'])}.")
            st.dataframe([summary(row) for row in week['rows']],use_container_width=True,hide_index=True)
            st.caption('Kwoty poszczególnych zmian wyświetlamy do grosza. Suma tygodnia jest liczona przed zaokrągleniem, więc może różnić się o grosz od sumy widocznych wierszy. Utworzone już wypłaty pozostają w historii.')


def delivery_admin_panel(user):
    with st.expander('E-maile i SMS-y — stan wysyłki'):
        config=delivery_config()
        enabled=setting('DELIVERY_ENABLED',False) is True
        st.write('E-mail: '+('skonfigurowany' if configured('email',config) and enabled else 'wymaga konfiguracji'))
        st.write('SMS: '+('skonfigurowany' if configured('sms',config) and enabled else 'wymaga konfiguracji'))
        st.caption('Status „Przekazano dostawcy” nie potwierdza doręczenia do skrzynki lub telefonu. Kolejka działa, kiedy serwer aplikacji jest uruchomiony.')
        if st.button('Sprawdź kolejkę wiadomości',key='check_delivery_queue'):
            names={'queued':'Oczekuje','sending':'W trakcie wysyłki','sent':'Przekazano dostawcy','failed':'Błąd — sprawdź konfigurację','unknown':'Wymaga sprawdzenia u dostawcy','cancelled':'Anulowano'}
            rows=delivery_status(user['id'])
            st.dataframe([{'Kanał':r['channel'],'Stan':names.get(r['status'],r['status']),'Liczba':r['count']} for r in rows],hide_index=True)
