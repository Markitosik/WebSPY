import json
import subprocess
import threading
import time
import os
import logging
import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from croniter import croniter
from datetime import datetime
import tempfile
from urllib.parse import urlparse, parse_qs
from zipfile import ZipFile

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HTML_OUTPUT_DIR = "/data/html_pages"

# Список для отслеживания активных дисплеев
active_displays = []
lock = threading.Lock()  # Для синхронизации доступа к списку


# Функция для получения user-agent по типу ОС
def get_user_agent(os_type):
    user_agents = {
        'windows': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0",
        'mac': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:92.0) Gecko/20100101 Firefox/92.0",
        'android': "Mozilla/5.0 (Android 10; Mobile; rv:89.0) Gecko/89.0 Firefox/89.0",
        'ios': "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/29.0 Mobile/15E148 Safari/605.1.15",
        'linux': "Mozilla/5.0 (X11; Linux x86_64; rv:92.0) Gecko/20100101 Firefox/92.0",
    }
    return user_agents.get(os_type.lower(), "")


# Функция для логирования редиректов
def log_redirects(url):
    redirects = []
    last_path = None

    try:
        session = requests.Session()
        response = session.get(url, allow_redirects=True)

        # Обработка истории редиректов
        for resp in response.history:
            parsed_url = urlparse(resp.url)
            query_params = parse_qs(parsed_url.query)

            if last_path is None or parsed_url.path != last_path:
                redirects.append({'url': resp.url, 'status': resp.status_code})
                logging.info(f"Редирект на: {resp.url} со статусом {resp.status_code}")
            last_path = parsed_url.path

        # Логирование финальной страницы
        final_url = response.url
        final_status = response.status_code
        redirects.append({'url': final_url, 'status': final_status})
        logging.info(f"Финальная ссылка: {final_url} со статусом {final_status}")

        return response, redirects

    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при выполнении запроса: {e}")
        return None, redirects


# Функция для сохранения финальной HTML-страницы
def save_final_html(response, original_url):
    if response is not None:
        domain_name = urlparse(original_url).netloc.replace('.', '_')
        output_dir = f"/data/{domain_name}"
        file_name = f"{domain_name}_final.html"
        file_path = os.path.join(output_dir, file_name)
        os.makedirs(output_dir, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(response.text)
        logging.info(f"HTML финальной страницы сохранен в: {file_path}")


# Настройка WebDriver для Firefox
def setup_driver(screen_size, os_type, proxy=None, profile_dir=None):
    options = FirefoxOptions()
    options.add_argument(f"--width={screen_size[0]}")
    options.add_argument(f"--height={screen_size[1]}")
    options.headless = True  # Включаем headless режим

    user_agent = get_user_agent(os_type)
    if user_agent:
        options.set_preference("general.useragent.override", user_agent)

    if profile_dir:
        options.profile = profile_dir

    service = FirefoxService()
    driver = webdriver.Firefox(options=options, service=service)
    driver.set_window_size(screen_size[0], screen_size[1])  # Установка размера окна браузера
    return driver


# Функция для поиска свободного нечетного дисплея
def find_free_display():
    with lock:
        for display_num in range(1, 100, 2):  # Проверяем нечетные дисплеи
            if display_num not in active_displays:
                active_displays.append(display_num)
                return display_num
    return None


# Функция для освобождения дисплея
def release_display(display_num):
    with lock:
        if display_num in active_displays:
            active_displays.remove(display_num)


# Функция для запуска браузера и записи экрана
def start_browser_and_record(display_num, url, screen_size, os_type, proxy, profile_dir):
    domain_name = urlparse(url).netloc.replace('.', '_')
    output_dir = f"/data/{domain_name}"
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/{domain_name}_output.mp4"

    logging.info(f"Запуск виртуального дисплея :{display_num} для {domain_name} с разрешением {screen_size[0]}x{screen_size[1]}")

    # Сбор информации о редиректах перед запуском браузера
    response, redirects = log_redirects(url)

    # Сохранение информации о редиректах
    redirect_file = f"{output_dir}/{domain_name}_redirects.txt"
    with open(redirect_file, 'w') as f:
        for redirect in redirects:
            f.write(f"{redirect['status']} {redirect['url']}\n")
    logging.info(f"Информация о редиректах сохранена в: {redirect_file}")

    # Сохранение финальной HTML-страницы
    save_final_html(response, url)

    # Запуск Xvfb с указанным разрешением экрана
    xvfb_process = subprocess.Popen(["Xvfb", f":{display_num}", "-screen", "0", f"{screen_size[0]}x{screen_size[1]}x24"])
    time.sleep(5)

    try:
        if xvfb_process.poll() is not None:
            raise RuntimeError(f"Не удалось запустить Xvfb на дисплее :{display_num}")

        # Создаем копию окружения с уникальным DISPLAY для каждого потока
        local_env = os.environ.copy()
        local_env["DISPLAY"] = f":{display_num}"
        logging.info(f"Настройка драйвера Selenium для дисплея :{display_num} с DISPLAY={local_env['DISPLAY']}")
        driver = setup_driver(screen_size, os_type, None, profile_dir)
        driver.get(url)

        # Проверка готовности страницы
        WebDriverWait(driver, 60).until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Формируем имена файлов на основе доменного имени
        screenshot_file = f"{output_dir}/{domain_name}.png"
        page_html = driver.find_element(By.TAG_NAME, 'html')
        page_html.screenshot(screenshot_file)

        logging.info(f"Сохранен скриншот для дисплея :{display_num}: {screenshot_file}")

        # Вызов следующей функции записи (на втором дисплее)
        start_browser_and_record1(display_num * 2, url, output_file, screen_size, profile_dir)

        # Архивирование файлов
        archive_file = f"{output_dir}/{domain_name}.zip"
        with ZipFile(archive_file, 'w') as archive:
            archive.write(screenshot_file, os.path.basename(screenshot_file))
            archive.write(output_file, os.path.basename(output_file))
            archive.write(redirect_file, os.path.basename(redirect_file))
            archive.write(f"{output_dir}/{domain_name}_final.html", f"{domain_name}_final.html")

        logging.info(f"Создан архив для {domain_name}: {archive_file}")

        logging.info(f"Останавливаем запись на дисплее :{display_num}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Произошла ошибка при выполнении команды: {e}")
    except RuntimeError as e:
        logging.error(f"Ошибка во время работы программы: {e}")
    finally:
        if xvfb_process:
            xvfb_process.terminate()
            xvfb_process.wait()
        if 'driver' in locals() and driver:
            driver.quit()

        # Освобождаем дисплей
        release_display(display_num)


# Функция для запуска браузера и записи экрана на следующий дисплей
def start_browser_and_record1(display_num, url, output_file, screen_size, profile_dir):
    # Запуск виртуального дисплея с указанным разрешением экрана
    xvfb_process = subprocess.Popen(["Xvfb", f":{display_num}", "-screen", "0", f"{screen_size[0]}x{screen_size[1]}x24"])
    time.sleep(2)

    try:
        if xvfb_process.poll() is not None:
            raise RuntimeError(f"Не удалось запустить Xvfb на дисплее :{display_num}")

        # Создание директории для профиля
        os.makedirs(profile_dir, exist_ok=True)

        # Запуск браузера с использованием отдельного профиля и установка точных размеров окна
        browser_process = subprocess.Popen(["firefox", "-no-remote", "-profile", profile_dir, url],
                                           env={"DISPLAY": f":{display_num}"})

        # Установка точного разрешения для браузера через xdotool
        subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "firefox", "windowsize", "100%", "100%"], env={"DISPLAY": f":{display_num}"})

        print(f"Начинаем запись на дисплее :{display_num}")

        # Запуск записи экрана с использованием ffmpeg
        ffmpeg_process = subprocess.Popen([
            "ffmpeg", "-y", "-f", "x11grab", "-s", f"{screen_size[0]}x{screen_size[1]}", "-i", f":{display_num}.0",
            "-r", "25", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", output_file
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        time.sleep(5)

        # Ожидание полной загрузки страницы
        max_wait_time = 15
        start_time = time.time()
        while True:
            if (time.time() - start_time) > max_wait_time:
                break
            time.sleep(1)

        print(f"Останавливаем запись на дисплее :{display_num}")
        ffmpeg_process.terminate()
        ffmpeg_process.wait()

        # Считывание и вывод журнала ffmpeg для отладки
        out, _ = ffmpeg_process.communicate()
        # print(out.decode())
    except subprocess.CalledProcessError as e:
        print(f"Произошла ошибка при выполнении команды: {e}")
    except RuntimeError as e:
        print(f"Ошибка во время работы программы: {e}")
    finally:
        if xvfb_process:
            xvfb_process.terminate()
            xvfb_process.wait()
        if browser_process:
            browser_process.terminate()
            browser_process.wait()


# Функция для планирования задач по cron-расписанию
def schedule_tasks():
    tasks = read_tasks()
    task_schedules = []

    for task in tasks:
        cron_expression = task.get("schedule")
        schedule_iter = croniter(cron_expression, datetime.now())
        next_run_time = schedule_iter.get_next(datetime)
        task_schedules.append((task, next_run_time))

    return task_schedules


# Функция для запуска задач по расписанию
def run_scheduled_tasks():
    # Хранение времени следующего запуска для каждой задачи
    task_schedules = schedule_tasks()

    while True:
        current_time = datetime.now()
        print(f'текущее время {current_time}')

        for i, (task, next_run_time) in enumerate(task_schedules):
            print(f'время запуска {next_run_time}')
            if current_time >= next_run_time:
                logging.info(f"Выполнение задачи: {task['url']}")

                # Поиск свободного дисплея
                display_num = find_free_display()
                if display_num is not None:
                    # Запуск задачи в отдельном потоке
                    threading.Thread(target=start_browser_and_record, args=(
                        display_num,
                        task['url'],
                        tuple(map(int, task['screen_size'].split('x'))),
                        task['os_type'],
                        task.get('proxy'),
                        tempfile.mkdtemp()
                    )).start()

                    # Пересчёт следующего времени выполнения
                    cron_expression = task.get("schedule")
                    schedule_iter = croniter(cron_expression, current_time)
                    next_run_time = schedule_iter.get_next(datetime)

                    # Обновляем время запуска для этой задачи
                    task_schedules[i] = (task, next_run_time)
                else:
                    logging.warning("Нет доступных дисплеев для выполнения задачи.")

        time.sleep(5)


# Чтение задач из файла
def read_tasks():
    with open("tasks.json", "r") as file:
        tasks = json.load(file)
    return tasks


if __name__ == "__main__":
    run_scheduled_tasks()
