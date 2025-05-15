# -*- coding: utf-8 -*-
import asyncio
import aiohttp
import json
import random
import time
import os
from fake_useragent import UserAgent
from termcolor import colored
import traceback
import config

# Пути к файлам
data_dir = 'data'
result_dir = 'result'
login_file = os.path.join(result_dir, 'login.txt')  # Теперь login.txt в папке result
proxies_file = os.path.join(data_dir, 'proxies.txt')
taskGood_file = os.path.join(result_dir, 'taskGood.txt')
failed_task_file = os.path.join(data_dir, 'failed_task.txt')

# Инициализация UserAgent
ua = UserAgent()

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
    return f'http://{login}:{password}@{ip_port}'

# Асинхронная функция для получения списка миссий
async def get_missions_list(session, proxy, token, task_id, email):
    try:
        url = 'https://api.openloop.so/missions'
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Authorization': f'Bearer {token}',
            'Cookie': '_ga=GA1.1.458110287.1745787541; _ga_WTJ5WKBKK9=GS1.1.1745787540.1.1.1745791694.0.0.0',
            'Priority': 'u=1, i',
            'Sec-Ch-Ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Storage-Access': 'active',
            'User-Agent': ua.random
        }
        async with session.get(url, headers=headers, proxy=proxy, timeout=25) as response:
            status_code = response.status
            if status_code == 200:
                try:
                    response_data = await response.json()
                    missions = response_data.get('data', {}).get('missions', [])
                    available_missions = [mission['missionId'] for mission in missions if mission.get('status') == 'available']
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Получен список миссий. Доступно: {len(available_missions)}", "green")}')
                    return available_missions
                except json.JSONDecodeError as e:
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ошибка парсинга JSON при получении миссий: {str(e)}", "red")}')
                    response_text = await response.text()
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Необработанный ответ сервера: {response_text[:200]}...", "yellow")}')
                    return []
            else:
                response_text = await response.text()
                print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ошибка получения списка миссий: {status_code}", "red")}')
                print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ответ сервера: {response_text[:200]}...", "yellow")}')
                return []
    except Exception as e:
        print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ошибка запроса списка миссий: {str(e)}", "red")}')
        return []

# Асинхронная функция для выполнения одной миссии
async def complete_mission(session, proxy, token, mission_id, email, task_id, max_retries=2):
    for attempt in range(max_retries):
        try:
            print(f'[Task {task_id}] [{colored(email, "blue")}] - Выполняем миссию {mission_id} (попытка {attempt+1}/{max_retries})...')
            url = f'https://api.openloop.so/missions/{mission_id}/complete'
            headers = {
                'Accept': '*/*',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Authorization': f'Bearer {token}',
                'Cookie': '_ga=GA1.1.458110287.1745787541; _ga_WTJ5WKBKK9=GS1.1.1745787540.1.1.1745791694.0.0.0',
                'Priority': 'u=1, i',
                'Sec-Ch-Ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'cross-site',
                'Sec-Fetch-Storage-Access': 'active',
                'User-Agent': ua.random
            }
            async with session.get(url, headers=headers, proxy=proxy, timeout=25) as response:
                status_code = response.status
                response_text = await response.text()
                response_data = {}
                
                # Проверка на "already" в ответе
                if "already" in response_text.lower():
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Миссия {mission_id} уже выполнена ранее", "yellow")}')
                    return True, f"mission_{mission_id}"
                
                try:
                    response_data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ошибка парсинга JSON: {str(e)}", "red")}')
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ответ сервера: {response_text[:200]}...", "yellow")}')
                
                if status_code == 200 or (response_data and response_data.get('code') == 2000):
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Миссия {mission_id} выполнена успешно!", "green")}')
                    return True, f"mission_{mission_id}"
                else:
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ошибка выполнения миссии {mission_id}: {status_code}", "red")}')
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ответ сервера: {response_text[:200]}...", "yellow")}')
                    
                    # Если последняя попытка, возвращаем False
                    if attempt == max_retries - 1:
                        return False, None
                    
                    # Если не последняя попытка, делаем задержку перед следующей попыткой
                    delay = random.uniform(2, 4)
                    print(f'[Task {task_id}] [{colored(email, "blue")}] - Ожидание {delay:.2f} секунд перед повторной попыткой')
                    await asyncio.sleep(delay)
                    
        except Exception as e:
            print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ошибка запроса для миссии {mission_id}: {str(e)}", "red")}')
            
            # Если последняя попытка, возвращаем False
            if attempt == max_retries - 1:
                return False, None
            
            # Если не последняя попытка, делаем задержку перед следующей попыткой
            delay = random.uniform(2, 4)
            print(f'[Task {task_id}] [{colored(email, "blue")}] - Ожидание {delay:.2f} секунд перед повторной попыткой')
            await asyncio.sleep(delay)
    
    # Если все попытки не удались
    return False, None

# Асинхронная функция для выполнения всех задач аккаунта
async def perform_account_tasks(account_data, session, proxy, task_id):
    try:
        email, password, access_token = account_data.split(':', 2)
        
        # Получаем список доступных миссий
        available_missions = await get_missions_list(session, proxy, access_token, task_id, email)
        
        # Если нет доступных миссий, проверяем, не находится ли аккаунт уже в taskGood_file
        if not available_missions:
            good_accounts = read_file(taskGood_file)
            if account_data.strip() in [x.strip() for x in good_accounts]:
                print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored("Нет доступных миссий и аккаунт уже в taskGood.txt", "yellow")}')
                return True, account_data
            
            # Если нет доступных миссий, это может означать, что все задания уже выполнены
            # или что возникла ошибка при получении списка миссий
            print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored("Нет доступных миссий для выполнения", "yellow")}')
            
            # Будем считать, что если нет доступных миссий - аккаунт успешный
            save_successful_task(account_data)
            print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored("Все миссии, вероятно, уже выполнены - сохраняем как успешный", "green")}')
            return True, account_data
            
        # Проверяем, не находится ли аккаунт уже в taskGood_file, если есть миссии
        good_accounts = read_file(taskGood_file)
        if account_data.strip() in [x.strip() for x in good_accounts]:
            print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored("Аккаунт уже в taskGood.txt, но есть доступные миссии. Выполняем...", "yellow")}')
            
        # Выполняем каждую миссию
        successful_missions = 0
        total_missions = len(available_missions)
        missions_results = []
        
        for mission_id in available_missions:
            success, result = await complete_mission(session, proxy, access_token, mission_id, email, task_id)
            if success:
                successful_missions += 1
                if result:
                    missions_results.append(result)
            
            # Задержка между миссиями
            delay = random.uniform(1, 3)
            print(f'[Task {task_id}] [{colored(email, "blue")}] - Задержка {delay:.2f} секунд перед следующей миссией')
            await asyncio.sleep(delay)
        
        # Проверяем, все ли миссии успешно выполнены
        if successful_missions == total_missions:
            save_successful_task(account_data)
            print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored("Все миссии выполнены успешно!", "green")}')
            return True, account_data
        else:
            save_failed_task(account_data)
            print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Выполнено {successful_missions}/{total_missions} миссий", "yellow")}')
            return False, account_data
            
    except Exception as e:
        print(f'[Task {task_id}] [{colored(email, "blue")}] - {colored(f"Ошибка при выполнении задачи: {str(e)}", "red")}')
        traceback.print_exc()
        save_failed_task(account_data)
        return False, account_data

# Функция для сохранения успешного выполнения задачи
def save_successful_task(account_data):
    current_successful = read_file(taskGood_file)
    if account_data.strip() not in [x.strip() for x in current_successful]:
        append_file(taskGood_file, account_data)
        print(f"Аккаунт {account_data.split(':')[0]} добавлен в taskGood.txt")

# Функция для сохранения неуспешного выполнения задачи
def save_failed_task(account_data):
    current_failed = read_file(failed_task_file)
    if account_data.strip() not in [x.strip() for x in current_failed]:
        append_file(failed_task_file, account_data)
        print(f"Аккаунт {account_data.split(':')[0]} добавлен в failed_task.txt")

# Асинхронная функция для обработки группы аккаунтов
async def process_account_batch(accounts_batch, batch_id):
    proxy = get_random_proxy()
    if not proxy:
        print(f'[Batch {batch_id}] Ошибка: Нет доступных прокси!')
        return 0, len(accounts_batch)
    
    successful_count = 0
    failed_count = 0
    
    print(f'[Batch {batch_id}] Запуск обработки пакета из {len(accounts_batch)} аккаунтов')
    
    # Создаем сессию с ограничением соединений
    connector = aiohttp.TCPConnector(limit=config.num_threads, ssl=False)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Создаем задачи для каждого аккаунта
        tasks = []
        for i, account_data in enumerate(accounts_batch):
            task_id = f"{batch_id}-{i+1}"
            tasks.append(perform_account_tasks(account_data.strip(), session, proxy, task_id))
        
        # Запускаем все задачи одновременно и ждем результаты
        results = await asyncio.gather(*tasks)
        
        # Обрабатываем результаты
        for success, _ in results:
            if success:
                successful_count += 1
            else:
                failed_count += 1
    
    print(f'[Batch {batch_id}] Обработка пакета завершена. Успешно: {successful_count}, Неуспешно: {failed_count}')
    return successful_count, failed_count

# Основная асинхронная функция
async def main_async():
    try:
        print(f"Запуск с настройками: {config.num_threads} потоков")
        
        # Создаем директории, если не существуют
        for directory in [data_dir, result_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Создана директория: {directory}")
        
        # Проверяем существование необходимых файлов
        for file_path in [login_file, proxies_file]:
            if not os.path.exists(file_path):
                print(f"Ошибка: Файл {file_path} не найден!")
                return 0, 0
        
        # Создаем файлы для результатов, если не существуют
        for file_path in [taskGood_file, failed_task_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass
                print(f"Создан пустой файл для результатов: {file_path}")
        
        # Получаем список аккаунтов
        all_accounts = read_file(login_file)
        if not all_accounts:
            print('Ошибка: Файл login.txt пуст или не найден!')
            return 0, 0
        
        print(f'Найдено {len(all_accounts)} аккаунтов для выполнения задач')
        
        # Разделение аккаунтов на пакеты по num_threads
        batch_size = config.num_threads
        batches = [all_accounts[i:i + batch_size] for i in range(0, len(all_accounts), batch_size)]
        
        print(f'Разделено на {len(batches)} пакетов по {batch_size} аккаунтов')
        
        total_successful = 0
        total_failed = 0
        
        # Обрабатываем каждый пакет последовательно
        for batch_id, batch in enumerate(batches, 1):
            print(f'Обработка пакета {batch_id}/{len(batches)}')
            successful, failed = await process_account_batch(batch, batch_id)
            total_successful += successful
            total_failed += failed
            
            # Задержка между пакетами
            if batch_id < len(batches):
                delay = random.uniform(3, 5)
                print(f'Задержка {delay:.2f} секунд перед следующим пакетом аккаунтов')
                await asyncio.sleep(delay)
        
        print(f'Все аккаунты обработаны. Успешно: {total_successful}, Неуспешно: {total_failed}')
        return total_successful, total_failed
    
    except Exception as e:
        print(f'Произошла глобальная ошибка: {str(e)}')
        traceback.print_exc()
        return 0, 0

# Основная функция
def main():
    try:
        print("Запуск выполнения задач...")
        return asyncio.run(main_async())
    except Exception as e:
        print(f'Произошла ошибка в main: {str(e)}')
        traceback.print_exc()
        return 0, 0

if __name__ == '__main__':
    main() 