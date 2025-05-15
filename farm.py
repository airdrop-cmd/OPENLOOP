#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import random
import asyncio
import time
import logging
import colorama
import sys
from typing import Dict, List
from fake_useragent import UserAgent
from config import num_threads
from better_proxy import Proxy  # Библиотека для работы с прокси
import httpx  # Асинхронный HTTP-клиент

# Инициализация colorama для цветной консоли в Windows
colorama.init()

# Добавляем фильтр для thread_id
class ThreadIdFilter(logging.Filter):
    def __init__(self, name=''):
        super().__init__(name)
        
    def filter(self, record):
        if not hasattr(record, 'threadid'):
            record.threadid = '0'
        return True

# Цвета для логирования
class LogColors:
    RESET = '\033[0m'
    INFO = '\033[92m'  # Зеленый
    ERROR = '\033[91m'  # Красный
    WARNING = '\033[93m'  # Желтый
    DEBUG = '\033[94m'  # Синий
    ACCOUNT_NUM = '\033[95m'  # Розовый
    EMAIL = '\033[94m'  # Синий
    BALANCE = '\033[33m'  # Оранжевый
    STATUS = '\033[92m'  # Зеленый

# Настраиваем цветное форматирование логов
class ColoredFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: LogColors.DEBUG + "[%(asctime)s][%(threadid)s][DEBUG] %(message)s" + LogColors.RESET,
        logging.INFO: LogColors.INFO + "[%(asctime)s][%(threadid)s][INFO] %(message)s" + LogColors.RESET,
        logging.WARNING: LogColors.WARNING + "[%(asctime)s][%(threadid)s][WARNING] %(message)s" + LogColors.RESET,
        logging.ERROR: LogColors.ERROR + "[%(asctime)s][%(threadid)s][ERROR] %(message)s" + LogColors.RESET,
        logging.CRITICAL: LogColors.ERROR + "[%(asctime)s][%(threadid)s][CRITICAL] %(message)s" + LogColors.RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M")
        return formatter.format(record)

# Создаем общий фильтр thread_id
thread_id_filter = ThreadIdFilter()

# Настройка логирования
logger = logging.getLogger("farm")
logger.setLevel(logging.INFO)
# Очищаем существующие обработчики
logger.handlers = []

# Добавляем фильтр к корневому логгеру
root_logger = logging.getLogger()
root_logger.addFilter(thread_id_filter)

# Создаем обработчики
file_handler = logging.FileHandler("farm_log.log", encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)

# Добавляем фильтр к каждому обработчику
file_handler.addFilter(thread_id_filter)
console_handler.addFilter(thread_id_filter)

# Устанавливаем форматирование
file_formatter = logging.Formatter("[%(asctime)s][%(threadid)s][%(levelname)s] %(message)s", datefmt="%H:%M")
file_handler.setFormatter(file_formatter)

console_handler.setFormatter(ColoredFormatter())

# Добавляем обработчики к логгеру
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Константы
API_URL = 'https://api.openloop.so/bandwidth/share'
FARM_RESULT_FILE = 'result/Farm.txt'  # Файл создается в папке result
PROXY_FILE = 'data/proxyFarm.txt'
LOGIN_FILE = 'result/login.txt'  # Файл с токенами авторизации
PROXY_BAN_TIME = 10  # 60 секунд блокировки проблемной прокси
MIN_PING_INTERVAL = 60  # Минимальный интервал между запросами в секундах
MAX_PING_INTERVAL = 200  # Максимальный интервал между запросами в секундах
MAX_PROXY_RETRIES = 3   # Максимальное количество попыток с разными прокси
CONNECTION_TIMEOUT = 30  # Таймаут подключения увеличен до 30 секунд
PROXY_CONNECTION_RETRIES = 3  # Количество попыток подключения с одной прокси
ACCOUNT_DELAY = 0.25  # Задержка между запусками аккаунтов (увеличена до 0.35 сек)

# Словарь для хранения забаненных прокси
banned_proxies = {}

# Словарь для отслеживания используемых прокси
used_proxies = {}

# Словарь для постоянного сопоставления аккаунтов и прокси
account_proxy_mapping = {}

# Загрузка прокси из файла
def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as f:
            proxy_lines = [line.strip() for line in f if line.strip()]
            # Создаем объекты Proxy из строк
            proxies = []
            for line in proxy_lines:
                try:
                    proxy = Proxy.from_str(line)
                    proxies.append(proxy)
                except Exception as e:
                    # Убираем лишний лог при ошибке парсинга
                    pass
            return proxies
    except Exception as e:
        logger.error(f"Ошибка при загрузке проксей: {e}")
        return []

# Получение рабочей прокси
def get_proxy(proxies, exclude_proxies=None):
    if exclude_proxies is None:
        exclude_proxies = []
    
    # Очистка истекших банов
    current_time = time.time()
    expired_bans = [p for p, ban_time in banned_proxies.items() 
                    if current_time - ban_time > PROXY_BAN_TIME]
    for p in expired_bans:
        banned_proxies.pop(p, None)
    
    # Получаем список доступных прокси
    exclude_set = set(exclude_proxies)
    
    # Используем строковое представление прокси для сравнения
    available_proxies = []
    for p in proxies:
        proxy_str = str(p)
        if proxy_str not in exclude_set and proxy_str not in banned_proxies and proxy_str not in used_proxies:
            available_proxies.append(p)
    
    if not available_proxies:
        logger.error("Нет доступных прокси!")
        return None
    
    # Выбираем случайную прокси
    proxy = random.choice(available_proxies)
    return proxy

# Назначение прокси аккаунтам
def assign_proxies_to_accounts(accounts, proxies):
    global account_proxy_mapping
    account_proxy_mapping.clear()
    available_proxies = proxies.copy()
    
    for email in accounts.keys():
        if available_proxies:
            proxy = random.choice(available_proxies)
            account_proxy_mapping[email] = proxy
            used_proxies[str(proxy)] = email
            available_proxies.remove(proxy)
        else:
            logger.warning(f"Не хватает прокси для аккаунта {email}. Аккаунт не будет обработан.")
            continue
    
    logger.info(f"Назначено {len(account_proxy_mapping)} прокси для {len(accounts)} аккаунтов")
    return account_proxy_mapping

# Загрузка аккаунтов
def load_accounts(login_file):
    accounts = {}
    try:
        if os.path.exists(login_file):
            with open(login_file, 'r') as f:
                for line in f:
                    parts = line.strip().split(':')
                    if len(parts) >= 3:
                        email = parts[0].strip()
                        token = parts[2].strip()
                        if email and token:
                            accounts[email] = token
            logger.info(f"Загружено {len(accounts)} аккаунтов")
        else:
            logger.error(f"Файл логинов {login_file} не найден")
    except Exception as e:
        logger.error(f"Ошибка при загрузке аккаунтов: {e}")
    return accounts

# Загрузка текущих балансов
def load_balances(farm_result_file):
    balances = {}
    try:
        if os.path.exists(farm_result_file):
            with open(farm_result_file, 'r') as f:
                for line in f:
                    parts = line.strip().split('|')
                    if len(parts) >= 2:
                        email = parts[0].strip()
                        balance = parts[1].strip()
                        balances[email] = balance
            # Убираем лишний лог при загрузке балансов
    except Exception as e:
        logger.error(f"Ошибка при загрузке балансов: {e}")
    return balances

# Обновление баланса
def update_balance(email, balance, balances, farm_result_file):
    balances[email] = balance
    
    try:
        # Собираем все записи для файла
        lines = []
        for acc_email, acc_balance in balances.items():
            lines.append(f"{acc_email}|{acc_balance}")
        
        # Создаем директорию для результатов, если её нет
        os.makedirs(os.path.dirname(farm_result_file), exist_ok=True)
        
        # Записываем в файл
        with open(farm_result_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        # Убираем лишний вывод при обновлении баланса
        # logger.info(f"Обновлен баланс для {email}: {balance}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении баланса: {e}")

# Отметка прокси как забаненной
def ban_proxy(proxy):
    """Временно запрещаем использование прокси"""
    if not proxy:
        return None
    
    # Добавляем прокси в черный список с текущим временем
    proxy_str = str(proxy)
    banned_proxies[proxy_str] = time.time()
    # Убираем лишний лог при бане прокси
    return proxy_str

# Освобождение прокси после использования
def release_proxy(proxy):
    proxy_str = str(proxy)
    if proxy_str in used_proxies:
        del used_proxies[proxy_str]

# Проверка аккаунта и фармилка
async def check_account(email, token, proxies, balances, ua, account_num):
    """
    Проверка баланса аккаунта с использованием уникальной прокси
    Возвращает (успех, время_следующего_пинга)
    """
    headers = {
        'User-Agent': ua.random,
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    # JSON-тело запроса с качеством в диапазоне 60-80, как в оригинальном JS коде
    quality = random.randint(60, 80)
    payload = {
        "quality": quality
    }
    
    # Очищаем истекшие баны прокси
    current_time = time.time()
    expired_bans = [p for p, ban_time in list(banned_proxies.items()) 
                  if current_time - ban_time > PROXY_BAN_TIME]
    for p in expired_bans:
        banned_proxies.pop(p, None)
    
    # Получаем прокси, назначенную этому аккаунту
    proxy = account_proxy_mapping.get(email)
    if not proxy:
        logger.error(f"Нет назначенной прокси для {email}")
        return False, random.randint(MIN_PING_INTERVAL, MAX_PING_INTERVAL)
    
    proxy_str = str(proxy)
    if proxy_str not in used_proxies:
        used_proxies[proxy_str] = email  # Отмечаем прокси как используемую
    
    # Делаем несколько попыток с выбранной прокси перед её баном
    for retry in range(PROXY_CONNECTION_RETRIES):
        try:
            # Получаем URL для httpx из объекта Proxy
            proxy_url = proxy.as_url
            
            # Устанавливаем более строгие таймауты для операций
            timeout = httpx.Timeout(30.0, connect=10.0)
            
            # Транспорт для httpx с настройками прокси
            transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
            
            # Создаем клиент с настроенным транспортом
            async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
                # Отправляем POST запрос
                response = await client.post(API_URL, headers=headers, json=payload)
                
                status = response.status_code
                response_text = response.text
                print(status)

                if status == 200:
                    try:
                        data = json.loads(response_text)
                        
                        # Пробуем извлечь баланс - в зависимости от структуры ответа
                        balance = None
                        
                        # Поддерживаем разные возможные структуры ответа
                        if 'data' in data:
                            if 'balances' in data['data'] and 'POINT' in data['data']['balances']:
                                balance = str(data['data']['balances']['POINT'])
                            elif 'user' in data['data'] and 'points' in data['data']['user']:
                                balance = str(data['data']['user']['points'])
                            elif 'points' in data['data']:
                                balance = str(data['data']['points'])
                            elif 'walletBalance' in data['data']:
                                balance = str(data['data']['walletBalance'])
                            elif 'balance' in data['data']:
                                balance = str(data['data']['balance'])
                        
                        if balance:
                            update_balance(email, balance, balances, FARM_RESULT_FILE)
                            # Красивый лог с цветным форматированием
                            log_msg = f"[{LogColors.ACCOUNT_NUM}{account_num}{LogColors.RESET}]-[{LogColors.EMAIL}{email}{LogColors.RESET}]-[{LogColors.STATUS}успешно{LogColors.RESET}]-[{LogColors.BALANCE}{balance}{LogColors.RESET}]"
                            logger.info(log_msg)
                            return True, random.randint(MIN_PING_INTERVAL, MAX_PING_INTERVAL)  # Случайный интервал между запросами
                        else:
                            # Даже если нет баланса, но запрос прошёл успешно - считаем успехом
                            # Красивый лог с цветным форматированием
                            log_msg = f"[{LogColors.ACCOUNT_NUM}{account_num}{LogColors.RESET}]-[{LogColors.EMAIL}{email}{LogColors.RESET}]-[{LogColors.STATUS}успешно{LogColors.RESET}]-[{LogColors.BALANCE}нет_баланса{LogColors.RESET}]"
                            logger.info(log_msg)
                            return True, random.randint(MIN_PING_INTERVAL, MAX_PING_INTERVAL)  # Случайный интервал между запросами
                    except json.JSONDecodeError:
                        logger.error(f"Невалидный JSON ответ для {email}")
                elif status == 400:
                    logger.warning(f"Ошибка 400 для {email}")
                    return False, random.randint(MIN_PING_INTERVAL, MAX_PING_INTERVAL)  # При ошибке 400 используем тот же случайный интервал
                else:
                    logger.error(f"Ошибка {status} для {email}")
                    # Баним прокси при ошибках статуса
                    ban_proxy(proxy)
        except httpx.TimeoutException:
            # Если последняя попытка - баним прокси
            if retry == PROXY_CONNECTION_RETRIES - 1:
                ban_proxy(proxy)
        except httpx.ProxyError:
            # Баним проблемную прокси
            ban_proxy(proxy)
            break  # Выходим из цикла retry - эта прокси точно не работает
        except Exception as e:
            error_text = str(e)
            # Если ошибка связана с сервером - баним прокси
            if "Server disconnected" in error_text:
                ban_proxy(proxy)
                break
            
        # Небольшая пауза перед повторной попыткой с той же прокси
        if retry < PROXY_CONNECTION_RETRIES - 1:
            await asyncio.sleep(2)
    
    # Если все попытки неудачны - тихо возвращаем ошибку
    return False, random.randint(MIN_PING_INTERVAL, MAX_PING_INTERVAL)

# Класс для управления обработкой аккаунтов
class FarmWorker:
    def __init__(self, worker_id):
        self.worker_id = worker_id
        self.thread_id = worker_id  # Сохраняем для совместимости с логгером
        
    async def process_account(self, email, token, proxies, balances, ua, account_num):
        """Последовательная обработка одного аккаунта с периодическими пингами"""
        
        while True:
            # Устанавливаем thread_id для логгера
            threading_context = {"threadid": str(self.thread_id)}
            
            success, sleep_time = await check_account(email, token, proxies, balances, ua, account_num)
            
            if not success:
                # Убираем лишний лог при неудаче - основное уже будет залогировано в check_account
                pass
            
            await asyncio.sleep(sleep_time)

# Основная функция
async def main():
    # Загружаем аккаунты и прокси
    accounts = load_accounts(LOGIN_FILE)
    balances = load_balances(FARM_RESULT_FILE)
    proxies = load_proxies(PROXY_FILE)
    ua = UserAgent()
    
    if not accounts:
        logger.error("Не удалось загрузить аккаунты")
        return
    
    if not proxies:
        logger.error("Не удалось загрузить прокси")
        return
    
    # Назначаем прокси аккаунтам
    assign_proxies_to_accounts(accounts, proxies)
    
    if not account_proxy_mapping:
        logger.error("Не удалось назначить прокси аккаунтам")
        return
    
    # Создаем задачи для каждого аккаунта с задержкой
    emails = list(account_proxy_mapping.keys())
    logger.info(f"Всего аккаунтов с назначенными прокси: {len(emails)}")
    
    # Создаем все задачи и запускаем их последовательно с задержкой
    tasks = []
    worker = FarmWorker(1)  # Используем только один воркер
    
    # Запускаем задачи для всех аккаунтов последовательно
    for i, email in enumerate(emails):
        account_num = i + 1
        token = accounts[email]
        
        # Устанавливаем threading_context для логгера
        threading_context = {"threadid": "1"}
        
        # Запускаем задачу для аккаунта
        task = asyncio.create_task(
            worker.process_account(email, token, proxies, balances, ua, account_num)
        )
        tasks.append(task)
        
        # Задержка между запуском аккаунтов
        if i < len(emails) - 1:
            await asyncio.sleep(ACCOUNT_DELAY)  # 0.35 секунды между аккаунтами
    
    logger.info(f"Все {len(emails)} аккаунтов запущены")
    
    # Скрипт не должен завершаться, пока работают задачи аккаунтов
    while True:
        await asyncio.sleep(3600)  # Проверка раз в час

if __name__ == "__main__":
    # Добавляем корневой фильтр для всех сообщений
    root_filter = ThreadIdFilter()
    for handler in logging.getLogger().handlers + logger.handlers:
        handler.addFilter(root_filter)
        
    logger.info("Запуск фарма...")
    try:
        # Создаем пример файла login.txt если он не существует
        if not os.path.exists(LOGIN_FILE):
            os.makedirs(os.path.dirname(LOGIN_FILE), exist_ok=True)
            sample_logins = [
                "email1@example.com:password1:token1", 
                "email2@example.com:password2:token2"
            ]
            with open(LOGIN_FILE, 'w', encoding='utf-8') as f:
                f.write('\n'.join(sample_logins))
            logger.info(f"Создан пример файла {LOGIN_FILE}")
        
        # Запуск главной функции
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Работа скрипта прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        import traceback
        logger.error(traceback.format_exc()) 