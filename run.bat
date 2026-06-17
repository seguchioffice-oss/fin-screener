@echo off
cd /d %~dp0
echo Starting Quality Compounder Screener...
echo Open http://localhost:8501 in your browser
echo.
"C:\Users\ksegu\AppData\Local\Programs\Python\Python313\python.exe" -m streamlit run app.py
pause
