<div align="center">

  <img src="banner.png" alt="MAX Hermes Bridge Banner" width="100%"/>

  <p>
    <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python"/>
    <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/Hermes-Agent-8B5CF6" alt="Hermes"/>
    <img src="https://img.shields.io/badge/Docker-🐳-2496ED?logo=docker&logoColor=white" alt="Docker"/>
    <img src="https://img.shields.io/badge/License-MIT-22C55E" alt="MIT"/>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Webhook-✅-34D399" alt="Webhook"/>
    <img src="https://img.shields.io/badge/CLI%20Bridge-✅-34D399" alt="CLI"/>
    <img src="https://img.shields.io/badge/Docker-✅-34D399" alt="Docker"/>
    <img src="https://img.shields.io/badge/systemd-✅-34D399" alt="systemd"/>
  </p>

  <h3>Мост между <a href="https://dev.max.ru">MAX Bot API</a> и <a href="https://hermes-agent.nousresearch.com">Hermes Agent</a></h3>
  <p>Python-мост через CLI с поддержкой webhook, Docker и systemd</p>

  <p><sub>🎨 Designed by <a href="https://br-design.ru/">BR-DESIGN</a></sub></p>

</div>

---

## 📋 Содержание

- [Архитектура](#-архитектура)
- [Возможности](#-возможности)
- [Требования](#-требования)
- [Установка](#-установка)
- [Настройка](#-настройка)
- [Запуск](#-запуск)
- [Структура проекта](#-структура-проекта)
- [Переменные окружения](#-переменные-окружения)
- [Roadmap](#-roadmap)
- [Релизы и CI/CD](#-релизы-и-cicd)
- [Сравнение с Telegram Bot API](#-сравнение-с-telegram-bot-api)
- [Тестирование](#-тестирование)
- [Устранение неполадок](#-устранение-неполадок)
- [Лицензия](#-лицензия)

---

## 🏗️ Архитектура

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

> **Хотите интеграцию уровня Hermes (send_message, cron, sessions)?** Используйте [MAX Hermes Plugin](https://github.com/RuslanStrogov/max-hermes-plugin) — нативный платформенный адаптер для Hermes Gateway.

## ✨ Возможности

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
| Обработка всех типов событий MAX API | ✅ |
| Скачивание вложений (изображения, видео, аудио, файлы) | ✅ |
| Отправка изображений через upload API | ✅ |
| Редактирование сообщений (PUT /messages/{id}) | ✅ |
| Удаление сообщений (DELETE /messages/{id}) | ✅ |
| Long Polling (GET /updates) | ✅ |
| Webhook управление (POST/GET/DELETE /subscriptions) | ✅ |
| Автодеплой через GitHub Actions | ✅ |
| CI (тесты на Python 3.11, 3.12) | ✅ |
| Автоматические релизы (GitHub Release) | ✅ |

### Roadmap

| Фича | Статус | Примечание |
|------|--------|------------|
| Отправка файлов пользователю | 🔜 | Upload работает, нужен формат attachment |
| Отправка голосовых сообщений | 🔜 | Нужен формат `audio` attachment |
| Отправка геолокации | 🔜 | Нужен формат `location` attachment |
| Групповые чаты | 🔜 | Нужна адаптация `chat_id` вместо `user_id` |
| Каналы | 🔜 | Аналогично групповым чатам |
| Стикеры | ❓ | Нет информации о поддержке в API |
| Read receipts (галочки) | ❌ | Не поддерживается MAX Bot API |
| Menu button (как в Telegram) | ❌ | Нет аналога `/setMyCommands` в MAX |

## 📋 Требования

- Python 3.11+
- Hermes Agent (установленный и настроенный)
- Сервер с публичным IP (или tunnel) для приёма webhook
- SSL-сертификат (Let's Encrypt или самоподписанный)

## 📦 Установка

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

> ⚠️ **Важно:** Создание ботов на платформе MAX доступно **только юридическим лицам, ИП и самозанятым** (резидентам РФ).

Подробная инструкция: [MAX для разработчиков — Создание чат-бота](https://dev.max.ru/docs/chatbots/bots-create)

### 4. Настройка конфигурации

```bash
cp .env.example .env
nano .env
```

### 5. Запуск

```bash
source venv/bin/activate
python -m src.main
```

## ⚙️ Настройка

### Переменные окружения

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

### Nginx (обратный прокси)

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

### systemd

```bash
sudo cp systemd/max-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now max-bridge
```

### Docker

```bash
docker compose up -d --build
```

## 🚀 Запуск

### Напрямую

```bash
source venv/bin/activate
python -m src.main
```

### Как служба (systemd)

```bash
sudo systemctl start max-bridge
sudo systemctl status max-bridge
sudo journalctl -u max-bridge -f
```

### Docker

```bash
docker compose up -d --build
docker compose logs -f
```

## 📁 Структура проекта

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

## 📊 Сравнение с Telegram Bot API

| Возможность | Telegram | MAX Bot API |
|-------------|----------|-------------|
| Webhook | ✅ | ✅ |
| Long Polling | ✅ | ✅ |
| Inline keyboard | ✅ | ✅ |
| Reply keyboard | ✅ | ❌ (только inline) |
| Callback buttons | ✅ | ✅ |
| Send/Edit/Delete messages | ✅ | ✅ |
| Typing indicator | ✅ | ✅ |
| Read receipts | ✅ | ❌ |
| Bot commands menu | ✅ | ❌ |
| Send images/files | ✅ | ✅ (через upload) |
| Send location | ✅ | ❓ |
| Send stickers | ✅ | ❓ |
| Group chats | ✅ | ✅ |
| Channels | ✅ | ✅ |

## 🧪 Тестирование

```bash
source venv/bin/activate
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

## 🔧 Устранение неполадок

### Мост не получает сообщения от MAX

1. Проверьте регистрацию webhook: `curl -H "Authorization: TOKEN" https://platform-api.max.ru/subscriptions`
2. Проверьте что порт открыт: `curl https://your-domain.com/health`
3. Проверьте логи: `sudo journalctl -u max-bridge -f`

### Hermes не отвечает

1. Проверьте что Hermes установлен: `hermes --version`
2. Проверьте что модель загружена: `ollama list`

### Бот не отвечает в MAX

1. Проверьте логи моста на наличие ошибок
2. Убедитесь что `MAX_BOT_TOKEN` валиден
3. Проверьте что бот активирован в MAX

## 🚀 Релизы и CI/CD

### Git flow

- `main` — стабильная ветка, релизы
- `develop` — ветка разработки, интеграция изменений
- Релизы помечаются тегами `v*` (например `v1.1.0`)
- При пуше в `main` или тег `v*` автоматически деплоится на сервер

### GitHub Actions

| Workflow | Триггер | Описание |
|----------|---------|----------|
| **CI** | push/PR в `main`, `develop` | Запуск тестов на Python 3.11, 3.12 + линтер |
| **Deploy** | push в `main` или тег `v*` | Автодеплой на сервер через SSH |
| **Release** | тег `v*` | Автоматическое создание GitHub Release |

### Настройка автодеплоя

В настройках репозитория GitHub → Settings → Secrets → Actions добавьте:

| Secret | Описание |
|--------|----------|
| `DEPLOY_HOST` | IP-адрес или домен сервера |
| `DEPLOY_USER` | Пользователь SSH |
| `DEPLOY_SSH_KEY` | Приватный SSH-ключ |

### Создание релиза

```bash
# Собрать изменения в develop
git checkout develop
# ... коммиты ...

# Слить в main и создать тег
git checkout main
git merge develop --no-ff
git tag -a v1.2.0 -m "Release v1.2.0: описание"
git push origin main --tags
```

## 📄 Лицензия

MIT License. См. [LICENSE](LICENSE).

---

## 🔗 Связанные проекты

| Проект | Описание |
|--------|----------|
| [MAX Hermes Plugin](https://github.com/RuslanStrogov/max-hermes-plugin) | Нативный платформенный плагин для Hermes Gateway. Прямая интеграция MAX без моста. |

<div align="center">

  <sub>🎨 Designed by <a href="https://br-design.ru/">BR-DESIGN</a></sub>

</div>
