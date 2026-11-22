@echo off
setlocal
cd /d "%~dp0"
rem start.bat          - strona WWW (http://localhost:8000), otwiera sie w przegladarce
rem start.bat --cli    - bez okna: wszystkie PDF-y z ..\input do ..\output

rem --- Python: nie instalujemy go sami, tylko sprawdzamy ---
rem "python --version", nie "where python": alias ze Sklepu Windows istnieje nawet bez Pythona.
python --version >nul 2>&1
if errorlevel 1 (
    echo BLAD: brak Pythona. Zainstaluj Python 3.13 lub nowszy z https://www.python.org/downloads/
    echo i zaznacz w instalatorze "Add python.exe to PATH". Potem uruchom start.bat ponownie.
    pause
    exit /b 1
)

rem --- Tesseract OCR: potrzebny do skanow PDF bez warstwy tekstowej ---
set "TESS_DIR=%ProgramFiles%\Tesseract-OCR"
where tesseract >nul 2>&1 && goto tess_lang
if not exist "%TESS_DIR%\tesseract.exe" (
    echo Brak Tesseract OCR - instaluje przez winget, potwierdz okno administratora...
    winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements
)
if not exist "%TESS_DIR%\tesseract.exe" (
    echo UWAGA: nie udalo sie zainstalowac Tesseracta. Skany PDF nie beda czytane, reszta dziala.
    goto app
)
rem Instalator UB-Mannheim nie dopisuje sie do PATH; dla tej sesji wystarczy.
set "PATH=%TESS_DIR%;%PATH%"

:tess_lang
tesseract --list-langs 2>nul | findstr /x "pol" >nul && goto app
rem Cichy instalator ma tylko angielski; polski model trafia do projektu, bez praw administratora.
if not exist ".tessdata\pol.traineddata" (
    echo Pobieram polski model Tesseracta...
    mkdir .tessdata 2>nul
    curl -L --fail -o ".tessdata\pol.traineddata" https://github.com/tesseract-ocr/tessdata/raw/main/pol.traineddata
)
if exist ".tessdata\pol.traineddata" (
    set "TESSDATA_PREFIX=%~dp0.tessdata"
) else (
    echo UWAGA: brak polskiego modelu Tesseracta. Skany PDF nie beda czytane, reszta dziala.
)

:app
if not exist .venv\Scripts\python.exe python -m venv .venv || goto fail
.venv\Scripts\python.exe -m pip install -q --disable-pip-version-check -r requirements.txt || goto fail
if /i "%~1"=="--cli" (
    .venv\Scripts\python.exe -m app
    pause
    exit /b
)
.venv\Scripts\python.exe -m app --serve --open || goto fail
exit /b

:fail
echo BLAD: uruchomienie nie powiodlo sie - szczegoly powyzej.
pause
exit /b 1
