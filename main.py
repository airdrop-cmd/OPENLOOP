#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import json
import random
import time
import os
import asyncio
import concurrent.futures
from anticaptchaofficial.turnstileproxyless import turnstileProxyless
from fake_useragent import UserAgent
from termcolor import colored
import traceback
import config

# Пути к файлам
data_dir = 'data'
result_dir = 'result'
email_file = os.path.join(data_dir, 'email.txt')
proxies_file = os.path.join(data_dir, 'proxies.txt')
invitecode_file = os.path.join(data_dir, 'invitecode.txt')
failed_reg_file = os.path.join(data_dir, 'failed_reg.txt')
failed_login_file = os.path.join(data_dir, 'failed_login.txt')
login_file = os.path.join(result_dir, 'login.txt')

# Создаем пул потоков для блокирующих операций
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=config.num_threads)

# Инициализация UserAgent
ua = UserAgent()

# Словарь для отслеживания количества регистраций на каждый invite code
invite_code_usage = {}

# Функция для чтения данных из файла
def read_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

# Функция для записи данных в файл
def write_file(file_path, lines):
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line.strip() + '\n')

# Функция для добавления данных в файл
def append_file(file_path, line):
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(line.strip() + '\n')

# Функция для получения случайного прокси
def get_random_proxy():
    proxies = read_file(proxies_file)
    if not proxies:
        return None
    proxy = random.choice(proxies).strip()
    login, rest = proxy.split(':', 1)
    password, ip_port = rest.split('@', 1)
    return {
        'http': f'http://{login}:{password}@{ip_port}',
        'https': f'http://{login}:{password}@{ip_port}'
    }

# Блокирующая функция решения капчи
def solve_turnstile_blocking(email, thread_id):
    try:
        print(f'[Thread {thread_id}] [{colored(email, "blue")}] - Решаем капчу...')
        solver = turnstileProxyless()
        solver.set_verbose(0)
        solver.set_key(config.anticaptcha_key)
        solver.set_website_url('https://openloop.so')
        solver.set_website_key('0x4AAAAAAA3AMTe5gwdZnIEL')
        token = solver.solve_and_return_solution()
        if token != 0:
            print(f'[Thread {thread_id}] [{colored(email, "blue")}] - Капча Решена!')
            return token
        else:
            print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Ошибка при решении капчи: " + solver.error_code, "red")}')
            return None
    except Exception as e:
        print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Непредвиденная ошибка при решении капчи: " + str(e), "red")}')
        return None

# Асинхронная обертка для блокирующей функции решения капчи
async def solve_turnstile(email, thread_id):
    return await asyncio.get_event_loop().run_in_executor(
        thread_pool,
        solve_turnstile_blocking,
        email,
        thread_id
    )

# Функция для получения следующего доступного invite code
def get_next_invite_code():
    invite_codes = read_file(invitecode_file)
    for code in invite_codes:
        code = code.split(':')[0] if ':' in code else code
        if code not in invite_code_usage:
            invite_code_usage[code] = 0
        if invite_code_usage[code] < 1000:
            return code
    return None

# Асинхронная функция для выполнения HTTP-запроса
async def make_async_request(method, url, headers, data, proxies, timeout):
    def _make_request():
        if method.lower() == 'post':
            return requests.post(
                url, 
                headers=headers, 
                data=data,
                proxies=proxies,
                timeout=timeout
            )
        else:
            return requests.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=timeout
            )
    
    return await asyncio.get_event_loop().run_in_executor(
        thread_pool,
        _make_request
    )

# Функция для удаления аккаунта из файла email.txt
def remove_account_from_email_file(account_data):
    try:
        current_accounts = read_file(email_file)
        account_data_stripped = account_data.strip()
        if account_data_stripped in current_accounts:
            current_accounts.remove(account_data_stripped)
            write_file(email_file, current_accounts)
            email = account_data.split(':')[0]
            print(f'Аккаунт {email} удален из email.txt')
    except Exception as e:
        print(f'Ошибка при удалении аккаунта из email.txt: {str(e)}')

# Функция для регистрации одного аккаунта
async def register_account(account_data, thread_id, max_retries=3):
    email, password = account_data.split(':')
    login_name = email.split('@')[0]
    
    for attempt in range(max_retries):
        try:
            print(f'[Thread {thread_id}] [{colored(email, "blue")}] - Регистрируем аккаунт (попытка {attempt+1}/{max_retries})...')
            
            invite_code = get_next_invite_code()
            if not invite_code:
                print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Нет доступных invite кодов с лимитом менее 1000 регистраций!", "red")}')
                save_failed_reg(account_data)
                return False, account_data
                
            proxy = get_random_proxy()
            if not proxy:
                print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Нет доступных прокси!", "red")}')
                save_failed_reg(account_data)
                return False, account_data
                
            url = 'https://api.openloop.so/users/register'
            registration_details = {
                'name': login_name,
                'username': email,
                'password': password.strip(),
                'inviteCode': invite_code.strip()
            }
            
            # Решаем капчу
            turnstile_token = await solve_turnstile(email, thread_id)
            if not turnstile_token:
                print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Не удалось получить токен Turnstile", "red")}')
                continue
                
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Origin': 'https://openloop.so',
                'Referer': 'https://openloop.so/',
                'User-Agent': ua.random,
                'x-recaptcha-response': turnstile_token
            }
            
            # Асинхронный запрос
            response = await make_async_request(
                'post',
                url, 
                headers,
                json.dumps(registration_details),
                proxy,
                30
            )
            
            status_code = response.status_code
            response_data = response.json() if response.text else {}
            
            if status_code == 200:
                print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Аккаунт успешно зарегистрирован!", "green")}')
                invite_code_usage[invite_code] = invite_code_usage.get(invite_code, 0) + 1
                return True, account_data
            else:
                print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored(f"Ошибка регистрации: {status_code}", "red")}')
                continue
                
        except Exception as e:
            print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored(f"Ошибка при регистрации: {str(e)}", "red")}')
            continue
    
    # После всех неудачных попыток
    save_failed_reg(account_data)
    return False, account_data

# Функция для авторизации одного аккаунта
async def login_account(account_data, thread_id, max_retries=3):
    email, password = account_data.split(':')
    
    for attempt in range(max_retries):
        try:
            print(f'[Thread {thread_id}] [{colored(email, "blue")}] - Авторизуемся (попытка {attempt+1}/{max_retries})...')
            
            proxy = get_random_proxy()
            if not proxy:
                print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Нет доступных прокси!", "red")}')
                save_failed_login(account_data)
                return False, account_data, None
                
            url = 'https://api.openloop.so/users/login'
            login_details = {
                'username': email,
                'password': password.strip()
            }
            
            turnstile_token = await solve_turnstile(email, thread_id)
            if not turnstile_token:
                print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Не удалось получить токен Turnstile", "red")}')
                continue
                
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Origin': 'https://openloop.so',
                'Referer': 'https://openloop.so/',
                'User-Agent': ua.random,
                'x-recaptcha-response': turnstile_token
            }
            
            # Асинхронный запрос
            response = await make_async_request(
                'post',
                url, 
                headers,
                json.dumps(login_details),
                proxy,
                30
            )
            
            status_code = response.status_code
            response_data = response.json() if response.text else {}
            
            if status_code == 200 and response_data.get('code') == 2000:
                access_token = response_data.get('data', {}).get('accessToken', '')
                print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Авторизация успешна!", "green")}')
                save_successful_login(account_data, access_token)
                return True, account_data, access_token
            else:
                print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored(f"Ошибка авторизации: {status_code}", "red")}')
                continue
                
        except Exception as e:
            print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored(f"Ошибка при авторизации: {str(e)}", "red")}')
            continue
    
    # После всех неудачных попыток
    save_failed_login(account_data)
    return False, account_data, None

# Функция для сохранения неуспешной регистрации
def save_failed_reg(account_data):
    current_failed = read_file(failed_reg_file)
    if account_data.strip() not in [x.strip() for x in current_failed]:
        append_file(failed_reg_file, account_data)
    # Удаляем аккаунт из email.txt после обработки
    remove_account_from_email_file(account_data)

# Функция для сохранения неуспешной авторизации
def save_failed_login(account_data):
    current_failed = read_file(failed_login_file)
    if account_data.strip() not in [x.strip() for x in current_failed]:
        append_file(failed_login_file, account_data)
    # Удаляем аккаунт из email.txt после обработки
    remove_account_from_email_file(account_data)

# Функция для сохранения успешной авторизации
def save_successful_login(account_data, access_token):
    email, password = account_data.split(':')
    login_entry = f"{email}:{password}:{access_token}"
    current_successful = read_file(login_file)
    if login_entry.strip() not in [x.strip() for x in current_successful]:
        append_file(login_file, login_entry)
    # Удаляем аккаунт из email.txt после обработки
    remove_account_from_email_file(account_data)

# Функция для обработки одного аккаунта (регистрация и логин)
async def process_account(account_data, thread_id):
    try:
        email = account_data.split(':')[0]
        print(f'[Thread {thread_id}] Обработка аккаунта: {email}')
        
        # Регистрация
        reg_success, _ = await register_account(account_data, thread_id)
        if not reg_success:
            # Если регистрация не удалась, аккаунт уже сохранен в failed_reg.txt и удален из email.txt
            return False
            
        # Небольшая пауза между регистрацией и логином
        await asyncio.sleep(random.uniform(1, 2))
        
        # Логин
        login_success, _, _ = await login_account(account_data, thread_id)
        
        # Если регистрация успешна, но логин не удался, специально обрабатываем этот случай
        if not login_success:
            print(f'[Thread {thread_id}] [{colored(email, "blue")}] - {colored("Регистрация успешна, но логин не удался", "yellow")}')
            
        # Удаляем аккаунт из email.txt в любом случае, так как он уже обработан
        remove_account_from_email_file(account_data)
            
        return login_success
        
    except Exception as e:
        print(f'[Thread {thread_id}] Ошибка при обработке аккаунта: {str(e)}')
        traceback.print_exc()
        # В случае непредвиденной ошибки также удаляем аккаунт из email.txt
        remove_account_from_email_file(account_data)
        return False

# Функция для запуска обработки аккаунтов в корутинах
async def process_accounts_chunk(accounts, thread_id):
    results = []
    for account in accounts:
        success = await process_account(account, thread_id)
        results.append(success)
        # Задержка между аккаунтами
        await asyncio.sleep(random.uniform(1, 3))
    return results

# Основная асинхронная функция
async def main_async():
    try:
        print(f"Запуск в {config.num_threads} потоках...")
        
        # Создаем директории, если не существуют
        for directory in [data_dir, result_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Создана директория: {directory}")
                
        # Проверяем существование необходимых файлов
        for file_path in [email_file, proxies_file, invitecode_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass
                print(f"Создан пустой файл: {file_path}")
                    
        # Создаем файлы для результатов, если не существуют
        for file_path in [failed_reg_file, failed_login_file, login_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass
                print(f"Создан пустой файл для результатов: {file_path}")
        
        # Получаем список аккаунтов
        all_accounts = read_file(email_file)
        if not all_accounts:
            print('Ошибка: Файл email.txt пуст или не найден!')
            return
            
        # Проверяем наличие invite кодов
        invite_codes = read_file(invitecode_file)
        if not invite_codes:
            print('Ошибка: Файл invitecode.txt пуст или не найден!')
            return
            
        print(f'Найдено {len(all_accounts)} аккаунтов для обработки')
        print(f'Найдено {len(invite_codes)} инвайт кодов')
        print(f'Распределяем аккаунты по {config.num_threads} потокам...')
        
        # Общее количество обрабатываемых аккаунтов
        total_accounts = len(all_accounts)
        
        # Разделение аккаунтов на чанки для обработки в корутинах
        chunk_size = max(1, len(all_accounts) // config.num_threads)
        
        tasks = []
        for i in range(config.num_threads):
            start_idx = i * chunk_size
            end_idx = min((i + 1) * chunk_size, len(all_accounts))
            chunk_accounts = all_accounts[start_idx:end_idx]
            
            if chunk_accounts:
                print(f"Поток {i+1} получил {len(chunk_accounts)} аккаунтов для обработки")
                task = asyncio.create_task(process_accounts_chunk(chunk_accounts, i+1))
                task.set_name(f"Thread-{i+1}")
                tasks.append(task)
                
        # Ожидание завершения всех задач
        print(f"Запущено {len(tasks)} асинхронных задач, ожидаем завершения...")
        results = await asyncio.gather(*tasks)
        
        # Подсчет статистики
        successful_count = 0
        for chunk_result in results:
            if chunk_result:  # Проверка на None
                successful_count += sum(1 for success in chunk_result if success)
        
        failed_count = total_accounts - successful_count
        
        print(f'Все аккаунты обработаны. Успешно: {successful_count}, Неуспешно: {failed_count}')
        
    except Exception as e:
        print(f'Произошла ошибка: {str(e)}')
        traceback.print_exc()

# Основная функция
def main():
    try:
        print(f"Запуск программы. Настройки: количество потоков = {config.num_threads}")
        # Запуск асинхронной функции в цикле событий
        asyncio.run(main_async())
    except Exception as e:
        print(f'Произошла ошибка: {str(e)}')
        traceback.print_exc()
    finally:
        # Закрываем пул потоков при завершении
        thread_pool.shutdown()

if __name__ == '__main__':
    main() 