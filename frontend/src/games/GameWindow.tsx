import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import './game-window.css';

export interface GameWindowProps {
  visible?: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  tools?: ReactNode;
  game?: string;
  children: ReactNode;
}

// Shared by independently mounted game surfaces; releasing one must not unlock another.
let scrollLocks = 0;
let previousBodyOverflow = '';
let previousRootOverflow = '';
function lockScroll() {
  if (scrollLocks++ === 0) {
    previousBodyOverflow = document.body.style.overflow;
    previousRootOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
  }
  return () => {
    if (--scrollLocks === 0) {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousRootOverflow;
    }
  };
}

export default function GameWindow({ visible = true, onClose, title, subtitle, tools, game, children }: GameWindowProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  useEffect(() => {
    if (!visible || !dialog.current) return;
    const element = dialog.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    element.showModal();
    const unlock = lockScroll();
    heading.current?.focus({ preventScroll: true });
    return () => {
      element.close();
      unlock();
      if (opener?.isConnected && opener.getClientRects().length && !opener.closest('[hidden], [inert]')) opener.focus({ preventScroll: true });
    };
  }, [visible]);

  if (typeof document === 'undefined') return null;
  return createPortal(
    <dialog ref={dialog} className="game-window" aria-labelledby={titleId} aria-describedby={subtitle ? descriptionId : undefined}
      onCancel={event => { event.preventDefault(); onClose(); }}>
      <div className="game-window-shell">
        <header className="game-window-header">
          <div className="game-window-title"><h2 ref={heading} id={titleId} tabIndex={-1}>{title}</h2>{subtitle && <p id={descriptionId}>{subtitle}</p>}</div>
          <div className="game-window-tools">{tools}<button type="button" className="game-window-close" aria-label="Закрыть игровое окно" title="Закрыть окно · Escape" onClick={onClose}><X size={22}/></button></div>
        </header>
        <div className="game-window-scroll"><div className="games is-playing game-window-content" data-game={game}>{children}</div></div>
      </div>
    </dialog>, document.body
  );
}
