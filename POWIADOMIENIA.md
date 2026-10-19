# Konfiguracja e-maili i SMS-ów

Wysyłka wymaga własnych kont usług. Sama aktualizacja aplikacji nie uruchamia wysyłki. Klucze wpisujesz wyłącznie w prywatnych Secrets aplikacji Streamlit, nigdy na GitHub ani w rozmowie.

## 1. E-mail — Resend

1. Załóż konto na https://resend.com.
2. W Domains dodaj domenę firmy, z której chcesz wysyłać wiadomości (np. flomaro.pl). Osoba zarządzająca domeną musi dodać rekordy DNS wskazane przez Resend. Poczekaj na potwierdzenie weryfikacji. Nie zmieniaj obecnej konfiguracji poczty firmy poza rekordami wymaganymi dla wysyłki.
3. Utwórz klucz API z prawem wysyłania dla tej domeny. Skopiuj go do RESEND_API_KEY w Secrets.
4. W EMAIL_FROM wpisz nadawcę w zweryfikowanej domenie, np. `FlomaroHUB <powiadomienia@flomaro.pl>` — dopiero po jej weryfikacji.

Adres Gmail Ariny jest odbiorcą zgłoszeń, a nie domeną nadawcy. Każde zgłoszenie zawiera dane kontaktowe autora. Dokumentacja: https://resend.com/docs/api-reference/emails/send-email.

## 2. SMS — SMSAPI

1. Załóż konto na https://www.smsapi.pl i sprawdź obowiązujące ceny oraz zasady konta. SMS-y wymagają środków i mogą być płatne.
2. Utwórz token API uprawniający do wysyłki SMS; zapisz go jako SMSAPI_TOKEN.
3. Skonfiguruj i zatwierdź nazwę nadawcy, np. FlomaroHUB, zgodnie z wymaganiami SMSAPI. Dokładną zatwierdzoną nazwę wpisz do SMSAPI_SENDER.
4. Numery pracowników muszą być poprawne. Aplikacja przyjmuje polskie numery 9-cyfrowe oraz numery międzynarodowe z prefiksem kraju.

SMS zawiera krótkie przypisanie, datę i godziny, bez polskich znaków; pełne szczegóły są w e-mailu i aplikacji. Dokumentacja: https://www.smsapi.pl/docs.

## 3. Włączenie

1. W Streamlit otwórz zarządzanie aplikacją → Settings → Secrets.
2. Zachowaj dotychczasowe ustawienia bazy. Dopisz pięć wpisów z notifications.secrets.example.toml na głównym poziomie TOML (przed ewentualnymi sekcjami `[nazwa]`). Uzupełnij klucze i nadawców.
3. Ustaw `DELIVERY_ENABLED = true` i zapisz. Uruchom aplikację ponownie (Reboot).
4. Konto szefa ma panel „E-maile i SMS-y — stan wysyłki”. Użyj „Sprawdź kolejkę wiadomości”.
5. Przypisz siebie do testowego przyszłego eventu, sprawdź odbiór obu wiadomości. Wyślij zgłoszenie problemu i sprawdź skrzynkę arinametluk@gmail.com. Te próby wykonujesz świadomie po skonfigurowaniu usług; przygotowanie paczki niczego nie wysłało.

Możesz skonfigurować najpierw tylko e-mail. Wiadomości SMS pozostaną w kolejce do czasu konfiguracji. Włączenie wysyłki przetwarza również wcześniej zapisane wiadomości, nie tylko nowe. Przed włączeniem usuń niepotrzebne testowe przypisania/eventy w aplikacji.

## Jak działa kolejka

- Przypisanie nowej osoby zapisuje e-mail i SMS razem z eventem. Sam ponowny zapis tej samej obsady nie dodaje kolejnych wiadomości. Zmiana szczegółów eventu bez zmiany obsady nie wysyła nowego e-maila/SMS.
- Usunięcie przypisania anuluje oczekujące wiadomości. Wiadomości już przekazanej dostawcy nie można cofnąć. Nie wysyłamy nowych powiadomień dla eventów z minionych dni ani nieaktywnych kont.
- Zgłoszenia problemów są zapisywane również bez konfiguracji poczty; użytkownik widzi wtedy ostrzeżenie. Limit to 5 zgłoszeń na godzinę na konto.
- Wysyłka odbywa się w tle, aby nie blokować przełączania zakładek. Kolejka działa tylko podczas działania serwera Streamlit. Po jego uśpieniu lub awarii wznowi pracę przy ponownym uruchomieniu; nie jest to gwarancja natychmiastowego ani całodobowego doręczenia.
- „Przekazano dostawcy” oznacza akceptację przez usługę, a nie potwierdzenie doręczenia. Sprawdź również spam i panel dostawcy.
- Przejściowe błędy są ponawiane. Niejednoznaczny wynik po upływie okna bezpiecznych ponowień trafia do „Wymaga sprawdzenia u dostawcy”. Błędy trwałe wymagają poprawienia konfiguracji/danych i sprawdzenia logów dostawcy; aplikacja nie ma przycisku ręcznego ponowienia.

Walidacja e-maila sprawdza składnię, popularne literówki i konfigurację domeny pocztowej. Nie jest potwierdzeniem własności konkretnej skrzynki. Nie zmienia podanego adresu bez zgody użytkownika.
