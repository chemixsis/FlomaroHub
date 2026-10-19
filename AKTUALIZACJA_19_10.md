# FlomaroHUB — aktualizacja 19.10.2026

Paczka aktualizuje obecną aplikację Streamlit. Nie zmienia jej w aplikację sklepową i zachowuje obecne logowanie PIN-em.

## Wgranie

1. Zachowaj kopię obecnych plików aplikacji i prywatną kopię bazy. Dotychczasowa baza flomaro.db na laptopie pozostaje bez zmian. Jeśli używasz lokalnego backup_online.py z aktualnymi sekretami bazy, uruchom go przed aktualizacją; nowa wersja narzędzia obsługuje również bazę sprzed tej aktualizacji. Kopii bazy ani secrets.toml nie wysyłaj na GitHub.
2. Rozpakuj ZIP. W repozytorium chemixsis/FlomaroHub zastąp pliki plikami z paczki — w tym nowe moduły, requirements.txt, schema.sql, sqlite_schema.sql i katalog static. Wgraj zawartość paczki do katalogu głównego repozytorium, bez dodatkowego katalogu nadrzędnego. Nie wgrywaj samego ZIP-a.
3. Nie usuwaj istniejących Secrets w Streamlit. Uruchom aplikację ponownie po zainstalowaniu nowych zależności.
4. Sprawdź logowanie, kliknięcie dnia w grafiku i rozliczenia tygodniowe. Przed zatwierdzeniem wypłat porównaj znaną zmianę z jej czasem i stawką.
5. Wysyłkę uruchom zgodnie z POWIADOMIENIA.md. Bez konfiguracji zgłoszenia i wiadomości czekają w bazie.

## Zmiany

- Rejestracja i zmiana kontaktu odrzucają nieprawidłowe e-maile, m.in. gmail.con z podpowiedzią gmail.com. Sprawdzanie domeny odbywa się przy zapisie, a nie podczas zwykłego przeglądania aplikacji.
- Nowe przypisanie do eventu dodaje e-mail i SMS do kolejki.
- Formularz obsady w panelu szefa otwiera się po kliknięciu daty w kalendarzu. Zapisujesz wszystkie wybory jednym przyciskiem. Kolory magazynu, lokalu i eventów pozostają różne.
- Każde zalogowane konto ma formularz „Zgłoś problem”; odbiorcą jest arinametluk@gmail.com.
- Rozliczenia mają tygodnie poniedziałek–niedziela z rozwijanym podglądem poszczególnych zmian.

## Zasady wynagrodzeń i zachowanie historii

Wynagrodzenie = pełne przepracowane minuty × stawka zapisana przy zmianie / 60. Nie zaokrąglamy czasu w górę do pełnych godzin ani pieniędzy do złotówek. Niepełna końcowa minuta nie jest liczona. Zmiana należy do tygodnia, w którym się rozpoczęła.

Tygodniową wypłatę wyliczamy z dokładnych kwot zmian, a na końcu ustalamy ją do grosza. Dzienny podgląd pokazuje dwa miejsca po przecinku. Przykład: trzy zmiany po 1 minucie przy 32 zł/h to tygodniowo 1,60 zł; każda z nich wyświetla się jako 0,53 zł. Kwoty widoczne w wierszach mogą więc sumować się inaczej o grosz.

Przy pierwszym uruchomieniu aplikacja przeliczy zamknięte zmiany, które nie mają jeszcze przypisanej wypłaty. Poprzednie minuty, godziny rozliczeniowe i kwoty zapisuje w tabeli payroll_migration_backup. Zmiany już przypisane do utworzonej wypłaty zachowują historyczne wartości. To nie jest pełna kopia bazy, dlatego przed aktualizacją zachowaj również backup.

Zatwierdzanie godzin i wypłat nadal należy do szefa. Aplikacja nie wykonuje przelewów. Konto julaa.leksz@gmail.con zostało osobno dezaktywowane w bazie produkcyjnej, z zachowaniem historii pracy; paczka nie usuwa innych kont.
