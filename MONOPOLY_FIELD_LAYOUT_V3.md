# Phone Field v3 — scoped handoff

## Сделано
- Только frontend/src/games/monopoly/Monopoly.tsx и новый field-layout-v3.css; общий mobile CSS, hook/server/art не редактировались.
- Phone Field: PlayableBoard вместо Board, без старого «Обзор города / Крупнее». Desktop и desktop zoom оставлены на исходном Board. Передаются tiles/state/selected/onSelect/you/rolling.
- Оставшееся место экрана — три строки: minmax(180px,1fr), strip 96px, решение clamp(96px,12dvh,112px), сложные состояния 120px. Нет собственного фиксированного размера карты или min-content shrink.
- Strip: текущая клетка активного участника + три следующих + предыдущая; настоящие кнопки шириной 196px и touch minimum 44px, name 14px, owner/price/rent 12px. Цена не сжимается владельцем. Текущая отмечена aria-current и рамкой.
- Turn/position/roll_sequence возвращают strip к текущей клетке через scrollTo, не focus. Во время dialog[open] прокрутка не инициируется; Чат не монтирует strip. Позиция только серверная.
- Обычный ход: строка статуса + кнопка 48px; удаляются только два generic hint на phone. Сложные решения, trade prompt и timeout не удалены: внутренний bounded scroll. Desktop wrapper display:contents сохраняет исходные grid-потомки.
- Сохранены пять вкладок, сделки/договоры/чат и обработчики мутаций.

## Проверка исходников, не браузерная приёмка
Context + craft-floor прочитаны; режим Operate и существующий brand сохранены. Отдельные layout assessment / mechanical review выполнены в одном агенте из-за запрета дальнейшей делегации. Файлы перечитаны после изменения. Build/server/browser по указанию lead не запускались до интеграции.

Расчёт при safe-area=0, без error/notice; исходные header64, player chips65, nav65:

| Phone viewport | Map, normal | Map, complex | Strip | Decision normal / complex |
|---|---:|---:|---:|---:|
| 360×740 | 354 | 330 | 96 | 96 / 120 |
| 584×913 | 513.44 | 503 | 96 | 109.56 / 120 |
| 390×844 | 452.72 | 434 | 96 | 101.28 / 120 |

Это вычисленные layout budgets, НЕ measured DOM rects. Safe-area и recovery могут уменьшить map; grid floor180 сохраняется. Header flex-shrink0 защищает верхнюю границу.

## Риски
- Геометрия мира/ячейки принадлежит PlayableBoard (lead решил 704px/64px); этот scoped patch её не переопределяет.
- Аренда в strip помечена базовой; rail показывает диапазон, utility множители. Не подменяет расчёт сервера или полную карточку.
- У длинного имени владельца возможен ellipsis, цена остаётся видима; полная карточка по нажатию.
- Нужен rendered check интеграции на реальной phone-height; пользовательская приёмка не заявлена.

## Осталось
Lead: build/typecheck после появления PlayableBoard, проверка 360×740 / 584×913 / 390×844, roll follow, All field / You / + / −, nearby modal и возврат, complex-scroll, chat draft + desktop regression. Убедиться, что телефонный primary виден без page scroll.

## Тебе
Scoped changes frozen; production не затронут.
