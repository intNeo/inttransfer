# intTransfer форк старого проекта ([FileTransfer](https://github.com/intNeo/FileTransfer)), переписанный на Python

## Особенности
- Передача и скачивание файлов
- Возможность указать пароль `(необязательно)`
- Возможность указать срок хранения файла `от 10 минут до недели`

## Необходимая версия Python:
- 3.12 и выше

## Необходимые компоненты:
- nginx
- certbot (Let's Encrypt) `желательно`

## Установка, настройка и запуск

### 1. Клонируем репозиторий в директорию `/var/www`

```bash
cd /var/www
git clone https://github.com/intNeo/inttransfer.git
```

### 2. Переходим в скачанный репозиторий и создаем виртуальную среду

```bash
cd inttransfer
python3.12 -m venv .env
source .env/bin/activate
```

### 3. Устанавливаем зависимости

```bash
pip install -r config/requirements.txt
```

### 4. Запускаем код для генерации закрытого ключа

```bash
python3.12 config/genkey.py
```
> В результате получите ключ: `LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUNkUUlCQ...`

### 5. Открываем конфигурационный файл `.env`

```bash
nano config/.env
```
> И вставляем скопированный ключ в переменную `PRIVATE_KEY`

### 6. Изменить права доступа директории

```bash
cd ..
chown -R www-data:www-data inttransfer/
chmod -R 755 inttransfer/
```

### 7. Скопировать демон systemd в директорию `/etc/systemd/system` и запустить

> По дефолту в демоне используется 3.12 версия, если у вас отличается, сначало поменяйте, а потом копируйте

```bash
cd inttransfer
cp config/inttransfer.service /etc/systemd/system
systemctl daemon-reload
systemctl enable inttransfer --now
systemctl status inttransfer
```

### 8. Настроить и скопировать nginx конфиг в `/etc/nginx/site-available`

```bash
nano config/inttransfer.conf
```
> Заполнить необходимую информацию ip/domain, пути к сертификату/ключу`

```bash
ln -s /var/www/inttransfer/config/inttransfer.conf /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### 9. Открыть в браузере

> Открыть в браузере `https://<ip/domain>/`

## Дополнительная информация

### Изменить лимиты загружаемого файла:

#### 1. Необходимо поменять значения в конфиге `nginx` и `.env`

```bash
nano config/inttransfer.conf
nano config/.env
```

> Для nginx

```bash
client_max_body_size;
```

> Еще желательно поэкспериментировать с этими настройками

```bash
proxy_read_timeout;
proxy_send_timeout;
```

> Для .env

```bash
MAX_CONTENT_LENGTH;
```

#### 2. Перезапустить демоны systemd

```bash
systemctl restart inttransfer nginx
```

### Если используете Python3.13+:

#### 1. Изменить версию в конфиге демона

```bash
nano config/inttransfer.service
```

#### 2. Перезаписать демон в директории `/etc/systemd/system/`

```bash
cp config/inttransfer.service /etc/systemd/system
systemctl daemon-reload
systemctl restart inttransfer
systemctl status inttransfer
```

### Возможные ошибки с правами доступа и установкой зависимостей:

> Все действия делались от пользователя `root` и потом передавались права на пользователя `www-data`

> Если у вас версия выше Python3.12, то меняйте цифру например `python3.13 -m venv .env` и т.д.
