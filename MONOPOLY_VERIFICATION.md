# Итог проверок локальной Монополии — 18.11.2026

## Дополнение — имена Telegram

Автоматическое имя из авторизованного /me + серверное разрешение User.name при create/private join/public join; свой ник необязателен и действует только в партии. Никакого initDataUnsafe для имени/доступа к чужим контактам. Финальные прогоны после изменения: backend202tests OK exit0 (6новых проверок имён), client42/42 PASS, production build exit0. Старый fingerprint witness обновлён корректно исключать новое поле при эмуляции схемы v1; совместимость подтверждена. Ни миграций, ни изменения текущих имён в уже созданных партиях. В браузере лобби показало предзаполненное «Демо-пользователь» из synthetic /me; «Создать комнату» нажато без ввода имени, список участников показал «Демо-пользователь · вы». Это проверка dev-мока, не реального аккаунта Telegram.

## Версия2 после отклонения мобильного интерфейса

Предыдущий v1 desktop-on-phone не принят пользователем. Ниже исторические115/36проверки не описывают актуальный мобильный релиз и не заменяют пользовательскую приёмку.

### Финальные повторные прогоны parent

- Backend: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p test_monopoly*.py — **196 прогонов, OK, exit0,5.673с**. Не196уникальных end-to-endсценариев: discovery включает импортированные TestCase повторы. Все engine/API/events/contracts/v2 наборы выполнены; реальнойБДнет.
- Frontend: node --test src/games/monopoly/useMonopoly.test.mjs src/games/monopoly/PropertyArt.test.mjs — **41/41 PASS, exit0** (38hook/recovery +3art). Одинаковые имена/цвета в artwork test исключают «различие только за счёт подписи»: все28SVG имеют разную геометрию.
- npm run build — **exit0,1628modules, последний прогон2.00с**. После finalsource/contrasts исправлений; TypeScript+productionVite. No source edits после этого кроме документации/test-harness.
- Официальные full-textисточники прочитаны rules-v2; parent самостоятельно прочитал monins.pdf через read_page. C1009F22 основа, Rev2/Deluxe cross-check, различияредакций не скрыты. Сдача, автоматическая рента, последовательные аукционы и наследованиезалогов — обозначенные цифровыеадаптации, friendly/timed — house presets.
- Новые196покрывают startertie, debttrade, оба вида jailcards, mortgagekeep/immediate, evenbuildanyturn/jail, last house+hotelauction, completegroup liquidation, timed expiry debt/auction/cardchain/ties, strictnumeric API без bool/float/string coercion, anyturnresign(highbidder/actor/foreign/current/debtor), legacyUUID fingerprint, friendlyrent expiry2globalturns/fee/ownershiptransfer. Независимый read-only contractreview нашёл bug chainedbankauctions losingpendingpurchase; rules-v2 исправил и добавил regression с2аукционами и pending39, parent rerun196PASS.

### Практическая мобильная проверка parent

- Native browsercontroller, syntheticui-lab; **360×740 light /390×844 dark**, учитываются ширина И высота. Native game dialogheight=viewport, document.scrollWidth=width. Primary roll360: top508,bottom560,height52; bottomnav680–736 (740viewport). На390: roll522–574, nav784–840 (844viewport). Zoom44px, навигация56px, основныеподтверждения44–52px.
- Проверены реальные DOM-переходы Поле→Активы, открытие «Рыбная лавка», native focus/Escape/close; крупные цены/рентнаятаблица/управление в отдельном scrollsheet. Изображения различимы в assetslist; overview намеренноне основная целькасания.
- Friendlyincomingoffer: видимые условия4общиххода/fee80/termination/nonrefund; принятие через реальную кнопку меняет вкладку на1activecontract с expiryturn10 и уже внесённой80. Это **mocktransport**, не multiuserинтеграция; финансовыеусловия подтверждают engineunittests отдельно.
- Меню→сдача→«Остаться в игре»: отмена сохраняет игру. Повторное открытие→«Да, сдаться навсегда» отправляет единственную команду в syntheticfixture. Чатдоступен отдельной вкладкой, вводчерновика и переходназад выполнены; хранениеdraft поднято ккорню компонента, не сбрасывается отtabunmount.
- Подпискиevents не теряются отпереключенияmobiletabs (hook живёт внеpanels). Parent reran прежниеlate-response/recoverytests с новымирежимами/commands. UnknownrequestUI продублирован внутри активного native formdialog, чтобы retryне оказался за inertфоном.
- Raw diagnostic g/path bounds могутвыходить заframe, но clippingSVG и клеток hidden, documentwidth неизменён; actualpixels reviewer не показалипротекания. Это НЕ выдано за rawoverflow=[]; в lists/deals/chat rawoverflowпуст. SVGAnimatedStringdiagnostic clonebug исправлен безизмененияappUI.
- Desktoprecapture1280×800 валиден послефокусировкиvisiblecontrol/Home. Старый blankcapture НЕиспользовался какдоказательство. Root read_imagebindingпериодическиотсутствовал; независимыйreviewer действительнооткрылdesktop/mobile/card/darkpixels и подтвердил ихсодержимое, rootпервыйmobileimageпросмотрел доbindingfailure.
- Единственныйmaterialfixфинальногоreview: darkaccenttext. Отдельный --m-accent-text используетdark --accent, primarybg#2254ffсбелымнеизменён. Контрастtext7.38:1(surface)/6.26:1(soft), primary5.56:1. Новыеdarkpixelsпроверены reviewer, **ship для scopedfix**, не заявленrealTelegram/полныйпродукт.

СнимкибезизмененияUIпикселей: [phone360](<.impeccable/review/mobile.png>), [desktop](<.impeccable/review/desktop.png>). Это точныеviewportcrops screenshot, не comp/отрисованнаякартинка. [Итогreview](<.tasks/mobile-finish-v2.md>), [правила/ограничения](<MONOPOLY.md>), [backendотчёт](<.tasks/rules-v2-report.md>).

**Остаётся до production:** realPostgreSQL196-тесты не заменяют;2workers/2Telegramаккаунта, proxytimeouts, WebView keyboard/safeareas, migrationsbackup и пользовательскаяприёмканафизическомтелефоне. Никакихsecrets/install/production действий не было. Front+backendвыпускатьсовместно только после отдельногосогласования.

## История v1 — выполнено до новой мобильной переработки

## Реально выполнено parent

- Frontend: npm run build — exit0, TypeScript + Vite production,1626 modules,2.03с последнего прогона. Новая Monopoly загружается отдельным lazy chunk. Поиск UI_LAB_MEMORY_TOKEN/UI_LAB_NOT_VALID/демо-маркеров/monopoly.fixture в dist JS —0 совпадений.
- Backend: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p test_monopoly_*.py — **115 прогонов, OK, exit0,5.514с**. В event-suite повторно открывается импортированный API TestCase; это количество выполненных прогонов, не115 уникальных бизнес-сценариев. Engine76, API16, events23 (включает4 импортированных API-case). Никакой реальной БД эти тесты не используют.
- Клиент: node --test src/games/monopoly/useMonopoly.test.mjs (cwd frontend) — **36/36 PASS, exit0,288мс**. Реальный transpiled hook, детерминированный scheduler вместо ReactDOM; mock API специально игнорирует abort для проверки гонок. Visible events-loop действительно запускается в новых сценариях. Не browser E2E.
- AST-проверка11 Python-файлов +一致ность40 названий/28 активов и экономики theme/engine —exit0. Новые AssetArt/Dice не содержат embedded raster, image/img или внешних HTTP URL.
- Engine long simulation:12 seeded complete parties, долги/банкротства/очереди, инварианты денег/владения/зданий, без зависания. Проверки: дубли/три дубля, тюрьма и deferred move после долга, рента, аукционы, строительство32/12, равномерная продажа, залоги/проценты, обе колоды, sequential payouts без печати денег, bankruptcy/foreign debtor/inheritor interest/trades. roll_sequence меняется только на принятый бросок.
- API/events witnesses: version/replay/mismatched payload, закрытые summaries без кода/decks, chat cooldown/отдельная event_version, reconnect при8 комнатах, mine discovery, noop timer/hard15мин, удаление/анонимизация исторических snapshots, замороженная миграция vs ORM, tiny event signal,300ms fake-clock detection,18s expiry, admission/cancellation, live generation/auth SQL, release session before sleep, fake transaction rollback witness.
- Client witnesses: bootstrap retry, strict recovery envelope, same UUID retry, transport/5xx uncertain, business409 read, stale GET after lobby/openB/leave, unmount/StrictMode/account generation, monotonic game/event versions, POST→lobby, stale precommit chat GET, hidden subscription cancellation, no hot spin after503/held reads. Отдельный latency witness: подтверждённый POST освобождает busy и разрешает promise, пока reconciliation GET намеренно не завершён.

## Браузерная проверка parent

Только изолированный dev ui-lab, synthetic data, без Telegram/server/очков. Нормальный браузерный controller; raw Playwright MCP не нашёл Chrome — ничего не устанавливалось. Vite поднят локально с managed job; после перезапуска среды восстановлен с polling watcher.

- Desktop1280x800: auto-open deep link, имя → создать комнату → старт demo, подтверждённый бросок/карточка, чат отправка, обзор/подробное поле. 3D SVG-кубы показывают именно3+3. Форма обмена — вложенный native dialog: Escape закрывает только обмен, партия остаётся открыта.
- Mobile390 light и360 dark: iframe CSS viewport, width=scrollWidth, overflow=[], errors=[], blocked requests=[] по DOM diagnostics. Это не device emulator и не реальный TelegramWebView. Подробный pan-mode увеличивает labels14px/prices13px, а карточка актива остаётся альтернативой микротексту обзора.
- Focus/underlying inert/body-scroll обеспечены native dialog; закрытие игры не отменяет серверную партию. Original12 game mechanics/API не переписывались; общая оболочка изменилась.
- Независимый finishing review: два material fix (читаемый detail-mode, постоянное aria-label приглашения) применены, новые captures просмотрены, disposition **ship** для проверенных визуальных исправлений. См. [.tasks/finish-review.md](<.tasks/finish-review.md>).

Итоговые снимки: [desktop](<C:/Users/User/.dsh/profiles/desktop/.dsh-browser/screenshots/monopoly-review-desktop.png>), [mobile390 full fixture](<C:/Users/User/.dsh/profiles/desktop/.dsh-browser/screenshots/monopoly-review-mobile-full.png>), [подробное поле](<C:/Users/User/.dsh/profiles/desktop/.dsh-browser/screenshots/monopoly-review-detail.png>), [3D кубики3+3](<C:/Users/User/.dsh/profiles/desktop/.dsh-browser/screenshots/monopoly-dice-final.png>).

## Не подтверждено — нельзя выдавать за проверенный production

- Реальные PostgreSQL транзакции/конкурентность двух workers, FK cascade, lock wait/deadlock и upgrade/downgrade0005 не запускались. Нет локального PostgreSQL/docker; установка не выполнялась. Fake rollback/session tests не доказывают свойства БД.
- Нет сетевой партии2 настоящих Telegram аккаунтов, startapp integration/WebView safe-area/push acceptance, измерения production RTT/FPS/load.300мс — interval detection,780мс — CSS duration, не production benchmark.
- Нет новой production-выкладки, не тронуты production env/БД/сервисы/балансы. Требуется staging+разрешение на релиз по [MONOPOLY.md](<MONOPOLY.md>).
- GUAPoly literal bitmap не переносился: явной лицензии не найдено, заменён оригинальным SVG. User-acceptance дизайна не подменена build/reviewer ship.

## Делегирование

Оригинальные SVG: внешний Codex (успешно завершён). Старый внешний rules-agent остановлен без code-результата, задачу выполнил native rules-engine. Native game-shell, rooms-review, rules-engine, client-review, client-fixes, realtime, dice-motion, finish-review — результаты собраны и интегрированы parent; parent повторил общий test/build и просмотрел итоговый код. В корне проекта нет Git metadata: git diff/status здесь недоступны, существующие файлы читались перед точечными изменениями; unrelated проекты не изменялись.
