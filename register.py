#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import csv
import secrets
import string
import subprocess
import smtplib
import requests
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from io import StringIO

from register_config import SHEET_CSV_URL, SMTP_USER, SMTP_SERVER, SMTP_PORT, SMTP_PASS, REGISTRATION_DIR, LOG_DIR, \
    BASE_DIR, LOG_RETENTION_DAYS, PROCESSED_FILE, USERS_FILE
from register_logger import log_info, log_error, log_warning, cleanup_old_logs



def init_dirs():
    os.makedirs(REGISTRATION_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    if not os.path.exists(PROCESSED_FILE):
        open(PROCESSED_FILE, 'w').close()

    if not os.path.exists(USERS_FILE):
        json.dump({}, open(USERS_FILE, 'w'))


def get_processed_hashes():
    with open(PROCESSED_FILE, 'r') as f:
        return set(line.strip() for line in f if line.strip())


def add_processed_hash(row_hash):
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{row_hash}\n")


def get_row_hash(row):
    content = f"{row.get('1. Ваше имя', '')}_{row.get('2.  Ваш статус', '')}_{row.get('3.  Цель использования системы', '')}_{row.get('4.  Планируемое количество выносных узлов', '')}_{row.get('5. Логин', '')}_{row.get('6. Пароль', '')}_{row.get('7. Адрес электронной почты для связи', '')}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def generate_login():
    """Генерирует валидный логин: только буквы/цифры, длина >= 6, не занят"""
    while True:
        login = f"user{secrets.randbelow(100000):05d}"
        if is_valid_login(login) and not is_login_taken(login):
            return login


def generate_password():
    """Генерирует валидный пароль: длина >= 10, цифра, заглавная буква, спецсимвол, без пробелов"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(12))
        if is_valid_password(password):
            return password


def is_valid_login(login):
    """Проверяет, соответствует ли логин требованиям: длина не менее 6 символов, только буквы/цифры"""
    return bool(login and len(login) >= 6 and re.match(r'^[a-zA-Z0-9]+$', login))


def is_valid_password(password):
    """Проверяет, соответствует ли пароль требованиям:
       - длина >= 10
       - хотя бы одна цифра
       - хотя бы одна заглавная буква
       - хотя бы один спецсимвол
       - без пробелов
    """
    if not password or len(password) < 10:
        return False
    if ' ' in password:
        return False
    has_digit = any(c.isdigit() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_special = any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/`~" for c in password)
    return has_digit and has_upper and has_special


def create_ftp_user(login, password):
    try:
        result = subprocess.run(["id", login], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            log_warning(f"Пользователь уже существует, пропустить", login=login)
            user_dir = os.path.join(BASE_DIR, login)
            return user_dir

        user_dir = os.path.join(BASE_DIR, login)

        subprocess.run(["sudo", "useradd", "-m", "-d", user_dir, "-s", "/bin/false", login], check=True)
        subprocess.run(["sudo", "chpasswd"], input=f"{login}:{password}".encode('utf-8'), check=True)
        subprocess.run(["sudo", "chown", "-R", f"{login}:{login}", user_dir], check=False)
        subprocess.run(["sudo", "chmod", "700", user_dir], check=False)

        log_info(f"Создан системный пользователь", login=login)
        return user_dir

    except Exception as e:
        log_error(f"Ошибка создания пользователя: {e}", login=login)
        raise


def create_device_folder(user_dir):
    devices_dir = os.path.join(user_dir, "devices")
    login = os.path.basename(user_dir)

    if not os.path.exists(devices_dir):
        subprocess.run(["sudo", "mkdir", "-p", devices_dir], check=False)
        subprocess.run(["sudo", "chmod", "700", devices_dir], check=False)
        log_info(f"Создана папка devices", login=login)
    else:
        log_info(f"Папка devices уже существует, пропустить создание", login=login)

    return devices_dir


def is_login_taken(login):
    user_dir = os.path.join(BASE_DIR, login)
    if os.path.exists(user_dir):
        return True

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
            if login in users:
                return True

    result = subprocess.run(["id", login], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0


def save_user_data(login, password, email, name, status, purpose, nodes, user_dir):
    users = {}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)

    users[login] = {
        "password": password,
        "email": email,
        "name": name,
        "status": status,
        "purpose": purpose,
        "nodes": nodes,
        "created_at": datetime.now().isoformat(),
        "user_folder": user_dir
    }
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def send_email(to_email, login, password):
    subject = "Регистрация в системе удалённого мониторинга параметров окружающей среды"

    data_block = f"""
    Логин для FTP:                     {login}
    Пароль для FTP:                    {password}
    IP-адрес FTP-сервера:              194.87.79.156
    Порт FTP-сервера:                  21
"""

    body = f"""Здравствуйте!

Вы получили это письмо, потому что заполнили форму регистрации в системе удалённого мониторинга параметров окружающей среды.

Ваша учётная запись создана. Данные для подключения:{data_block}

Для начала работы Вам необходимо скачать по приведённым ссылкам:
1. Прошивку выносного узла: https://cloud.mail.ru/public/eJ1x/i71AxdYoS
2. Клиентское приложение для Windows / Linux: https://cloud.mail.ru/public/U2B7/f5KiukTnH
3. Инструкцию по настройке и запуску: https://cloud.mail.ru/public/i33r/zeWhH2zC4

Если у Вас возникли проблемы:
1. Проверьте правильность ввода логина и пароля в файлах прошивки и клиентского приложения (см. инструкцию).
2. Убедитесь, что FTP-сервер доступен (проверьте интернет-соединение)
3. Обратитесь в поддержку: env.monitoring@mail.ru

С уважением,
Команда системы удалённого мониторинга
"""

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        log_info(f"Письмо отправлено", login=login)
        return True
    except Exception as e:
        log_error(f"Ошибка отправки письма: {e}", login=login)
        return False


def get_csv_data():
    try:
        response = requests.get(SHEET_CSV_URL, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        content = response.text
        if content.startswith('\ufeff'):
            content = content[1:]
        return content
    except Exception as e:
        log_error(f"Ошибка загрузки CSV: {e}")
        return None


def main():
    init_dirs()
    log_file = os.path.join(LOG_DIR, "register.log")
    deleted = cleanup_old_logs(log_file, LOG_RETENTION_DAYS)
    if deleted > 0:
        log_info(f"register.log очищен: удалено {deleted} устаревших записей")
    log_info("=== Скрипт регистрации запущен ===")

    csv_content = get_csv_data()
    if not csv_content:
        log_error("Не удалось загрузить CSV, завершение")
        return

    reader = csv.DictReader(StringIO(csv_content))
    processed_hashes = get_processed_hashes()

    for row_index, row in enumerate(reader, start=2):
        row_hash = get_row_hash(row)

        if row_hash in processed_hashes:
            continue

        email = row.get('7. Адрес электронной почты для связи', '').strip()

        name = row.get('1. Ваше имя', '').strip()
        status = row.get('2.  Ваш статус', '').strip()
        purpose = row.get('3.  Цель использования системы', '').strip()
        nodes = row.get('4.  Планируемое количество выносных узлов', '').strip()
        custom_login = row.get('5. Логин', '').strip()
        custom_password = row.get('6. Пароль', '').strip()

        log_info(f"Обработка {email}")

        if custom_login and is_valid_login(custom_login) and not is_login_taken(custom_login):
            login = custom_login.lower()
            log_info(f"Логин принят: {login}", login=login)
        else:
            if custom_login and not is_valid_login(custom_login):
                log_warning(
                    f"Логин '{custom_login}' не соответствует требованиям (мин. 6 символов, буквы/цифры), генерируется автоматически",
                    login=login)
            elif custom_login and is_login_taken(custom_login):
                log_warning(f"Логин '{custom_login}' уже занят, генерируется автоматически", login=login)
            login = generate_login()
            log_info(f"Логин сгенерирован: {login}", login=login)

        if custom_password and is_valid_password(custom_password):
            password = custom_password
            log_info(f"Пароль принят пользовательский", login=login)
        else:
            if custom_password and not is_valid_password(custom_password):
                log_warning(
                    f"Пароль не соответствует требованиям (мин. 10 символов, цифра, заглавная буква, спецсимвол, без пробелов), генерируется автоматически",
                    login=login)
            password = generate_password()
            log_info(f"Пароль сгенерирован автоматически", login=login)

        try:
            user_dir = create_ftp_user(login, password)
            create_device_folder(user_dir)
            save_user_data(login, password, email, name, status, purpose, nodes, user_dir)
            send_email(email, login, password)

            log_info(f"Регистрация успешно завершена", login=login)
        except Exception as e:
            log_error(f"Ошибка регистрации: {e}", login=login)
            continue

        add_processed_hash(row_hash)

    log_info("=== Скрипт регистрации завершён ===")


if __name__ == "__main__":
    main()