from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
import os
from dotenv import load_dotenv
import base64
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def load_private_key():
    private_key_b64 = os.getenv('PRIVATE_KEY')
    if not private_key_b64:
        logger.error("PRIVATE_KEY не указан в .env файле")
        raise ValueError("PRIVATE_KEY не указан в .env файле")
    try:
        private_key_bytes = base64.b64decode(private_key_b64)
    except Exception as e:
        logger.error(f"Не удалось декодировать PRIVATE_KEY: {e}")
        raise ValueError(f"Неверный формат PRIVATE_KEY в .env файле: {e}")
    try:
        private_key = serialization.load_pem_private_key(
            private_key_bytes,
            password=None,
            backend=default_backend()
        )
        # Log key size
        key_size = private_key.key_size
        logger.info(f"Загружен приватный ключ с размером {key_size} бит")
        return private_key
    except Exception as e:
        logger.error(f"Не удалось загрузить приватный ключ: {e}")
        raise ValueError(f"Не удалось загрузить приватный ключ: {e}")

def load_public_key():
    private_key = load_private_key()
    return private_key.public_key()

def encrypt_file(input_path, output_path):
    public_key = load_public_key()
    key_size_bytes = public_key.key_size // 8
    max_chunk_size = key_size_bytes - 2 * 32 - 2  # SHA256: 32 bytes
    chunk_size = int(os.getenv('ENCRYPTION_CHUNK_SIZE', max_chunk_size))
    if chunk_size <= 0 or chunk_size > max_chunk_size:
        logger.error(f"Недопустимый ENCRYPTION_CHUNK_SIZE: {chunk_size}, должен быть в диапазоне 1-{max_chunk_size}")
        raise ValueError(f"Недопустимый ENCRYPTION_CHUNK_SIZE: {chunk_size}")
    logger.info(f"Шифрование файла из {input_path} в {output_path} с chunk_size={chunk_size}")
    
    if not os.path.exists(input_path):
        logger.error(f"Входной файл {input_path} не существует")
        raise FileNotFoundError(f"Входной файл {input_path} не существует")
    
    file_size = os.path.getsize(input_path)
    if file_size == 0:
        logger.warning(f"Входной файл {input_path} пустой")
        raise ValueError("Нельзя зашифровать пустой файл")
    
    with open(output_path, 'wb') as out_file:
        out_file.write(file_size.to_bytes(8, byteorder='big'))
    
    with open(input_path, 'rb') as in_file, open(output_path, 'ab') as out_file:
        chunk_count = 0
        while True:
            chunk = in_file.read(chunk_size)
            if not chunk:
                break
            chunk_count += 1
            logger.debug(f"Чанк #{chunk_count}: размер {len(chunk)} байт")
            try:
                encrypted = public_key.encrypt(
                    chunk,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                if len(encrypted) != key_size_bytes:
                    logger.error(f"Неверный размер зашифрованного чанка #{chunk_count}: {len(encrypted)} байт, ожидалось {key_size_bytes}")
                    raise ValueError(f"Неверный размер зашифрованного чанка")
                out_file.write(encrypted)
                logger.debug(f"Зашифрован чанк #{chunk_count} размером {len(chunk)} байт, зашифрованный размер {len(encrypted)} байт")
            except Exception as e:
                logger.error(f"Ошибка шифрования чанка #{chunk_count}: {e}")
                logger.error(f"Размер чанка: {len(chunk)} байт")
                raise ValueError(f"Ошибка шифрования: {e}")
    
    logger.info(f"Шифрование завершено, обработано {chunk_count} чанков")

def decrypt_file(input_path, output_path):
    private_key = load_private_key()
    key_size_bytes = private_key.key_size // 8
    chunk_size = int(os.getenv('DECRYPTION_CHUNK_SIZE', key_size_bytes))
    if chunk_size != key_size_bytes:
        logger.error(f"Недопустимый DECRYPTION_CHUNK_SIZE: {chunk_size}, должен быть {key_size_bytes}")
        raise ValueError(f"Недопустимый DECRYPTION_CHUNK_SIZE: {chunk_size}")
    logger.info(f"Расшифровка файла из {input_path} в {output_path} с chunk_size={chunk_size}")
    
    if not os.path.exists(input_path):
        logger.error(f"Зашифрованный файл {input_path} не существует")
        raise FileNotFoundError(f"Зашифрованный файл {input_path} не существует")
    
    file_size = os.path.getsize(input_path)
    if file_size < 8:
        logger.error(f"Недостаточный размер файла {file_size} для {input_path}")
        raise ValueError(f"Недостаточный размер зашифрованного файла")
    
    with open(input_path, 'rb') as in_file:
        original_size = int.from_bytes(in_file.read(8), byteorder='big')
        logger.debug(f"Оригинальный размер файла: {original_size} байт")
        
        with open(output_path, 'wb') as out_file:
            bytes_written = 0
            chunk_count = 0
            while True:
                chunk = in_file.read(chunk_size)
                if not chunk:
                    break
                chunk_count += 1
                if len(chunk) != chunk_size:
                    logger.error(f"Неверный размер чанка #{chunk_count}: {len(chunk)} в {input_path}")
                    raise ValueError(f"Неверный размер чанка: {len(chunk)}")
                try:
                    decrypted = private_key.decrypt(
                        chunk,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    )
                    remaining_bytes = original_size - bytes_written
                    if remaining_bytes < len(decrypted):
                        decrypted = decrypted[:remaining_bytes]
                    out_file.write(decrypted)
                    bytes_written += len(decrypted)
                    logger.debug(f"Расшифрован чанк #{chunk_count} размером {len(decrypted)} байт")
                except Exception as e:
                    logger.error(f"Ошибка расшифровки чанка #{chunk_count}: {e}")
                    raise ValueError(f"Ошибка расшифровки: {e}")
            
            if bytes_written != original_size:
                logger.error(f"Неверный размер расшифрованного файла: {bytes_written} вместо {original_size}")
                raise ValueError(f"Неверный размер расшифрованного файла")
    
    logger.info(f"Расшифровка завершена, обработано {chunk_count} чанков")