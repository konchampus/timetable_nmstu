import {useLayoutEffect, useRef, useState} from 'react';
import type {CSSProperties} from 'react';
import './dice.css';

export type DiceProps = {
  /** Exactly two authoritative server values. Missing/invalid values stay neutral. */
  values: number[];
  /** Stable server roll marker, NOT the room version or local request counter. */
  rollId?: string | number;
  /** Local request pending: hide previous values behind a neutral waiting state. */
  rolling?: boolean;
};

type DieValue = 1 | 2 | 3 | 4 | 5 | 6;
const FACES: readonly DieValue[] = [1, 6, 2, 5, 3, 4];
const PIPS: Record<DieValue, readonly (readonly [number, number])[]> = {
  1: [[50, 50]],
  2: [[27, 27], [73, 73]],
  3: [[27, 27], [50, 50], [73, 73]],
  4: [[27, 27], [73, 27], [27, 73], [73, 73]],
  5: [[27, 27], [73, 27], [50, 50], [27, 73], [73, 73]],
  6: [[27, 25], [73, 25], [27, 50], [73, 50], [27, 75], [73, 75]],
};

/** Euler angles bring the requested face to the front; opposite faces sum to 7.
 * Kept pure/exported so consumers can verify all six orientations without a DOM.
 */
export function dieOrientation(value: number): readonly [number, number] {
  switch (value) {
    case 1: return [0, 0];
    case 2: return [-90, 0];
    case 3: return [0, -90];
    case 4: return [0, 90];
    case 5: return [90, 0];
    case 6: return [0, 180];
    default: return [0, 0];
  }
}

function isDieValue(value: number | undefined): value is DieValue {
  return Number.isInteger(value) && value! >= 1 && value! <= 6;
}

function PipFace({value}: {value: DieValue}) {
  return <svg className={'mono-dice__face mono-dice__face--' + value}
    viewBox="0 0 100 100" aria-hidden="true" focusable="false">
    <rect className="mono-dice__ivory" x="1" y="1" width="98" height="98" rx="13"/>
    <rect className="mono-dice__rim" x="5" y="5" width="90" height="90" rx="10"/>
    {PIPS[value].map(([x, y]) => <g key={x + ':' + y}>
      <circle className="mono-dice__pip-well" cx={x} cy={y + 1} r="9.2"/>
      <circle className="mono-dice__pip" cx={x} cy={y} r="7.5"/>
      <circle className="mono-dice__pip-light" cx={x - 2} cy={y - 2} r="1.6"/>
    </g>)}
  </svg>;
}

/** A presentation only: never chooses outcomes, dispatches actions, or awaits motion. */
export default function Dice({values, rollId, rolling = false}: DiceProps) {
  const previousRoll = useRef(rollId);
  const [motion, setMotion] = useState({sequence: 0, active: false});

  useLayoutEffect(() => {
    // A new local request may interrupt an old flight; a failed request must not
    // replay that old result when the neutral indicator disappears.
    if (rolling) setMotion(current => current.active ? {...current, active: false} : current);
  }, [rolling]);

  useLayoutEffect(() => {
    // The initial snapshot (also StrictMode's effect replay) must remain static.
    // Ignore absent markers without forgetting the last known one on reconnect.
    if (rollId === undefined || Object.is(previousRoll.current, rollId)) return;
    previousRoll.current = rollId;
    setMotion(current => ({sequence: current.sequence + 1, active: !window.matchMedia('(prefers-reduced-motion: reduce)').matches}));
  }, [rollId]);

  const pair = [values[0], values[1]];
  const complete = pair.every(isDieValue);
  const label = rolling ? 'Кости: бросок, ожидаем сервер' : complete
    ? 'Кости: ' + pair.join(' и ') + '. Сумма: ' + (pair[0] + pair[1])
    : 'Кости: результат ещё не получен';

  return <div className="mono-dice" role="img" aria-label={label}
    data-pending={rolling || undefined} data-roll-active={motion.active || undefined}>
    <div className="mono-dice__pair" aria-hidden="true">
      {pair.map((value, index) => {
        const known = isDieValue(value);
        const [x, y] = dieOrientation(value);
        const neutral = rolling || !known;
        return <div className="mono-dice__slot" key={index}>
          <span className="mono-dice__shadow" data-moving={!neutral && motion.active || undefined}
            key={'shadow-' + motion.sequence}/>
          <div className="mono-dice__camera">
            <div className="mono-dice__flight" key={motion.sequence}
              data-moving={!neutral && motion.active || undefined}
              style={{'--die-direction': index === 0 ? -1 : 1} as CSSProperties}
              onAnimationEnd={event => {
                if (event.target === event.currentTarget) {
                  setMotion(current => current.active ? {...current, active: false} : current);
                }
              }}>
              <div className="mono-dice__attitude" style={{visibility: neutral ? 'hidden' : undefined}}>
                <div className="mono-dice__cube" style={{transform: 'rotateX(' + x + 'deg) rotateY(' + y + 'deg)'}}>
                  {FACES.map(face => <PipFace key={face} value={face}/>)}
                </div>
              </div>
            </div>
          </div>
          {neutral && <span className="mono-dice__neutral" data-waiting={rolling || undefined}>
            <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">
              <rect x="8" y="8" width="32" height="32" rx="9"/>
              <path d="M19 24h10"/>
            </svg>
          </span>}
        </div>;
      })}
    </div>
    <span className="mono-dice__caption" aria-hidden="true">{rolling ? 'Бросок…' : complete ? pair[0] + ' + ' + pair[1] : 'Ждём бросок'}</span>
  </div>;
}
