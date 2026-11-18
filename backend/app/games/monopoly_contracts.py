"""Friendly house rule: prepaid, binding rent waivers; never a classic rule.

Helpers mutate only the JSON state supplied by the caller (normally engine.act's
copy). No persistence, clocks, environment or engine imports. A failed command
raises HTTPException(409) before changing even cleanup/log state. The engine owns
turn_number and must call cleanup after ownership changes, bankruptcies and turns.
"""
from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from fastapi import HTTPException

MAX_CONTRACTS = 8
MAX_TILES = 28
MAX_TURNS = 12


def require(ok, message):
    if not ok:
        raise HTTPException(409, message)


def log(s, text):
    s['log'] = (s.get('log', []) + [text])[-100:]


def _player(s, pid):
    return next((p for p in s.get('players', []) if p['id'] == pid), None)


def _alive(s, pid):
    p = _player(s, pid)
    return p is not None and not p.get('out', False)


def _turn(s):
    value = s.get('turn_number', 0)
    require(type(value) is int and value >= 0, 'Некорректный счётчик ходов')
    return value


def _gate(s, pid):
    require(s.get('mode') == 'friendly', 'Договоры доступны только в дружеском режиме')
    require(s.get('phase') == 'playing', 'Партия не идёт')
    require(_alive(s, pid), 'Вы не участвуете в партии')
    require(not s.get('auction') and not s.get('debt')
            and s.get('pending') is None and not s.get('trade'),
            'Сначала завершите долг, аукцион, покупку или обмен')
    _turn(s)


def _participants(s, owner, beneficiary):
    require(owner != beneficiary and _alive(s, owner) and _alive(s, beneficiary),
            'Выберите другого действующего игрока')


def _tiles(s, tiles, owner):
    require(isinstance(tiles, list) and 1 <= len(tiles) <= MAX_TILES,
            'Выберите от 1 до 28 участков')
    require(all(type(i) is int and str(i) in s.get('properties', {}) for i in tiles),
            'Выберите существующие покупаемые участки')
    require(len(set(tiles)) == len(tiles), 'Участки не должны повторяться')
    require(all(s['properties'][str(i)]['owner'] == owner for i in tiles),
            'Можно обещать отказ от аренды только на своих участках')


def _terms(s, owner, beneficiary, tiles, turns, fee):
    _participants(s, owner, beneficiary)
    _tiles(s, tiles, owner)
    require(type(turns) is int and 1 <= turns <= MAX_TURNS, 'Срок: от 1 до 12 общих ходов')
    require(type(fee) is int and fee >= 0, 'Цена должна быть целым неотрицательным числом')


def _active(s):
    """Compute cleanup without mutating input, so rejected commands stay atomic."""
    now = _turn(s)
    if s.get('mode') != 'friendly' or s.get('phase') != 'playing':
        return []
    result = []
    for contract in s.get('contracts', []):
        owner, beneficiary = contract['owner'], contract['beneficiary']
        if (now >= contract['expires_turn'] or owner == beneficiary
                or not _alive(s, owner) or not _alive(s, beneficiary)):
            continue
        tiles = [i for i in contract['tiles']
                 if s.get('properties', {}).get(str(i), {}).get('owner') == owner]
        if tiles:
            result.append(dict(contract, tiles=tiles))
    return result


def _capacity(active, owner, beneficiary, tiles):
    require(len(active) < MAX_CONTRACTS, 'Одновременно возможно не больше 8 договоров')
    require(not any(c['owner'] == owner and c['beneficiary'] == beneficiary
                    and any(i in c['tiles'] for i in tiles) for c in active),
            'На эти участки уже действует договор с этим игроком')


def propose(s, pid, target, tiles, turns, fee):
    """Offerer owns tiles; target pays offerer once, only upon acceptance."""
    _gate(s, pid)
    require(not s.get('contract_offer'), 'Сначала ответьте на действующее предложение или отмените его')
    _terms(s, pid, target, tiles, turns, fee)
    active = _active(s)
    _capacity(active, pid, target, tiles)
    offer = dict(id=str(uuid4()), offerer=pid, target=target,
                 tiles=list(tiles), turns=turns, fee=fee)
    s['contracts'] = active
    s['contract_offer'] = offer
    log(s, _player(s, pid)['name'] + ' предлагает договор: ' + _offer_text(s, offer))
    return deepcopy(offer)


def respond(s, pid, accept: bool):
    _gate(s, pid)
    require(type(accept) is bool, 'Ответ должен быть логическим значением')
    offer = s.get('contract_offer')
    require(offer is not None and offer['target'] == pid, 'Нет предложения для вас')
    if not accept:
        s['contract_offer'] = None
        log(s, _player(s, pid)['name'] + ' отклоняет договор.')
        return None
    owner = offer['offerer']
    _terms(s, owner, pid, offer['tiles'], offer['turns'], offer['fee'])
    active = _active(s)
    _capacity(active, owner, pid, offer['tiles'])
    payer, recipient = _player(s, pid), _player(s, owner)
    require(type(payer['cash']) is int and payer['cash'] >= offer['fee'], 'Недостаточно денег для оплаты договора')
    require(type(recipient['cash']) is int and recipient['cash'] >= 0, 'Некорректный баланс владельца')
    contract = dict(id=offer['id'], owner=owner, beneficiary=pid,
                    tiles=list(offer['tiles']), expires_turn=_turn(s) + offer['turns'], fee=offer['fee'])
    # Every validation precedes the one immediate, money-conserving transfer.
    payer['cash'] -= offer['fee']
    recipient['cash'] += offer['fee']
    s['contracts'] = active + [contract]
    s['contract_offer'] = None
    log(s, payer['name'] + ' принимает договор: ' + _contract_text(s, contract))
    return deepcopy(contract)


def cancel(s, pid):
    """Only offerer can cancel a pending offer; accepted waivers are binding."""
    _gate(s, pid)
    offer = s.get('contract_offer')
    require(offer is not None and offer['offerer'] == pid, 'Нет вашего предложения для отмены')
    s['contract_offer'] = None
    log(s, _player(s, pid)['name'] + ' отменяет предложение договора.')


def _offer_valid(s, offer):
    return (offer is not None and s.get('mode') == 'friendly' and s.get('phase') == 'playing'
            and offer['offerer'] != offer['target'] and _alive(s, offer['offerer'])
            and _alive(s, offer['target']) and all(
                s.get('properties', {}).get(str(i), {}).get('owner') == offer['offerer']
                for i in offer['tiles']))


def cleanup(s):
    """Permanently prune transferred tiles; do not reset expiry or refund fees."""
    active = _active(s)
    valid_offer = _offer_valid(s, s.get('contract_offer'))
    s['contracts'] = active
    if not valid_offer:
        s['contract_offer'] = None


def waived(s, owner, visitor, tile) -> bool:
    """Read-only rent decision, independent of whose turn it is or other gates."""
    if type(tile) is not int:
        return False
    return any(c['owner'] == owner and c['beneficiary'] == visitor and tile in c['tiles']
               for c in _active(s))


def _name(s, pid):
    p = _player(s, pid)
    return str(p['name']) if p else str(pid)


def _offer_text(s, offer):
    return (f"{_name(s, offer['offerer'])} → {_name(s, offer['target'])}: без аренды на участках "
            f"{', '.join(map(str, offer['tiles']))}; {offer['turns']} общих завершённых ходов; "
            f"{offer['fee']} владельцу сразу при принятии.")


def _contract_text(s, contract):
    return (f"{_name(s, contract['owner'])} → {_name(s, contract['beneficiary'])}: "
            f"без аренды на участках {', '.join(map(str, contract['tiles']))}; "
            f"до счётчика хода {contract['expires_turn']} (не включая); "
            f"разовая цена {contract['fee']} уже оплачена.")


def public(s):
    """Allowlisted JSON snapshot; never expose decks, balances or private state."""
    offer = s.get('contract_offer')
    if not _offer_valid(s, offer):
        offer = None
    offer_keys = ('id', 'offerer', 'target', 'tiles', 'turns', 'fee')
    contract_keys = ('id', 'owner', 'beneficiary', 'tiles', 'expires_turn', 'fee')
    return dict(contract_offer={k: deepcopy(offer[k]) for k in offer_keys} if offer else None,
                contracts=[{k: deepcopy(c[k]) for k in contract_keys} for c in _active(s)])


def summary(s):
    """Public human-readable snapshot, explicitly labelled as a friendly rule."""
    snapshot = public(s)
    lines = ['Дружеские договоры — дополнительное правило, не классическая Монополия.']
    if snapshot['contract_offer']:
        lines.append('Предложение: ' + _offer_text(s, snapshot['contract_offer']))
    lines.extend(_contract_text(s, c) for c in snapshot['contracts'])
    return '\n'.join(lines)
