export const gameIds = ['slots', 'fishing', 'dice', 'darts', 'bowling', 'basketball', 'football', 'coin', 'roulette', 'blackjack', 'mines', 'wheel'] as const;
export type GameId = typeof gameIds[number];
export function gameFromUrl():GameId|null {
 const value=new URLSearchParams(window.location.search).get('game');
 return gameIds.find(id=>id===value)??null;
}
export interface GameInfo { fishing_world_version?:1|null; gameplay_version?: 1 | null; id: GameId; title: string; description: string; rules: string[]; min_bet: number; max_bet: number; payouts: Record<string, number>; probabilities: Record<string, number>; rules_version?: number | string; }
export interface Round { id: string; game: GameId; status: 'active' | 'won' | 'lost' | 'push' | 'caught' | 'expired'; bet: number; payout: number; balance: number; version: number; created_at: string; available_at?: string | null; state: Record<string, unknown>; result: Record<string, unknown> | null; rules_version?: number | string; }
export interface Wallet { balance: number; inventory_value: number; daily_available: boolean; rod_level: number; }
export interface Catch { species: string; rarity: string; count: number; value: number; weight: number; }
export type FishingLocationId = 'shore'|'river'|'mountain'|'golden';
export type FishingSkinId = 'angler'|'bear';
export interface LocationFish { species:string; rarity:string; value:number; min_weight:number; max_weight:number; probability:number; }
export interface FishingLocation { id:FishingLocationId; title:string; description:string; tagline?:string; story_title?:string; story?:string; landmark?:string; featured_species?:string[]; min_rod_level:number; unlocked:boolean; value_multiplier:number; theme:string; preview_rod_level:number; fish:LocationFish[]; }
export interface FishingSkin { id:FishingSkinId; title:string; description:string; min_rod_level:number; unlocked:boolean; }
export interface Inventory { items: Catch[]; rod_level: number; upgrade_cost?: number | null; next_upgrade_cost?: number | null; max_rod_level?: number; collection?: string[]; record_weight?: number; world_version?:1; selected_location?:FishingLocationId; selected_skin?:FishingSkinId; locations?:FishingLocation[]; skins?:FishingSkin[]; species?:{name:string;rarity:string}[]; }
export interface Leaderboard { items: {rank: number; nickname: string; score: number}[]; self: {rank: number | null; score: number}; }
export const points = (value: number) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 4 }).format(value);
export const numberValue = (data: Record<string, unknown> | null, key: string, fallback = 0): number => typeof data?.[key] === 'number' ? data[key] as number : fallback;
export const stringValue = (data: Record<string, unknown> | null, key: string): string => typeof data?.[key] === 'string' ? data[key] as string : '';
export const strings = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
export const numbers = (value: unknown): number[] => Array.isArray(value) ? value.filter((item): item is number => typeof item === 'number') : [];
export const labels: Record<string, string> = { cherry: 'Вишня', lemon: 'Лимон', bell: 'Колокол', diamond: 'Алмаз', seven: 'Семёрка', heads: 'Орёл', tails: 'Решка', red: 'Красное', black: 'Чёрное', green: 'Зелёное', even: 'Чётное', odd: 'Нечётное', low: '1–3', high: '4–6', common: 'Обычная', uncommon: 'Необычная', rare: 'Редкая', epic: 'Эпическая', legendary: 'Легендарная', won: 'Победа', lost: 'Без выигрыша', push: 'Возврат', caught: 'Улов получен', active: 'Игра продолжается', expired: 'Раунд истёк' };
export const label = (value: string):string => {
  if(labels[value])return labels[value];
  if(value.startsWith('triple_'))return 'Три одинаковых: '+label(value.slice(7));
  const rod=/^rod_(\d+)_(.+)$/.exec(value);if(rod)return 'Удочка '+rod[1]+' · '+label(rod[2]);
  const safe=/^first_safe_mines_(\d+)$/.exec(value);if(safe)return 'Первая безопасная · мин '+safe[1];
  const extra:Record<string,string>={pair:'Ровно пара',other:'Остальные исходы',win:'Победа',lose:'Проигрыш',success:'Попадание',miss:'Промах',number:'Точное число',zero:'Ноль',natural:'Натуральный блэкджек',initial_natural:'Начальный блэкджек',initial_each_card:'Каждая начальная карта',no_reveal_cashout:'Возврат до первого открытия',edge:'Коэффициент формулы',maximum_multiplier:'Максимальный множитель'};
  return extra[value]??value;
};
export function resultText(round: Round): string {
  if (round.status === 'active') return round.game === 'fishing' ? 'Поплавок на воде' : 'Ваш ход';
  const result = round.result;
  switch (round.game) {
    case 'slots': return strings(result?.symbols).map(label).join(' · ') || label(round.status);
    case 'fishing': if(result?.escaped===true)return ({line_broke:'Леска оборвалась',slack_line:'Рыба сошла с крючка',missed_hook:'Подсечка не удалась',fish_escaped:'Рыба ушла'} as Record<string,string>)[stringValue(result,'reason')]??'Рыба ушла';return [stringValue(result, 'species'), label(stringValue(result, 'rarity')), result?.weight != null ? points(numberValue(result, 'weight')) + ' кг' : ''].filter(Boolean).join(' · ') || label(round.status);
    case 'dice': return 'Выпало ' + numberValue(result, 'value');
    case 'darts': return numberValue(result, 'value') + ' очков';
    case 'bowling': return 'Сбито кеглей: ' + numberValue(result, 'value');
    case 'basketball': return result?.success === true ? 'Точное попадание' : 'Мимо корзины';
    case 'football': return result?.success === true ? 'Гол!' : 'Мимо ворот';
    case 'coin': return label(stringValue(result, 'side'));
    case 'roulette': return numberValue(result, 'number') + ' · ' + label(stringValue(result, 'color'));
    case 'wheel': return 'Множитель ×' + points(numberValue(result, 'multiplier'));
    case 'blackjack': { const player=numberValue(result,'player_total',numberValue(round.state,'player_total')); const dealer=numberValue(result,'dealer_total',numberValue(round.state,'dealer_total')); return player>21?'Перебор: у вас '+player+' очков':dealer>21?'Перебор у дилера: '+dealer+' очков':'У вас '+player+', у дилера '+dealer+' очков'; }
    case 'mines': return round.status==='lost'?'Вы открыли мину. Раунд окончен.':'Безопасных клеток: '+numbers(round.state.cells).length+'. Выплата зафиксирована.';
    default: return label(round.status);
  }
}
