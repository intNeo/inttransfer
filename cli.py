import argparse
import requests
import os
import sys
from tqdm import tqdm
import logging
import re
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from urllib.parse import urlparse

# Логирование
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
logger.info("Запуск CLI-клиента, версия файла: 2025-08-21-v10")

def validate_time(time_str):
    valid_times = ['10m', '30m', '1h', '1d', '2d', '3d', '4d', '5d', '6d', '7d']
    if time_str.lower().strip() not in valid_times:
        logger.error(f"Недопустимое значение времени: {time_str}. Доступно: {', '.join(valid_times)}")
        sys.exit(1)
    return time_str

def parse_download_input(input_str, server_url):
    if not server_url:
        logger.error("URL сервера обязателен. Укажите --server.")
        sys.exit(1)
    if input_str.startswith('http://') or input_str.startswith('https://'):
        parsed = urlparse(input_str)
        file_id = parsed.path.split('/download/')[-1]
        server_url = f"{parsed.scheme}://{parsed.netloc}"
        if not file_id:
            logger.error("Некорректный URL. Формат: <server>/download/<file_id>")
            sys.exit(1)
        return file_id, server_url
    return input_str, server_url

def upload_file(server_url, file_path, password=None, time_str='7d', insecure=False):
    if not os.path.exists(file_path):
        logger.error(f"Файл не найден: {file_path}")
        sys.exit(1)

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    time_str = validate_time(time_str)
    logger.info(f"Загрузка файла: {file_name}, размер: {file_size}, срок: {time_str}")

    with open(file_path, 'rb') as f:
        encoder = MultipartEncoder(fields={
            'file': (file_name, f, 'application/octet-stream'),
            'password': password or '',
            'days': time_str
        })
        bar = tqdm(total=encoder.len, unit='B', unit_scale=True, desc="Uploading")

        def callback(monitor):
            bar.update(monitor.bytes_read - bar.n)

        monitor = MultipartEncoderMonitor(encoder, callback)

        try:
            response = requests.post(f"{server_url}/upload", data=monitor,
                                     headers={'Content-Type': monitor.content_type},
                                     verify=not insecure)
            bar.close()
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ Файл загружен: {data['url']}")
                if password:
                    print(f"Пароль: {password}")
                print(f"Срок хранения: {time_str}")
            else:
                logger.error(f"Ошибка загрузки: {response.text}")
                sys.exit(1)
        except requests.RequestException as e:
            bar.close()
            logger.error(f"Ошибка сети: {e}")
            sys.exit(1)

def download_file(server_url, file_id, password=None, output=None, insecure=False):
    file_id, server_url = parse_download_input(file_id, server_url)
    data = {'password': password or ''}
    try:
        meta = requests.get(f"{server_url}/download/{file_id}", verify=not insecure)
        if meta.status_code != 200:
            logger.error(f"Файл не найден: {meta.text}")
            sys.exit(1)

        match = re.search(r'Скачать файл: ([^<]+)', meta.text)
        filename = match.group(1) if match else f"{file_id}_file"
        output = output or filename

        response = requests.post(f"{server_url}/download/{file_id}/file", data=data, stream=True, verify=not insecure)
        if response.status_code == 200:
            total = int(response.headers.get('content-length', 0))
            bar = tqdm(total=total, unit='B', unit_scale=True, desc="Downloading")
            with open(output, 'wb') as f:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
            bar.close()
            logger.info(f"Файл скачан: {output}")
        else:
            logger.error(f"Ошибка: {response.json().get('error', 'Неизвестная ошибка')}")
            sys.exit(1)
    except requests.RequestException as e:
        logger.error(f"Ошибка сети: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="""CLI-клиент для загрузки и скачивания файлов.

Примеры:
  Загрузка:
    cli.py --action upload --file /path/to/file.txt --server https://example.com --password 123 --time 1d
  Скачивание:
    cli.py --action download --file-id d2976312... --server https://example.com --password 123 --output /path/to/save.txt
""",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument('-a', '--action', required=True, choices=['upload', 'download'], help="Действие: upload или download")
    parser.add_argument('-s', '--server', required=True, help="URL сервера, например: https://example.com")
    parser.add_argument('-i', '--insecure', action='store_true', help="Отключить проверку SSL")

    # Общие опции
    parser.add_argument('-p', '--password', help="Пароль для файла")
    parser.add_argument('-o', '--output', help="Путь для сохранения (только для download)")

    # Для upload
    parser.add_argument('--file', help="Путь к файлу для загрузки")
    parser.add_argument('-t', '--time', default='7d', help="Срок хранения (10m, 30m, 1h, 1-7d)")

    # Для download
    parser.add_argument('--file-id', help="ID файла или URL для скачивания")

    args = parser.parse_args()

    if args.action == 'upload':
        if not args.file:
            logger.error("--file обязателен для upload")
            sys.exit(1)
        upload_file(args.server, args.file, args.password, args.time, args.insecure)
    elif args.action == 'download':
        if not args.file_id:
            logger.error("--file-id обязателен для download")
            sys.exit(1)
        download_file(args.server, args.file_id, args.password, args.output, args.insecure)

if __name__ == '__main__':
    main()