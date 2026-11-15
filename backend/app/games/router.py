from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.security import current_user, lock_authenticated_user
from .engine import catalog
from .schemas import (CatalogResponse, DailyResponse, InventoryResponse, LeaderboardResponse,
                      LedgerResponse, Mutation, RoundAction, RoundResponse, RoundsResponse, SaleResponse,
                      StartRound, UpgradeResponse, WalletResponse)
from .service import GamesService


async def private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Authorization"


router = APIRouter(prefix="/games", tags=["games"], dependencies=[Depends(private_response)])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog(user: CurrentUser, session: Session) -> dict:
    async with session.begin():
        await lock_authenticated_user(session, user)
        return {"items": catalog()}


@router.get("/wallet", response_model=WalletResponse)
async def get_wallet(user: CurrentUser, session: Session) -> dict:
    return await GamesService(session, user).wallet()


@router.get("/ledger", response_model=LedgerResponse)
async def get_ledger(user: CurrentUser, session: Session,
                     limit: Annotated[int, Query(ge=1, le=100)] = 50,
                     offset: Annotated[int, Query(ge=0, le=100000)] = 0) -> dict:
    return await GamesService(session, user).ledger(limit=limit, offset=offset)


@router.post("/daily", response_model=DailyResponse)
async def claim_daily(body: Mutation, user: CurrentUser, session: Session) -> dict:
    return await GamesService(session, user).daily(body.key)


@router.get("/history", response_model=RoundsResponse)
async def get_history(user: CurrentUser, session: Session,
                      limit: Annotated[int, Query(ge=1, le=100)] = 50,
                      offset: Annotated[int, Query(ge=0, le=100000)] = 0) -> dict:
    return await GamesService(session, user).rounds(limit=limit, offset=offset)


@router.get("/fishing/inventory", response_model=InventoryResponse)
async def get_inventory(user: CurrentUser, session: Session) -> dict:
    return await GamesService(session, user).inventory()


@router.post("/fishing/upgrade", response_model=UpgradeResponse)
async def upgrade_rod(body: Mutation, user: CurrentUser, session: Session) -> dict:
    return await GamesService(session, user).upgrade(body.key)


@router.post("/fishing/sell", response_model=SaleResponse)
async def sell_fish(body: Mutation, user: CurrentUser, session: Session) -> dict:
    return await GamesService(session, user).sell(body.key)


@router.post("/rounds", response_model=RoundResponse)
async def start_round(body: StartRound, user: CurrentUser, session: Session) -> dict:
    return await GamesService(session, user).start(body)


# Static route must precede the dynamic UUID route.
@router.get("/rounds/active", response_model=RoundsResponse)
async def get_active_rounds(user: CurrentUser, session: Session) -> dict:
    return await GamesService(session, user).rounds(active=True, limit=12)


@router.get("/rounds/{round_id}", response_model=RoundResponse)
async def get_round(round_id: UUID, user: CurrentUser, session: Session) -> dict:
    return await GamesService(session, user).round(round_id)


@router.post("/rounds/{round_id}/actions", response_model=RoundResponse)
async def act_on_round(round_id: UUID, body: RoundAction, user: CurrentUser, session: Session) -> dict:
    return await GamesService(session, user).action(round_id, body)


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(user: CurrentUser, session: Session, kind: Literal["wealth", "fishing"] = "wealth") -> dict:
    return await GamesService(session, user).leaderboard(kind)
