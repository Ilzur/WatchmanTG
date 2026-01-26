import psutil
import time
import requests
import sys
import os
import json
from datetime import datetime

up_name = r"""
__        __    _       _                         _____ ____ 
\ \      / /_ _| |_ ___| |__  _ __ ___   __ _ _ _|_   _/ ___|
 \ \ /\ / / _` | __/ __| '_ \| '_ ` _ \ / _` | '_ \| || |  _ 
  \ V  V / (_| | || (__| | | | | | | | | (_| | | | | || |_| |
   \_/\_/ \__,_|\__\___|_| |_|_| |_| |_|\__,_|_| |_|_| \____|
"""
print(up_name)

# Конфигурация
DEFAULT_PROGRAM_NAME = "Monitor.exe"
DEFAULT_CHECK_INTERVAL = 5
CONFIG_FILE = "config.json"  # Изменено с .py на .json
LOG_FILE = "process_monitor.log"

# Глобальные переменные для конфигурации
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = []
PROGRAM_NAME = DEFAULT_PROGRAM_NAME
CHECK_INTERVAL = DEFAULT_CHECK_INTERVAL


def load_config():
    """Загрузка конфигурации из JSON файла"""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PROGRAM_NAME, CHECK_INTERVAL

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)

            TELEGRAM_BOT_TOKEN = config.get('telegram_bot_token', '')
            TELEGRAM_CHAT_ID = config.get('telegram_chat_id', [])
            PROGRAM_NAME = config.get('program_name', DEFAULT_PROGRAM_NAME)
            CHECK_INTERVAL = config.get('check_interval', DEFAULT_CHECK_INTERVAL)

            return True
        except Exception as e:
            print(f"Ошибка загрузки конфига: {e}")
            return False
    return False


def save_config():
    """Сохранение конфигурации в JSON файл"""
    config = {
        'telegram_bot_token': TELEGRAM_BOT_TOKEN,
        'telegram_chat_id': TELEGRAM_CHAT_ID,
        'program_name': PROGRAM_NAME,
        'check_interval': CHECK_INTERVAL
    }

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения конфига: {e}")
        return False


def setup_config():
    """Настройка конфигурации при первом запуске"""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PROGRAM_NAME, CHECK_INTERVAL

    if not os.path.exists(CONFIG_FILE):
        print("=== Первоначальная настройка ===")

        # Получение токена бота
        bot_token = input("Введите токен вашего Telegram бота: ").strip()
        if not bot_token:
            print("Токен не может быть пустым!")
            return False

        # Получение chat_id
        print("\nДля получения chat_id выполните следующие шаги:")
        print("1. Найдите бота @userinfobot в Telegram")
        print("2. Начните с ним диалог и отправьте /start")
        print("3. Скопируйте полученный ID")
        print("4. Введите его здесь:\n")

        chat_ids = []
        while True:
            chat_id = input("Ваш chat_id (оставьте пустым для завершения): ").strip()
            if chat_id:
                chat_ids.append(chat_id)
                print(f'Добавлен ID: {chat_id}')
            else:
                break

        if not chat_ids:
            print("Нужно указать хотя бы один chat_id!")
            return False

        # Имя процесса
        program_name = input(f"\nИмя процесса для мониторинга [{DEFAULT_PROGRAM_NAME}]: ").strip()
        if not program_name:
            program_name = DEFAULT_PROGRAM_NAME

        # Интервал проверки
        interval_input = input(f"Интервал проверки в секундах [{DEFAULT_CHECK_INTERVAL}]: ").strip()
        if interval_input:
            try:
                interval = int(interval_input)
                if interval < 1:
                    print("Интервал должен быть не менее 1 секунды. Используется значение по умолчанию.")
                    interval = DEFAULT_CHECK_INTERVAL
            except ValueError:
                print("Некорректное значение. Используется значение по умолчанию.")
                interval = DEFAULT_CHECK_INTERVAL
        else:
            interval = DEFAULT_CHECK_INTERVAL

        # Сохранение значений
        TELEGRAM_BOT_TOKEN = bot_token
        TELEGRAM_CHAT_ID = chat_ids
        PROGRAM_NAME = program_name
        CHECK_INTERVAL = interval

        if save_config():
            print(f"\nКонфигурация сохранена в {CONFIG_FILE}")
            print(f"Токен бота: {bot_token[:10]}...")
            print(f"Chat IDs: {chat_ids}")
            print(f"Процесс для мониторинга: {program_name}")
            print(f"Интервал проверки: {interval} сек")
            return True
        else:
            print("Ошибка сохранения конфигурации!")
            return False
    return False


def send_telegram_message(message):
    """Отправка сообщения в Telegram"""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    success_count = 0
    total_count = len(TELEGRAM_CHAT_ID)

    for chat_id in TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                success_count += 1
                log_message(f"Сообщение отправлено в Telegram для chat_id {chat_id}")
            else:
                log_message(f"Ошибка отправки для chat_id {chat_id}: {response.text}")
        except Exception as e:
            log_message(f"Исключение при отправке для chat_id {chat_id}: {str(e)}")

    if success_count == total_count:
        log_message(f"Все сообщения успешно отправлены ({success_count}/{total_count})")
        return True
    elif success_count > 0:
        log_message(f"Часть сообщений отправлена ({success_count}/{total_count})")
        return True  # Возвращаем True даже если часть сообщений отправлена
    else:
        log_message("Не удалось отправить ни одного сообщения")
        return False


def is_process_running(process_name):
    """Проверка, запущен ли процесс"""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() == process_name.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def log_message(message):
    """Логирование сообщений"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"

    print(log_entry)

    # Запись в лог-файл
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"Ошибка записи в лог-файл: {e}")


def edit_config():
    """Редактирование существующей конфигурации"""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PROGRAM_NAME, CHECK_INTERVAL

    print("\n=== Редактирование конфигурации ===")
    print("Оставьте поле пустым, чтобы оставить текущее значение")

    # Токен бота
    new_token = input(f"Токен бота [{TELEGRAM_BOT_TOKEN[:10]}...]: ").strip()
    if new_token:
        TELEGRAM_BOT_TOKEN = new_token

    # Chat IDs
    print(f"\nТекущие chat_id: {TELEGRAM_CHAT_ID}")
    edit_chats = input("Редактировать chat_id? (y/n): ").lower()
    if edit_chats == 'y':
        TELEGRAM_CHAT_ID = []
        print("\nВведите новые chat_id:")
        while True:
            chat_id = input("chat_id (пусто для завершения): ").strip()
            if chat_id:
                TELEGRAM_CHAT_ID.append(chat_id)
                print(f'Добавлен ID: {chat_id}')
            else:
                break

    # Имя процесса
    new_program = input(f"\nИмя процесса [{PROGRAM_NAME}]: ").strip()
    if new_program:
        PROGRAM_NAME = new_program

    # Интервал
    new_interval = input(f"Интервал проверки [{CHECK_INTERVAL}]: ").strip()
    if new_interval:
        try:
            CHECK_INTERVAL = int(new_interval)
        except ValueError:
            print("Некорректное значение, оставлено предыдущее")

    if save_config():
        print("\nКонфигурация обновлена!")
        return True
    else:
        print("\nОшибка сохранения конфигурации!")
        return False


def main():
    """Основная функция мониторинга"""
    print("=== Мониторинг процессов ===")

    # Загрузка конфигурации
    if not load_config():
        print("Конфигурационный файл не найден или поврежден.")
        if setup_config():
            print("\nКонфигурация создана успешно!")
            # Перезагрузка конфига
            load_config()
        else:
            print("Не удалось создать конфигурацию. Используются значения по умолчанию.")

    print(f"Отслеживается процесс: {PROGRAM_NAME}")
    print(f"Интервал проверки: {CHECK_INTERVAL} сек")
    print(f"Количество получателей: {len(TELEGRAM_CHAT_ID)}")

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ВНИМАНИЕ: Telegram уведомления отключены (не настроены)")

    print("\nКоманды во время работы:")
    print("  Ctrl+E - Редактировать конфигурацию")
    print("  Ctrl+C - Остановить мониторинг")

    was_running = False

    try:
        while True:
            is_running = is_process_running(PROGRAM_NAME)

            if was_running and not is_running:
                # Программа была запущена, но теперь закрыта
                message = f"⚠️ Программа <b>{PROGRAM_NAME}</b> была закрыта!\n"
                message += f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                log_message(f"Обнаружено закрытие процесса: {PROGRAM_NAME}")
                if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                    send_telegram_message(message)

            elif not was_running and is_running:
                # Программа была запущена
                message = f"✅ Программа <b>{PROGRAM_NAME}</b> была запущена!\n"
                message += f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                log_message(f"Процесс запущен: {PROGRAM_NAME}")
                if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                    send_telegram_message(message)

            was_running = is_running

            # Проверка ввода команд
            try:
                import msvcrt
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x05':  # Ctrl+E
                        edit_config()
                        print(f"\nОтслеживается процесс: {PROGRAM_NAME}")
                        print(f"Интервал проверки: {CHECK_INTERVAL} сек")
                        print(f"Количество получателей: {len(TELEGRAM_CHAT_ID)}")
            except ImportError:
                pass  # Для не-Windows систем

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        log_message("Мониторинг остановлен пользователем")
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            send_telegram_message(f"Мониторинг процесса {PROGRAM_NAME} остановлен")
    except Exception as e:
        error_msg = f"Критическая ошибка: {str(e)}"
        log_message(error_msg)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            send_telegram_message(f"❌ Ошибка в мониторе: {str(e)}")


if __name__ == "__main__":
    # Установка необходимых библиотек
    try:
        import psutil
        import requests
    except ImportError:
        print("Установка необходимых библиотек...")
        try:
            os.system("pip install psutil requests")
            print("Библиотеки установлены. Перезапустите скрипт.")
        except:
            print("Не удалось установить библиотеки. Установите вручную:")
            print("pip install psutil requests")
        sys.exit(1)

    # Создание ярлыка для автозапуска (опционально)
    create_shortcut = input("Создать ярлык для автозапуска? (y/n): ").lower()
    if create_shortcut == 'y':
        try:
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")
            startup_folder = shell.SpecialFolders("Startup")
            shortcut = shell.CreateShortcut(os.path.join(startup_folder, "ProcessMonitor.lnk"))
            shortcut.TargetPath = sys.executable
            shortcut.Arguments = f'"{os.path.abspath(__file__)}"'
            shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(__file__))
            shortcut.save()
            print(f"Ярлык создан в автозагрузке: {startup_folder}")
        except ImportError:
            print("Для создания ярлыка установите pywin32: pip install pywin32")
        except Exception as e:
            print(f"Не удалось создать ярлык: {e}")

    main()