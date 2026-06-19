# MAX-Hermes Bridge

Мост между [MAX Bot API](https://dev.max.ru) и [Hermes Agent](https://hermes-agent.nousresearch.com) — позволяет подключить бота в мессенджере MAX к AI-агенту Hermes.

## Архитектура

```
┌──────────┐   webhook    ┌─────────────┐   CLI/SUB    ┌──────────────┐
│          │ ──────────►  │             │ ──────────►  │              │
│ MAX Bot  │              │ MAX Bridge  │              │ Hermes Agent │
│ API      │ ◄──────────  │ (Python)    │ ◄──────────  │              │
│          │  send_msg    │             │  response    │              │
└──────────┘              └─────────────┘              └──────────────┘
```

1. Пользователь пишет боту в MAX
2. MAX API отправляет webhook на мост
3. Мост показывает индикатор «Печатает...»
4. Мост вызывает Hermes Agent через CLI
5. Ответ Hermes отправляется обратно в MAX через Bot API

## Требования

- Python 3.11+
- Hermes Agent (установленный и настроенный)
- Сервер с публичным IP (или tunnel) для приёма webhook
- SSL-сертификат (Let's Encrypt или самоподписанный)

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/RuslanStrogov/max-hermes.git
cd max-hermes
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Создание бота в MAX

1. Перейдите на [MAX для партнёров](https://business.max.ru)
2. Создайте чат-бота с разработкой
3. Получите токен бота
4. Запишите `user_id` бота (понадобится для настройки)

### 4. Настройка конфигурации

```bash
cp .env.example .env
nano .env
```

Заполните обязательные поля:

| Переменная | Описание |
|------------|----------|
| `MAX_BOT_TOKEN` | Токен бота от MAX |
| `MAX_API_BASE_URL` | URL MAX API (по умолчанию `https://platform-api.max.ru`) |
| `HERMES_BIN` | Путь к команде `hermes` (по умолчанию `hermes`) |
| `HERMES_MODEL` | Модель Hermes (например `qwen2:1.5b`) |
| `HERMES_TIMEOUT` | Таймаут ожидания ответа в секундах |
| `BRIDGE_HOST` | Хост для HTTP-сервера моста |
| `BRIDGE_PORT` | Порт для HTTP-сервера моста |
| `LOG_LEVEL` | Уровень логирования (`DEBUG`, `INFO`, `WARNING`) |
| `ALLOWED_USERS` | Разрешённые user ID (через запятую, пустое = все) |

### 5. Настройка Hermes Agent

Убедитесь, что Hermes Agent установлен и работает:

```bash
hermes --version
```

Если используется Ollama, убедитесь, что нужные модели загружены:

```bash
ollama list
ollama pull qwen2:1.5b
```

### 6. Настройка сервера (Linux)

#### Nginx (обратный прокси)

Создайте конфигурацию `/etc/nginx/sites-available/max-bridge`:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location /webhook {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:8787;
    }
}
```

Активируйте и проверьте:

```bash
sudo ln -s /etc/nginx/sites-available/max-bridge /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### Let's Encrypt (SSL)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

#### Добавление пользователя

```bash
sudo useradd -r -s /bin/false max-bridge
sudo chown -R max-bridge:max-bridge /var/log/max-bridge
```

### 7. Системная установка (systemd)

Скопируйте файл сервиса:

```bash
sudo cp systemd/max-bridge.service /etc/systemd/system/
```

Создайте папку для конфигурации:

```bash
sudo mkdir -p /etc/max-bridge
sudo cp .env.example /etc/max-bridge/.env
sudo nano /etc/max-bridge/.env   # Вставьте свой токен!
sudo chmod 600 /etc/max-bridge/.env
sudo chown max-bridge:max-bridge /etc/max-bridge/.env
```

Перезагрузите и запустите:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now max-bridge
```

Или используйте скрипт автоматической установки:

```bash
sudo bash scripts/setup.sh
```

### 8. Регистрация webhook в MAX

После запуска моста зарегистрируйте webhook:

```bash
curl -X POST https://platform-api.max.ru/subscriptions \
  -H "Authorization: YOUR_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/webhook", "update_types": ["message_created"]}'
```

## Запуск

### Напрямую

```bash
source venv/bin/activate
python -m src.main
```

### Как служба (systemd)

```bash
# Запуск
sudo systemctl start max-bridge

# Остановка
sudo systemctl stop max-bridge

# Проверка статуса
sudo systemctl status max-bridge

# Просмотр логов
sudo journalctl -u max-bridge -f
```

### Docker

```bash
# Сборка и запуск
docker compose up -d --build

# Просмотр логов
docker compose logs -f

# Остановка
docker compose down
```

## Структура проекта

```
max-hermes/
├── src/
│   ├── main.py              # Точка входа, цикл событий
│   ├── config.py            # Загрузка конфигурации из .env
│   ├── max_client.py        # HTTP-клиент MAX Bot API
│   ├── hermes_client.py     # Клиент Hermes (через CLI)
│   ├── converter.py         # Конвертация форматов данных
│   ├── webhook_server.py    # HTTP-сервер для webhook от MAX
│   └── models.py            # Pydantic модели данных
├── systemd/
│   └── max-bridge.service   # Unit-файл systemd
├── scripts/
│   ├── setup.sh             # Скрипт автоматической установки
│   └── test_max_api.sh      # Тестирование MAX API
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_converter.py
│   ├── test_max_client.py
│   └── test_webhook.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `MAX_BOT_TOKEN` | *(обяз.)* | Токен бота MAX |
| `MAX_API_BASE_URL` | `https://platform-api.max.ru` | Базовый URL API |
| `HERMES_BIN` | `hermes` | Путь к исполняемому файлу hermes |
| `HERMES_MODEL` | *(пусто)* | Модель AI (напр. `qwen2:1.5b`) |
| `HERMES_TIMEOUT` | `120` | Таймаут ожидания ответа (сек) |
| `BRIDGE_HOST` | `0.0.0.0` | Адрес HTTP-сервера |
| `BRIDGE_PORT` | `8787` | Порт HTTP-сервера |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `ALLOWED_USERS` | *(пусто)* | Список разрешённых ID |

## Возможности

### Что уже работает

| Фича | Статус |
|------|--------|
| Приём сообщений от MAX через webhook | ✅ |
| Отправка ответов в MAX | ✅ |
| Индикатор «Печатает...» пока агент думает | ✅ |
| Inline keyboard (кнопки в сообщении) | ✅ |
| Callback от кнопок | ✅ |
| Поддержка нескольких пользователей | ✅ |
| Белый список пользователей (ALLOWED_USERS) | ✅ |
| Markdown-форматирование ответов | ✅ |
| systemd-сервис с автозапуском | ✅ |
| Docker / Docker Compose | ✅ |
| Health check endpoint | ✅ |
| Логирование в journald / файл | ✅ |

### Что можно добавить (roadmap)

| Фича | Статус | Примечание |
|------|--------|------------|
| Отправка изображений | 🔜 | Upload через `/uploads?type=image` работает, нужен правильный формат attachment |
| Отправка файлов | 🔜 | Аналогично изображениям |
| Отправка голосовых сообщений | 🔜 | Нужен формат `audio` attachment |
| Отправка геолокации | 🔜 | Нужен формат `location` attachment |
| Reply на сообщения | 🔜 | `reply_to` в `send_message` поддерживается |
| Редактирование сообщений | 🔜 | `PUT /messages/{id}` есть в API |
| Удаление сообщений | 🔜 | `DELETE /messages/{id}` есть в API |
| Групповые чаты | 🔜 | Нужна адаптация `chat_id` вместо `user_id` |
| Каналы | 🔜 | Аналогично групповым чатам |
| Стикеры | ❓ | Нет информации о поддержке в API |
| Read receipts (галочки) | ❌ | Не поддерживается MAX Bot API |
| Menu button (как в Telegram) | ❌ | Нет аналога `/setMyCommands` в MAX |

## Сравнение с Telegram Bot API

| Возможность | Telegram | MAX Bot API |
|-------------|----------|-------------|
| Webhook | ✅ | ✅ |
| Long Polling | ✅ | ✅ |
| Inline keyboard | ✅ | ✅ |
| Reply keyboard | ✅ | ❌ (только inline) |
| Callback buttons | ✅ | ✅ |
| Send/Edit/Delete messages | ✅ | ✅ |
| Typing indicator | ✅ | ✅ (`typing_on` / `typing_off`) |
| Read receipts | ✅ | ❌ |
| Bot commands menu | ✅ (`/setMyCommands`) | ❌ |
| Send images/files | ✅ | ✅ (через upload) |
| Send location | ✅ | ❓ |
| Send stickers | ✅ | ❓ |
| Group chats | ✅ | ✅ |
| Channels | ✅ | ✅ |

## Тестирование

```bash
source venv/bin/activate
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

## Устранение неполадок

### Мост не получает сообщения от MAX

1. Проверьте регистрацию webhook: `curl -H "Authorization: TOKEN" https://platform-api.max.ru/subscriptions`
2. Проверьте что порт открыт: `curl https://your-domain.com/health`
3. Проверьте логи: `sudo journalctl -u max-bridge -f`

### Hermes не отвечает

1. Проверьте что Hermes установлен: `hermes --version`
2. Проверьте что модель загружена: `ollama list`
3. Проверьте права на запись в `~/.hermes/logs/`

### Бот не отвечает в MAX

1. Проверьте логи моста на наличие ошибок
2. Убедитесь что `MAX_BOT_TOKEN` валиден
3. Проверьте что бот активирован в MAX

## Лицензия

MIT License. См. [LICENSE](LICENSE).
