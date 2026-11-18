"""Authenticated durable multiplayer aggregate. Polling works across API workers."""
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
from secrets import token_hex
from typing import Annotated, Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ConfigDict, StrictInt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.models import User
from app.security import current_user, lock_authenticated_user, now, rate_limit
from .monopoly_models import MonopolyRoom as Room, MonopolyMember as Member, MonopolyCommand as Command, MonopolyMessage as Message
from . import monopoly_engine as rules
from .monopoly_theme import THEMED_BOARD
from .monopoly_events import poll_events

router=APIRouter(prefix='/monopoly', tags=['monopoly'])
Session=Annotated[AsyncSession, Depends(get_session)]
Principal=Annotated[User, Depends(current_user)]
COLORS=['#2254ff','#d54757','#16876a','#b36b13','#8556bd','#087e9b']
class CommandBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    key: UUID
    version: int=Field(default=1,ge=1,strict=True)
    action: Literal['create','join','ready','start','leave','color','roll','end','buy','auction','bid','pass','build','start_build_auction','sell','sell_group','mortgage','redeem','bail','jail_card','trade','accept_trade','reject_trade','cancel_trade','bankrupt','resign','timeout','chat','propose_contract','accept_contract','reject_contract','cancel_contract']
    title: str=Field(default='Игра с друзьями',min_length=1,max_length=60)
    nickname: str=Field(default='Игрок',min_length=1,max_length=30)
    use_telegram_name: bool=Field(default=False,strict=True)
    mode: Literal['classic','friendly','timed20','timed40','timed60']='classic'
    duration_minutes: StrictInt | None=None
    give_cards: list[Literal['chance','chest']]=Field(default_factory=list,max_length=2)
    take_cards: list[Literal['chance','chest']]=Field(default_factory=list,max_length=2)
    redeem_give: list[StrictInt]=Field(default_factory=list,max_length=28)
    redeem_take: list[StrictInt]=Field(default_factory=list,max_length=28)
    contract_tiles: list[StrictInt]=Field(default_factory=list,max_length=28)
    contract_turns: int=Field(default=1,ge=1,le=12,strict=True)
    contract_fee: int=Field(default=0,ge=0,le=1000000,strict=True)
    public: bool=False
    capacity: int=Field(default=4,ge=2,le=6)
    code: str=Field(default='',max_length=24,pattern=r'^[a-fA-F0-9]*$')
    tile: int | None=Field(default=None,ge=0,le=39,strict=True)
    amount: int=Field(default=0,ge=0,le=1000000,strict=True)
    target: str | None=Field(default=None,max_length=36)
    give: list[StrictInt]=Field(default_factory=list,max_length=28)
    take: list[StrictInt]=Field(default_factory=list,max_length=28)
    cash: int=Field(default=0,ge=0,le=1000000,strict=True)
    ask: int=Field(default=0,ge=0,le=1000000,strict=True)
    color: str=Field(default=COLORS[0],max_length=7)
    text: str=Field(default='',max_length=500)

def entry_name(body, user):
    # User.name comes from verified Telegram initData, never initDataUnsafe or contacts.
    raw=getattr(user,'name','') if body.use_telegram_name else body.nickname
    name=' '.join(raw.split())[:30] if isinstance(raw,str) else ''
    return name or 'Игрок'

def summary(r):
    return dict(id=str(r.id),title=r.title,public=r.public,capacity=r.capacity,status=r.status,
                count=len(r.state['players']),version=r.version,mode=r.state.get('mode','classic'),duration_minutes=r.state.get('duration_minutes'))

def snapshot(r, member):
    state=deepcopy(r.state); state.pop('decks',None)
    state.setdefault('mode','classic'); state.setdefault('duration_minutes',None);state.setdefault('game_deadline',None);state.setdefault('turn_number',0)
    from .monopoly_contracts import public
    state.update(public(state))
    return dict(**summary(r),event_version=r.event_version,code=r.code,host=r.host,you=str(member.id),state=state,
                deadline=state.get('game_deadline') if state['phase']=='playing' else None,server_now=now().isoformat())

async def membership(db, room, user):
    return (await db.execute(select(Member).where(Member.room_id==room.id, Member.user_id==user.id,
                                                 Member.generation==user.account_generation))).scalar_one_or_none()

async def authenticated_room(db, rid, user, member_required=True):
    r=(await db.execute(select(Room).where(Room.id==rid).with_for_update())).scalar_one_or_none()
    if not r: raise HTTPException(404,'Комната не найдена')
    m=await membership(db,r,user)
    if member_required and not m: raise HTTPException(403,'Войдите в комнату по приглашению')
    return r,m

async def replay(db,user,fingerprint,key):
    previous=(await db.execute(select(Command).where(Command.user_id==user.id,Command.key==str(key)))).scalar_one_or_none()
    if previous:
        if previous.fingerprint!=fingerprint: raise HTTPException(409,'Ключ уже использован для другого действия')
        return previous.response
    return None

def journal(db,user,body,fingerprint,response):
    db.add(Command(user_id=user.id,key=str(body.key),fingerprint=fingerprint,response=response))

def fingerprint(body,path):
    data=body.model_dump(mode='json')
    # Preserve fingerprints of durable v1 commands when all v2 extensions are defaults.
    defaults=dict(use_telegram_name=False,mode='classic',duration_minutes=None,give_cards=[],take_cards=[],redeem_give=[],redeem_take=[],
                  contract_tiles=[],contract_turns=1,contract_fee=0)
    for key,value in defaults.items():
        if data.get(key)==value: data.pop(key,None)
    return sha256((path+json.dumps(data,sort_keys=True,ensure_ascii=False)).encode()).hexdigest()

async def require_room_slot(db, user):
    active=(await db.execute(select(func.count()).select_from(Member).join(Room).where(
        Member.user_id==user.id, Member.generation==user.account_generation,
        Room.status.in_(['lobby','playing'])))).scalar_one()
    rules.require(active<8,'Не более 8 активных комнат')


def decision_key(s):
    """Identity of a timed decision, not every incidental state mutation.

    Asset management / partial debt payments do not buy extra decision time.
    Auction bids change the actual offer, so a new highest bid gets a deadline.
    """
    if s['phase']!='playing': return None
    if s.get('auction'):
        a=s['auction']
        return ('auction',a['tile'],a['actor'],a['bid'],a.get('bidder'))
    if s.get('debt'):
        d=s['debt']
        return ('debt',d['player'],d.get('creditor'))
    if s.get('trade'):
        tr=s['trade']
        return ('trade',tr['from'],tr['target'])
    if s.get('pending') is not None: return ('buy',s['turn'],s['pending'])
    p=rules.player(s,s['turn'])
    return ('turn',s['turn'],'end' if s['rolled'] else 'roll',bool(p and p.get('jailed')))


def turn_due(s, clock):
    """Classic/friendly have no per-decision or per-turn forfeiture."""
    return None


def update_deadlines(room, s, previous_turn, before_decision, clock):
    s.pop('turn_started_at',None); s.pop('turn_due',None)
    room.deadline=datetime.fromisoformat(s['game_deadline']) if s['phase']=='playing' and s.get('game_deadline') else None


MODES=[dict(id='classic',name='Классика',duration_minutes=None,house_rules=False,description='До последнего участника. Без лимита времени и автоматического банкротства.'),
       dict(id='friendly',name='Дружеская',duration_minutes=None,house_rules=True,description='Классическая экономика плюс временные освобождения от аренды. Домашний режим.'),
       *[dict(id=f'timed{n}',name=f'{n} минут',duration_minutes=n,house_rules=True,description='Домашний пресет: выигрывает богатейший; долги и аукционы сначала разрешаются.') for n in [20,40,60]]]
RULES_SYNOPSIS=[
    'Старт: 1500 каждому; старший бросок одного кубика определяет первого игрока; равенство перебрасывается.',
    'Проход или остановка на Старте: +200. Бесплатная стоянка без выплаты.',
    'Не покупаете свободный участок — обязательный аукцион, участвовать может и отказавшийся.',
    'Дома и сделки доступны вне своего хода и в тюрьме. Стройте и продавайте равномерно; залог в группе запрещает строительство.',
    'В банке 32 дома и 12 отелей. Последнее здание при конкуренции продаётся через аукцион. Для размена отеля нужны 4 дома; можно продать все здания группы.',
    'Обмен: деньги, участки без зданий во всей группе, карты выхода Шанс/Казна. Всё одновременно, без будущих долгов.',
    'Получатель залога сразу платит 10% банку или залог + 10% для выкупа; поздний выкуп требует ещё 10%.',
    'Заложенный участок не приносит аренду, остальные участки полного комплекта сохраняют повышенную аренду.',
    'Три дубля подряд — тюрьма. Тюремный дубль не даёт дополнительного броска; после третьей неудачи штраф 50.',
    'Займы и обязательства не брать аренду запрещены в классике. Friendly-договорённости — отдельные домашние правила.',
    'Сдаться можно в любой момент: кредитору по текущему долгу, иначе активы банку на аукционы; друга выбрать нельзя.',
    'Закрытие окна не сдача. В классике нет принудительного банкротства по таймеру.'
]


@router.get('/board')
async def board(user:Principal):
    return dict(tiles=THEMED_BOARD,colors=COLORS,rules_version=rules.RULES_VERSION,modes=MODES,rules_synopsis=RULES_SYNOPSIS,
                config=dict(starting_cash=1500,go_salary=200,houses=32,hotels=12,mortgage_interest_percent=10,
                            forced_timeouts=False,timed_valuation='cash + deed value (mortgaged half) + building purchase cost',
                            source='Hasbro C1009 F22, 0622C1009780; timed presets and friendly agreements are house rules',
                            limitations=['Аренда взыскивается автоматически','Ставки аукциона по очереди','Аукцион последнего здания запускается явно; участвуют все с подходящими участками']))

@router.get('/rooms')
async def rooms(user:Principal,db:Session):
    async with db.begin():
        await lock_authenticated_user(db,user)
        mine=select(Member.room_id).where(Member.user_id==user.id,Member.generation==user.account_generation)
        mine_ids=set((await db.execute(mine)).scalars().all())
        owned=(await db.execute(select(Room).where(Room.id.in_(mine_ids)).order_by(Room.updated_at.desc(),Room.id))).scalars().all()
        public=(await db.execute(select(Room).where(Room.public.is_(True),Room.status=='lobby',Room.updated_at>now()-timedelta(days=1),Room.id.not_in(mine_ids)).order_by(Room.updated_at.desc(),Room.id).limit(50))).scalars().all()
        return dict(items=[dict(**summary(r),mine=r.id in mine_ids) for r in [*owned,*public]])

@router.post('/rooms')
async def enter(body:CommandBody,user:Principal,db:Session):
    await rate_limit(str(user.id),'monopoly-enter',20)
    fp=fingerprint(body,'rooms')
    async with db.begin():
        await lock_authenticated_user(db,user)
        old=await replay(db,user,fp,body.key)
        if old: return old
        rules.require(body.action in ['create','join'],'Ожидалось создание или вход')
        if body.action=='create':
            await require_room_slot(db,user)
            mid=uuid4(); name=entry_name(body,user)
            state=rules.new_state(str(mid),name,body.mode,body.duration_minutes); state['players'][0]['color']=body.color if body.color in COLORS else COLORS[0]
            r=Room(id=uuid4(),code=token_hex(10),title=body.title.strip() or 'Игра с друзьями',host=str(mid),public=body.public,capacity=body.capacity,version=1,event_version=1,status='lobby',state=state,updated_at=now())
            db.add(r); await db.flush()
            m=Member(id=mid,room_id=r.id,user_id=user.id,generation=user.account_generation);db.add(m)
        else:
            r=(await db.execute(select(Room).where(Room.code==body.code.lower()).with_for_update())).scalar_one_or_none()
            if not r: raise HTTPException(404,'Проверьте код комнаты')
            m=await membership(db,r,user)
            if not m:
                await require_room_slot(db,user)
                rules.require(r.status=='lobby' and len(r.state['players'])<r.capacity,'Партия уже началась или комната заполнена')
                mid=uuid4(); m=Member(id=mid,room_id=r.id,user_id=user.id,generation=user.account_generation);db.add(m)
                s=deepcopy(r.state); p=rules.new_player(str(mid),entry_name(body,user))
                used={o.get('color') for o in s['players']}; p['color']=next(c for c in COLORS if c not in used);s['players'].append(p)
                rules.log(s,p['name']+' присоединился.');r.state=s;r.version+=1;r.event_version+=1;r.updated_at=now()
        result=snapshot(r,m);journal(db,user,body,fp,result);return result

@router.post('/rooms/{rid}/join')
async def join_public(rid:UUID,body:CommandBody,user:Principal,db:Session):
    # Public ids are discoverable; private rooms require the high-entropy code.
    await rate_limit(str(user.id),'monopoly-enter',20)
    fp=fingerprint(body,str(rid)+'/join')
    async with db.begin():
        await lock_authenticated_user(db,user)
        old=await replay(db,user,fp,body.key)
        if old:return old
        r,m=await authenticated_room(db,rid,user,False)
        if not m:
            rules.require(r.public and r.status=='lobby' and len(r.state['players'])<r.capacity,'Комната закрыта')
            await require_room_slot(db,user)
            m=Member(id=uuid4(),room_id=r.id,user_id=user.id,generation=user.account_generation);db.add(m)
            s=deepcopy(r.state);p=rules.new_player(str(m.id),entry_name(body,user));used={o.get('color') for o in s['players']};p['color']=next(c for c in COLORS if c not in used);s['players'].append(p);r.state=s;r.version+=1;r.event_version+=1;r.updated_at=now()
        result=snapshot(r,m);journal(db,user,body,fp,result);return result

@router.get('/rooms/{rid}/events')
async def events(rid:UUID,request:Request,user:Principal,cursor:Annotated[int,Query(ge=0)]):
    return await poll_events(rid,user,cursor,request)


@router.get('/rooms/{rid}')
async def room(rid:UUID,user:Principal,db:Session):
    async with db.begin():
        await lock_authenticated_user(db,user);r,m=await authenticated_room(db,rid,user)
        messages=(await db.execute(select(Message).where(Message.room_id==rid).order_by(Message.created_at.desc(),Message.id.desc()).limit(80))).scalars().all()
        return dict(**snapshot(r,m),messages=[dict(id=str(v.id),player=str(v.member_id),text=v.text,at=v.created_at.isoformat()) for v in reversed(messages)])

@router.post('/rooms/{rid}/actions')
async def command(rid:UUID,body:CommandBody,user:Principal,db:Session):
    await rate_limit(str(user.id),'monopoly-actions',90)
    fp=fingerprint(body,str(rid))
    async with db.begin():
        await lock_authenticated_user(db,user)
        old=await replay(db,user,fp,body.key)
        if old:return old
        r,m=await authenticated_room(db,rid,user);pid=str(m.id);s=deepcopy(r.state)
        before_decision=decision_key(s)
        if body.action=='chat':
            text=body.text.strip();rules.require(bool(text),'Введите сообщение')
            last=(await db.execute(select(Message.created_at).where(Message.member_id==m.id).order_by(Message.created_at.desc()).limit(1))).scalar_one_or_none()
            rules.require(not last or (now()-last).total_seconds()>=1,'Подождите секунду перед следующим сообщением')
            db.add(Message(room_id=rid,member_id=m.id,text=text,created_at=now()))
            r.event_version+=1;r.updated_at=now()
            result=snapshot(r,m);journal(db,user,body,fp,result);return result
        clock=now();previous_turn=s['turn']
        rules.require(body.version==r.version,'Состояние изменилось. Обновите комнату и повторите действие.')
        if body.action=='leave':
            rules.require(r.status=='lobby','Закрытие окна не сдача. Во время партии используйте отдельное действие «Сдаться»')
            s['players']=[p for p in s['players'] if p['id']!=pid]
            await db.delete(m)
            if not s['players']:s['phase']='finished'
            elif r.host==pid:r.host=s['players'][0]['id'];s['turn']=r.host
        elif body.action=='start':
            rules.require(pid==r.host and r.status=='lobby','Начать может только создатель комнаты')
            rules.require(len(s['players'])>=2 and all(p['ready'] for p in s['players']),'Нужно минимум двое готовых игроков')
            rules.start(s)
            if s.get('duration_minutes'): s['game_deadline']=(clock+timedelta(minutes=s['duration_minutes'])).isoformat()
            rules.log(s,'Партия началась. У каждого 1500. За Старт — 200.')
        elif body.action=='color':
            rules.require(r.status=='lobby' and body.color in COLORS,'Цвет выбирается в комнате ожидания')
            rules.require(not any(p['id']!=pid and p.get('color')==body.color for p in s['players']),'Этот цвет уже занят')
            rules.player(s,pid)['color']=body.color
        elif body.action=='timeout':
            rules.require(s.get('game_deadline') and clock>=datetime.fromisoformat(s['game_deadline']), 'В этом режиме нет истёкшего таймера партии')
            rules.require(rules.finish_timed(s,clock), 'Сначала разрешите долг, покупку или аукцион; автоматического банкротства нет')
        else:
            finished=rules.finish_timed(s,clock)
            if not finished:
                if s.get('time_expired'):
                    rules.require(body.action in ['sell','sell_group','mortgage','trade','accept_trade','reject_trade','cancel_trade','bankrupt','resign','bid','pass','buy','auction'], 'Время истекло: сначала разрешите незавершённые обязательства')
                s=rules.act(s,pid,body.action,tile=body.tile,amount=body.amount,target=body.target,give=body.give,take=body.take,cash=body.cash,ask=body.ask,
                            give_cards=body.give_cards,take_cards=body.take_cards,redeem_give=body.redeem_give,redeem_take=body.redeem_take,
                            contract_tiles=body.contract_tiles,contract_turns=body.contract_turns,contract_fee=body.contract_fee)
                rules.finish_timed(s,clock)
        from .monopoly_contracts import cleanup
        cleanup(s)
        if s['phase']=='playing' and rules.player(s,r.host) and rules.player(s,r.host)['out']:
            r.host=next(p['id'] for p in s['players'] if not p['out'])
        r.state=s;r.version+=1;r.event_version+=1;r.status=s['phase'];r.updated_at=now()
        update_deadlines(r,s,previous_turn,before_decision,clock)
        result=snapshot(r,m);journal(db,user,body,fp,result);return result
