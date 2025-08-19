from flask import Flask, request, render_template, send_file, jsonify, abort
from file_manager import FileManager
from encryption import encrypt_file, decrypt_file
import os
import uuid
import hashlib
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta, UTC
import re
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Explicitly load .env from config directory
env_path = os.path.join(os.path.dirname(__file__), '..', 'config', '.env')
load_dotenv(env_path)

app = Flask(__name__, template_folder="../web/templates", static_folder="../web/static")

# Ensure UPLOAD_FOLDER is set
upload_folder = os.getenv('UPLOAD_FOLDER')
if not upload_folder:
    raise ValueError("UPLOAD_FOLDER не указан в .env файле")

# Create storage and temp directories
os.makedirs(upload_folder, exist_ok=True)
temp_folder = os.path.join(upload_folder, 'temp')
os.makedirs(temp_folder, exist_ok=True)

# Clean up temp directory on startup
for temp_file in os.listdir(temp_folder):
    temp_file_path = os.path.join(temp_folder, temp_file)
    try:
        os.remove(temp_file_path)
        logger.info(f"Удалён старый временный файл: {temp_file_path}")
    except Exception as e:
        logger.error(f"Не удалось удалить старый временный файл {temp_file_path}: {e}")

app.config['UPLOAD_FOLDER'] = upload_folder
app.config['TEMP_FOLDER'] = temp_folder
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

file_manager = FileManager(app.config['UPLOAD_FOLDER'])

def parse_duration(duration_str):
    """Преобразует строку вида '10m', '30m', '1h', '1d' в секунды."""
    match = re.match(r'(\d+)([mhd])', duration_str)
    if not match:
        logger.warning(f"Недопустимый формат срока хранения: {duration_str}, используется 7 дней по умолчанию")
        return 7 * 86400  # По умолчанию 7 дней в секундах
    value, unit = match.groups()
    value = int(value)
    if unit == 'm':
        return value * 60  # Минуты в секунды
    elif unit == 'h':
        return value * 3600  # Часы в секунды
    elif unit == 'd':
        return value * 86400  # Дни в секунды

@app.route('/favicon.ico')
def favicon():
    favicon_path = os.path.join(app.static_folder, 'favicon.ico')
    if not os.path.exists(favicon_path):
        logger.error(f"Favicon file not found at {favicon_path}")
        return '', 204  # Return empty response if favicon doesn't exist
    return send_file(favicon_path, mimetype='image/x-icon')

@app.route('/get_max_file_size', methods=['GET'])
def get_max_file_size():
    """Возвращает максимальный размер файла в байтах и MB."""
    max_size_bytes = app.config['MAX_CONTENT_LENGTH']
    max_size_mb = max_size_bytes / (1024 * 1024)
    return jsonify({'maxSizeBytes': max_size_bytes, 'maxSizeMB': round(max_size_mb, 2)})

@app.errorhandler(400)
def bad_request(e):
    return render_template('default.html', code=400, message="Неверный запрос. Проверьте введённые данные."), 400

@app.errorhandler(403)
def forbidden(e):
    return render_template('default.html', code=403, message="Доступ запрещён. У вас нет прав для этого действия."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('default.html', code=404, message="Страница не найдена. Проверьте URL или вернитесь на главную."), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('default.html', code=500, message="Внутренняя ошибка сервера. Попробуйте позже."), 500

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не предоставлен'}), 400
    
    file = request.files['file']
    password = request.form.get('password', '')
    duration_str = request.form.get('days', '7d')  # По умолчанию 7 дней
    
    if not file or not file.filename:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    # Преобразуем срок хранения в секунды
    expiration_seconds = parse_duration(duration_str)
    expiration_time = datetime.now(UTC) + timedelta(seconds=expiration_seconds)
    # Валидация: минимальный срок 10 минут (600 секунд), максимальный 7 дней (604800 секунд)
    if expiration_seconds < 600 or expiration_seconds > 7 * 86400:
        return jsonify({'error': 'Недопустимая длительность хранения (от 10 минут до 7 дней)'}), 400

    temp_path = None
    try:
        # Save file temporarily
        file_id = str(uuid.uuid4())
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}.tmp")
        logger.info(f"Сохранение временного файла в {temp_path}")
        file.save(temp_path)
        
        # Check if file is empty
        file_size = os.path.getsize(temp_path)
        if file_size == 0:
            logger.error(f"Временный файл {temp_path} пустой")
            os.remove(temp_path)
            return jsonify({'error': 'Загруженный файл пустой'}), 400
        
        # Encrypt the file
        encrypted_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        logger.info(f"Шифрование файла из {temp_path} в {encrypted_path}")
        encrypt_file(temp_path, encrypted_path)
        
        # Save metadata after successful encryption
        logger.info(f"Сохранение метаданных для file_id {file_id}")
        file_manager.save_file(file, password, expiration_time, file_id=file_id, temp_path=temp_path)
        
        # Clean up temporary file
        os.remove(temp_path)
        temp_path = None
        
        file_size = os.path.getsize(encrypted_path) if os.path.exists(encrypted_path) else 0
        logger.info(f"Зашифрованный файл {encrypted_path} создан с размером {file_size} байт")
        
        download_url = f"{request.host_url}download/{file_id}"
        return jsonify({'url': download_url})
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
        if temp_path and os.path.exists(temp_path):
            logger.info(f"Очистка временного файла: {temp_path}")
            os.remove(temp_path)
        return jsonify({'error': f"Ошибка загрузки: {str(e)}"}), 500

@app.route('/download/<file_id>')
def download_page(file_id):
    metadata = file_manager.get_file_metadata(file_id)
    if not metadata:
        logger.error(f"Метаданные для file_id {file_id} не найдены")
        return render_template(
            'download.html',
            error='Файл не найден',
            filename=None,
            requires_password=False,
            expires_at=None
        )

    expires_at_str = None
    expires_at = metadata.get("expires_at")

    if expires_at:
        try:
            if isinstance(expires_at, (int, float)):
                dt = datetime.fromtimestamp(expires_at)
            elif isinstance(expires_at, str):
                dt = datetime.fromisoformat(expires_at)
            elif isinstance(expires_at, datetime):
                dt = expires_at
            else:
                raise TypeError("Неподдерживаемый формат expires_at")

            expires_at_str = dt.strftime("%d.%m.%Y %H:%M")
        except Exception as e:
            logger.warning(f"Невозможно распарсить expires_at: {e}")

    return render_template(
        'download.html',
        filename=metadata.get('original_name'),
        requires_password=bool(metadata.get('password')),
        expires_at=expires_at_str,
        error=None
    )

@app.route('/download/<file_id>/file', methods=['POST'])
def download_file(file_id):
    metadata = file_manager.get_file_metadata(file_id)
    if not metadata:
        logger.error(f"Метаданные для file_id {file_id} не найдены")
        abort(404)
    
    password = request.form.get('password', '')
    if metadata['password'] and not file_manager.verify_password(password, metadata['password']):
        logger.error(f"Неверный пароль для file_id: {file_id}")
        return jsonify({'error': 'Неверный пароль'}), 403
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    if not os.path.exists(file_path):
        logger.error(f"Зашифрованный файл не найден: {file_path}")
        abort(404)
    
    file_size = os.path.getsize(file_path)
    logger.info(f"Зашифрованный файл {file_path} имеет размер {file_size} байт")
    
    try:
        # Создаём уникальный временный файл с помощью tempfile
        with tempfile.NamedTemporaryFile(dir=app.config['TEMP_FOLDER'], delete=False) as temp_decrypted_file:
            decrypted_path = temp_decrypted_file.name
            logger.info(f"Расшифровка файла {file_path} в уникальный временный файл {decrypted_path}")
            decrypt_file(file_path, decrypted_path)
            
            if not os.path.exists(decrypted_path):
                logger.error(f"Расшифрованный файл не создан: {decrypted_path}")
                return jsonify({'error': 'Не удалось создать расшифрованный файл'}), 500
            
            decrypted_size = os.path.getsize(decrypted_path)
            logger.info(f"Расшифрованный файл {decrypted_path} создан с размером {decrypted_size} байт")
            
            # Проверка размера
            if decrypted_size != metadata['original_size']:
                logger.error(f"Неверный размер расшифрованного файла: {decrypted_size} вместо {metadata['original_size']}")
                return jsonify({'error': 'Расшифрованный файл повреждён'}), 500
            
            # Проверка хэша
            sha256_hash = hashlib.sha256()
            with open(decrypted_path, 'rb') as f:
                while chunk := f.read(8192):
                    sha256_hash.update(chunk)
            decrypted_hash = sha256_hash.hexdigest()
            if decrypted_hash != metadata['file_hash']:
                logger.error(f"Неверный хэш расшифрованного файла: {decrypted_hash} вместо {metadata['file_hash']}")
                return jsonify({'error': 'Расшифрованный файл повреждён (хэш не совпадает)'}), 500
            
            # Отправляем файл (send_file автоматически обрабатывает потоковую передачу)
            response = send_file(decrypted_path, download_name=metadata['original_name'], as_attachment=True)
            return response
    except Exception as e:
        logger.error(f"Ошибка скачивания для {file_id}: {e}")
        return jsonify({'error': f"Ошибка скачивания: {str(e)}"}), 500
    finally:
        # Удаляем файл вручную (на случай, если delete=False)
        if 'decrypted_path' in locals() and os.path.exists(decrypted_path):
            logger.info(f"Очистка расшифрованного файла: {decrypted_path}")
            try:
                os.remove(decrypted_path)
            except Exception as remove_e:
                logger.error(f"Не удалось удалить временный файл {decrypted_path}: {remove_e}")

if __name__ == '__main__':
    app.run(debug=False)