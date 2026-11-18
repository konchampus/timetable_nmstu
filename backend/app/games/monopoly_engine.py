"""Versioned, server-authoritative Monopoly rules. No shared arcade wallet."""
from __future__ import annotations
from copy import deepcopy
from secrets import randbelow, SystemRandom
from fastapi import HTTPException

RULES_VERSION = 2
GROUPS = [([1, 3], 'brown', 50), ([6, 8, 9], 'sky', 50), ([11, 13, 14], 'pink', 100), ([16, 18, 19], 'orange', 100), ([21, 23, 24], 'red', 150), ([26, 27, 29], 'yellow', 150), ([31, 32, 34], 'green', 200), ([37, 39], 'blue', 200)]
NAMES = ['Старт','Рыбная лавка','Казна','Карповый пруд','Подоходный налог','Северный аэропорт','Ателье','Шанс','Джинсовая фабрика','Дом моды','Тюрьма / в гостях','Пекарня','Электростанция','Кофейня','Ресторан','Восточный аэропорт','Радиостанция','Казна','Киностудия','Медиахолдинг','Бесплатная стоянка','Студия игр','Шанс','Облачный сервис','Технопарк','Южный аэропорт','Рыбный порт','Океанская ферма','Водоканал','Морской комбинат','Отправляйтесь в тюрьму','Текстильный завод','Модный квартал','Казна','Неделя моды','Западный аэропорт','Шанс','Ювелирный дом','Налог на роскошь','Люксовый бутик']
PRICES = [60,60,100,100,120,140,140,160,180,180,200,220,220,240,260,260,280,300,300,320,350,400]
RENTS = [[2,10,30,90,160,250],[4,20,60,180,320,450],[6,30,90,270,400,550],[6,30,90,270,400,550],[8,40,100,300,450,600],[10,50,150,450,625,750],[10,50,150,450,625,750],[12,60,180,500,700,900],[14,70,200,550,750,950],[14,70,200,550,750,950],[16,80,220,600,800,1000],[18,90,250,700,875,1050],[18,90,250,700,875,1050],[20,100,300,750,925,1100],[22,110,330,800,975,1150],[22,110,330,800,975,1150],[24,120,360,850,1025,1200],[26,130,390,900,1100,1275],[26,130,390,900,1100,1275],[28,150,450,1000,1200,1400],[35,175,500,1100,1300,1500],[50,200,600,1400,1700,2000]]
BOARD = [dict(id=i, name=n, kind='special', price=0, group='', build=0, rents=[]) for i,n in enumerate(NAMES)]
k = 0
for ids, group, build in GROUPS:
    for i in ids:
        BOARD[i].update(kind='street', price=PRICES[k], group=group, build=build, rents=RENTS[k]); k += 1
for i in [5,15,25,35]: BOARD[i].update(kind='rail', price=200, group='rail')
for i in [12,28]: BOARD[i].update(kind='utility', price=150, group='utility')
for i in [2,17,33]: BOARD[i]['kind']='chest'
for i in [7,22,36]: BOARD[i]['kind']='chance'
for i in [4,38]: BOARD[i]['kind']='tax'

def require(ok, message):
    if not ok: raise HTTPException(409, message)

def log(s, text):
    s['log'] = (s['log'] + [text])[-100:]

def player(s, pid):
    return next((p for p in s['players'] if p['id']==pid), None)

def new_player(pid, name):
    return dict(id=pid, name=name, cash=1500, pos=0, jail=0, jailed=False, cards=[], out=False, ready=False)

def new_state(pid, name, mode="classic", duration_minutes=None):
    require(mode in ["classic", "friendly", "timed20", "timed40", "timed60"], "Неизвестный режим")
    expected=int(mode[5:]) if mode.startswith("timed") else None
    require(duration_minutes is None or type(duration_minutes) is int and duration_minutes==expected, "Длительность не соответствует режиму")
    decks = {}
    for deck in ['chance','chest']:
        cards=list(range(16)); SystemRandom().shuffle(cards); decks[deck]=cards
    return dict(rules_version=RULES_VERSION, mode=mode, duration_minutes=expected, game_deadline=None, turn_number=0, players=[new_player(pid,name)], phase='lobby', turn=pid,
                properties={str(t['id']):dict(owner=None, houses=0, mortgaged=False) for t in BOARD if t['price']},
                dice=[1,1], doubles=0, rolled=False, extra=False, pending=None, auction=None, debt=None,
                trade=None, log=['Комната создана. Пригласите друзей.'], decks=decks, winner=None, bank_queue=[])

def prop(s, i):
    require(str(i) in s['properties'], 'Выберите участок'); return s['properties'][str(i)]

def group_ids(i):
    return [t['id'] for t in BOARD if t['group'] and t['group']==BOARD[i]['group']]

def complete(s, pid, i):
    return all(prop(s,n)['owner']==pid for n in group_ids(i))

def rent(s, i, dice, special=None):
    a=prop(s,i); t=BOARD[i]; owner=a['owner']
    if owner is None or a['mortgaged']: return 0
    count=sum(prop(s,n)['owner']==owner for n in group_ids(i))
    if t['kind']=='rail': return 25*2**(count-1)*(2 if special=='rail' else 1)
    if t['kind']=='utility': return dice*(10 if special=='utility' or count==2 else 4)
    return t['rents'][a['houses']]*(2 if a['houses']==0 and complete(s,owner,i) else 1)

def charge(s, p, amount, creditor=None):
    require(type(amount) is int and amount>=0, 'Некорректная сумма платежа')
    if not amount: return
    require(not s['debt'], 'Сначала погасите долг')
    paid=min(p['cash'], amount); p['cash']-=paid
    if creditor is not None: player(s,creditor)['cash']+=paid
    if paid<amount: s['debt']=dict(player=p['id'], amount=amount-paid, creditor=creditor)

def settle(s):
    debt=s['debt']
    if not debt: return
    p=player(s,debt['player']); paid=min(p['cash'],debt['amount']); p['cash']-=paid; debt['amount']-=paid
    if debt['creditor'] is not None: player(s,debt['creditor'])['cash']+=paid
    if not debt['amount']: s['debt']=None; log(s,'Долг погашен.')

def jail(s,p):
    p.update(pos=10, jailed=True, jail=0); s['extra']=False; s['doubles']=0
    log(s,p['name']+' отправляется в тюрьму.')

def move(s,p,to,salary=True,special=None):
    if salary and to<p['pos']: p['cash']+=200; log(s,p['name']+': +200 за Старт.')
    p['pos']=to; land(s,p,special)

def draw(s,p,deck):
    card=s['decks'][deck].pop(0)
    if card==0:
        p['cards'].append(deck); log(s,'Карта: бесплатный выход из тюрьмы.'); return
    s['decks'][deck].append(card)
    if deck=='chance':
        if card in [1,2,3,4]:
            to={1:0,2:24,3:11,4:39}[card]; log(s,'Шанс: переход на '+NAMES[to]); move(s,p,to); return
        if card==5: jail(s,p); return
        if card==6: log(s,'Шанс: три клетки назад.'); move(s,p,(p['pos']-3)%40,False); return
        if card in [7,8,15]:
            targets=[12,28] if card==8 else [5,15,25,35]
            to=min(targets,key=lambda i:(i-p['pos'])%40)
            if card==8: s['rent_dice']=randbelow(6)+randbelow(6)+2
            log(s,'Шанс: ближайшее предприятие.'); move(s,p,to,special='utility' if card==8 else 'rail'); return
        if card==9:
            cost=sum((100 if a['houses']==5 else 25*a['houses']) for a in s['properties'].values() if a['owner']==p['id'])
            log(s,'Ремонт: '+str(cost)); charge(s,p,cost); return
        if card==10: move(s,p,5); return
        if card==11:
            # Do not credit money before the payer actually pays it.
            s['payments']=[dict(player=p['id'], amount=50, creditor=o['id'])
                           for o in s['players'] if o['id']!=p['id'] and not o['out']]
            log(s,'Шанс: по 50 каждому игроку.'); collect(s); return
        value={12:50,13:150,14:-15}[card]
    else:
        if card==1: move(s,p,0); return
        if card==2: jail(s,p); return
        if card==3:
            value=sum((115 if a['houses']==5 else 40*a['houses']) for a in s['properties'].values() if a['owner']==p['id'])
            log(s,'Ремонт: '+str(value)); charge(s,p,value); return
        if card==4:
            # Collect from each player in sequence; unpaid obligations remain explicit.
            s['collections']=[o['id'] for o in s['players'] if o['id']!=p['id'] and not o['out']]
            s['collector']=p['id']; collect(s); return
        value={5:200,6:-50,7:50,8:100,9:20,10:100,11:-100,12:-50,13:25,14:10,15:100}[card]
    log(s,('Шанс' if deck=='chance' else 'Казна')+': '+('+' if value>0 else '')+str(value))
    if value>0: p['cash']+=value
    else: charge(s,p,-value)

def collect(s):
    """Resume interrupted obligations before allowing another turn or auction."""
    if s['phase'] != 'playing': return
    while s.get('payments') and not s['debt']:
        payment=s['payments'].pop(0)
        payer=player(s,payment['player'])
        recipient=player(s,payment['creditor']) if payment['creditor'] is not None else None
        if payer and not payer['out'] and (payment['creditor'] is None or recipient and not recipient['out']):
            charge(s,payer,payment['amount'],payment['creditor'])
    while s.get('collections') and not s['debt']:
        other=player(s,s['collections'].pop(0)); recipient=player(s,s['collector'])
        if other and not other['out'] and recipient and not recipient['out']:
            charge(s,other,10,s['collector'])
    if not s['debt'] and s.get('jail_move') is not None:
        distance=s.pop('jail_move'); p=player(s,s['turn'])
        if p and not p['out']: move(s,p,(p['pos']+distance)%40)
    if not s['debt'] and not s['auction'] and s['bank_queue']:
        auction(s,s['bank_queue'].pop(0),preserve_pending=True)

def land(s,p,special=None):
    i=p['pos']; t=BOARD[i]; dice=s.pop('rent_dice',sum(s['dice']))
    log(s,p['name']+' → '+t['name'])
    if i==30: jail(s,p)
    elif t['kind'] in ['chance','chest']: draw(s,p,t['kind'])
    elif t['kind']=='tax': charge(s,p,200 if i==4 else 100)
    elif t['price']:
        a=prop(s,i)
        if a['owner'] is None: s['pending']=i
        elif a['owner']!=p['id']:
            amount=rent(s,i,dice,special)
            if s.get('mode')=='friendly':
                from app.games.monopoly_contracts import waived
                if waived(s,a['owner'],p['id'],i): amount=0
            charge(s,p,amount,a['owner']); log(s,'Аренда: '+str(amount))

def building_stock(s,kind):
    if kind=='hotel': return 12-sum(a['houses']==5 for a in s['properties'].values())
    return 32-sum(a['houses'] for a in s['properties'].values() if a['houses']<5)


def building_slots(s,pid,kind):
    return [t['id'] for t in BOARD if t['kind']=='street'
            and prop(s,t['id'])['owner']==pid and complete(s,pid,t['id'])
            and not any(prop(s,n)['mortgaged'] for n in group_ids(t['id']))
            and prop(s,t['id'])['houses']==min(prop(s,n)['houses'] for n in group_ids(t['id']))
            and (prop(s,t['id'])['houses']==4 if kind=='hotel' else prop(s,t['id'])['houses']<4)]


def start_build_auction(s,p,tile):
    require(not s['auction'] and not s['debt'], 'Сначала завершите аукцион или долг')
    require(type(tile) is int and str(tile) in s['properties'], 'Выберите участок')
    kind='hotel' if prop(s,tile)['houses']==4 else 'house'
    require(tile in building_slots(s,p['id'],kind), 'Нет права строить на этом участке')
    require(building_stock(s,kind)==1, 'Аукцион нужен для последнего дома или отеля')
    placements={o['id']:building_slots(s,o['id'],kind) for o in s['players'] if not o['out'] and o['cash']>=10}
    placements={pid:ids for pid,ids in placements.items() if ids}
    require(len(placements)>1 and p['id'] in placements, 'Нужны минимум два претендента с 10')
    s['auction']=dict(kind='building',building=kind,tile=tile,bid=0,bidder=None,passed=[],actor=p['id'],
                      placements=placements,selected={p['id']:tile})
    log(s,'Аукцион последнего здания: '+('отель' if kind=='hotel' else 'дом'))


def auction(s,i,preserve_pending=False):
    s['auction']=dict(tile=i, bid=0, bidder=None, passed=[], actor=next(p['id'] for p in s['players'] if not p['out']))
    if not preserve_pending: s['pending']=None
    log(s,'Аукцион: '+NAMES[i])

def advance_auction(s):
    a=s['auction']; eligible=[p['id'] for p in s['players'] if not p['out'] and p['id'] not in a['passed']
                            and (a.get('kind')!='building' or p['id'] in a['placements'])]
    challengers=[pid for pid in eligible if pid!=a['bidder']]
    if not challengers:
        if a['bidder'] is not None:
            p=player(s,a['bidder'])
            require(p and not p['out'] and p['cash']>=a['bid'], 'Ставка больше не обеспечена')
            if a.get('kind')=='building':
                placement=a['selected'][p['id']]
                require(placement in building_slots(s,p['id'],a['building']) and building_stock(s,a['building'])>0, 'Здание или участок больше недоступны')
                prop(s,placement)['houses']+=1
            else: prop(s,a['tile'])['owner']=p['id']
            p['cash']-=a['bid']; log(s,p['name']+' выигрывает аукцион: '+str(a['bid']))
        s['auction']=None
        if s['bank_queue']: auction(s,s['bank_queue'].pop(0),preserve_pending=True)
        return
    ids=[p['id'] for p in s['players']]; start=ids.index(a['actor'])
    a['actor']=next(ids[(start+j)%len(ids)] for j in range(1,len(ids)+1) if ids[(start+j)%len(ids)] in challengers)

def next_turn(s):
    alive=[p for p in s['players'] if not p['out']]
    if len(alive)<=1:
        s.update(phase='finished',winner=alive[0]['id'] if alive else None,auction=None,pending=None,trade=None,debt=None,bank_queue=[])
        for key in ['payments','collections','collector','jail_move','rent_dice']: s.pop(key,None)
        return
    ids=[p['id'] for p in s['players']]; start=ids.index(s['turn'])
    s['turn_number']=s.get('turn_number',0)+1
    s['turn']=next(ids[(start+j)%len(ids)] for j in range(1,len(ids)+1) if not player(s,ids[(start+j)%len(ids)])['out'])
    s.update(rolled=False,doubles=0,extra=False,trade=None)

def bankrupt(s,p):
    debt=s['debt']; creditor=debt['creditor'] if debt and debt['player']==p['id'] else None
    if creditor is not None: player(s,creditor)['cash']+=p['cash']
    p['cash']=0; p['out']=True
    for deck in p['cards']:
        if creditor is not None: player(s,creditor)['cards'].append(deck)
        else: s['decks'][deck].append(0)
    p['cards']=[]
    inherited_interest=0
    for key,a in s['properties'].items():
        if a['owner']!=p['id']: continue
        if creditor is not None:
            player(s,creditor)['cash']+=a['houses']*BOARD[int(key)]['build']//2 if a['houses']<5 else BOARD[int(key)]['build']*5//2
            a['houses']=0; a['owner']=creditor
            if a['mortgaged']: inherited_interest+=(BOARD[int(key)]['price']//2+9)//10
        else:
            a.update(owner=None,houses=0,mortgaged=False); s['bank_queue'].append(int(key))
    if debt and debt['player']==p['id']: s['debt']=None
    if inherited_interest: charge(s,player(s,creditor),inherited_interest)
    log(s,p['name']+' объявлен банкротом.'); s['trade']=None
    if sum(not o['out'] for o in s['players'])<=1: next_turn(s); return
    if s['turn']==p['id']:
        s['pending']=None; s.pop('jail_move',None); next_turn(s)
    collect(s)

def start(s):
    """C1009: highest one-die roll starts; only tied leaders reroll."""
    contenders=[p['id'] for p in s['players'] if not p['out']]
    history=[]
    while len(contenders)>1:
        rolls=[dict(player=pid,die=randbelow(6)+1) for pid in contenders]
        history.append(rolls); best=max(r['die'] for r in rolls)
        contenders=[r['player'] for r in rolls if r['die']==best]
    s.update(phase='playing',turn=contenders[0],starter_rolls=history,turn_number=0)
    log(s,'Начинает '+player(s,s['turn'])['name']+' — старший стартовый бросок.')


def net_worth(s,pid):
    p=player(s,pid)
    return p['cash']+sum((BOARD[int(i)]['price']//(2 if a['mortgaged'] else 1))+a['houses']*BOARD[int(i)]['build']
                         for i,a in s['properties'].items() if a['owner']==pid)


def finish_timed(s,clock):
    """House preset: expiry never destroys an unsettled debt/auction/card chain."""
    from datetime import datetime
    if s['phase']!='playing' or not s.get('game_deadline'): return False
    if clock<datetime.fromisoformat(s['game_deadline']): return False
    s['time_expired']=True
    if s['debt'] or s['auction'] or s['pending'] is not None or s.get('bank_queue') or s.get('payments') or s.get('collections') or s.get('jail_move') is not None: return False
    scores={p['id']:net_worth(s,p['id']) for p in s['players'] if not p['out']}
    best=max(scores.values(),default=0); winners=[pid for pid,v in scores.items() if v==best]
    s.update(phase='finished',scores=scores,winners=winners,winner=winners[0] if len(winners)==1 else None,
             finish_reason='time_limit',trade=None,contract_offer=None)
    log(s,'Время партии истекло. Итог по стоимости активов; равенство — ничья.')
    return True


def surrender(s,p):
    """Online departure policy, distinct from insolvency: no chosen beneficiary."""
    pid=p['id']; a=s.get('auction')
    if s['debt'] and s['debt']['creditor']==pid:
        s['debt']['creditor']=None
    for payment in s.get('payments',[]):
        if payment['creditor']==pid: payment['creditor']=None
    if s.get('collector')==pid:
        s['collections']=[]; s.pop('collector',None)
    if s['turn']==pid and s['pending'] is not None:
        s['bank_queue'].append(s['pending']); s['pending']=None
    if a:
        if a['bidder']==pid:
            a.update(bid=0,bidder=None,passed=[])
            log(s,'Лидер торгов сдался: ставка отменена, аукцион начинается заново.')
        if pid not in a['passed']: a['passed'].append(pid)
    bankrupt(s,p)
    p['surrendered']=True
    if s['phase']=='playing' and a and s['auction'] is a:
        # Restart at the next surviving participant; never award to an out bidder.
        a['actor']=pid; advance_auction(s)
    collect(s)


def trade_action(s,p,action,target,give,take,cash,ask,give_cards,take_cards,redeem_give,redeem_take):
    pid=p['id']
    if action in ['cancel_trade','reject_trade']:
        tr=s['trade']; require(tr and pid==(tr['from'] if action=='cancel_trade' else tr['target']), 'Предложение недоступно')
        s['trade']=None; return
    if action=='trade':
        require(not s['trade'], 'Уже есть предложение обмена')
        other=player(s,target); require(other and not other['out'] and target!=pid, 'Выберите другого игрока')
        require(all(ids is None or isinstance(ids,(list,tuple)) and all(type(i) is int and 0<=i<40 for i in ids)
                    for ids in [give,take,redeem_give,redeem_take]), 'Некорректные участки обмена')
        require(all(cards is None or isinstance(cards,(list,tuple)) and all(c in ['chance','chest'] for c in cards)
                    and len(set(cards))==len(cards) for cards in [give_cards,take_cards]), 'Некорректные карты выхода')
        tr=dict(target=target,**{'from':pid},give=list(dict.fromkeys(give or [])),take=list(dict.fromkeys(take or [])),
                cash=cash,ask=ask,give_cards=list(give_cards or []),take_cards=list(take_cards or []),
                redeem_give=list(dict.fromkeys(redeem_give or [])),redeem_take=list(dict.fromkeys(redeem_take or [])))
        require(any(tr[k] for k in ['give','take','cash','ask','give_cards','take_cards']), 'Пустой обмен')
    else:
        tr=s['trade']; require(tr and tr['target']==pid, 'Предложение уже недоступно')
    a=player(s,tr['from']); b=player(s,tr['target'])
    require(a and b and not a['out'] and not b['out'], 'Участник выбыл')
    require(type(tr['cash']) is int and type(tr['ask']) is int and min(tr['cash'],tr['ask'])>=0, 'Некорректная сумма')
    costs={a['id']:0,b['id']:0}
    for ids,owner,recipient,cards,redeems in [
        (tr['give'],a,b,tr.get('give_cards',[]),tr.get('redeem_give',[])),
        (tr['take'],b,a,tr.get('take_cards',[]),tr.get('redeem_take',[]))]:
        require(set(redeems)<=set(ids), 'Выкупать можно только получаемый заложенный участок')
        for card in cards: require(card in owner['cards'], 'Карта выхода больше не принадлежит участнику')
        for i in ids:
            asset=prop(s,i)
            require(asset['owner']==owner['id'] and not any(prop(s,n)['houses'] for n in group_ids(i)), 'Состав собственности изменился или в группе есть здания')
            require(i not in redeems or asset['mortgaged'], 'Участок уже не заложен')
            if asset['mortgaged']:
                principal=BOARD[i]['price']//2
                costs[recipient['id']]+=(principal+9)//10+(principal if i in redeems else 0)
    # Exchange is simultaneous, so incoming cash may fund the bank interest; no credit is created.
    balances={a['id']:a['cash']+tr['ask']-tr['cash']-costs[a['id']],
              b['id']:b['cash']+tr['cash']-tr['ask']-costs[b['id']]}
    require(a['cash']>=tr['cash'] and b['cash']>=tr['ask'] and min(balances.values())>=0, 'Недостаточно денег для обмена и процентов банку')
    if action=='trade': s['trade']=tr; return
    a['cash']=balances[a['id']]; b['cash']=balances[b['id']]
    for ids,owner,recipient,cards,redeems in [
        (tr['give'],a,b,tr.get('give_cards',[]),tr.get('redeem_give',[])),
        (tr['take'],b,a,tr.get('take_cards',[]),tr.get('redeem_take',[]))]:
        for i in ids:
            prop(s,i)['owner']=recipient['id']
            if i in redeems: prop(s,i)['mortgaged']=False
        for card in cards: owner['cards'].remove(card); recipient['cards'].append(card)
    s['trade']=None; log(s,'Обмен принят: '+a['name']+' и '+b['name'])
    settle(s); collect(s)


def _act(original, pid, action, tile=None, amount=0, target=None, give=None, take=None, cash=0, ask=0,
        give_cards=None, take_cards=None, redeem_give=None, redeem_take=None,
        contract_tiles=None, contract_turns=1, contract_fee=0):
    s=deepcopy(original); p=player(s,pid)
    require(p is not None and not p['out'], 'Вы не участвуете в партии')
    if s['phase']=='lobby':
        require(action=='ready', 'Партия ещё не началась'); p['ready']=not p['ready']; return s
    require(s['phase']=='playing', 'Партия завершена')
    if action=='resign':
        surrender(s,p); return s
    if s['auction']:
        a=s['auction']; require(pid==a['actor'], 'Сейчас очередь другого участника аукциона')
        require(action in ['bid','pass'], 'Завершите аукцион')
        if action=='bid':
            if a.get('kind')=='building':
                placement=tile if tile is not None else a.get('selected',{}).get(pid,a['placements'][pid][0])
                require(amount>=10 and placement in building_slots(s,pid,a['building']), 'Минимум 10 и доступный участок под здание')
                a['selected'][pid]=placement
            require(type(amount) is int and a['bid']<amount<=p['cash'], 'Ставка должна превышать текущую и быть по средствам')
            a.update(bid=amount,bidder=pid)
        else: a['passed'].append(pid)
        advance_auction(s); return s
    if action=='start_build_auction':
        start_build_auction(s,p,tile); return s
    debtor=s['debt']['player'] if s['debt'] else None
    if action=='bankrupt':
        require(debtor==pid, 'Нет непогашенного долга')
        liquidity=p['cash']+sum(a['houses']*BOARD[int(i)]['build']//2+(0 if a['mortgaged'] else BOARD[int(i)]['price']//2)
                               for i,a in s['properties'].items() if a['owner']==pid)
        require(liquidity<s['debt']['amount'], 'Можно погасить долг: продайте здания и заложите участки; для добровольного выхода используйте «Сдаться»')
        bankrupt(s,p); return s
    if action in ['trade','accept_trade','reject_trade','cancel_trade']:
        trade_action(s,p,action,target,give,take,cash,ask,give_cards,take_cards,redeem_give,redeem_take)
        return s
    if action in ['propose_contract','accept_contract','reject_contract','cancel_contract']:
        from app.games import monopoly_contracts as contracts
        if action=='propose_contract': contracts.propose(s,pid,target,contract_tiles,contract_turns,contract_fee)
        elif action=='cancel_contract': contracts.cancel(s,pid)
        else: contracts.respond(s,pid,action=='accept_contract')
        return s
    if action in ['build','sell','sell_group','mortgage','redeem']:
        require(tile is not None and type(tile) is int and 0<=tile<40, 'Выберите участок')
        a=prop(s,tile); t=BOARD[tile]; ids=group_ids(tile)
        require(a['owner']==pid, 'Это не ваша собственность')
        if action=='build':
            require(not s['debt'] and t['kind']=='street' and complete(s,pid,tile) and not any(prop(s,n)['mortgaged'] for n in ids), 'Нужна полная незаложенная цветовая группа без долга')
            require(a['houses']<5 and a['houses']==min(prop(s,n)['houses'] for n in ids), 'Застраивайте группу равномерно')
            houses=sum(v['houses'] for v in s['properties'].values() if v['houses']<5); hotels=sum(v['houses']==5 for v in s['properties'].values())
            require((a['houses']==4 and hotels<12) or (a['houses']<4 and houses<32), 'В банке закончились здания')
            kind='hotel' if a['houses']==4 else 'house'
            competitors=[o for o in s['players'] if not o['out'] and o['cash']>=10 and building_slots(s,o['id'],kind)]
            require(building_stock(s,kind)!=1 or len(competitors)<=1, 'На последнее здание есть другие претенденты: начните аукцион здания')
            require(p['cash']>=t['build'], 'Не хватает денег'); p['cash']-=t['build']; a['houses']+=1
        elif action=='sell_group':
            require(t['kind']=='street' and all(prop(s,n)['owner']==pid for n in ids) and any(prop(s,n)['houses'] for n in ids), 'Нужна своя группа со зданиями')
            for n in ids:
                asset=prop(s,n); p['cash']+=asset['houses']*BOARD[n]['build']//2; asset['houses']=0
        elif action=='sell':
            require(a['houses']>0 and a['houses']==max(prop(s,n)['houses'] for n in ids), 'Продавайте здания равномерно')
            if a['houses']==5: require(sum(v['houses'] for v in s['properties'].values() if v['houses']<5)<=28, 'Для размена отеля в банке нужны четыре дома')
            a['houses']-=1; p['cash']+=t['build']//2
        elif action=='mortgage':
            require(not a['mortgaged'] and not any(prop(s,n)['houses'] for n in ids), 'Сначала продайте здания всей группы')
            a['mortgaged']=True; p['cash']+=t['price']//2
        else:
            cost=(t['price']//2*110+99)//100
            require(not s['debt'] and a['mortgaged'] and p['cash']>=cost, 'Нужна сумма залога + 10% без долга')
            a['mortgaged']=False; p['cash']-=cost
        s['trade']=None; log(s,p['name']+': '+{'build':'постройка','sell':'продажа здания','sell_group':'продажа зданий группы','mortgage':'залог','redeem':'выкуп'}[action]+' — '+t['name']); settle(s); collect(s); return s
    require(not s['debt'], 'Продайте здания, заложите участки или объявите банкротство')
    require(pid==s['turn'], 'Дождитесь своего хода')
    if action in ['buy','auction']:
        require(s['pending'] is not None, 'Нет участка для покупки'); i=s['pending']
        if action=='auction': auction(s,i)
        else:
            require(p['cash']>=BOARD[i]['price'], 'Не хватает денег — отправьте участок на аукцион')
            p['cash']-=BOARD[i]['price']; prop(s,i)['owner']=pid; s['pending']=None; log(s,p['name']+' покупает '+NAMES[i])
        return s
    require(s['pending'] is None, 'Купите участок или начните аукцион')
    if action in ['bail','jail_card']:
        require(p['jailed'] and not s['rolled'], 'Выход из тюрьмы выбирается перед броском')
        if action=='bail': require(p['cash']>=50,'Не хватает 50'); p['cash']-=50
        else:
            require(p['cards'], 'У вас нет карты'); s['decks'][p['cards'].pop(0)].append(0)
        p.update(jailed=False,jail=0); return s
    if action=='roll':
        require(not s['rolled'], 'Кости уже брошены')
        s['roll_sequence']=s.get('roll_sequence',0)+1; s['dice']=[randbelow(6)+1,randbelow(6)+1]; double=s['dice'][0]==s['dice'][1]; s['rolled']=True; s['extra']=False
        log(s,p['name']+': '+str(s['dice'][0])+' + '+str(s['dice'][1]))
        if p['jailed']:
            p['jail']+=1
            if double: p.update(jailed=False,jail=0)
            elif p['jail']<3: return s
            else:
                charge(s,p,50); p.update(jailed=False,jail=0)
                if s['debt']: s['jail_move']=sum(s['dice']); return s
        else:
            s['doubles']=s['doubles']+1 if double else 0; s['extra']=double
            if s['doubles']==3: jail(s,p); return s
        move(s,p,(p['pos']+sum(s['dice']))%40); return s
    if action=='end':
        require(s['rolled'], 'Сначала бросьте кости')
        if s['extra'] and not p['jailed']: s.update(rolled=False,extra=False)
        else: next_turn(s)
        return s
    raise HTTPException(422,'Неизвестное действие')


def act(original, pid, action, **kwargs):
    s=_act(original,pid,action,**kwargs)
    if s.get('contracts') or s.get('contract_offer'):
        from app.games.monopoly_contracts import cleanup
        cleanup(s)
    return s
