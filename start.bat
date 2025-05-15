@echo off
REM Активируем виртуальную среду
call venv\Scripts\activate

REM Запускаем скрипт main.py
python app.py

pip install --no-cache-dir -r requirements.txt

REM Деактивируем виртуальную среду после завершения
deactivate
pause