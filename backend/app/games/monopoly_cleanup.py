"""Account deletion hook. Caller owns User lock and commits this transaction.

Deleting a participant ends a running game without a winner: no hidden liquidation
or arbitrary redistribution. Lobby ownership is transferred. Historical snapshots
are scrubbed too, including rooms the account previously left.
"""
from copy import deepcopy
from sqlalchemy import select, delete
from .monopoly_models import MonopolyRoom as Room, MonopolyMember as Member, MonopolyCommand as Command, MonopolyMessage as Message
from app.security import now


def scrub_state(state, deleted_ids):
    s=deepcopy(state)
    for p in s.get('players',[]):
        if p['id'] in deleted_ids:
            p['name']='Удалённый игрок'
    # Free-form history cannot be reliably anonymised by substring replacement.
    s['log']=[]
    return s


async def cleanup_account(db, user):
    members=(await db.execute(select(Member).where(Member.user_id==user.id))).scalars().all()
    own_commands=(await db.execute(select(Command).where(Command.user_id==user.id))).scalars().all()
    affected={m.room_id: {str(m.id)} for m in members}
    # Journal "you" retains the historical member id after a normal lobby leave.
    from uuid import UUID
    for c in own_commands:
        response=c.response
        if response.get('id') and response.get('you'):
            affected.setdefault(UUID(response['id']),set()).add(response['you'])
    if not affected: return
    rooms=(await db.execute(select(Room).where(Room.id.in_(affected)).order_by(Room.id).with_for_update())).scalars().all()
    for r in rooms:
        ids=affected[r.id]
        s=scrub_state(r.state,ids)
        present=any(p['id'] in ids for p in s['players'])
        if r.status=='lobby':
            s['players']=[p for p in s['players'] if p['id'] not in ids]
            if not s['players']:
                s['phase']='finished';r.host='';s['turn']=None
            elif r.host in ids:
                r.host=s['players'][0]['id'];s['turn']=r.host
        elif r.status=='playing' and present:
            s.update(phase='finished',winner=None,auction=None,trade=None,debt=None,pending=None)
            for p in s['players']:
                if p['id'] in ids: p['out']=True
            s['log']=['Партия завершена без победителя: один из участников удалил аккаунт.']
        r.state=s;r.status=s['phase'];r.version+=1;r.event_version+=1;r.updated_at=now()
        r.title='Игра с друзьями'  # user-authored title may contain the deleted name
        if r.status!='playing':r.deadline=None
        commands=(await db.execute(select(Command).where(Command.response['id'].astext==str(r.id)).order_by(Command.id).with_for_update())).scalars().all()
        for c in commands:
            response=deepcopy(c.response)
            if 'state' in response:response['state']=scrub_state(response['state'],ids)
            response['title']='Игра с друзьями'
            # Old stored snapshots never include chat today; scrub defensively.
            response.pop('messages',None)
            c.response=response
    # Explicit deletion also covers historical member ids retained in journals.
    deleted_ids={pid for ids in affected.values() for pid in ids}
    await db.execute(delete(Message).where(Message.member_id.in_([UUID(pid) for pid in deleted_ids])))
    # Actual members and own journal are removed by users.id ON DELETE CASCADE.
