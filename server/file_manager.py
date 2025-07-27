import uuid
import os
import json
import time
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self.metadata_file = os.path.join(storage_path, 'orig.json')
        self.metadata = self._load_metadata()
    
    def _load_metadata(self):
        if not os.path.exists(self.metadata_file):
            logger.info(f"Файл метаданных {self.metadata_file} не существует, инициализация пустых метаданных")
            return {}
        try:
            with open(self.metadata_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    logger.warning(f"Файл метаданных {self.metadata_file} пустой, инициализация пустых метаданных")
                    return {}
                return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Не удалось разобрать файл метаданных {self.metadata_file}: {e}")
            return {}
    
    def _save_metadata(self):
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Не удалось сохранить метаданные в {self.metadata_file}: {e}")
            raise
    
    def save_file(self, file, password, expiration_time, file_id=None, temp_path=None):
        file_id = file_id or str(uuid.uuid4())
        original_name = file.filename
        expires_at = int(expiration_time.timestamp())
    
        if not temp_path or not os.path.exists(temp_path):
            logger.error(f"Временный файл {temp_path} не существует для получения метаданных")
            raise ValueError("Временный файл не существует")
    
        original_size = os.path.getsize(temp_path)
        if original_size == 0:
            logger.error(f"Временный файл {temp_path} пустой")
            raise ValueError("Временный файл пустой")
    
        sha256_hash = hashlib.sha256()
        with open(temp_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256_hash.update(chunk)
        file_hash = sha256_hash.hexdigest()
    
        logger.info(f"Сохранение метаданных для file_id {file_id}, пароль {'задан' if password else 'не задан'}")
    
        self.metadata[file_id] = {
            'original_name': original_name,
            'password': generate_password_hash(password) if password else '',
            'expires_at': expires_at,
            'original_size': original_size,
            'file_hash': file_hash
        }
        self._save_metadata()
    
        return file_id
    
    def get_file_metadata(self, file_id):
        self._cleanup_expired_files()
        return self.metadata.get(file_id)
    
    def verify_password(self, password, hashed_password):
        logger.debug(f"Проверка пароля: предоставлен {'пароль' if password else 'пустой пароль'}, хэш {'есть' if hashed_password else 'отсутствует'}")
        if not hashed_password:
            result = not password
            logger.debug(f"Пароль не требуется, результат проверки: {result}")
            return result
        result = check_password_hash(hashed_password, password)
        logger.debug(f"Проверка хэша пароля: {result}")
        return result
    
    def _cleanup_expired_files(self):
        current_time = int(time.time())
        for file_id, metadata in list(self.metadata.items()):
            if metadata['expires_at'] < current_time:
                file_path = os.path.join(self.storage_path, file_id)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Удалён истёкший файл: {file_path}")
                    except Exception as e:
                        logger.error(f"Не удалось удалить истёкший файл {file_path}: {e}")
                del self.metadata[file_id]
        self._save_metadata()