# MAX-Hermes Bridge

Мессенджер-мост между MAX Bot API и Hermes Agent.

## Архитектура

```
┌─────────┐  HTTPS (webhook)  ┌──────────────┐  HTTP POST  ┌──────────────┐
│ MAX API  │ ◄──────────────► │  MAX Bridge   │ ──────────► │ Hermes       │
│          │  POST /messages   │  (Python)     │             │ Webhook      │
│          │ ◄──────────────► │               │ ◄────────── │ Adapter      │
└─────────┘                   └──────────────┘  response    └──────────────┘
```

## Быстрый старт

### 1. Установка зависимостей

```bash
cd /mnt/data/projects/max-hermes
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройка

```bash
cp .env.example .env
# Отредактируй .env — вставь токен бота и секрет
nano .env
```

### 3. Запуск

```bash
# Напрямую
python -m src.main

# Или как systemd сервис
sudo cp systemd/max-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now max-bridge
```

### 4. Регистрация webhook в MAX

```bash
curl -X POST https://platform-api.max.ru/subscriptions \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/webhook", "update_types": ["message_created"]}'
```

## Структура проекта

```
max-hermes/
├── src/
│   ├── main.py           # Точка входа, asyncio loop
│   ├── config.py         # Загрузка конфигурации
│   ├── max_client.py     # HTTP-клиент MAX Bot API
│   ├── hermes_client.py  # Клиент Hermes webhook
│   ├── converter.py      # Конвертация форматов
│   ├── webhook_server.py # HTTP-сервер для приёма webhook от MAX
│   └── models.py         # Pydantic модели данных
├── systemd/
│   └── max-bridge.service
├── tests/
│   ├── test_max_client.py
│   ├── test_converter.py
│   └── test_webhook.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `MAX_BOT_TOKEN` | Токен бота от MasterBot |
| `MAX_API_BASE_URL` | URL MAX API (по умолчанию `https://platform-api.max.ru`) |
| `HERMES_WEBHOOK_URL` | URL Hermes webhook |
| `HERMES_WEBHOOK_SECRET` | HMAC-секрет Hermes webhook |
| `BRIDGE_HOST` | Хост для HTTP-сервера моста |
| `BRIDGE_PORT` | Порт для HTTP-сервера моста |
| `BRIDGE_SECRET` | Секрет для авторизации webhook от MAX |
| `LOG_LEVEL` | Уровень логирования |
| `ALLOWED_USERS` | Разрешённые user ID (пусто = все) |

## Команды

```bash
# Статус сервиса
sudo systemctl status max-bridge

# Логи
sudo journalctl -u max-bridge -f

# Перезапуск
sudo systemctl restart max-bridge
```
