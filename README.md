### Описание
 Мощный автоматизированный инструмент для работы с платформой OpenLoop, который позволяет автоматизировать процесс регистрации, авторизации и фарминга токенов. Инструмент оптимизирован для работы с большим количеством аккаунтов и обеспечивает стабильную работу через систему прокси.

### Функциональность
- 🔄 Автоматическая регистрация аккаунтов с использованием инвайт-кодов
- 🔐 Автоматическая авторизация и управление токенами
- 🌐 Поддержка работы через прокси с автоматической ротацией
- 🛡️ Обход защиты Turnstile 
- 📊 Мониторинг балансов и статистики в реальном времени
- 📝 Подробное логирование всех операций
- ⚡ Многопоточная обработка аккаунтов
- 🔄 Автоматическое восстановление после ошибок
- 📈 Система учета успешных и неудачных операций
- 🔌 Интеграция с AntiCaptcha для решения капчи

### Установка
1. Клонируйте репозиторий:
```bash
git clone https://github.com/airdrop-cmd/OpenLoop.git
```

2. Запустите скрипт установки:
```bash
start.bat
```
Скрипт автоматически установит все необходимые зависимости.

### Использование
1. Подготовьте файлы в папке `data`:
   - `email.txt` - список email:password
   - `proxies.txt` - список прокси
   - `invitecode.txt` - список инвайт-кодов

2. Настройте параметры в `config.py`:
   - Количество потоков
   - Ключ AntiCaptcha
   - Другие настройки

3. Запустите основной скрипт:
```bash
python main.py
```

### Требования
- Python 3.8+
- Windows OS
- Подключение к интернету
- Аккаунт AntiCaptcha

Для обновлений присоединяйтесь к нашему Telegram-каналу: [@serversdrop](https://t.me/serversdrop)

---

## English

### Description
OpenLoop is a powerful automated tool for working with the OpenLoop platform, designed to automate the process of registration, authorization, and token farming. The tool is optimized for handling multiple accounts and ensures stable operation through a proxy system.

### Features
- 🔄 Automatic account registration using invite codes
- 🔐 Automatic authorization and token management
- 🌐 Proxy support with automatic rotation
- 🛡️ Turnstile protection bypass 
- 📊 Real-time balance and statistics monitoring
- 📝 Detailed operation logging
- ⚡ Multi-threaded account processing
- 🔄 Automatic error recovery
- 📈 Success and failure tracking system
- 🔌 AntiCaptcha integration for captcha solving

### Installation
1. Clone this repository:
```bash
git clone https://github.com/airdrop-cmd/OpenLoop.git
```

2. Run the setup script:
```bash
start.bat
```
The script will automatically install all required dependencies.

### Usage
1. Prepare files in the `data` folder:
   - `email.txt` - list of email:password
   - `proxies.txt` - list of proxies
   - `invitecode.txt` - list of invite codes

2. Configure settings in `config.py`:
   - Number of threads
   - AntiCaptcha key
   - Other settings

3. Run the main script:
```bash
python main.py
```

### Requirements
- Python 3.8+
- Windows OS
- Internet connection
- AntiCaptcha account

### Support
For support and updates, join our Telegram channel: [@serversdrop](https://t.me/serversdrop) 