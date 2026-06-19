# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - develop

### Added
- Support for all MAX API update types: `message_edited`, `message_removed`, `bot_added`, `bot_removed`, `chat_created`
- Attachment download from MAX CDN (images, video, audio, files) with local temp storage
- Chat action support: `typing_on`, `typing_off` via `POST /chats/{chatId}/actions`
- Callback answer support via `POST /callback`
- Message edit/delete support via `PUT/DELETE /messages/{messageId}`
- Long Polling support via `GET /updates`
- File upload support via `POST /uploads`
- Inline keyboard builder for structured button attachments
- GitHub Actions CI (test on Python 3.11, 3.12)
- GitHub Actions CD (auto-deploy to server via SSH on push to main)
- GitHub Actions release automation (create GitHub Release on tag)
- Git flow: `main` (stable) / `develop` (development)
- Detailed bot creation instructions in README (including legal entity requirements)

## [1.0.0] - 2026-06-22

### Added
- Initial release: MAX Bot API ↔ Hermes Agent bridge
- Webhook server receiving MAX updates via `POST /webhook`
- Message forwarding from MAX to Hermes via `hermes chat -q -Q` CLI
- Response forwarding from Hermes back to MAX via Bot API
- Typing indicator while Hermes is processing
- User access control (whitelist)
- Health check (`GET /health`) and status (`GET /status`) endpoints
- Webhook subscription management (`POST /subscriptions`)
- systemd service for production deployment
- Docker support (Dockerfile + docker-compose)
- Nginx config template for reverse proxy with SSL
- Open source preparation: MIT License, .env.example, setup.sh
