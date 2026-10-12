# FlomaroHUB na iPhonie i Androidzie

Adres: https://dfcyvx9ubfujogubnvrrnk.streamlit.app/

Ta wersja dodaje instalację aplikacji internetowej z przeglądarki, ikonę FH oraz
instrukcje na ekranie. Internet jest potrzebny do korzystania z aplikacji.
Nie jest to pakiet APK/IPA ani wersja opublikowana w sklepie.

## Aktualizacja istniejącej aplikacji

1. Rozpakuj ZIP. Na GitHubie otwórz repozytorium chemixsis/FlomaroHub i gałąź,
   z której działa aplikacja w Streamlit.
2. Wgraj ZAWARTOŚĆ folderu GITHUB do głównego katalogu repozytorium.
   Zachowaj foldery static, tests oraz .streamlit. Nie twórz dodatkowego folderu GITHUB.
3. W .streamlit/config.toml musi znaleźć się enableStaticServing = true w sekcji [server].
   Ten plik znajduje się już w paczce. Zatwierdź zmiany przyciskiem Commit changes.
4. Poczekaj na aktualizację Streamlit. Jeżeli pliki ikon nie są dostępne po aktualizacji,
   wybierz Reboot app w panelu zarządzania aplikacją Streamlit.
5. Otwórz aplikację ponownie. Pod nagłówkiem pojawi się „FlomaroHUB na telefonie”.

Nie uruchamiaj ponownie konfiguracji ani importu danych. Nie zmieniaj zapisanych
Secrets w Streamlit. Baza Supabase i istniejący flomaro.db pozostają bez zmian.
Nie wgrywaj flomaro.db ani secrets.toml na GitHub.

## Dodanie do telefonu

iPhone: otwórz adres w Safari → Udostępnij → Do ekranu początkowego.
Jeżeli jest dostępne „Otwórz jako aplikację internetową”, włącz je, następnie Dodaj.

Android: otwórz adres w Chrome → menu ⋮ → Dodaj do ekranu głównego → Zainstaluj,
jeśli przeglądarka pokazuje tę opcję. Nazwy opcji zależą od wersji systemu.
Jeżeli dostępny jest jedynie skrót, będzie otwierał stronę z ekranu głównego.
Nie instaluj ze strony logowania Streamlit: najpierw otwórz właściwy FlomaroHUB.

Po instalacji używaj ikony FH. Dotychczasowe hasło testowe i konto nadal obowiązują.
Pierwsze otwarcie z ikony może wymagać ponownego logowania.
Aktualizacje wgrywasz nadal przez GitHub; użytkownik wczytuje nową wersję po ponownym
otwarciu aplikacji. Nową ikonę lub nazwę może zobaczyć dopiero po ponownym dodaniu aplikacji.

## Sprawdzenie na urządzeniu po wdrożeniu

- Na iPhonie i Androidzie dodaj aplikację i otwórz ją z ikony: sprawdź nazwę FH/FlomaroHUB,
  własną ikonę oraz tryb osobnego okna, jeśli system go obsługuje.
- Zaloguj się i otwórz grafik w pionie oraz poziomie. Sprawdź czytelność pól i klawiaturę.
- Sprawdź odczyt tych samych danych na komputerze i telefonie.
- Zamknij i otwórz aplikację ponownie. W razie utraty sesji zaloguj się ponownie.
- Bez internetu aplikacja nie zapisuje działań w kolejce. Po powrocie połączenia
  sprawdź stan zmiany, zanim ponowisz czynność.

Wykonano 29 lokalnych testów istniejących funkcji, sprawdzono składnię Pythona
i JavaScriptu, manifest, rozmiary ikon i aktualizację metadanych przy ponownym renderowaniu.
Sprawdzono też strukturę działającej strony Streamlit (ramka tego samego pochodzenia).
Nie wykonano instalacji na fizycznym iPhonie/Androidzie ani wdrożenia tej paczki.
Pełne uruchomienie nowej wersji Streamlit lokalnie nie było dostępne w środowisku.

## App Store i Google Play później

Publikacja jest możliwym kolejnym etapem, ale wymaga przygotowania i podpisania
oddzielnych pakietów mobilnych, kont deweloperskich, testów, informacji o prywatności
i przeglądu sklepu. Nie wystarczy zmienić rozszerzenia tej paczki.
Apple wymaga wartości i interfejsu wykraczających poza przepakowaną stronę.
Decyzję o przyjęciu aplikacji podejmuje sklep. Ten etap zostawiamy na ukończenie funkcji.

Źródła:
- https://support.apple.com/en-hk/guide/iphone/iphea86e5236/ios
- https://developer.chrome.com/blog/update-install-criteria
- https://developer.apple.com/app-store/review/guidelines/#minimum-functionality
- https://docs.streamlit.io/develop/concepts/configuration/serving-static-files

## Informacje dla osoby rozwijającej kod

mobile.py dodaje metadane do nadrzędnego dokumentu tego samego pochodzenia, ponieważ
Community Cloud używa ramki /~/+/. Publiczne zasoby są adresowane względem dokumentu
aplikacji. Hosting w ramce innego pochodzenia wymaga osobnej integracji dokumentu nadrzędnego.
Nie dodano service workera ani pamięci offline. Folder static zawiera wyłącznie
publiczny manifest i ikony; nigdy nie należy umieszczać tam danych ani załączników pracowników.
