@echo off
setlocal EnableExtensions

cd /d "%~dp0"
if errorlevel 1 goto :fail

set "BUILD_VENV=.build-venv"
set "BUILD_ENTRY=_pyinstaller_entry.py"
set "APP_VERSION=0.1.0"
set "RELEASE_ROOT=release"
set "VERSION_DIR=%RELEASE_ROOT%\v%APP_VERSION%"
set "PORTABLE_DIR=%VERSION_DIR%\portable"
set "PORTABLE_ARCHIVE=%RELEASE_ROOT%\DSCode v%APP_VERSION% Portable.zip"
set "INSTALLER_PATH=%RELEASE_ROOT%\DSCode v%APP_VERSION%.exe"

echo [1/6] Preparing isolated build environment...
if not exist "%BUILD_VENV%\Scripts\python.exe" (
    python -m venv "%BUILD_VENV%"
    if errorlevel 1 goto :fail
)

call "%BUILD_VENV%\Scripts\activate.bat"
if errorlevel 1 goto :fail

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo Python 3.11 or newer is required to build DSCode Assistant.
    goto :fail
)

echo [2/6] Installing runtime and build dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
python -m pip install --upgrade pyinstaller
if errorlevel 1 goto :fail

echo [3/6] Cleaning previous build output...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "%VERSION_DIR%" rmdir /s /q "%VERSION_DIR%"
if exist "%PORTABLE_ARCHIVE%" del /q "%PORTABLE_ARCHIVE%"
if exist "%INSTALLER_PATH%" del /q "%INSTALLER_PATH%"

> "%BUILD_ENTRY%" echo from dscode_assistant.app import main
>> "%BUILD_ENTRY%" echo raise SystemExit(main^(^))

echo [4/6] Building DSCode Assistant.exe...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --onedir ^
    --name "DSCode Assistant" ^
    --icon "%CD%\assets\icon.ico" ^
    --version-file "%CD%\windows_version_info.txt" ^
    --add-data "%CD%\assets;assets" ^
    --paths "%CD%" ^
    --collect-all markdown ^
    --collect-all pygments ^
    --collect-all bleach ^
    --collect-all keyring ^
    --hidden-import keyring.backends.Windows ^
    --distpath "dist" ^
    --workpath "build\work" ^
    --specpath "build" ^
    "%BUILD_ENTRY%"
if errorlevel 1 goto :fail

del /q "%BUILD_ENTRY%"

echo [5/6] Creating portable release directory...
mkdir "%PORTABLE_DIR%"
xcopy "dist\DSCode Assistant\*" "%PORTABLE_DIR%\" /E /I /Y >nul
if errorlevel 1 goto :fail

if not exist "%PORTABLE_DIR%\DSCode Assistant.exe" (
    echo Build failed: %PORTABLE_DIR%\DSCode Assistant.exe was not created.
    goto :fail
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$bad = Get-ChildItem -LiteralPath '%PORTABLE_DIR%' -Recurse -File ^| Where-Object { $_.Name -eq 'settings.json' -or $_.Name -like '*.db' -or $_.Name -like '*.db-shm' -or $_.Name -like '*.db-wal' }; if ($bad) { $bad.FullName; exit 1 }"
if errorlevel 1 (
    echo Build failed: user data was found in the release directory.
    goto :fail
)

echo [6/6] Creating versioned portable archive...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Compress-Archive -Path '%PORTABLE_DIR%\*' -DestinationPath '%PORTABLE_ARCHIVE%' -CompressionLevel Optimal -Force"
if errorlevel 1 goto :fail

set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_EXE%" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_EXE%" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC_EXE%" (
    echo Building Windows installer...
    "%ISCC_EXE%" /DAppVersion=%APP_VERSION% "/DBuildSource=%PORTABLE_DIR%" "installer.iss"
    if errorlevel 1 goto :fail
) else (
    echo Inno Setup 6 was not found. Portable release is ready; installer build was skipped.
)

echo.
echo Build completed successfully.
echo Portable folder:  %CD%\%PORTABLE_DIR%
echo Portable archive: %CD%\%PORTABLE_ARCHIVE%
echo Executable:       %CD%\%PORTABLE_DIR%\DSCode Assistant.exe
if exist "%INSTALLER_PATH%" echo Installer:        %CD%\%INSTALLER_PATH%
call deactivate >nul 2>&1
exit /b 0

:fail
if exist "%BUILD_ENTRY%" del /q "%BUILD_ENTRY%"
echo.
echo Windows build failed.
call deactivate >nul 2>&1
exit /b 1
