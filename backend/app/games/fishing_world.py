"""Fishing expansion v1. Public pools and fictional lore are not hidden catches.

Location IDs, pools and multipliers are stable across narrative/theme revisions.
Old rounds keep their secret_state unchanged. Cosmetics have no economy effect.
"""
from fractions import Fraction

LOCATIONS = {
    "shore": {
        "title": "Пруд старого карася", "tagline": "Рыбацкие байки · плотва и карась",
        "description": "Тёплый пруд для первых забросов. Чаще встречаются плотва и карась; стоимость улова базовая.",
        "story_title": "Карась, который помнит всех",
        "story": "На этом причале оставляли чайник и спорили о самой большой рыбе. По местной байке, старый карась пережил всех рассказчиков и теперь сам выбирает, чью историю выслушать. Плотва, конечно, перебивает первой.",
        "landmark": "Чайник и старое рыбацкое ведро на берегу",
        "featured_species": ["Плотва", "Карась"],
        "min_rod_level": 1, "value_multiplier": Fraction(1), "weights": None, "theme": "shore",
    },
    "river": {
        "title": "Река рекурсии", "tagline": "Программистская байка · карп и щука",
        "description": "Петляющее русло с камышами. Карп и щука встречаются чаще, чем на пруду; стоимость улова ×1,5.",
        "story_title": "Река, которая вызывает себя",
        "story": "Смотритель-программист поставил у трёх изгибов таблички f(n), f(n−1) и return. Рыбаки шутят, что карп ищет базовый случай, а щука перехватывает всё, что возвращается. Одно здесь точно: каждый заброс новый, улов не зацикливается.",
        "landmark": "Три камня с отметками f(n), f(n−1) и return",
        "featured_species": ["Карп", "Щука"],
        "min_rod_level": 3, "value_multiplier": Fraction(3, 2), "weights": (20, 24, 18, 18, 13, 5, 2), "theme": "river",
    },
    "mountain": {
        "title": "Сомовье озеро", "tagline": "Легенда глубины · сом и карп",
        "description": "Холодное горное озеро с крупной рыбой. Сом встречается чаще, чем в реке; стоимость улова ×2.",
        "story_title": "Тот, кто спит под лодкой",
        "story": "У дальнего берега виден борт затонувшей лодки. Говорят, огромный сом однажды утащил её вместе с запасом наживки и с тех пор охраняет тишину озера. Рыбаки приходят проверить байку, а остаются ради гор и хорошего карпа.",
        "landmark": "Полузатопленная деревянная лодка у скал",
        "featured_species": ["Сом", "Карп"],
        "min_rod_level": 4, "value_multiplier": Fraction(2), "weights": (8, 15, 23, 18, 20, 10, 6), "theme": "mountain",
    },
    "golden": {
        "title": "Золотой коммит", "tagline": "Легенда о коде · золотой карп",
        "description": "Осенняя заводь для максимальной удочки. Плотвы нет, золотой карп встречается чаще всего среди локаций; стоимость улова ×3.",
        "story_title": "Последнее исправление",
        "story": "Кто-то принёс на берег старый терминал, чтобы закончить код в тишине. На экране так и осталось catch(): программист ушёл, а рыбаки нашли другое применение слову. По легенде, золотой карп хранит тот самый коммит. Но даже здесь его ещё нужно поймать.",
        "landmark": "Старый терминал с надписью catch() на берегу",
        "featured_species": ["Золотой карп", "Золотая рыба"],
        "min_rod_level": 5, "value_multiplier": Fraction(3), "weights": (0, 8, 25, 17, 25, 13, 12), "theme": "golden",
    },
}
SKINS = {
    "angler": {"title": "Рыбак", "description": "Классическая удочка без персонажа в кадре.", "min_rod_level": 1},
    "bear": {"title": "Медведь", "description": "Медведь на причале. Только внешний вид, без бонуса к улову.", "min_rod_level": 3},
}


def pool_weights(level: int, location_id: str, shore_weights: tuple) -> tuple:
    location = LOCATIONS[location_id]
    return shore_weights[level - 1] if location["weights"] is None else location["weights"]


def public_world(level: int, fish: tuple, shore_weights: tuple, selected_location: str, selected_skin: str) -> dict:
    locations = []
    for id_, location in LOCATIONS.items():
        preview_level = max(level, location["min_rod_level"])
        weights = pool_weights(preview_level, id_, shore_weights)
        locations.append({"id": id_, "title": location["title"], "description": location["description"],
                          "tagline": location["tagline"], "story_title": location["story_title"],
                          "story": location["story"], "landmark": location["landmark"],
                          "featured_species": list(location["featured_species"]),
                          "min_rod_level": location["min_rod_level"], "unlocked": level >= location["min_rod_level"],
                          "value_multiplier": float(location["value_multiplier"]), "theme": location["theme"],
                          "preview_rod_level": preview_level,
                          "fish": [{"species": item[0], "rarity": item[1],
                                    "value": int(item[2] * location["value_multiplier"]),
                                    "min_weight": item[3] / 1000, "max_weight": item[4] / 1000,
                                    "probability": weights[index] / sum(weights)}
                                   for index, item in enumerate(fish) if weights[index] > 0]})
    return {"world_version": 1, "locations": locations,
            "skins": [{"id": id_, **skin, "unlocked": level >= skin["min_rod_level"]} for id_, skin in SKINS.items()],
            "selected_location": selected_location, "selected_skin": selected_skin,
            "species": [{"name": item[0], "rarity": item[1]} for item in fish]}
