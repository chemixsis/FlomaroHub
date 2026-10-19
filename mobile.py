"""Public installation metadata; no credentials or employee data are stored here."""
import streamlit as st


MOBILE_HTML = """
<style>
  #flomaro-install {color:#fff;background:#12385E;border:1px solid #50708E;
    border-radius:14px;padding:12px 16px;font:inherit;max-width:100%;box-sizing:border-box;}
  #flomaro-install summary {cursor:pointer;font-weight:700;min-height:24px;}
  #flomaro-install p {line-height:1.5;margin:12px 0 4px;}
  #flomaro-install a {color:#E7B843;}
  @media(max-width:640px) {
    input,select,textarea {font-size:16px !important;}
  }
  @media(display-mode:standalone) {#flomaro-install {display:none;}}
</style>
<details id="flomaro-install">
  <summary>FlomaroHUB na telefonie</summary>
  <p><strong>iPhone:</strong> otwórz tę stronę w Safari, wybierz Udostępnij →
  Do ekranu początkowego. Jeśli widzisz „Otwórz jako aplikację internetową”, włącz tę opcję.
  Następnie wybierz Dodaj.</p>
  <p><strong>Android:</strong> otwórz tę stronę w Chrome, wybierz menu ⋮ →
  Dodaj do ekranu głównego → Zainstaluj (jeśli ta opcja jest dostępna).</p>
  <p>Jeśli widzisz tylko opcję skrótu, możesz dodać skrót do strony.
  Aplikacja wymaga internetu. Logujesz się tym samym kontem.
  Po zmianach w aplikacji zamknij ją i otwórz ponownie, aby wczytać aktualną wersję.</p>
</details>
<script>
(() => {
  // Community Cloud hosts the app inside a same-origin /~/+/ frame.
  // Installation metadata belongs to the outer page; assets belong to the app.
  let installDocument = document;
  try { if (window.top.document) installDocument = window.top.document; }
  catch (_) { /* Cross-origin hosts retain metadata inside the app only. */ }
  const head = installDocument.head;
  installDocument.title = 'FlomaroHUB';
  // The cloud shell may update the page title after Streamlit renders.
  const titleElement = head.querySelector('title');
  if (titleElement && !titleElement.dataset.flomaroObserved) {
    titleElement.dataset.flomaroObserved = 'true';
    new MutationObserver(() => {
      if (installDocument.title !== 'FlomaroHUB') installDocument.title = 'FlomaroHUB';
    }).observe(titleElement, {childList:true, characterData:true, subtree:true});
  }
  const assetBase = new URL('app/static/', window.location.href);
  function link(rel, href, type) {
    let element = head.querySelector('link[rel="' + rel + '"]');
    if (!element) {element = installDocument.createElement('link'); head.appendChild(element);}
    element.rel = rel;
    element.href = href;
    if (type) element.type = type;
  }
  function meta(name, content) {
    let element = head.querySelector('meta[name="' + name + '"]');
    if (!element) {element = installDocument.createElement('meta'); head.appendChild(element);}
    element.name = name; element.content = content;
  }
  link('manifest', new URL('manifest.json?v=20261019icon', assetBase).href, 'application/manifest+json');
  link('apple-touch-icon', new URL('apple-touch-icon.png?v=20261019icon', assetBase).href);
  link('icon', new URL('icon-192.png?v=20261019icon', assetBase).href, 'image/png');
  meta('application-name', 'FlomaroHUB');
  meta('apple-mobile-web-app-title', 'FlomaroHUB');
  meta('apple-mobile-web-app-capable', 'yes');
  meta('mobile-web-app-capable', 'yes');
  meta('apple-mobile-web-app-status-bar-style', 'default');
  meta('theme-color', '#0D2947');
  if (navigator.standalone) {
    const help = document.getElementById('flomaro-install');
    if (help) help.hidden = true;
  }
})();
</script>
"""


def install_mobile_support():
    """Available before either login gate; no extra database work on reruns."""
    st.html(MOBILE_HTML, unsafe_allow_javascript=True)

