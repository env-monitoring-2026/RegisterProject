#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import time
from datetime import datetime
from register_config import LOG_DIR

def setup_register_logger():
    os.makedirs(LOG_DIR, exist_ok=True)

    log_file = os.path.join(LOG_DIR, "register.log")

    logger = logging.getLogger("RegistrationScript")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


_logger = None


def get_logger():
    global _logger
    if _logger is None:
        _logger = setup_register_logger()
    return _logger


def _format_message(message, login):
    if login:
        return f"[{login}] {message}"
    return message


def log_info(message, login=None):
    get_logger().info(_format_message(message, login))


def log_error(message, login=None):
    get_logger().error(_format_message(message, login))


def log_warning(message, login=None):
    get_logger().warning(_format_message(message, login))


def cleanup_old_logs(log_file_path: str, retention_days: int):
    if not os.path.exists(log_file_path) or os.path.getsize(log_file_path) == 0:
        return 0

    cutoff_time = time.time() - retention_days * 86400

    with open(log_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    filtered_lines = []
    for line in lines:
        try:
            date_str = line[:10]
            timestamp = datetime.strptime(date_str, "%Y-%m-%d").timestamp()
            if timestamp >= cutoff_time:
                filtered_lines.append(line)
        except (ValueError, IndexError):
            continue

    with open(log_file_path, 'w', encoding='utf-8') as f:
        f.writelines(filtered_lines)

    return len(lines) - len(filtered_lines)