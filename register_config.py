#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

# ===================== ПУТИ =====================
BASE_DIR = "/sim7600/FTP"
REGISTRATION_DIR = "/sim7600/registration"
LOG_DIR = "/sim7600/registration/logs"
PROCESSED_FILE = os.path.join(REGISTRATION_DIR, "processed_hashes.txt")
USERS_FILE = os.path.join(REGISTRATION_DIR, "users.json")

LOG_RETENTION_DAYS = 30

# ===================== GOOGLE SHEETS =====================
SHEET_NAME = "Форма регистрации в системе удалённого мониторинга (Ответы)"
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQwXZfk9Jp5SK7sUd4a_31gYPw3_v8Sx5aAAxf1wlJEFJYAivB0VDK_zN_B-1FsM2BEM2V2GIkbAVbG/pub?output=csv"

# ===================== SMTP (Mail.ru) =====================
SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 587
SMTP_USER = "env.monitoring@mail.ru"
SMTP_PASS = "M4Z6NicPmI7MOd0dtBEo"

