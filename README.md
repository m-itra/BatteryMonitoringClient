# Battery Monitoring Client

Настольный Windows-клиент для мониторинга телеметрии батареи и отправки собранных данных на backend.

## Запуск из исходного кода

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
```powershell
.\.venv\Scripts\python.exe main.py
```

## Сборка Windows EXE

Для сборки используется PyInstaller. Он указан в `requirements.txt`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --noconfirm --clean --name BatteryMonitoringClient --windowed --specpath build --workpath build\pyinstaller --distpath dist --hidden-import pythoncom --hidden-import pywintypes --hidden-import win32timezone --hidden-import win32com.client --collect-submodules keyring.backends main.py
```

Готовый файл будет создан здесь:

```text
dist\BatteryMonitoringClient.exe
```