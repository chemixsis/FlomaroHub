from datetime import date
import json
import streamlit as st
from schedule_proposals import context, submit, decide

LABELS = {'local':'Lokal', None:'Wolne od grafiku', 'unchanged':'Bez zmian'}
STATUSES = {'pending':'Czeka na szefa','accepted':'Zaakceptowana','rejected':'Odrzucona'}


def proposals_panel(user, admin=False):
    people, proposals = context(user['id'])
    if not admin and user['id'] not in {p['id'] for p in people}:
        return
    names = {p['id']:f"{p['first_name']} {p['last_name']}" for p in people}
    if admin:
        admin_proposals_panel(user, proposals, names)
        return
    with st.expander('Propozycje grafiku' + (' — do zatwierdzenia' if admin else ' — zaproponuj zmianę')):
        st.caption('Propozycje dotyczą lokalu. Obowiązują dopiero po akceptacji szefa. Możesz zaproponować własny dzień albo wspólną zamianę. Wybranie lokalu zastąpi ewentualny magazyn w tym dniu.')
        if not admin:
            with st.form('propose_roster'):
                day = st.date_input('Dzień proponowanej zmiany',min_value=date.today())
                assignments = {}
                for person in people:
                    assignments[person['id']] = st.selectbox(names[person['id']], ['unchanged','local',None],format_func=lambda x:LABELS[x],key=f"proposal_person_{person['id']}")
                note = st.text_area('Wyjaśnienie / uzgodniona zamiana',max_chars=1000)
                send = st.form_submit_button('Zaproponuj szefowi',type='primary')
            if send:
                changes = {uid:value for uid,value in assignments.items() if value!='unchanged'}
                if user['id'] not in changes:
                    st.error('Wybierz również proponowany status swojego dnia.')
                else:
                    ok,msg = submit(user['id'],day,changes,note)
                    if ok:
                        st.session_state['proposal_flash'] = msg
                        st.rerun()
                    else: st.error(msg)
        if 'proposal_flash' in st.session_state:
            st.success(st.session_state.pop('proposal_flash'))
        if not proposals: st.info('Brak propozycji.')
        for p in proposals:
            st.markdown(f"**{p['work_date']} · {p['first_name']} {p['last_name']} · {STATUSES[p['status']]}**")
            for uid,group in json.loads(p['assignments']).items():
                st.write(f"{names.get(int(uid),'Konto nieaktywne')}: {LABELS[group]}")
            if p['note']: st.write(p['note'])
            if p['decision_note']: st.caption('Decyzja szefa: '+p['decision_note'])
            if admin and p['status']=='pending':
                with st.form('review_'+p['id']):
                    reason = st.text_input('Uwagi do decyzji',key='reason_'+p['id'],max_chars=1000)
                    yes = st.form_submit_button('Akceptuj',type='primary')
                    no = st.form_submit_button('Odrzuć')
                if yes or no:
                    ok,msg = decide(user['id'],p['id'],yes,reason)
                    if ok:
                        st.session_state['proposal_flash'] = msg
                        st.rerun()
                    else: st.error(msg)
            st.divider()


def proposal_card(user, proposal, names):
    p = proposal
    day = date.fromisoformat(str(p['work_date'])[:10])
    with st.container(border=True, key='proposal_card_'+str(p['id'])):
        left, right = st.columns([3, 2])
        left.markdown(f"### {day:%d.%m.%Y}")
        right.caption(STATUSES[p['status']])
        st.caption(f"Zgłasza: {p['first_name']} {p['last_name']}")
        st.dataframe([
            {'Pracownik': names.get(int(uid), 'Konto nieaktywne'),
             'Proponowany grafik': LABELS[group]}
            for uid, group in json.loads(p['assignments']).items()
        ], hide_index=True, use_container_width=True)
        if p['note']:
            st.markdown("**Uzasadnienie pracownika**")
            st.write(p['note'])
        if p['decision_note']:
            st.caption('Uwagi szefa: '+p['decision_note'])
        if p['status'] == 'pending':
            with st.form('review_'+str(p['id']), border=False):
                reason = st.text_input('Uwagi do decyzji (opcjonalnie)',
                    key='reason_'+str(p['id']), max_chars=1000)
                yes_col, no_col = st.columns(2)
                with yes_col:
                    yes = st.form_submit_button('Akceptuj propozycję', type='primary', use_container_width=True)
                with no_col:
                    no = st.form_submit_button('Odrzuć', use_container_width=True)
            if yes or no:
                ok, msg = decide(user['id'], p['id'], yes, reason)
                if ok:
                    st.session_state['proposal_flash'] = msg
                    st.rerun()
                else:
                    st.error(msg)


def admin_proposals_panel(user, proposals, names):
    pending = [p for p in proposals if p['status'] == 'pending']
    history = [p for p in proposals if p['status'] != 'pending']
    title = (f"🟡 Propozycje grafiku · do zatwierdzenia: {len(pending)}"
             if pending else "Propozycje grafiku · brak oczekujących")
    with st.container(key="proposals_pending" if pending else "proposals_clear"):
        with st.expander(title, expanded=False):
            if 'proposal_flash' in st.session_state:
                st.success(st.session_state.pop('proposal_flash'))
            st.caption('Zmiany w lokalu trafią do grafiku po akceptacji. Lokal zastępuje magazyn przypisany tej osobie w tym dniu.')
            if pending:
                for p in sorted(pending, key=lambda item: str(item['work_date'])):
                    proposal_card(user, p, names)
            else:
                st.info('Wszystkie propozycje są rozpatrzone. Brak nowych wniosków.')
            if history:
                with st.expander(f"Historia decyzji ({len(history)})"):
                    for p in history:
                        proposal_card(user, p, names)
