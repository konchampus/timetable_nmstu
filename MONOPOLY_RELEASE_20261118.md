# Проверки релиза Монополии · 18.11.2026

## До публикации

- Чистая integration main наследует d88751f: прежние выпущенные Telegram/дизайн/рыбалка сохранены.
- Из integration checkout: backend202/202 OK; client54/54 PASS; TypeScript/Vite production build exit0. npm ci --offline использовал существующий кэш.
- Просмотрены API wiring, account-cleanup, bounded-event config, deep links, общий GameWindow. Секреты и личная конфигурация не копируются.
- Реальный iframe360×740: карта360×321, обзор321×321; действие48px и нижняя навигация видны. В584×913 карта584×494, обзор494×494 вместо260×260. document scrollWidth равен viewport, errors[]. Лента клеток прокручивается намеренно.
- Dev-мок: zoom к фишке/обратно, клавиатурное перемещение48px; финальный сценарий с ожиданием реальных кнопок: бросок→покупка→завершение хода→виден ход Саши. Это синтетические данные, не реальные Telegram-аккаунты.
- Карточка текущей клетки14px; режим фишки показывает клетки~64px, поле тянется на месте. Кубики видимы независимо от камеры и честно подписаны «Последний бросок».
- Математика drag/pinch проверена тестами; физический Android/iOS отдельно не проверен.

## Дополнительная регрессия

Общая оболочка:25/25 PASS на360×740 light, включая открытие/закрытие всех12 игр, навигацию, поиск, профиль, заметки, Карповый пруд, историю и рейтинг. Устаревший селектор «Все игры» в dev-harness заменён на реальную кнопку «Закрыть игровое окно»; runtime-код не меняется. Повторная production-сборка даёт те же index-BTISLNId.js и Monopoly-2s9g3v23.js, что серверный образ97a0fc1.

## PostgreSQL и серверная сборка

Образы97a0fc1 собраны на сервере: backend Python3.12, web Node22/TypeScript/Vite1632modules, exit0. Создана существующим backup.sh зашифрованная pre-release копия. В отдельной внутренней Docker-сети, tmpfs PostgreSQL16 без host-портов:202 Monopoly tests+9 реальных DB invariants OK; миграция0004→0005 прошла, синтетические кошелёк777/снасть3/локацияcarp и заметка сохранены, все4таблицы созданы; exit0. Первый тестовый DSN не содержал обязательного синтетического пароля и был отклонён валидатором; fixture исправлен, рабочая конфигурация не менялась. Тестовая БД и сеть убраны EXIT-trap. На момент завершения rehearsal прод ещё не был переключён; фактический cutover подтверждён ниже.

## Реальные блокировки и журнал команд

Дополнительный smoke на отдельной PostgreSQL16 с реальными enter/command/current_user/lock_authenticated_user и async_session_factory: параллельный одинаковыйUUID create даёт1room/1command; имя берётся из principal; второй участник входит; гонка ready на одной версии даёт ровно200/409 и version+1; replay не мутирует, иной payload с тем жеUUID даёт409 без изменений. Итог1room/3commands/2members/version3, exit0. Собственная сеть/БД удалены и отсутствие проверено отдельно. Это direct endpoints с синтетическими AuthSession, не Telegram end-to-end.

## Выпуск

Prod переключается после PostgreSQL0004→0005 rehearsal и проверок нового образа. До миграции — существующий зашифрованный backup. API/web получают отдельные immutable теги; bot/worker/PostgreSQL не пересоздаются. Rollback сохраняет схему и данные. Фактически активирован97a0fc1422aca6c5620e1c835d2a5576a9da6138: migration0005_monopoly(head), праваCRUD4таблиц безDDL, API probe200/private401, activation exit0. Bot/worker/PostgreSQL container IDs сохранены. Внешние / и health200/statusok, index-BTISLNId.js,Monopoly-2s9g3v23.js,Monopoly-6jY87NeK.css200, неавторизованные rooms/board401. API/web running/restarts0, ERROR/Traceback0. Публичная страница открыта browser_*; реальную Telegram-сессию не подменяли. Startup curl56 восстановился ограниченным retry без отката.
