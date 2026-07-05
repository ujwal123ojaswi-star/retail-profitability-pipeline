@echo off
setlocal
cd /d "%~dp0"

echo ==^> Building the warehouse (ingest -^> load -^> transform -^> checks)
.venv\Scripts\python build.py || goto :error

echo.
echo ==^> Done. Launch the dashboard with:
echo     .venv\Scripts\streamlit run app\dashboard.py
goto :eof

:error
echo.
echo Build failed. Scroll up to read the error message.
exit /b 1
