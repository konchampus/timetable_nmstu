"""Original brandless enterprise theme. Classical economics remain in the engine."""
from copy import deepcopy
from .monopoly_engine import BOARD
THEMED_BOARD=deepcopy(BOARD)
THEMES={
 'brown':('fish',['Рыбная лавка','Карповый пруд']),
 'sky':('clothing',['Ателье','Джинсовая фабрика','Дом моды']),
 'pink':('food',['Пекарня','Кофейня','Ресторан']),
 'orange':('media',['Радиостанция','Киностудия','Медиахолдинг']),
 'red':('technology',['Студия игр','Облачный сервис','Технопарк']),
 'yellow':('fish',['Рыбный порт','Океанская ферма','Морской комбинат']),
 'green':('clothing',['Текстильный завод','Модный квартал','Неделя моды']),
 'blue':('luxury',['Ювелирный дом','Люксовый бутик']),
 'rail':('airport',['Северный аэропорт','Восточный аэропорт','Южный аэропорт','Западный аэропорт']),
 'utility':('energy',['Электростанция','Водоканал'])}
for group,(art,names) in THEMES.items():
    for tile,name in zip([t for t in THEMED_BOARD if t['group']==group],names):
        tile['name']=name;tile['art']='water' if tile['id']==28 else art
