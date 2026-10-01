"""Additional password gate, required before any database access or registration."""
import threading
import time
import streamlit as st
from access_password import valid_hash, verify
from cloud_config import setting


@st.cache_resource
def attempts():
    # Shared across sessions in this server process, rather than a browser-only limit.
    return {'lock': threading.Lock(), 'failures': [], 'blocked_until': 0.0}


def require_access():
    encoded = setting('ACCESS_PASSWORD_HASH', '')
    if not valid_hash(encoded):
        st.info('Właściciel musi skonfigurować dostęp do wersji testowej.')
        st.stop()
    if (st.session_state.get('_access_hash') == encoded
            and time.time() - st.session_state.get('_access_at', 0) < 8 * 3600):
        return
    st.session_state.pop('user_id', None)
    st.subheader('Dostęp do testów FlomaroHUB')
    st.caption('Wpisz hasło otrzymane od właściciela aplikacji.')
    with st.form('test_access', clear_on_submit=True):
        password = st.text_input('Hasło dostępu', type='password', max_chars=1024)
        submitted = st.form_submit_button('Wejdź', use_container_width=True)
    if submitted:
        state = attempts()
        with state['lock']:
            now = time.monotonic()
            state['failures'] = [t for t in state['failures'] if now - t < 60]
            if now < state['blocked_until']:
                result = 'blocked'
            elif verify(password, encoded):
                result = 'ok'
                state['failures'].clear()
            else:
                result = 'bad'
                state['failures'].append(now)
                if len(state['failures']) >= 10:
                    state['blocked_until'] = now + 60
        if result == 'ok':
            st.session_state['_access_hash'] = encoded
            st.session_state['_access_at'] = time.time()
            st.rerun()
        elif result == 'blocked':
            st.error('Zbyt wiele prób. Spróbuj ponownie za minutę.')
        else:
            st.error('Nieprawidłowe hasło dostępu.')
    st.stop()
