import subprocess
import threading
import time
import os

# Проверка зависимостей
def check_dependencies():
    try:
        subprocess.run(["which", "xwd"], check=True)
        subprocess.run(["which", "convert"], check=True)
        print("Все зависимости установлены.")
    except FileNotFoundError as e:
        print(f"Необходимая утилита не найдена: {e}")
        exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Проблема с проверкой утилит: {e}")
        exit(1)

# Функция для запуска браузера и записи экрана
def start_browser_and_record(display_num, url, output_file, profile_dir):
    # Запуск виртуального дисплея
    xvfb_process = subprocess.Popen(["Xvfb", f":{display_num}", "-screen", "0", "1024x768x24"])
    time.sleep(5)  # Увеличенная задержка для инициализации дисплея

    try:
        # Проверка доступности дисплея
        if not xvfb_process.poll() is None:
            raise RuntimeError(f"Не удалось запустить Xvfb на дисплее :{display_num}")

        # Создание директории для профиля
        os.makedirs(profile_dir, exist_ok=True)

        # Запуск браузера с использованием отдельного профиля
        browser_process = subprocess.Popen(["firefox", "-no-remote", "-profile", profile_dir, url],
                                           env={"DISPLAY": f":{display_num}"})
        #time.sleep(1)  # Задержка для инициализации браузера и полной загрузки страницы
        print(f"начинаем запись на дисплее :{display_num}")


        # Запуск записи экрана
        ffmpeg_process = subprocess.Popen([
            "ffmpeg", "-y", "-f", "x11grab", "-s", "1024x768", "-i", f":{display_num}.0",
            "-r", "25", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", output_file
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        time.sleep(5)
        # Сохранение скриншота экрана для проверки
        screenshot_xwd = f"/data/screenshot_{display_num}.xwd"
        screenshot_png = f"/data/screenshot_{display_num}.png"
        with open(screenshot_xwd, "wb") as f:
            subprocess.run(["xwd", "-root", "-display", f":{display_num}"], stdout=f, check=True)

        # Конвертация скриншота в PNG
        subprocess.run(["convert", screenshot_xwd, screenshot_png], check=True)

        # Ожидание времени записи
        time.sleep(10)  # Увеличенная задержка для записи видео
        ffmpeg_process.terminate()  # Завершение записи
        ffmpeg_process.wait()  # Ждем завершения

        # Считывание и вывод журнала ffmpeg для отладки
        out, _ = ffmpeg_process.communicate()
        print(out.decode())

        print(f"останавливаем запись на дисплее :{display_num}")
    except subprocess.CalledProcessError as e:
        print(f"Произошла ошибка при выполнении команды: {e}")
    except RuntimeError as e:
        print(f"Ошибка во время работы программы: {e}")
    finally:
        # Завершение процессов
        xvfb_process.terminate()
        browser_process.terminate()
        xvfb_process.wait()
        browser_process.wait()

# Основной блок программы
if __name__ == "__main__":
    # Проверка наличия зависимостей
    check_dependencies()

    # Определение ссылок и выходных файлов
    url = "http://example.com"
    url2 = 'http://github.com/Markitosik'
    output1 = "/data/output1.mp4"
    output2 = "/data/output2.mp4"
    profile1 = "/data/profile1"
    profile2 = "/data/profile2"

    print('qwer')
    # Создание потоков для параллельного запуска
    thread1 = threading.Thread(target=start_browser_and_record, args=(2, url, output1, profile1))
    thread2 = threading.Thread(target=start_browser_and_record, args=(3, url2, output2, profile2))

    # Запуск потоков
    thread1.start()
    thread2.start()

    # Ожидание завершения потоков
    thread1.join()
    thread2.join()

    print("Запись завершена для обоих дисплеев.")
