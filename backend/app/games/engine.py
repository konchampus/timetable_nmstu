"""Rules v1: pure state transitions except the explicit cryptographic random source.

Payouts are total returns, not profit. Never serialize secret dictionaries.
"""
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from secrets import SystemRandom
from . import fishing_world

RNG = SystemRandom()
RULES_VERSION = 1
SYMBOLS = ("cherry", "lemon", "bell", "diamond", "seven")
SLOT_TRIPLES = dict(zip(SYMBOLS, (5, 7, 10, 15, 25), strict=True))
DART_ZONES = (0, 5, 10, 20, 25, 50)
DART_PAYOUTS = dict(zip(DART_ZONES, (0, 0, 0, 1, 2, 3), strict=True))
BOWLING_PAYOUTS = {i: (7 if i == 10 else 2 if i == 9 else 1 if i >= 7 else 0) for i in range(11)}
WHEEL = tuple(Fraction(n, 2) for n in (0, 0, 0, 1, 1, 2, 2, 3, 4, 6))
RED = frozenset((1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36))
FISH = (
    ("Плотва", "common", 10, 100, 500),
    ("Карась", "uncommon", 25, 300, 1200),
    ("Карп", "rare", 60, 1000, 8000),
    ("Щука", "rare", 60, 1000, 4000),
    ("Сом", "epic", 150, 3000, 12000),
    ("Золотая рыба", "legendary", 400, 500, 2000),
    ("Золотой карп", "legendary", 900, 2000, 10000),
)
FISH_WEIGHTS = ((65, 23, 3, 6, 2, 1, 0), (57, 26, 4, 8, 4, 1, 0), (49, 28, 5, 10, 6, 2, 0), (40, 30, 6, 12, 9, 3, 0), (30, 30, 8, 14, 13, 5, 0))
ROD_WAIT = (15, 12, 10, 8, 6)
ROD_COST = (250, 750, 1500, 3000)
GAME_IDS = ("slots", "fishing", "dice", "darts", "bowling", "basketball", "football", "coin", "roulette", "blackjack", "mines", "wheel")


@dataclass(frozen=True)
class Outcome:
    result: dict
    multiplier: Fraction


def payout(bet: int, multiplier: Fraction | int) -> int:
    amount = bet * multiplier
    return amount.numerator // amount.denominator if isinstance(amount, Fraction) else amount


def instant(game: str, choice: str | None) -> Outcome:
    if game == "slots":
        symbols = [RNG.choice(SYMBOLS) for _ in range(3)]
        counts = Counter(symbols)
        multiplier = SLOT_TRIPLES[symbols[0]] if len(counts) == 1 else 1 if len(counts) == 2 else 0
        return Outcome({"symbols": symbols}, Fraction(multiplier))
    if game == "dice":
        value = RNG.randrange(1, 7)
        success = (value <= 3) == (choice == "low")
        return Outcome({"value": value}, Fraction(19, 10) if success else Fraction(0))
    if game == "darts":
        value = RNG.choice(DART_ZONES)
        return Outcome({"value": value}, Fraction(DART_PAYOUTS[value]))
    if game == "bowling":
        value = RNG.randrange(11)
        return Outcome({"value": value}, Fraction(BOWLING_PAYOUTS[value]))
    if game in ("basketball", "football"):
        value = RNG.randrange(1, 6)
        success = value >= (4 if game == "basketball" else 3)
        multiplier = Fraction(9, 4) if game == "basketball" else Fraction(3, 2)
        return Outcome({"value": value, "success": success}, multiplier if success else Fraction(0))
    if game == "coin":
        side = RNG.choice(("heads", "tails"))
        return Outcome({"side": side}, Fraction(19, 10) if side == choice else Fraction(0))
    if game == "roulette":
        number = RNG.randrange(37)
        color = "green" if number == 0 else "red" if number in RED else "black"
        if choice and choice.startswith("number:"):
            multiplier = 36 if number == int(choice[7:]) else 0
        else:
            success = number != 0 and (choice == color or choice == ("even" if number % 2 == 0 else "odd"))
            multiplier = 2 if success else 0
        return Outcome({"number": number, "color": color}, Fraction(multiplier))
    if game == "wheel":
        multiplier = RNG.choice(WHEEL)
        return Outcome({"multiplier": float(multiplier)}, multiplier)
    raise ValueError("Not an instantaneous game")


def hand_total(cards: list[str]) -> int:
    total, aces = 0, 0
    for card in cards:
        rank = card[:-1]
        if rank == "A":
            total += 11
            aces += 1
        else:
            total += 10 if rank in ("J", "Q", "K") else int(rank)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def blackjack_start() -> dict:
    deck = [rank + suit for suit in "SHDC" for rank in ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")]
    RNG.shuffle(deck)
    player = [deck.pop()]
    dealer = [deck.pop()]
    player.append(deck.pop())
    dealer.append(deck.pop())
    return {"deck": deck, "player": player, "dealer": dealer}


def blackjack_natural(secret: dict) -> bool:
    return any(len(secret[side]) == 2 and hand_total(secret[side]) == 21 for side in ("player", "dealer"))


def blackjack_public(secret: dict, finished: bool) -> dict:
    dealer = list(secret["dealer"]) if finished else [secret["dealer"][0], "?"]
    return {"player": list(secret["player"]), "dealer": dealer, "player_total": hand_total(secret["player"]),
            "dealer_total": hand_total(secret["dealer"] if finished else secret["dealer"][:1])}


def blackjack_finish(secret: dict) -> Outcome:
    player = hand_total(secret["player"])
    player_natural = len(secret["player"]) == 2 and player == 21
    dealer_natural = len(secret["dealer"]) == 2 and hand_total(secret["dealer"]) == 21
    if player_natural or dealer_natural:
        multiplier = Fraction(1) if player_natural and dealer_natural else Fraction(5, 2) if player_natural else Fraction(0)
    elif player > 21:
        multiplier = Fraction(0)
    else:
        while hand_total(secret["dealer"]) < 17:
            secret["dealer"].append(secret["deck"].pop())
        dealer = hand_total(secret["dealer"])
        multiplier = Fraction(2 if dealer > 21 or player > dealer else 1 if player == dealer else 0)
    state = blackjack_public(secret, True)
    return Outcome({**state, "natural": player_natural, "dealer_natural": dealer_natural}, multiplier)


def mines_multiplier(mines: int, opened: int) -> Fraction:
    if opened == 0:
        return Fraction(1)
    raw = Fraction(97 * comb(25, opened), 100 * comb(25 - mines, opened))
    scaled = raw * 10000
    return Fraction(scaled.numerator // scaled.denominator, 10000)


def adjacent_mines(cell: int, positions: list[int]) -> int:
    row, column = divmod(cell, 5)
    return sum(abs(divmod(mine, 5)[0] - row) <= 1 and abs(divmod(mine, 5)[1] - column) <= 1 for mine in positions)


def fishing_result(level: int, location_id: str = "shore") -> dict:
    weights = fishing_world.pool_weights(level, location_id, FISH_WEIGHTS)
    draw = RNG.randrange(sum(weights))
    index = 0
    for index, weight in enumerate(weights):
        if draw < weight:
            break
        draw -= weight
    species, rarity, value, low, high = FISH[index]
    value = int(value * fishing_world.LOCATIONS[location_id]["value_multiplier"])
    return {"species": species, "rarity": rarity, "value": value, "weight_grams": RNG.randint(low, high)}


def catalog() -> list[dict]:
    common = ["Только игровые очки без денежной стоимости.", "Множитель — общая выплата со ставкой; прибыль = выплата минус ставка. Округление вниз до целого.", "Версия правил: 1. Ставка 10–500, кроме бесплатной рыбалки. Например, 10 × 1.9 = 19, прибыль 9."]
    definitions = {
        "slots": ("Слоты", "Три независимых барабана", ["Каждый из пяти символов равновероятен на каждом барабане.", "Тройка cherry/lemon/bell/diamond/seven: ×5/7/10/15/25. Ровно пара ×1, иначе 0. Максимальная выплата 12500."], {**{f"triple_{s}": float(v) for s, v in SLOT_TRIPLES.items()}, "pair": 1, "other": 0}, {**{f"triple_{s}": 1 / 125 for s in SYMBOLS}, "pair": 60 / 125, "other": 60 / 125}),
        "fishing": ("Рыбалка", "Лови, открывай локации и собирай коллекцию", [
            "Бесплатный заброс, только один активный раунд. Улов сначала попадает в садок; очки начисляются при продаже.",
            "Удочки 1–5; улучшения стоят 250/750/1500/3000 очков. Локации: берег (уровень 1), Пруд Карпа (2), река (3), горное озеро (4), золотая заводь (5).",
            "На берегу действует базовая стоимость, в Пруду Карпа ×1.25, в реке ×1.5, в горном озере ×2, в золотой заводи ×3. Дробная стоимость округляется вниз.",
            "Состав и вероятности улова выбранной локации указаны перед забросом. Они относятся к успешно вываженной рыбе, не гарантируют успешную ловлю.",
            "Золотой карп — отдельный легендарный вид, встречается за пределами тихого берега. Базовая стоимость 900 очков, вес 2–10 кг.",
            "Скин медведя открывается на уровне удочки 3 бесплатно и не меняет шансы, стоимость или управление.",
            "Продажа всех рыб атомарна; коллекция и рекорд сохраняются. Старые забросы сохраняют уже определённый улов.",
            "За день Asia/Yekaterinburg: до 25 обычных попыток и 10 успешных обычных уловов; до 3 босс-попыток суммарно. Между любыми забросами 45 секунд, в том числе в старом режиме.",
            "Награда каждого босса — один улов фиксированной стоимости не более раза за день; очки только после продажи. Лимиты сдерживают фарм, но не исключают ботов."
        ], {fish[1]: fish[2] for fish in FISH[:6]},
            {f"rod_{level}_{rarity}": sum(FISH_WEIGHTS[level-1][i] for i, fish in enumerate(FISH) if fish[1] == rarity) / 100
             for level in range(1, 6) for rarity in dict.fromkeys(fish[1] for fish in FISH)} |
            {f"rod_{level}_species_{fish[0]}": FISH_WEIGHTS[level-1][i] / 100
             for level in range(1, 6) for i, fish in enumerate(FISH)}),
        "dice": ("Кости", "Угадай диапазон", ["low: 1–3, high: 4–6. Значения 1–6 равновероятны, угаданный диапазон ×1.9, иначе 0. Максимум 950."], {"win": 1.9, "lose": 0}, {"win": .5, "lose": .5}),
        "darts": ("Дартс", "Шесть зон мишени", ["Зоны 0/5/10/20/25/50 равновероятны. Выплаты 0/0/0/1/2/3. Максимум 1500."], {str(k): v for k, v in DART_PAYOUTS.items()}, {str(k): 1/6 for k in DART_ZONES}),
        "bowling": ("Боулинг", "Один бросок — до десяти кеглей", ["0–10 кеглей равновероятны: 0–6 ×0, 7–8 ×1, 9 ×2, 10 ×7. Максимум 3500."], {str(k): v for k, v in BOWLING_PAYOUTS.items()}, {str(k): 1/11 for k in range(11)}),
        "basketball": ("Баскетбол", "Попади в кольцо", ["value 1–5 равновероятно, 4–5 — попадание ×2.25, остальные промах ×0. Максимум 1125."], {"success": 2.25, "miss": 0}, {"success": .4, "miss": .6}),
        "football": ("Футбол", "Удар по воротам", ["value 1–5 равновероятно, 3–5 — гол ×1.5, остальные промах ×0. Максимум 750."], {"success": 1.5, "miss": 0}, {"success": .6, "miss": .4}),
        "coin": ("Монетка", "Орёл или решка", ["heads/tails: по 50%; угаданный исход ×1.9, иначе 0. Максимум 950."], {"win": 1.9, "lose": 0}, {"heads": .5, "tails": .5}),
        "roulette": ("Рулетка", "Европейское колесо 0–36", ["Каждое число 0–36: 1/37. number:N ×36; red/black/even/odd ×2.", "Ноль зелёный, для цвета и чётности всегда проигрыш. Максимум 18000.", "Красные: 1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36."], {"number": 36, "red": 2, "black": 2, "even": 2, "odd": 2}, {"number": 1/37, "red": 18/37, "black": 18/37, "even": 18/37, "odd": 18/37, "zero": 1/37}),
        "blackjack": ("Блэкджек", "Игрок против дилера", ["Одна колода 52 карт без возврата, карты AS,10H и т.д. Туз 1/11, J/Q/K по 10.", "Дилер стоит на любых 17. hit/stand; на 21 auto-stand. Без split/double/страховки.", "Natural ×2.5, оба natural ×1, обычная победа ×2, ничья ×1, проигрыш ×0. Максимум 1250.", "Каждая следующая карта равновероятна среди оставшихся; вероятности победы зависят от действий.", "Через 24 часа сервер выполняет stand без штрафа за закрытый WebView."], {"natural": 2.5, "win": 2, "push": 1, "lose": 0}, {"initial_natural": 2*4*16/(52*51), "initial_each_card": 1/52}),
        "mines": ("Сапёр", "5 × 5, от 1 до 10 мин", ["Индексы 0–24; первая клетка не защищена; выборка мин равновероятна без возвращения.", "После k безопасных клеток: floor(10000×0.97×C(25,k)/C(25−m,k))/10000; выплата floor(bet×множитель).", "cashout до первого открытия возвращает ставку. Все безопасные открыты — автоматическая выплата.", "Вероятность пережить k клеток: C(25−m,k)/C(25,k); следующая безопасная: (25−m−k)/(25−k).", "Через 24 часа auto-cashout. Максимум при 10 минах: 1585348600."], {"no_reveal_cashout": 1, "edge": .97, "maximum_multiplier": float(mines_multiplier(10, 15))}, {f"first_safe_mines_{m}": (25-m)/25 for m in range(1,11)}),
        "wheel": ("Колесо", "Десять равновероятных секторов", ["Секторы [0,0,0,0.5,0.5,1,1,1.5,2,3], каждый 10%. Максимум 1500."], {str(float(m)): float(m) for m in WHEEL}, {str(float(m)): WHEEL.count(m)/10 for m in WHEEL}),
    }
    result = []
    for game in GAME_IDS:
        title, description, rules, payouts, probabilities = definitions[game]
        if game == "fishing":
            description = "Заброс, подсечка и вываживание с натяжением"
            rules = ["Локальная механика v1: выберите место, подсеките в течение 1.2 секунды после поклёвки, затем управляйте натяжением.",
                     "Удерживайте кнопку для подтягивания; отпускайте для ослабления. Натяжение 100% рвёт леску; слабина в течение секунды позволяет рыбе уйти.",
                     "Подтягивание эффективно при натяжении 28–78%. Доведите прогресс до берега; максимум 30 игровых секунд на ловлю.",
                     "Вид, вес и стоимость скрыты до успешного вываживания. Сервер воспроизводит журнал и только затем сохраняет улов.",
                     "Локальный раунд истекает через 5 минут реального времени. Старые раунды без gameplay_version сохраняют прежний collect.", *rules]
        sport = game in {"darts", "bowling", "basketball", "football"}
        if sport:
            description = {"darts": "Наведи прицел и выбери силу броска", "bowling": "Направь шар в карман между кеглями", "basketball": "Рассчитай дугу и попади в кольцо", "football": "Выбери направление и силу удара"}[game]
            rules = ["Механика v1: прицел и сила управляются локально, сервер воспроизводит тот же бросок.",
                     "Бросок зависит от направления, силы и показанного бокового сноса, а не от случайного ответа после броска.",
                     "Один бросок на раунд; завершите его за 5 минут. Истёкший раунд закрывается без выплаты.",
                     "Шансы не фиксированы: результат зависит от ввода. Баланс и выплату изменяет только сервер.",
                     "Лимит 40 skill-раундов в день Asia/Yekaterinburg суммарно на дартс, боулинг, баскетбол и футбол. Попытка расходуется при старте; это ограничение фарма, не защита от всех ботов.",
                     "Совместимость: старые клиенты без gameplay_version продолжают использовать прежние случайные правила."]
            probabilities = {}
        result.append({"id": game, "fishing_world_version": 1 if game == "fishing" else None, "gameplay_version": 1 if sport or game == "fishing" else None, "rules_version": RULES_VERSION, "title": title, "description": description, "rules": [*common[:2], *rules] if sport else [*common, *rules], "min_bet": 0 if game == "fishing" else 10, "max_bet": 0 if game == "fishing" else 500, "payouts": payouts, "probabilities": probabilities})
    return result
