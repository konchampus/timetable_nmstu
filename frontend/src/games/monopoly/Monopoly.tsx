import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { ArrowRight, Check, Copy, Dices, DoorOpen, Expand, Flag, Handshake, Info, LayoutGrid, MessageCircle, RefreshCw, Send, Trophy, Wallet, X, Menu as MenuIcon } from 'lucide-react';
import GameWindow from '../GameWindow';
import Board, { GROUP_COLORS, Token } from './Board';
import PropertyArt from './PropertyArt';
import PlayableBoard from './PlayableBoard';
import { inviteCode, useMonopoly, type Room, type Tile, type State } from './useMonopoly';
import './monopoly.css';
import './monopoly-mobile.css';
import './field-layout-v3.css';
type Model = ReturnType<typeof useMonopoly>;
type Tab = 'field' | 'assets' | 'deals' | 'chat' | 'menu';
type ExtendedTrade = NonNullable<State['trade']>;
const number = (value: number) => new Intl.NumberFormat('ru-RU').format(value);
const modeNames: Record<string, string> = { classic: 'Классика', timed20: 'На 20 минут', timed40: 'На 40 минут', timed60: 'На 60 минут', friendly: 'Дружеская' };
const colorNames = ['Синий', 'Красный', 'Зелёный', 'Янтарный', 'Фиолетовый', 'Бирюзовый'];
const disabled = (game: Model) => game.busy || !!game.pending || !game.ready;
const stateOf = (room: Room) => room.state;
const playerName = (room: Room, id: string | null | undefined) => room.state.players.find(p => p.id === id)?.name ?? 'Участник';
const tileNames = (tiles: Tile[], ids: number[]) => ids.map(id => tiles.find(t => t.id === id)?.name ?? 'Актив ' + id).join(', ') || 'Нет активов';
const cardName = (card: string) => card === 'chance' ? 'Выход из тюрьмы · Шанс' : 'Выход из тюрьмы · Казна';
/** Native top-layer dialogs keep focus inside and restore the actual opener. */
function Modal({ title, onClose, children, wide = false, game }: {
    title: string;
    onClose: () => void;
    children: ReactNode;
    wide?: boolean;
    game: Model;
}) {
    const ref = useRef<HTMLDialogElement>(null), id = useId();
    useEffect(() => { const element = ref.current; if (!element)
        return; const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null; element.showModal(); return () => { element.close(); if (opener?.isConnected)
        opener.focus({ preventScroll: true }); }; }, []);
    return <dialog ref={ref} className={'mono-modal' + (wide ? ' mono-map-modal' : '')} aria-labelledby={id} onCancel={event => { event.preventDefault(); event.stopPropagation(); onClose(); }}>
        <header>
            <h2 id={id}>
                {title}
            </h2>
            <button className="mono-icon" aria-label="Закрыть диалог" onClick={onClose}>
                <X size={22}/>
            </button>
        </header>
        {(game.error || game.pending && !game.busy) && <Recovery game={game}/>}
        <div className="mono-modal-body">
            {children}
        </div>
    </dialog>;
}
function Recovery({ game }: {
    game: Model;
}) { return <div className="mono-error" role="alert">
        <Info size={18}/>
        <div>
            <strong>
                {game.pending ? 'Результат действия пока неизвестен' : 'Не удалось обновить игру'}
            </strong>
            <p>
                {game.error || 'Не отправляйте другое действие до подтверждения.'}
            </p>
            <button disabled={game.busy} onClick={() => void (game.pending ? game.retry() : game.refresh())}>
                {game.pending ? 'Проверить то же действие' : 'Повторить подключение'}
            </button>
        </div>
    </div>; }
function useMobile() { const [mobile, setMobile] = useState(() => window.matchMedia('(max-width:700px)').matches); useEffect(() => { const media = window.matchMedia('(max-width:700px)'), update = () => setMobile(media.matches); media.addEventListener('change', update); return () => media.removeEventListener('change', update); }, []); return mobile; }
export default function Monopoly({ visible = true, onClose }: {
    visible?: boolean;
    onClose: () => void;
}) {
    const game = useMonopoly(visible), mobile = useMobile();
    const [tab, setTab] = useState<Tab>('field'), [tile, setTile] = useState<number | null>(null), [zoom, setZoom] = useState(false), [rules, setRules] = useState(false), [trade, setTrade] = useState(false), [resign, setResign] = useState(false), [notice, setNotice] = useState(''), [chatDraft, setChatDraft] = useState('');
    const room = game.room, s = room ? stateOf(room) : null, selected = game.tiles.find(t => t.id === tile);
    const [seenMessages, setSeenMessages] = useState(0);
    useEffect(() => { setTab('field'); setTile(null); setChatDraft(''); setSeenMessages(0); setZoom(false); setTrade(false); setResign(false); }, [room?.id]);
    useEffect(() => { if (tab === 'chat')
        setSeenMessages(room?.messages?.length ?? 0); }, [tab, room?.messages?.length]);
    async function copy() { if (!room)
        return; try {
        await navigator.clipboard.writeText('https://t.me/timetable_casino_nmstu_bot?startapp=mono_' + room.code);
        setNotice('Приглашение скопировано · ' + room.code);
    }
    catch {
        setNotice('Код комнаты: ' + room.code + ' — отправьте его другу.');
    } }
    const select = (id: number) => setTile(id);
    const actions = <Actions game={game} onAssets={() => { if (mobile)
        setTab('assets');
    else
        document.querySelector('.mono-desktop-board .mono-assets')?.scrollIntoView({ block: 'start' }); }} onDeals={() => { if (mobile)
        setTab('deals');
    else
        document.querySelector('.mono-sidebar .mono-deals')?.scrollIntoView({ block: 'start' }); }}/>;
    const board = room && <Board tiles={game.tiles} state={room.state} selected={tile} onSelect={select} rolling={game.pending?.body.action === 'roll'}/>;
    const chat = room && <RoomChat game={game} text={chatDraft} setText={setChatDraft}/>;
    const deals = room && <Deals game={game} onTrade={() => setTrade(true)}/>;
    const menu = room && <RoomMenu game={game} onRules={() => setRules(true)} onInvite={() => void copy()} onResign={() => setResign(true)}/>;
    const nav: [
        Tab,
        string,
        typeof LayoutGrid,
        number
    ][] = [['field', 'Поле', LayoutGrid, s?.debt?.player === room?.you || s?.pending != null || s?.auction?.actor === room?.you ? 1 : 0], ['assets', 'Активы', Wallet, 0], ['deals', 'Сделки', Handshake, s?.trade || s?.contract_offer ? 1 : 0], ['chat', 'Чат', MessageCircle, Math.max(0, (room?.messages?.length ?? 0) - seenMessages)], ['menu', 'Меню', MenuIcon, 0]];
    return <GameWindow visible={visible} game="monopoly" title="Монополия" onClose={onClose}>
        <section className={'mono-app mono-v2' + (room ? ' has-room' : '')} aria-label="Монополия">

            <header className="mono-header">
                <div className="mono-heading">
                    <div>
                        <h1>Монополия</h1>
                        <span>
                            {room ? modeNames[s?.mode ?? 'classic'] ?? 'Партия' : 'Игра с друзьями'}
                            {room ? ' · ' + room.title : ''}
                        </span>
                    </div>
                </div>
                <div className="mono-header-tools">
                    <span className={'mono-connection' + (!game.connected ? ' is-offline' : '')} role="status">
                        {game.connected ? 'На связи' : 'Подключение'}
                    </span>
                    <button className="mono-icon" aria-label="Правила Монополии" onClick={() => setRules(true)}>
                        <Info size={20}/>
                    </button>
                </div>
            </header>

            <div className="mono-status-area">

                {(game.error || game.pending && !game.busy) && <Recovery game={game}/>}

                {!game.persistent && <p className="mono-error" role="status">Хранилище недоступно. Не закрывайте окно до подтверждения действия.</p>}

                {notice && <div className="mono-notice" role="status">
                    <span>
                        {notice}
                    </span>
                    <button className="mono-icon" aria-label="Скрыть сообщение" onClick={() => setNotice('')}>
                        <X size={18}/>
                    </button>
                </div>}

            </div>

            {game.loading && !room ? <div className="mono-loading" role="status">
                <p>Подключаем игровую комнату…</p>
            </div> : !room ? <div className="mono-main-scroll">
                <Lobby game={game}/>
            </div> : <>

                {mobile ? <>
                    <Players game={game} compact/>
                    <main className={'mono-main-scroll' + (tab === 'field' ? ' mono-field-workspace' : '')} id="mono-current-panel" aria-label={nav.find(n => n[0] === tab)?.[1]} key={tab}>

                        {tab === 'field' && <>
                            <section className="mono-field-map" aria-label="Игровое поле">
                                <PlayableBoard tiles={game.tiles} state={room.state} selected={tile} onSelect={select} you={room.you} rolling={game.pending?.body.action === 'roll'}/>
                            </section>
                            <NearbyTiles tiles={game.tiles} room={room} onSelect={select}/>
                            <section className={'mono-action-panel mono-field-decision' + (s?.phase !== 'playing' || s?.debt || s?.auction || s?.pending !== null || s?.players.find(p => p.id === room.you)?.jailed ? ' is-complex' : '')} aria-label="Следующее действие" aria-live="polite">
                                {actions}
                            </section>
                        </>}

                        {tab === 'assets' && <Assets game={game} onSelect={select}/>}
                        {tab === 'deals' && deals}
                        {tab === 'chat' && chat}
                        {tab === 'menu' && menu}

                    </main>
                    <nav className="mono-bottom-nav" aria-label="Разделы партии">
                        {nav.map(([id, label, Icon, badge]) => <button key={id} aria-pressed={tab === id} aria-controls="mono-current-panel" onClick={() => setTab(id)}>
                            <span>
                                <Icon size={21}/>
                                {badge > 0 && <b aria-label={badge + ' новых'}>
                                {badge > 99 ? '99+' : badge}
                                </b>}
                            </span>
                            {label}
                        </button>)}
                    </nav>
                </> : <main className="mono-desktop-layout">
                    <section className="mono-desktop-board">
                        <div className="mono-board-toolbar">
                            <span>{room.title} · {room.code}</span>
                            <button className="mono-link" onClick={() => setZoom(true)}><Expand size={16}/>Увеличить поле</button>
                        </div>
                        {board}
                        <Assets game={game} onSelect={select}/>
                    </section>
                    <aside className="mono-sidebar">
                        <Players game={game}/>
                        <section className="mono-action-panel" aria-live="polite">
                            {actions}
                        </section>
                        {deals}
                        {menu}
                        {chat}
                    </aside>
                </main>}

            </>}

            {game.busy && <span className="mono-saving" role="status">Сохраняем…</span>}

            {rules && <Modal game={game} title="Правила партии" onClose={() => setRules(false)}>
                <Rules game={game}/>
            </Modal>}

            {room && zoom && <Modal game={game} title="Поле крупным планом" onClose={() => setZoom(false)} wide>
                <p>Прокручивайте только карту. Нажмите клетку, чтобы прочитать карточку.</p>
                <Board tiles={game.tiles} state={room.state} selected={tile} onSelect={select} zoom rolling={game.pending?.body.action === 'roll'}/>
                <button className="mono-secondary" onClick={() => setZoom(false)}>Вернуться к игре</button>
            </Modal>}

            {room && selected && <Modal game={game} title={selected.name} onClose={() => setTile(null)}>
                <PropertyDetails tile={selected} game={game}/>
            </Modal>}

            {room && trade && <Modal game={game} title="Предложить обмен" onClose={() => setTrade(false)}>
                <TradeForm room={room} tiles={game.tiles} blocked={disabled(game)} onSubmit={async (body) => { if (await game.mutate('trade', body))
        setTrade(false); }}/>
            </Modal>}

            {room && resign && <Modal game={game} title="Сдаться и выйти из партии?" onClose={() => setResign(false)}>
                <p>Это окончательная уступка, а не выход из окна. Вы потеряете участие в этой партии; деньги, активы и карты будут обработаны сервером по регламенту. Вернуться игроком в эту партию нельзя.</p>
                <p>Если нужно просто сделать паузу, закройте это подтверждение. Закрытие окна само по себе не означает сдачу.</p>
                <button className="mono-secondary" autoFocus onClick={() => setResign(false)}>Остаться в игре</button>
                <button className="mono-danger" disabled={disabled(game)} onClick={async () => { if (await game.mutate('resign'))
        setResign(false); }}><Flag size={18}/>Да, сдаться навсегда</button>
            </Modal>}

        </section>
    </GameWindow>;
}
/** Large native targets complement the map: no precision aiming at overview cells. */
function NearbyTiles({ tiles, room, onSelect }: { tiles: Tile[]; room: Room; onSelect: (id: number) => void }) {
    const s = room.state, player = s.players.find(p => p.id === s.turn) ?? s.players.find(p => p.id === room.you);
    const position = player?.pos ?? 0, strip = useRef<HTMLDivElement>(null);
    useEffect(() => {
        // Follow the authoritative landing without taking keyboard focus or moving a dialog/chat.
        if (!document.querySelector('dialog[open]')) strip.current?.scrollTo({ left: 0, behavior: 'instant' });
    }, [position, s.turn, s.roll_sequence]);
    const nearby = [0, 1, 2, 3, -1].map(offset => tiles.find(t => t.id === (position + offset + 40) % 40)).filter((t): t is Tile => !!t);
    return <div className="mono-nearby-strip" ref={strip} aria-label="Текущая клетка и соседние активы">
        {nearby.map(t => {
            const asset = s.properties[t.id], current = t.id === position;
            const rent = asset?.mortgaged ? 'В залоге · без аренды' : t.kind === 'rail' ? 'Аренда 25–200' : t.price > 0 && !t.rents.length ? 'Аренда ×4 / ×10 костей' : t.rents.length ? 'Базовая аренда ' + number(t.rents[asset?.houses ?? 0] ?? t.rents[0]) : 'Специальная клетка';
            return <button key={t.id} className={'mono-nearby-tile' + (current ? ' is-current' : '')} aria-current={current ? 'location' : undefined} onClick={() => onSelect(t.id)}>
                <span className="mono-nearby-position">{current ? 'Сейчас · ' + (player?.name ?? 'Игрок') : offsetLabel(t.id, position)}</span>
                <strong>{t.name}</strong>
                <span className="mono-nearby-ownership"><span>{asset?.owner ? playerName(room, asset.owner) : t.price > 0 ? 'Свободен' : 'Без владельца'}</span>{t.price > 0 && <b>Цена {number(t.price)}</b>}</span>
                <span>{rent}</span>
            </button>;
        })}
    </div>;
}
function offsetLabel(id: number, position: number) {
    const steps = (id - position + 40) % 40;
    return steps === 39 ? 'Предыдущая клетка' : 'Через ' + steps + (steps === 1 ? ' клетку' : ' клетки');
}
function Lobby({ game }: {
    game: Model;
}) {
    const [view, setView] = useState<'create' | 'join'>(() => inviteCode() ? 'join' : 'create'), [nickname, setNickname] = useState<string|null>(null), [title, setTitle] = useState('Игра с друзьями'), [capacity, setCapacity] = useState(4), [isPublic, setPublic] = useState(false), [code, setCode] = useState(inviteCode), [color, setColor] = useState('#2254ff'), [mode, setMode] = useState('classic');
    const modes = game.modes;
    const choices = modes?.length ? modes.map(m => ({ id: m.id, label: m.name ?? m.title ?? modeNames[m.id] })) : Object.entries(modeNames).map(([id, label]) => ({ id, label }));
    const blocked = disabled(game);
    const nameOptions = nickname?.trim() ? { nickname: nickname.trim(), use_telegram_name: false } : { use_telegram_name: true };
    const enter = (action: string) => void game.mutate(action, { ...nameOptions, title, capacity, public: isPublic, code, color, mode, ...(mode.startsWith('timed') ? { duration_minutes: Number(mode.slice(5)) } : {}) }, '/monopoly/rooms');
    return <div className="mono-lobby mono-lobby-v2">
        <h2>Соберите свою компанию</h2>
        <p>2–6 игроков. Только деньги партии — без ставок и общего баланса.</p>
        <div className="mono-segmented" aria-label="Вход в игру">
            <button aria-pressed={view === 'create'} onClick={() => setView('create')}>Создать</button>
            <button aria-pressed={view === 'join'} onClick={() => setView('join')}>Войти</button>
        </div>

        <label>Имя в игре<input autoComplete="nickname" maxLength={30} value={nickname ?? game.profileName} placeholder={game.profileName || "Имя из Telegram"} onChange={e => setNickname(e.target.value)}/></label>
        <p className="mono-mode-description">По умолчанию — ваше имя из Telegram. Можно указать свой ник только для этой партии. Имена из чужих контактов недоступны.</p>
        <ColorPicker colors={game.colors} value={color} onChange={setColor}/>

        {view === 'create' ? <form className="mono-setup" onSubmit={e => { e.preventDefault(); enter('create'); }}>
            <label>Режим<select value={mode} onChange={e => setMode(e.target.value)}>
                    {choices.map(m => <option key={m.id} value={m.id}>
                        {m.label}
                    </option>)}
                </select></label>
            <p className="mono-mode-description">
                {modes?.find(m => m.id === mode)?.description ?? (mode === 'classic' ? 'Официальные правила. Без лимита длительности партии.' : mode === 'friendly' ? 'Классическая основа и договоры об освобождении от аренды на будущие ходы.' : 'Партия по таймеру. По окончании сравнивается капитал по регламенту режима.')}
            </p>
            <div className="mono-form-row">
                <label>Название комнаты<input maxLength={60} value={title} onChange={e => setTitle(e.target.value)}/></label>
                <label>Мест<select value={capacity} onChange={e => setCapacity(Number(e.target.value))}>
                        {[2, 3, 4, 5, 6].map(n => <option key={n}>
                            {n}
                        </option>)}
                    </select></label>
            </div>
            <label className="mono-checkbox"><input type="checkbox" checked={isPublic} onChange={e => setPublic(e.target.checked)}/>Открыта для других игроков</label>
            <button className="mono-primary" disabled={blocked || !title.trim()}>Создать комнату<ArrowRight size={18}/></button>
        </form> : <form className="mono-setup" onSubmit={e => { e.preventDefault(); enter('join'); }}>
            <label>Код приглашения<input value={code} maxLength={20} autoCapitalize="none" autoComplete="off" spellCheck={false} onChange={e => setCode(e.target.value.trim().toLowerCase())} placeholder="Код от друга"/></label>
            <button className="mono-primary" disabled={blocked || !/^[a-f0-9]{20}$/.test(code)}>Присоединиться<ArrowRight size={18}/></button>
        </form>}

        <section className="mono-room-list">
            <div className="mono-list-heading">
                <h3>Ваши и открытые комнаты</h3>
                <button className="mono-icon" aria-label="Обновить комнаты" disabled={game.busy} onClick={() => void game.refresh()}>
                    <RefreshCw size={18}/>
                </button>
            </div>
            {game.rooms.length ? game.rooms.map(r => <div className="mono-room-row" key={r.id}>
                <div>
                    <strong>
                        {r.title}
                    </strong>
                    <span>{r.count}/{r.capacity} · {r.status === 'lobby' ? 'Сбор игроков' : r.status === 'playing' ? 'Идёт партия' : 'Завершена'}</span>
                </div>
                <button className="mono-secondary" disabled={disabled(game) || (!r.mine && blocked)} onClick={() => r.mine ? void game.open(r.id) : void game.mutate('join', { ...nameOptions, color }, '/monopoly/rooms/' + r.id + '/join')}>
                    {r.mine ? 'Открыть' : 'Войти'}
                </button>
            </div>) : <p className="mono-empty">Пока нет комнат. Создайте свою или войдите по коду.</p>}
        </section>

    </div>;
}
function ColorPicker({ colors, value, onChange, unavailable = [] }: {
    colors: string[];
    value: string;
    onChange: (color: string) => void;
    unavailable?: string[];
}) { return <div className="mono-color-picker" role="group" aria-label="Цвет фишки">
        {colors.map((color, i) => <button key={color} type="button" aria-label={colorNames[i] ?? color} aria-pressed={value === color} disabled={unavailable.includes(color)} style={{ background: color }} onClick={() => onChange(color)}>
            {value === color && <Check size={20}/>}
        </button>)}
    </div>; }
function Players({ game, compact = false }: {
    game: Model;
    compact?: boolean;
}) { const room = game.room!; return <section className={'mono-players' + (compact ? ' mono-player-chips' : '')} aria-label="Игроки и деньги">
        {!compact && <h2>За столом <span>{room.state.players.length}/{room.capacity}</span></h2>}
        {room.state.players.map((p, i) => <div className={'mono-player' + (room.state.turn === p.id ? ' is-turn' : '') + (p.out ? ' is-out' : '')} key={p.id}>
            <Token player={p} index={i} size={compact ? 26 : 34}/>
            <div>
                <strong>
                    {p.name}
                    {p.id === room.you ? ' · вы' : ''}
                </strong>
                <span>
                    {p.out ? 'Выбыл' : room.status === 'lobby' ? (p.ready ? 'Готов' : 'Не готов') : number(p.cash) + (p.jailed ? ' · тюрьма' : room.state.turn === p.id ? ' · ходит' : '')}
                </span>
            </div>
            {!compact && room.status !== 'lobby' && <b>
                {number(p.cash)}
            </b>}
        </div>)}
    </section>; }
function DecisionClock({ room }: {
    room: Room;
}) {
    const deadline=room.state.game_deadline??room.deadline;
    const [now, setNow] = useState(Date.now());
    useEffect(() => { if (!deadline)
        return; const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, [deadline]);
    const clock = useRef({ server: room.server_now, received: room.received_at ?? Date.now() });
    if (clock.current.server !== room.server_now)
        clock.current = { server: room.server_now, received: room.received_at ?? Date.now() };
    if (!deadline)
        return null;
    const seconds = Math.max(0, Math.ceil((Date.parse(deadline) - now - (Date.parse(clock.current.server) - clock.current.received)) / 1000));
    return <time title={room.state.game_deadline?"До конца партии":"Осталось на решение"}>{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</time>;
}
function Actions({ game, onAssets, onDeals }: {
    game: Model;
    onAssets: () => void;
    onDeals: () => void;
}) {
    const room = game.room!, s = stateOf(room), me = s.players.find(p => p.id === room.you), blocked = disabled(game), mine = s.turn === room.you;
    const [bid, setBid] = useState(''), [placement, setPlacement] = useState(''), [bankrupt, setBankrupt] = useState(false);
    const [now, setNow] = useState(Date.now());
    const clock = useRef({server:room.server_now,received:room.received_at??Date.now()});
    if(clock.current.server!==room.server_now) clock.current={server:room.server_now,received:room.received_at??Date.now()};
    useEffect(()=>{if(s.phase!=='playing'||!s.game_deadline&&!room.deadline)return;const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[s.phase,s.game_deadline,room.deadline]);
    const serverNow=now+Date.parse(clock.current.server)-clock.current.received;
    const timeExpired=!!s.game_deadline&&serverNow>=Date.parse(s.game_deadline);
    const go = (action: string, body: Record<string, unknown> = {}) => void game.mutate(action, body);
    if (!me)
        return <p>Вы наблюдаете за партией.</p>;
    if (s.phase === 'lobby')
        return <>
        <h3>Готовы к игре?</h3>
        <p>{modeNames[s.mode ?? 'classic']} · {s.mode?.startsWith('timed') ? 'Длительность ' + (s.duration_minutes ?? s.mode.slice(5)) + ' минут' : 'Без таймера партии'}</p>
        <ColorPicker colors={game.colors} value={me.color} unavailable={blocked ? game.colors : s.players.filter(p => p.id !== room.you).map(p => p.color)} onChange={color => go('color', { color })}/>
        <button className="mono-primary" disabled={blocked} onClick={() => go('ready')}>
            {me.ready ? 'Отменить готовность' : 'Я готов'}
        </button>
        {room.host === room.you && <button className="mono-secondary" disabled={blocked || s.players.length < 2 || !s.players.every(p => p.ready)} onClick={() => go('start')}>Начать партию</button>}
        <p>
            {s.players.every(p => p.ready) ? 'Все готовы. Создатель может начать.' : 'Ждём готовности участников.'}
        </p>
    </>;
    if (s.phase === 'finished') {
        const winners = s.winners ?? (s.winner ? [s.winner] : []);
        return <div className="mono-finished">
        <Trophy size={30}/>
        <h3>
            {winners.includes(room.you) ? 'Вы победили!' : 'Партия завершена'}
        </h3>
        <p>
            {winners.length ? 'Победитель: ' + winners.map(id => playerName(room, id)).join(', ') : 'Без победителя'}
        </p>
        {s.finish_reason && <p>
            {s.finish_reason === 'time_limit' ? 'Время партии истекло.' : s.finish_reason === 'last_player' ? 'Остался один участник.' : 'Причина: ' + s.finish_reason}
        </p>}
        {s.scores && <dl>
            {Object.entries(s.scores).map(([id, score]) => <div key={id}>
                <dt>
                    {playerName(room, id)}
                </dt>
                <dd>
                    {number(score)}
                </dd>
            </div>)}
        </dl>}
        <button className="mono-secondary" onClick={game.lobby}>К комнатам</button>
    </div>;
    }
    let decision: ReactNode;
    if(timeExpired) decision=<><p>Время партии истекло. Подведите итог, чтобы сервер рассчитал капитал участников.</p><button className="mono-primary" disabled={blocked} onClick={()=>go('timeout')}>Подвести итог по таймеру</button></>;
    else if (me.out)
        decision = <p>Вы выбыли. Можно наблюдать за полем и общаться в чате.</p>;
    else if (s.debt)
        decision = <>
        <p>
            <strong>{s.debt.player === room.you ? 'Ваш долг' : playerName(room, s.debt.player) + ' должен'}: {number(s.debt.amount)}</strong>
        </p>
        {s.debt.player === room.you ? <>
            <p>Продайте здания или заложите активы, чтобы расплатиться.</p>
            <button className="mono-primary" onClick={onAssets}>Управлять активами</button>
            <button className="mono-link" disabled={blocked} onClick={() => setBankrupt(true)}>Не могу выплатить долг</button>
        </> : <p>Ждём погашения долга.</p>}
    </>;
    else if (s.auction)
        decision = <>
        <h4>Аукцион: {s.auction.kind === 'building' ? (s.auction.building === 'hotel' ? 'последний отель' : 'последний дом') : game.tiles.find(t => t.id === s.auction!.tile)?.name}</h4>
        <p>Ставка <strong>
                {number(s.auction.bid)}
            </strong> · {s.auction.bidder ? playerName(room, s.auction.bidder) : 'пока без ставок'}</p>
        {s.auction.actor === room.you ? <>
            {s.auction.kind === 'building' && <label>Где строить<select value={placement && s.auction.placements?.[room.you]?.includes(Number(placement)) ? placement : String(s.auction.placements?.[room.you]?.[0] ?? '')} onChange={e => setPlacement(e.target.value)}>
                    {(s.auction.placements?.[room.you] ?? []).map(id => <option key={id} value={id}>
                        {game.tiles.find(t => t.id === id)?.name}
                    </option>)}
                </select></label>}
            <label>Ваша ставка<input type="number" inputMode="numeric" min={s.auction.bid + 1} max={me.cash} value={bid} placeholder={String(s.auction.bid + 1)} onChange={e => setBid(e.target.value)}/></label>
            <div className="mono-action-row">
                <button className="mono-primary" disabled={blocked || !Number.isSafeInteger(Number(bid)) || Number(bid) <= s.auction.bid || Number(bid) > me.cash} onClick={() => go('bid', { amount: Number(bid), ...(s.auction?.kind === 'building' ? { tile: placement && s.auction.placements?.[room.you]?.includes(Number(placement)) ? Number(placement) : s.auction.placements?.[room.you]?.[0] } : {}) })}>Сделать ставку</button>
                <button className="mono-secondary" disabled={blocked} onClick={() => go('pass')}>Пас</button>
            </div>
        </> : <p>Ставку делает {playerName(room, s.auction.actor)}.</p>}
    </>;
    else if (!mine)
        decision = <p>Ходит {playerName(room, s.turn)}. Пока можно изучить активы или написать в чат.</p>;
    else if (s.pending !== null) {
        const property = game.tiles.find(t => t.id === s.pending);
        decision = <>
        <h4>
            {property?.name}
        </h4>
        <p>Свободный актив · <strong>
                {number(property?.price ?? 0)}
            </strong></p>
        <div className="mono-action-row">
            <button className="mono-primary" disabled={blocked || me.cash < (property?.price ?? 0)} onClick={() => go('buy')}>Купить</button>
            <button className="mono-secondary" disabled={blocked} onClick={() => go('auction')}>На аукцион</button>
        </div>
    </>;
    }
    else if (!s.rolled)
        decision = <>
        {me.jailed ? <>
            <p>Вы в тюрьме. Попытайтесь выбросить дубль или выйдите за 50.</p>
            <button className="mono-primary mono-roll" disabled={blocked} onClick={() => go('roll')}><Dices size={22}/>Бросить на дубль</button>
            <div className="mono-action-row">
                <button className="mono-secondary" disabled={blocked || me.cash < 50} onClick={() => go('bail')}>Заплатить 50</button>
                {me.cards.length > 0 && <button className="mono-secondary" disabled={blocked} onClick={() => go('jail_card')}>Карта выхода</button>}
            </div>
        </> : <>
            <p className="mono-action-hint">Бросьте кости и сделайте следующий шаг.</p>
            <button className="mono-primary mono-roll" disabled={blocked} onClick={() => go('roll')}><Dices size={22}/>Бросить кости</button>
        </>}
    </>;
    else
        decision = <>
        <p className="mono-action-hint">
            {s.extra ? 'Выпал дубль — у вас ещё один бросок.' : 'Покупки и расчёты завершены.'}
        </p>
        <button className="mono-primary" disabled={blocked} onClick={() => go(s.extra ? 'roll' : 'end')}>
            {s.extra ? 'Бросить ещё раз' : 'Завершить ход'}
            <ArrowRight size={18}/>
        </button>
    </>;
    return <>
        <div className="mono-turn-title">
            <h3>
                {s.debt?.player === room.you ? 'Ваш долг' : s.auction?.actor === room.you ? 'Ваша ставка' : mine ? 'Ваш ход' : 'Ход: ' + playerName(room, s.turn)}
            </h3>
            <DecisionClock room={room}/>
        </div>
        <div className={'mono-decision-content' + (s.pending !== null && !s.auction && !s.debt ? ' is-purchase' : '')}>
        {decision}
        {(s.trade || s.mode === 'friendly' && s.contract_offer) && <button className="mono-link" onClick={onDeals}>Рассмотреть {s.trade ? 'обмен' : 'договорённость'} в «Сделках»</button>}
        {!timeExpired && room.deadline && Date.parse(room.deadline) < serverNow && <button className="mono-secondary" disabled={blocked} onClick={() => go('timeout')}>Применить регламент времени</button>}
        </div>
        {bankrupt && <Modal game={game} title="Объявить банкротство?" onClose={() => setBankrupt(false)}>
            <p>Банкротство — окончательный выход из-за долга. Сначала используйте продажу зданий и залог. Сервер проверит, действительно ли выплатить долг невозможно.</p>
            <button className="mono-secondary" autoFocus onClick={() => setBankrupt(false)}>Вернуться к активам</button>
            <button className="mono-danger" disabled={blocked} onClick={async () => { if (await game.mutate('bankrupt'))
        setBankrupt(false); }}>Подтвердить банкротство</button>
        </Modal>}
    </>;
}
function Assets({ game, onSelect }: {
    game: Model;
    onSelect: (id: number) => void;
}) {
    const [filter, setFilter] = useState('all'), room = game.room!, tiles = game.tiles.filter(t => t.price > 0);
    const shown = tiles.filter(t => { const a = room.state.properties[t.id]; return filter === 'all' || filter === 'mine' && a?.owner === room.you || filter === 'free' && !a?.owner || filter === 'mortgaged' && a?.owner === room.you && a.mortgaged; });
    return <section className="mono-assets">
        <header>
            <h2>Активы <span>
                    {tiles.length}
                </span></h2>
            <label>Показать<select value={filter} onChange={e => setFilter(e.target.value)}>
                    <option value="all">Все активы</option>
                    <option value="mine">Мои</option>
                    <option value="free">Свободные</option>
                    <option value="mortgaged">Мои в залоге</option>
                </select></label>
        </header>
        {room.state.debt?.player === room.you && <p className="mono-debt-note">Долг {number(room.state.debt.amount)}. Откройте свой актив: продажа зданий и залог — в карточке.</p>}
        <div className="mono-asset-list">
            {shown.length ? shown.map(t => { const a = room.state.properties[t.id]; return <button className="mono-asset-row" key={t.id} onClick={() => onSelect(t.id)}>
                <PropertyArt tile={t} color={GROUP_COLORS[t.group]}/>
                <span>
                    <strong>
                        {t.name}
                    </strong>
                    <small>
                        {a?.owner ? playerName(room, a.owner) : 'Свободен'}
                        {a?.mortgaged ? ' · залог' : ''}
                        {a?.houses ? ' · ' + (a.houses === 5 ? 'отель' : a.houses + ' дома') : ''}
                    </small>
                </span>
                <b>
                    {number(t.price)}
                </b>
                <ArrowRight size={16}/>
            </button>; }) : <p className="mono-empty">Нет активов с таким фильтром.</p>}
        </div>
    </section>;
}
function PropertyDetails({ tile, game }: {
    tile: Tile;
    game: Model;
}) {
    const room = game.room!, s = room.state, a = s.properties[tile.id], own = a?.owner === room.you, blocked = disabled(game), canManage = own && room.status === 'playing' && !s.auction && !s.players.find(p => p.id === room.you)?.out;
    const go = (action: string) => void game.mutate(action, { tile: tile.id });
    const built = Object.values(s.properties), housesLeft = Number(game.config?.houses ?? 32) - built.reduce((sum, p) => sum + (p.houses < 5 ? p.houses : 0), 0), hotelsLeft = Number(game.config?.hotels ?? 12) - built.filter(p => p.houses === 5).length;
    const group = game.tiles.filter(t => t.group === tile.group && t.build > 0), complete = group.length > 0 && group.every(t => s.properties[t.id]?.owner === room.you && !s.properties[t.id]?.mortgaged);
    const lastBuilding = a && complete && a.houses < 5 && (a.houses === 4 ? hotelsLeft === 1 : housesLeft === 1);
    return <section className="mono-property mono-property-v2">
        <PropertyArt tile={tile} color={GROUP_COLORS[tile.group]}/>
        <p>
            <strong>
                {a?.owner ? 'Владелец: ' + playerName(room, a.owner) : tile.price ? 'Свободный актив' : 'Специальная клетка'}
            </strong>
            {a?.mortgaged ? ' · В залоге' : ''}
            {a?.houses ? ' · ' + (a.houses === 5 ? 'Отель' : a.houses + ' дома') : ''}
        </p>
        {tile.price > 0 ? <>
            <dl>
                <div>
                    <dt>Покупка</dt>
                    <dd>
                        {number(tile.price)}
                    </dd>
                </div>
                <div>
                    <dt>Залог</dt>
                    <dd>
                        {number(tile.price / 2)}
                    </dd>
                </div>
                <div>
                    <dt>Выкуп</dt>
                    <dd>
                        {number(Math.ceil(tile.price * .55))}
                    </dd>
                </div>
                {tile.build > 0 && <div>
                    <dt>Дом / отель</dt>
                    <dd>
                        {number(tile.build)}
                    </dd>
                </div>}
            </dl>
            {tile.rents.length > 0 ? <div className="mono-rents">
                {tile.rents.map((rent, i) => <div key={i}>
                    <span>
                        {i === 0 ? 'Без зданий' : i === 5 ? 'С отелем' : i + ' дом' + (i === 1 ? '' : 'а')}
                    </span>
                    <b>
                        {number(rent)}
                    </b>
                </div>)}
                <small>Полная отрасль удваивает аренду без зданий. Заложенный актив не приносит аренду.</small>
            </div> : <p>
                {tile.kind === 'rail' ? 'Аренда за 1 / 2 / 3 / 4 аэропорта: 25 / 50 / 100 / 200.' : 'Аренда — сумма костей ×4 за одно предприятие или ×10 за оба.'}
            </p>}
            {canManage && <div className="mono-property-actions">
                {tile.build > 0 && <>
                    <button className="mono-secondary" disabled={blocked || !!s.debt || a.houses >= 5 || a.mortgaged} onClick={() => go('build')}>Построить за {number(tile.build)}</button>
                    {lastBuilding && <button className="mono-secondary" disabled={blocked || !!s.debt} onClick={() => go('start_build_auction')}>Аукцион последнего {a.houses === 4 ? 'отеля' : 'дома'}</button>}
                    <button className="mono-secondary" disabled={blocked || !a.houses} onClick={() => go('sell')}>Продать здание за {number(tile.build / 2)}</button>
                    {game.tiles.some(t => t.group === tile.group && s.properties[t.id]?.houses > 0) && <button className="mono-secondary" disabled={blocked} onClick={() => go('sell_group')}>Продать все здания отрасли</button>}
                </>}
                <button className="mono-secondary" disabled={blocked || !!s.debt && a.mortgaged} onClick={() => go(a.mortgaged ? 'redeem' : 'mortgage')}>
                    {a.mortgaged ? 'Выкупить за ' + number(Math.ceil(tile.price * .55)) : 'Заложить за ' + number(tile.price / 2)}
                </button>
                <small>Сервер проверит равномерность застройки, запас домов и платёжеспособность. Продажа всех зданий помогает, если отель нельзя обменять на дома банка.</small>
            </div>}
        </> : <p>
            {({ 0: 'Прохождение старта: +200.', 4: 'Налог: 200 в банк.', 38: 'Налог: 100 в банк.', 10: 'В гостях — без штрафа. Из тюрьмы: дубль, 50 или карта выхода.', 20: 'Бесплатная стоянка. Налоговый приз не начисляется.', 30: 'Отправляйтесь в тюрьму, без выплаты за старт.' } as Record<number, string>)[tile.id] ?? 'Карту и её эффект определяет сервер.'}
        </p>}
    </section>;
}
function Deals({ game, onTrade }: {
    game: Model;
    onTrade: () => void;
}) {
    const room = game.room!, s = stateOf(room), me = s.players.find(p => p.id === room.you), blocked = disabled(game), offer = s.contract_offer;
    const mayTrade = s.phase === 'playing' && !!me && !me.out && !s.auction && s.pending === null && !s.trade && !offer;
    const mayContract = mayTrade && !s.debt && (s.contracts?.length ?? 0) < 8;
    const go = (action: string) => void game.mutate(action);
    return <section className="mono-deals">
        <h2>Сделки</h2>
        {s.trade ? <TradeSummary game={game}/> : <>
            <p>Обмен активами, деньгами и картами выхода — только по согласию обоих.</p>
            <button className="mono-secondary" disabled={blocked || !mayTrade} onClick={onTrade}><Handshake size={18}/>Предложить обмен</button>
        </>}

        {s.mode === 'friendly' ? <>
            <h3>Будущие договорённости</h3>
            <p>Владелец освобождает выбранного игрока от аренды своих активов на 1–12 общих завершённых ходов. Это не заём и не обещание платежа в будущем.</p>
            {offer ? <section className="mono-offer">
                <h4>{playerName(room, offer.offerer)} → {playerName(room, offer.target)}</h4>
                <p>
                    <strong>Без аренды:</strong>
                    {tileNames(game.tiles, offer.tiles)}
                </p>
                <p>Срок: {offer.turns} общих завершённых ходов с момента принятия — не кругов и не только ваших ходов.</p>
                <p><strong>Разовая плата владельцу: {number(offer.fee)}</strong> — сразу при принятии. При смене владельца актива или выходе участника льгота прекращается. Плата не возвращается.</p>
                {offer.target === room.you ? <div className="mono-action-row">
                    <button className="mono-primary" disabled={blocked} onClick={() => go('accept_contract')}>Принять за {number(offer.fee)}</button>
                    <button className="mono-secondary" disabled={blocked} onClick={() => go('reject_contract')}>Отклонить</button>
                </div> : offer.offerer === room.you ? <button className="mono-secondary" disabled={blocked} onClick={() => go('cancel_contract')}>Отменить предложение</button> : <p>Ждём ответа получателя.</p>}
            </section> : <ContractForm game={game} blocked={blocked || !mayContract}/>}

            <h3>Действуют сейчас · {s.contracts?.length ?? 0}</h3>
            <p>Общий счётчик хода: {s.turn_number ?? 0}. Ход считается после завершения любого игрока, не после круга.</p>
            {s.contracts?.length ? s.contracts.map(c => <article className="mono-agreement" key={c.id}>
                <strong>{playerName(room, c.owner)} → {playerName(room, c.beneficiary)}</strong>
                <p>
                    {tileNames(game.tiles, c.tiles)}
                </p>
                <p>Без аренды до хода {c.expires_turn}, не включая его · осталось {Math.max(0, c.expires_turn - (s.turn_number ?? 0))} общих ходов.</p>
                <small>Плата {number(c.fee)} уже внесена и не возвращается. Нельзя отозвать; смена владельца актива или выход участника прекращает льготу.</small>
            </article>) : <p>Действующих договоров нет.</p>}
        </> : <p className="mono-mode-description">Будущие договоры доступны только в режиме «Дружеская». В стандартных режимах нет займов и обещаний будущей аренды.</p>}

    </section>;
}
function TradeSummary({ game }: {
    game: Model;
}) {
    const room = game.room!, trade = room.state.trade as ExtendedTrade, blocked = disabled(game);
    const cost = (ids: number[], redeem: number[] = []) => ids.reduce((sum, id) => { const tile = game.tiles.find(t => t.id === id); return sum + (room.state.properties[id]?.mortgaged ? Math.ceil((tile?.price ?? 0) * (redeem.includes(id) ? .55 : .05)) : 0); }, 0);
    const terms = (ids: number[], cash: number, cards: string[] = [], redeem: number[] = []) => <>
        <p>
            {tileNames(game.tiles, ids)}
        </p>
        <p>Деньги: {number(cash)}{cards.length ? ' · Карты: ' + cards.map(cardName).join(', ') : ''}</p>
        {ids.some(id => room.state.properties[id]?.mortgaged) && <p>Получатель платит банку: <strong>
                {number(cost(ids, redeem))}
            </strong>. {redeem.length ? 'Выкуп сразу: ' + tileNames(game.tiles, redeem) + '. ' : 'Остальные залоги остаются с уплатой 10%.'}</p>}
    </>;
    return <article className="mono-offer">
        <h3>Обмен на рассмотрении</h3>
        <h4>{playerName(room, trade.from)} отдаёт</h4>
        {terms(trade.give, trade.cash, trade.give_cards, trade.redeem_give)}
        <h4>{playerName(room, trade.target)} отдаёт</h4>
        {terms(trade.take, trade.ask, trade.take_cards, trade.redeem_take)}
        <p>Получение залога требует немедленно заплатить 10% залоговой суммы либо выкупить его целиком. Все суммы проверяются при принятии.</p>
        {trade.target === room.you ? <div className="mono-action-row">
            <button className="mono-primary" disabled={blocked} onClick={() => void game.mutate('accept_trade')}>Принять обмен</button>
            <button className="mono-secondary" disabled={blocked} onClick={() => void game.mutate('reject_trade')}>Отклонить</button>
        </div> : trade.from === room.you ? <button className="mono-secondary" disabled={blocked} onClick={() => void game.mutate('cancel_trade')}>Отменить предложение</button> : <p>Ждём ответа получателя.</p>}
    </article>;
}
function ContractForm({ game, blocked }: {
    game: Model;
    blocked: boolean;
}) {
    const room = game.room!, [target, setTarget] = useState(room.state.players.find(p => p.id !== room.you && !p.out)?.id ?? ''), [tiles, setTiles] = useState<number[]>([]), [turns, setTurns] = useState(3), [fee, setFee] = useState('0');
    const own = game.tiles.filter(t => room.state.properties[t.id]?.owner === room.you);
    return <details className="mono-contract-form">
        <summary>Предложить освобождение от аренды</summary>
        <form onSubmit={async (e) => { e.preventDefault(); if (await game.mutate('propose_contract', { target, contract_tiles: tiles, contract_turns: turns, contract_fee: Number(fee) }))
        setTiles([]); }}>
            <label>Кому<select value={target} onChange={e => setTarget(e.target.value)}>
                    {room.state.players.filter(p => p.id !== room.you && !p.out).map(p => <option key={p.id} value={p.id}>
                        {p.name}
                    </option>)}
                </select></label>
            <fieldset>
                <legend>Ваши активы без аренды для получателя</legend>
                {own.length ? own.map(t => <label className="mono-checkbox" key={t.id}>
                    <input type="checkbox" checked={tiles.includes(t.id)} onChange={() => setTiles(ids => ids.includes(t.id) ? ids.filter(id => id !== t.id) : [...ids, t.id])}/>
                    {t.name}
                </label>) : <p>Сначала приобретите актив.</p>}
            </fieldset>
            <div className="mono-form-row">
                <label>Общих ходов<select value={turns} onChange={e => setTurns(Number(e.target.value))}>
                        {Array.from({ length: 12 }, (_, i) => <option key={i + 1}>
                            {i + 1}
                        </option>)}
                    </select></label>
                <label>Разовая плата вам<input type="number" min="0" max="1000000" value={fee} onChange={e => setFee(e.target.value)}/></label>
            </div>
            <p>{playerName(room, target)} платит {number(Number(fee) || 0)} сразу при принятии. Льгота на {turns} общих завершённых ходов, не кругов и не только ваших ходов. Принятый договор отозвать нельзя. При смене владельца актива или выходе участника льгота прекращается; плата не возвращается.</p>
            <button className="mono-primary" disabled={blocked || !target || !tiles.length || !Number.isSafeInteger(Number(fee)) || Number(fee) < 0 || Number(fee) > 1000000}>Отправить условия</button>
        </form>
    </details>;
}
function TradeForm({ room, tiles, blocked, onSubmit }: {
    room: Room;
    tiles: Tile[];
    blocked: boolean;
    onSubmit: (body: Record<string, unknown>) => Promise<void>;
}) {
    const [target, setTarget] = useState(room.state.players.find(p => p.id !== room.you && !p.out)?.id ?? ''), [give, setGive] = useState<number[]>([]), [take, setTake] = useState<number[]>([]), [cash, setCash] = useState('0'), [ask, setAsk] = useState('0'), [giveCards, setGiveCards] = useState<string[]>([]), [takeCards, setTakeCards] = useState<string[]>([]), [redeemGive, setRedeemGive] = useState<number[]>([]), [redeemTake, setRedeemTake] = useState<number[]>([]);
    const toggle = <T,>(value: T, values: T[], set: (v: T[]) => void) => set(values.includes(value) ? values.filter(v => v !== value) : [...values, value]);
    const options = (owner: string, ids: number[], set: (v: number[]) => void, cards: string[], setCards: (v: string[]) => void, redeem: number[], setRedeem: (v: number[]) => void) => <>
        {tiles.filter(t => room.state.properties[t.id]?.owner === owner).map(t => { const a = room.state.properties[t.id], built = tiles.some(other => other.group === t.group && room.state.properties[other.id]?.houses > 0); return <div key={t.id}>
            <label className="mono-checkbox">
                <input type="checkbox" checked={ids.includes(t.id)} disabled={built} onChange={() => { toggle(t.id, ids, set); setRedeem(redeem.filter(id => id !== t.id)); }}/>
                {t.name}
                {a.mortgaged ? ' · залог' : ''}
                {built ? ' · сначала продать здания' : ''}
            </label>
            {a.mortgaged && ids.includes(t.id) && <label className="mono-checkbox mono-redemption"><input type="checkbox" checked={redeem.includes(t.id)} onChange={() => toggle(t.id, redeem, setRedeem)}/>Получатель выкупает сразу за {number(Math.ceil(t.price * .55))} (иначе 10%: {number(Math.ceil(t.price * .05))})</label>}
        </div>; })}
        {[...new Set(room.state.players.find(p => p.id === owner)?.cards ?? [])].map(card => <label className="mono-checkbox" key={card}>
            <input type="checkbox" checked={cards.includes(card)} onChange={() => toggle(card, cards, setCards)}/>
            {cardName(card)}
        </label>)}
    </>;
    const bankCost = (ids: number[], redeem: number[]) => ids.reduce((sum, id) => sum + (room.state.properties[id]?.mortgaged ? Math.ceil((tiles.find(t => t.id === id)?.price ?? 0) * (redeem.includes(id) ? .55 : .05)) : 0), 0);
    return <form className="mono-trade-form" onSubmit={e => { e.preventDefault(); void onSubmit({ target, give, take, cash: Number(cash), ask: Number(ask), give_cards: giveCards, take_cards: takeCards, redeem_give: redeemGive, redeem_take: redeemTake }); }}>
        <p>Сделка выполняется только после согласия получателя. Активы с застройкой отрасли сначала нужно освободить от зданий.</p>
        <label>Кому предложить<select value={target} onChange={e => { setTarget(e.target.value); setTake([]); setTakeCards([]); setRedeemTake([]); }}>
                {room.state.players.filter(p => p.id !== room.you && !p.out).map(p => <option key={p.id} value={p.id}>
                    {p.name}
                </option>)}
            </select></label>
        <div className="mono-trade-columns">
            <fieldset>
                <legend>Вы отдаёте</legend>
                {options(room.you, give, setGive, giveCards, setGiveCards, redeemGive, setRedeemGive)}
                <label>Ваши деньги<input type="number" min="0" max="1000000" value={cash} onChange={e => setCash(e.target.value)}/></label>
            </fieldset>
            <fieldset>
                <legend>Вы получаете</legend>
                {options(target, take, setTake, takeCards, setTakeCards, redeemTake, setRedeemTake)}
                <label>Деньги получателя<input type="number" min="0" max="1000000" value={ask} onChange={e => setAsk(e.target.value)}/></label>
            </fieldset>
        </div>
        <div className="mono-trade-total">
            <strong>Итог предложения</strong>
            <p>Вы отдаёте: {tileNames(tiles, give)}; {number(Number(cash) || 0)}; карт {giveCards.length}.</p>
            <p>Вы получаете: {tileNames(tiles, take)}; {number(Number(ask) || 0)}; карт {takeCards.length}.</p>
            <p>Дополнительно банку за залоги: вы {number(bankCost(take, redeemTake))}, получатель {number(bankCost(give, redeemGive))}.</p>
        </div>
        <button className="mono-primary" disabled={blocked || !target || (!give.length && !take.length && !giveCards.length && !takeCards.length && !Number(cash) && !Number(ask)) || ![Number(cash), Number(ask)].every(v => Number.isSafeInteger(v) && v >= 0 && v <= 1000000)}>Отправить предложение</button>
    </form>;
}
function RoomMenu({ game, onRules, onInvite, onResign }: {
    game: Model;
    onRules: () => void;
    onInvite: () => void;
    onResign: () => void;
}) { const room = game.room!, s = stateOf(room), me = s.players.find(p => p.id === room.you); return <section className="mono-menu">
        <h2>Меню партии</h2>
        <p>{modeNames[s.mode ?? 'classic']} · {room.title}</p>
        {s.game_deadline && <p>Конец партии: {new Date(s.game_deadline).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</p>}
        <p>Код комнаты: <code>
                {room.code}
            </code></p>
        <button className="mono-secondary" onClick={onInvite}><Copy size={18}/>Копировать приглашение</button>
        <button className="mono-secondary" onClick={onRules}><Info size={18}/>Правила и режим</button>
        <button className="mono-secondary" onClick={() => void game.refresh()} disabled={game.busy}><RefreshCw size={18}/>Обновить состояние</button>
        <button className="mono-secondary" onClick={game.lobby} disabled={game.busy || !!game.pending}><DoorOpen size={18}/>К списку комнат</button>
        {s.phase === 'lobby' && <button className="mono-secondary" disabled={disabled(game)} onClick={() => void game.mutate('leave')}>Покинуть комнату</button>}
        {s.phase === 'playing' && me && !me.out && <button className="mono-danger" onClick={onResign}><Flag size={18}/>Сдаться в этой партии</button>}
        <small>Только игровые деньги партии. Закрытие окна не означает сдачу.</small>
    </section>; }
function RoomChat({ game, text, setText }: {
    game: Model;
    text: string;
    setText: (value: string | ((current: string) => string)) => void;
}) {
    const [tab, setTab] = useState<'chat' | 'log'>('chat'), list = useRef<HTMLDivElement>(null), nearEnd = useRef(true), room = game.room!, messages = room.messages ?? [];
    useEffect(() => { if (nearEnd.current && list.current)
        list.current.scrollTop = list.current.scrollHeight; }, [messages.at(-1)?.id, room.state.log.at(-1), tab]);
    async function send() { if (!text.trim())
        return; const sent = text; if (await game.mutate('chat', { text: sent })) {
        setText(current => current === sent ? '' : current);
        void game.refresh();
    } }
    return <section className="mono-chat">
        <div className="mono-chat-tabs" aria-label="Сообщения и события">
            <button aria-pressed={tab === 'chat'} onClick={() => setTab('chat')}><MessageCircle size={18}/>Чат</button>
            <button aria-pressed={tab === 'log'} onClick={() => setTab('log')}>Ход партии</button>
        </div>
        <div ref={list} className="mono-chat-messages" role="log" aria-label={tab === 'chat' ? 'Сообщения комнаты' : 'События партии'} aria-live="polite" onScroll={() => { const el = list.current!; nearEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60; }}>
            {tab === 'chat' ? (messages.length ? messages.map(m => <article className={'mono-chat-message' + (m.player === room.you ? ' is-you' : '')} key={m.id}>
                <strong>
                    {playerName(room, m.player)}
                    <time>
                        {new Date(m.at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                    </time>
                </strong>
                <p>
                    {m.text}
                </p>
            </article>) : <p className="mono-chat-empty">Напишите друзьям. Черновик сохранится при переключении разделов.</p>) : room.state.log.map((entry, i) => <p className="mono-log-entry" key={i}>
                {entry}
            </p>)}
        </div>
        <form onSubmit={e => { e.preventDefault(); void send(); }}>
            <label className="mono-chat-label">Сообщение<input value={text} onChange={e => setText(e.target.value)} maxLength={500} placeholder="Напишите участникам…"/></label>
            <button className="mono-primary" aria-label="Отправить сообщение" disabled={disabled(game) || !text.trim()}>
                <Send size={20}/>
            </button>
        </form>
        <small>Виден только участникам комнаты · до 500 символов</small>
    </section>;
}
function Rules({ game }: {
    game: Model;
}) {
    const s = game.room ? stateOf(game.room) : null;
    const synopsis = game.rulesSynopsis ?? [];
    const config = game.config ?? {};
    return <section className="mono-rules mono-rules-v2">
        <p>
            <strong>Режим: {modeNames[s?.mode ?? 'classic']}.</strong>
            {s?.mode?.startsWith('timed') ? 'Таймер и начальные условия задаёт сервер выбранного режима. При окончании времени сравнивается капитал.' : 'Партия без лимита длительности. Бездействие само по себе не означает банкротство.'}
        </p>
        {synopsis.length > 0 && <ul className="mono-rule-synopsis">
            {synopsis.map((line, i) => <li key={i}>
                {line}
            </li>)}
        </ul>}
        {s?.mode?.startsWith('timed') && <p>
            <strong>Домашний режим:</strong>
            {game.modes?.find(m => m.id === s.mode)?.description}
            {typeof config.timed_valuation === 'string' ? config.timed_valuation : ''}
        </p>}
        <h3>Цель и деньги</h3>
        <p>Классическая основа: остаться последним платёжеспособным участником. Начальный капитал 1500, за прохождение старта 200. Игровые деньги не связаны с общим балансом приложения.</p>
        <h3>Активы и аукционы</h3>
        <p>Свободный актив можно купить или передать на аукцион. Полная цветовая группа удваивает аренду без зданий. Стройте равномерно до четырёх домов, затем отель; банк ограничен 32 домами и 12 отелями. Бесплатная стоянка не даёт налоговый приз.</p>
        <h3>Кости и тюрьма</h3>
        <p>Дубль даёт повторный бросок; три дубля подряд отправляют в тюрьму. Выход: заплатить 50, использовать карту или выбросить дубль за три попытки. На третьей неудаче платёж обязателен.</p>
        <h3>Залог и долг</h3>
        <p>Здания продаются за половину цены. Для залога цветовую группу нужно освободить от зданий. Выкуп — залоговая сумма +10%. При получении залога в обмене сразу уплачивается 10% либо полный выкуп. Если денег не хватает, распродайте здания и закладывайте активы; банкротство — только при невозможности расплатиться.</p>
        <h3>Обмены и договорённости</h3>
        <p>Деньги, активы без зданий и карты выхода можно обменивать по взаимному согласию. Предложение можно отклонить, а автор может его отменить. Стандартные правила не разрешают займы и обещания будущих платежей.</p>
        <p>Только «Дружеская»: владелец может предложить освобождение выбранного игрока от аренды перечисленных активов на 1–12 общих завершённых ходов. Получатель платит разовую сумму сразу при принятии. Принятый договор нельзя отозвать. Смена владельца актива или выход участника прекращает льготу; плата не возвращается. Условия и срок видны в «Сделках».</p>
        <h3>Сдача и закрытие окна</h3>
        <p>«Сдаться» в меню — добровольная онлайн-уступка с отдельным подтверждением и окончательным выходом из партии. Это не официальное банкротство из-за долга. Закрытие окна не останавливает игру и не сдаёт её.</p>
        <small>Основа: официальные правила Hasbro C1009F22; тематические предприятия соответствуют улицам, аэропорты — вокзалам. Сервер рассчитывает броски, карты и платежи.</small>
    </section>;
}
