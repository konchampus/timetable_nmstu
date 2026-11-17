# Фактическое развёртывание

## Пруд Карпа и серверные квоты · 17.11.2026

- Прямое разрешение пользователя: «залевай». Выпущен [679004d](https://github.com/konchampus/timetable_nmstu/commit/679004db3d6b0bc271cbc8f7a4a04d45b57f96c7), ветка feat/carp-pond-progression (основная реализация — 1f65ad6; 679004d фиксирует старый wire payload в DB regression).
- На zerox-prod обновлены только API/web: magtu-companion-backend:carp-679004d и magtu-companion-web:carp-679004d. Current указывает на /opt/magtu-companion-releases/679004db3d6b0bc271cbc8f7a4a04d45b57f96c7.
- Создана зашифрованная backup-точка штатным backup.sh (04:14 UTC). Применена добавочная миграция 0004_fishing_progression поверх 0003. Никаких reset/TRUNCATE/DELETE пользовательских данных не выполнялось.
- До production: 58 offline tests, 15 replay-векторов рыбалки, 16 спортивных векторов; 9 PostgreSQL integration tests на одноразовой внутренней сети и tmpfs-БД; репетиция 0003 → 0004 сохранила синтетические баланс/снасти/улов/активный раунд/заметку. Тестовые контейнер и сеть удалены.
- В production проверены права SELECT/INSERT/UPDATE/DELETE новой таблицы runtime-ролью без CREATE, startup отдельного API probe без host-port, health 200 и private catalog 401. Probe удалён до переключения.
- Контейнерные ID bot/worker/postgres совпали с pre-release снимком. Прежние образы сохранены как pre-carp-679004d; rollback приложения не должен откатывать схему и терять квоты.
- Внешние HTTPS / и /api/health — 200; health status=ok. index-DSjbJ2eE.js и Games-DE2G_XaY.js доступны, игровые ресурсы содержат Пруд Карпа и метаданные Пыялы, dev auth-маркер отсутствует. API/web restarts=0, в последних 5 мин просмотренных логов ERROR/CRITICAL/Traceback=0. Публичная страница осмотрена browser_* после refresh.
- Технические остановки до cutover: исправлены merge connect_args в операторском скрипте и чтение SSH stdin командой compose run; первая остановка не изменила схему, после второй схема уже была 0004, но старые API/web продолжали работать до завершения preflight. Откат/сброс данных не понадобился.
- Реальные пользовательские раунды и Telegram iOS/Android не выполнялись. Музыка не скачивалась: плеер без файла отключён.

## История · 16.11.2026

- Сервер: zerox-prod. vices-prod не отвечает по SSH; на нём ничего не менялось, бот коллоквиума не остановлен.
- Mini App: https://timetaaaas2ble.chickenkiller.com/
- Бот: https://t.me/timetable_casino_nmstu_bot
- Источники: https://github.com/konchampus/timetable_nmstu . Начальный запуск d245017; исправления поиска e9ad4ef и преподавательских ссылок dea0d7d. Точную текущую ревизию получать командой ниже.
- Новый сервис изолирован: отдельная PostgreSQL 16, роли runtime/migrator, Docker network и volume. БД не публикуется наружу, web слушает только 127.0.0.1:18080 за отдельным HTTPS-vhost.
- Рабочие контейнеры — non-root, read-only rootfs, no-new-privileges. Старые конфигурации сайта не редактировались; Nginx применял graceful reload, master PID сохранился. Прежний домен при обследовании отвечал HTTP 403; его содержимое/политику не меняли.

## Точечный выпуск оформления Telegram · 16.11.2026

- bot/worker переведены на образ `telegram-68117b6`; точный commit: `68117b63551502b8ed9904293f1cf69a973eb341`, ветка `feat/telegram-rich-timetable`. Исходная рабочая копия на сервере пока остаётся на a83a115: образ собран из git archive отдельной ветки, поэтому один rev-parse HEAD не описывает текущие bot/worker.
- Сборка и import app.bot/app.worker прошли. bot/worker running, restarts=0, в просмотренных последних 80 строках нет ERROR/Traceback. API, web и PostgreSQL не пересоздавались; Mini App не менялся.
- Добавлены нативные rich-таблицы, раскрываемые дни, список-fallback, inline-дни/недели/формат и copy-text аудиторий. Новые уведомления используют тот же формат, старый outbox сохранён.
- Метод sendRichMessage распознан live API запросом без получателя (400 chat_id is empty). Успешной отправки/визуальной приёмки в Telegram пока нет: произвольным пользователям демонстрации не отправлялись; в runtime-report rich_accepted=0/rich_rejected=0.
- Предыдущий backend-образ сохранён как `magtu-companion-backend:pre-telegram-68117b6`. Текущая local-tag указывает на новый backend, но уже запущенный api использует прежний image ID. При следующем общем restart api тоже получит новый образ; HTTP-код в нём не менялся.
- Полное описание формата и ограничений: [TELEGRAM_MESSAGES.md](TELEGRAM_MESSAGES.md).

## Где конфигурация и как заменить токен

На сервере, не в локальном проекте и не в Git:

	authenticated shell: ssh zerox-prod
	application env: /etc/magtu-companion/backend.env
	migration env: /etc/magtu-companion/migration.env
	compose selectors: /etc/magtu-companion/compose.env
	additional private PostgreSQL config: /etc/magtu-companion/postgres.yaml
	source checkout: /opt/magtu-companion

Для смены токена:

	nano /etc/magtu-companion/backend.env

Заменить только значение BOT_TOKEN, сохранить остальные настройки и затем выполнить:

	magtu-companion restart

Команда пересоздаёт только новые api/web/bot/worker с обновлённым env, БД и чужие сервисы не останавливает. Если бот отозван в BotFather, сначала получить действующий токен там. Не вставлять токен в команды, Git, логи или переписку. Env и ключи имеют права 0600; каталог конфигурации — 0700.

## Управление

	magtu-companion status
	git -C /opt/magtu-companion rev-parse HEAD
	magtu-companion restart
	magtu-companion stop-new

Последняя команда останавливает только новые процессы и сохраняет БД/volume. Автоматическое удаление volumes, сброс данных и переключение старого бота не выполнялись.

## Что подтверждено

- Backend-образ с Python 3.12 собран из существующего hash-lock; web собран npm ci → TypeScript/Vite внутри Node 22 image. Это сборка, не тестовая suite.
- Миграции новой БД применены до 0002_note_source; companion_app и companion_migrator без superuser/CREATEDB/CREATEROLE, runtime не может создавать объекты схемы.
- Внешний HTTPS отдаёт главную страницу 200; /api/health отвечает {"status":"ok"}. Получен отдельный сертификат до 13.02.2027; renewal-hook перезагружает Nginx только для этого lineage.
- Telegram getMe/getChatMenuButton/getMyCommands подтвердили бот-аккаунт, меню Mini App на конечный HTTPS-адрес и установленные команды. Polling-контейнер запущен, конфликтующий webhook не обнаружен.
- После жалобы пользователя выполнены разрешённые живые запросы официального поиска с ПК и zerox-prod: обе подгруппы АВб-26-2 и Коробков Ю.Д. доступны с HTTP 200. В развёрнутом адаптере реально загружены 30 занятий группы и 26 нормализованных занятий преподавателя, обе недели, без stale fallback.

## Исправления поиска

1. Безусловная crawler-policy проверка robots.txt блокировала публичный поиск ещё до HTTP-запроса. Теперь public_viewer использует только endpoint поиска из клиентского JS сайта и canonical страницы выбранных расписаний. Строгий SOURCE_ACCESS_MODE=robots доступен оператору явно; на этом сервере установлен public_viewer. Лимиты, идентифицируемый User-Agent, проверка хоста/путей, запрет обхода 403/429 и редиректов сохранены.
2. На странице преподавателя подписи подгрупп используют «п/г», тогда как поиск ожидает другое обозначение. Для canonical group URL используется сама ссылка источника, без дополнительных неоднозначных поисковых запросов. Связанные группы регистрируются при публикации проверенного снимка; их подписи нормализуются.
3. Найденные, но не открытые связанные объекты не считаются просмотренными; worker не продлевает сам себе срок активности. Обновляются домашние и реально открытые объекты, не весь каталог.

## Резервная копия и пределы готовности

Ручная зашифрованная age-копия новой БД создана; открытый дамп на диск не писался. Команда нового снимка:

	/etc/magtu-companion/backup.sh

Архивы находятся отдельно от ключа:

	/var/backups/magtu-companion/*.dump.age
	/etc/magtu-companion/backup.agekey

Ключ и копии не публиковались и не скачивались. Внешнее backup-хранилище, автоматическое расписание backup и проверка восстановления не настроены/не выполнялись.

Автоматические suites, нагрузочные/security/concurrency испытания, приёмка всех 12 игр и пользовательский сценарий авторизации внутри Telegram не запускались. Работоспособность всего продукта не выводится из health-check: подтверждены перечисленные сборка, развёртывание и конкретные живые обращения поиска/расписания.
## Локальные игры и тематическая рыбалка · 2026-11-16

- Исходный коммит `b52a289a3fa00fc978af076c354bab4aa9632f64` опубликован в `feat/client-gameplay-and-calendar`. Push выполнен существующим SSH-ключом; remote URL и глобальная Git/SSH-конфигурация не менялись.
- API: `magtu-companion-backend:games-b52a289`, web: `magtu-companion-web:games-b52a289`. Образы собраны на сервере из точного git archive, отдельно от bot/worker; их общий тег backend:local не переназначался.
- До миграции создана age-копия: `/var/backups/magtu-companion/magtu-20261116T180246Z-2531939.dump.age`, права 0600. Ключ не читался и не переносился.
- Alembic: `0003_fishing_world (head)`. Только добавлены предпочтения и расширен лимит коллекции до 7. Никакого сброса баланса, снастей, рыбы, раундов, рейтинга, заметок или настроек не выполнялось.
- Первый ранний probe получил curl 56 (connection reset при запуске nginx) и автоматически вернул прежние API/web без downgrade БД. После отдельного запуска нового API подтверждены readiness 200 и анонимный доступ к приватному каталогу 401. Исправлен ограниченный startup-retry (`--retry-all-errors`), повторное переключение завершилось успешно.
- bot, worker и PostgreSQL сохранили точные container IDs из pre-release снимка. API/web running, restarts=0 при финальной проверке. Прежние образы сохранены с тегами `pre-games-b52a289`.
- Release source: `/opt/magtu-companion-releases/b52a289a3fa00fc978af076c354bab4aa9632f64`. Симлинк `/opt/magtu-companion-releases/current` указывает на него. Штатная команда `magtu-companion` условно добавляет `current/games.override.yaml`, поэтому дальнейший restart сохраняет раздельные API/web образы и не заменяет Telegram-релиз. Исходный wrapper сохранён в release-каталоге.
- Основной checkout `/opt/magtu-companion` по-прежнему на a83a115: он не отражает код работающих контейнеров. Не запускать общий build/restart с переименованием backend:local из этого checkout.
- Внешняя главная: HTTPS 200; `/api/health`: `{"status":"ok"}`. Browser открыл публичную гостевую страницу. Полный Telegram login/gameplay, реальные игровые мутации, восстановление backup и автоматические тестовые suites не выполнялись. Узкие read-only ревью миграции/экономики и cutover-скриптов двумя субагентами не нашли критических блокеров; это не интеграционные тесты.
- Возможности и пределы релиза: [рыбалка и UX](<FISHING_WORLD.md>). На main ветка автоматически не сливалась.

## Web-only редизайн · 2026-11-16

- Feature branch feat/companion-mini-app-redesign, source commit 5d8b66a6fd7993e839e2278bec5c1095a22834b4. Собран архив точного commit; production image: magtu-companion-web:mini-app-5d8b66a.
- Live browser review: desktop 1280×902, mobile emulation 360×732; осмотрены mobile first viewport, прокрутка до иллюстраций/футера и system-dark screenshot. Гостевая страница видима, явного горизонтального overflow не замечено. Нативный resize tool не нашёл Chrome, поэтому повторные снимки сделаны через уже установленный Edge и эфемерный Playwright CLI, без установки нового ПО. Публичная страница и все 12 game-art WebP: HTTP 200.
- Docker npm ci: 0 найденных vulnerabilities. TypeScript + Vite production build завершились успешно; 1598 модулей, ~8.4 kB CSS gzip для основного stylesheet. Three.js GameScene — отдельный lazy chunk 513 kB minified / 132.44 kB gzip, Vite напечатал стандартное предупреждение >500 kB.
- Пересоздан и healthy только Compose service web; api, bot, worker и PostgreSQL имели прежние container ID. PostgreSQL оставлен без изменений, несмотря на предупреждение Compose про уже существующий orphan container. Автоматическая очистка orphans не запускалась.
- Для отката сохранён прежний image tag magtu-companion-web:pre-mini-app-redesign-5d8b66a. Код/контейнеры backend и БД не обновлялись; миграции не запускались.
- Приёмка была на гостевой странице без Telegram initData: приватные экраны, аккаунтные настройки и игровые серверные мутации не запускались; фальшивые балансы и результаты не создавались. Telegram-specific safe-area визуально в WebView не проверена (CSS и события проверены в коде). Эмулятор отметил один внешний timeout telegram.org/js/telegram-web-app.js, при 0 warnings; HTML, entry JS/CSS и видимые изображения — HTTP 200.
