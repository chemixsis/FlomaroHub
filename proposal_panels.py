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
