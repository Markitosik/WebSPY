# Базовый образ
FROM ubuntu:22.04

# Установка переменной окружения для неинтерактивной установки
ENV DEBIAN_FRONTEND=noninteractive

# Установка необходимых пакетов, включая x11-apps для xwd и imagemagick для convert
RUN apt-get update && \
    apt-get install -y wget xvfb x11vnc ffmpeg python3 python3-pip openbox \
    libgl1-mesa-glx libegl1-mesa libpci3 adwaita-icon-theme gnome-themes-extra \
    tzdata imagemagick x11-apps curl jq xdotool  # Добавлено xdotool

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    dpkg-reconfigure -f noninteractive tzdata

# Установка Firefox
RUN wget -qO- "https://download.mozilla.org/?product=firefox-latest&os=linux64&lang=en-US" | tar xjf - -C /opt/ && \
    ln -s /opt/firefox/firefox /usr/bin/firefox

# Установка geckodriver для работы с Selenium и Firefox
RUN GECKODRIVER_VERSION=$(curl -s https://api.github.com/repos/mozilla/geckodriver/releases/latest | jq -r '.tag_name') && \
    wget -q "https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz" -O /tmp/geckodriver.tar.gz && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin && \
    rm /tmp/geckodriver.tar.gz

# Установка Python-библиотек, включая Selenium и Requests
RUN pip3 install selenium requests

# Установка переменной окружения для дисплея
ENV DISPLAY=:1
ENV XDG_RUNTIME_DIR=/tmp/runtime
RUN mkdir -p /tmp/runtime && chmod 700 /tmp/runtime

# Создание необходимых директорий и установление прав
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

# Создание директории для вывода
RUN mkdir -p /data

# Копирование скрипта в контейнер
COPY parallel_recording1.py /parallel_recording1.py

# Запуск скрипта автоматически при старте контейнера
CMD ["python3", "/parallel_recording1.py"]
