# FlomaroHUB — przygotowanie do prywatnych testów online

Wersja oparta na ostatniej aktualizacji v14: panel szefa, pracownicy, eventy i załączniki. Dane online są zapisywane w PostgreSQL Supabase, a nie na dysku Streamlit. Oryginalny flomaro.db pozostaje na komputerze. Po przejściu na wersję online lokalna i internetowa baza nie synchronizują się automatycznie — podczas testów używaj jednej wersji jako źródła aktualnych danych.

## Stan przygotowania

To pakiet do konfiguracji i testów, nie potwierdzenie wdrożenia. Nie wykonano połączenia z Twoją bazą Supabase ani importu rzeczywistych danych. Testy lokalne sprawdzają składnię, adapter, hasło dostępu oraz import na sztucznych danych; nie zastępują próby na prawdziwym PostgreSQL i testów całej aplikacji w przeglądarce. Ostateczne wdrożenie wymaga wykonania punktów poniżej.

## 1. Wgraj czysty kod do GitHuba

Repozytorium chemixsis/FlomaroHub jest prywatne. W pustym repozytorium wybierz „uploading an existing file”. Wgraj zawartość folderu GITHUB z paczki ZIP, tak aby app.py znalazł się bezpośrednio w repozytorium, a nie w podfolderze GITHUB. Zachowaj też folder .streamlit z config.toml oraz .gitignore. Kliknij „Commit changes”. Nazwę utworzonej gałęzi sprawdź nad listą plików (zwykle main).

Ten folder z oryginalnej paczki nie zawiera danych ani prawdziwych haseł. Nie wysyłaj flomaro.db, kopii zapasowych ani pliku .streamlit/secrets.toml. GitHubowy formularz przesyłania plików nie stosuje reguł .gitignore — wgrywaj tylko czysty folder GITHUB z paczki, przed lokalnym przygotowaniem haseł.

## 2. Przygotuj połączenie lokalnie

Otwórz terminal w rozpakowanym folderze GITHUB. Polecenia poniżej uruchamiaj na swoim komputerze. Potrzebny jest Python (dla całej aplikacji zalecany 3.12).

```powershell
python -m pip install -r requirements-tools.txt
python setup_local.py
```

Program zapyta o e-mail właściciela, obecne hasło bazy Supabase i nowe, osobne hasło dostępu do testów (minimum 16 znaków). Podczas wpisywania haseł terminal nie pokazuje znaków. Adres serwera, port i użytkownik projektu są już uzupełnione. E-mail właściciela służy tylko do zabezpieczenia pierwszej rejestracji szefa w pustej bazie; importowane konta zachowują role.

Powstanie prywatny plik .streamlit/secrets.toml. Nie wklejaj jego zawartości do czatu ani GitHuba. Nie jest to hasło konta Supabase — DB_PASSWORD jest hasłem bazy danych ustawionym przy tworzeniu projektu.

## 3. Przenieś dotychczasowe dane

Zamknij lokalną aplikację, aby nikt nie dopisywał zmian w trakcie przenoszenia. Podaj rzeczywistą ścieżkę do używanego flomaro.db:

```powershell
python migrate_data.py --source "C:\PELNA_SCIEZKA\flomaro.db"
python check_connection.py
```

Import tworzy prywatną lokalną kopię w backups, czyta źródło bez prawa zapisu i zachowuje identyfikatory, PIN-y, role, historię oraz załączniki. Po skopiowaniu porównuje zawartość rekordów. Całość jest jedną transakcją: błąd wycofuje import. Jeśli docelowe tabele zawierają już dane, program zatrzyma się zamiast je nadpisywać. Nie usuwa duplikatów grafików ani nie zmienia starych godzin. Dodatkowe nierozpoznane tabele/kolumny zatrzymują import do ręcznego sprawdzenia.

Po udanym imporcie w lokalnych sekretach DATA_READY zmieni się na true. Jeśli przerwano program po zatwierdzeniu importu, ale przed aktualizacją pliku, nie powtarzaj importu: wykonaj check_connection.py i sprawdź dane, a dopiero potem ustaw DATA_READY = true ręcznie.

Opcja `python migrate_data.py --empty` jest dostępna wyłącznie, jeśli świadomie chcesz rozpocząć od pustej bazy zamiast importować stare dane. Nie używaj jej przy zachowywaniu dotychczasowych kont.

## 4. Uruchom w Streamlit Community Cloud

W formularzu wdrożenia wybierz repozytorium chemixsis/FlomaroHub, rzeczywistą nazwę gałęzi i plik app.py. W Advanced settings wybierz Python 3.12. Do pola Secrets wklej zawartość prywatnego pliku .streamlit/secrets.toml po udanym imporcie i sprawdzeniu połączenia. Następnie zatwierdź wdrożenie.

Brak poprawnego hasła testowego blokuje aplikację przed dostępem do bazy. DATA_READY = false także blokuje uruchomienie funkcji. Hasło testowe jest zapisane jako solony skrót PBKDF2; hasło bazy musi być dostępne serwerowi jako sekret. Zwykłe konta nadal używają swoich PIN-ów. Hasło dostępu do testów jest dodatkową ochroną, nie zastępuje przyszłego pełnego systemu uwierzytelniania pracowników.

W ustawieniach aplikacji w Sharing sprawdź „Only specific people can view this app”. Wersja z prywatnego repozytorium jest domyślnie prywatna, ale sprawdź to przed udostępnieniem danych. Dopiero po sprawdzeniu działania dodaj e-mail szefa jako viewer. Szef potrzebuje także hasła testowego i konta z rolą szefa w samej aplikacji. Jeśli konto istnieje w SQLite, zachowuje swój dotychczasowy PIN i rolę. Nie wysyłaj testerowi hasła bazy danych.

## 5. Sprawdź przed przekazaniem szefowi

Zaloguj się i porównaj listę pracowników, kwoty oraz historię ze starą bazą. Na testowych kontach sprawdź Eventy, Magazyn, Lokal i wybór miejsca pracy; własny/zespołowy grafik; rozpoczęcie i zakończenie zmiany; zmianę danych kontaktowych; edycję eventu, plik i dostęp osoby przypisanej oraz nieprzypisanej. Sprawdź panel szefa oraz wypłaty i zatwierdzenia na oznaczonych danych testowych. Odśwież stronę i sprawdź trwałość danych. Sprawdź wygląd na telefonie. Nie potwierdzaj realnych wypłat tylko w celu testowania.

## Kopie zapasowe i kolejne zmiany

```powershell
python backup_online.py
```

To polecenie tworzy nowy plik SQLite w backups z jednego spójnego odczytu bazy online. Nie nadpisuje lokalnego flomaro.db. Wykonuj je przed większymi zmianami i regularnie podczas testów. Kopię przechowuj prywatnie. Odtworzenie przez importer wymaga pustej bazy docelowej. Kopia ma format SQLite, lecz starsza lokalna aplikacja może wykonać własne migracje po otwarciu — najpierw zachowaj nietkniętą kopię.

Kod możesz później aktualizować w tym samym repozytorium. Streamlit pobierze zmiany; dane pozostaną w Supabase. Zmiany samej struktury bazy wymagają osobnej migracji i kopii zapasowej. Dla tej pierwszej wersji init_db tworzy brakujące tabele, nie usuwa danych.

Załączniki tej wersji są przechowywane w bazie PostgreSQL, więc zajmują limit bazy Supabase (Free: 500 MB), a nie osobny limit Storage. Free nie zapewnia automatycznych kopii bazy i projekt może zostać wstrzymany po okresie nieaktywności. To wariant do ograniczonych testów.

## Źródła i testy

- [Połączenie Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Limity Supabase](https://supabase.com/pricing)
- [Sekrety Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [Prywatny dostęp Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app)

Testy lokalne bez połączenia sieciowego: `python -m unittest discover -s tests -v`. Nie podawaj w testach rzeczywistych danych pracowników.
