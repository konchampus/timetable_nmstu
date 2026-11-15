import { useCallback, useEffect, useRef } from 'react';
import type { GameId } from './types';
const voices: Record<GameId, {type:OscillatorType;pitch:number;tempo:number}> = { slots:{type:'square',pitch:1.5,tempo:0.04}, fishing:{type:'sine',pitch:1.1,tempo:0.11}, dice:{type:'triangle',pitch:0.7,tempo:0.045}, darts:{type:'sine',pitch:2.2,tempo:0.04}, bowling:{type:'triangle',pitch:0.4,tempo:0.08}, basketball:{type:'sine',pitch:0.65,tempo:0.09}, football:{type:'triangle',pitch:0.55,tempo:0.07}, coin:{type:'sine',pitch:2.4,tempo:0.06}, roulette:{type:'square',pitch:0.8,tempo:0.045}, blackjack:{type:'triangle',pitch:1.2,tempo:0.045}, mines:{type:'sine',pitch:1.8,tempo:0.08}, wheel:{type:'triangle',pitch:1.4,tempo:0.075} };
type Cue = 'tap' | 'start' | 'win' | 'lose' | 'catch' | 'reveal';
const phrases: Record<Cue, number[]> = { tap: [440], start: [220, 330, 440], win: [523.25, 659.25, 783.99, 1046.5], lose: [246.94, 196], catch: [392, 587.33, 783.99], reveal: [660, 880] };
export function useGameAudio(enabled: boolean) {
  const context = useRef<AudioContext | null>(null);
  const enabledRef = useRef(enabled); enabledRef.current = enabled;
  const oscillators = useRef(new Set<OscillatorNode>());
  const stop = useCallback(() => { for (const node of oscillators.current) { try { node.stop(); } catch { /* Already stopped. */ } } oscillators.current.clear(); }, []);
  const unlock = useCallback((enableFromGesture = false) => {
    if (enableFromGesture) enabledRef.current = true;
    if (!enabledRef.current) return;
    try { context.current ??= new AudioContext(); if (context.current.state === 'suspended') void context.current.resume().catch(() => undefined); } catch { /* Audio is optional; game state never depends on a device API. */ }
  }, []);
  const play = useCallback((cue: Cue, game?:GameId) => {
    const audio = context.current;
    if (!enabledRef.current || !audio || audio.state !== 'running' || document.hidden) return;
    const voice=game?voices[game]:{type:'triangle' as OscillatorType,pitch:1,tempo:0.075};
    const notes = cue==='start'&&game==='slots'?[220,330,220,440,330,660]:phrases[cue];
    for (const [index, note] of notes.entries()) {
      const frequency=note*voice.pitch;const start = audio.currentTime + index * voice.tempo;
      const oscillator = audio.createOscillator(); const gain = audio.createGain();
      oscillator.type = cue === 'catch' ? 'sine' : voice.type; oscillator.frequency.setValueAtTime(frequency, start);
      oscillator.frequency.exponentialRampToValueAtTime(frequency * 0.99, start + 0.16);
      gain.gain.setValueAtTime(0, start); gain.gain.linearRampToValueAtTime(0.055 / notes.length, start + 0.008); gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.22);
      oscillator.connect(gain); gain.connect(audio.destination); oscillator.start(start); oscillator.stop(start + 0.24);
      oscillators.current.add(oscillator);
      oscillator.onended = () => { oscillators.current.delete(oscillator); oscillator.disconnect(); gain.disconnect(); };
    }
  }, []);
  useEffect(() => { if (!enabled) { stop(); if (context.current?.state === 'running') void context.current.suspend().catch(() => undefined); } }, [enabled, stop]);
  useEffect(() => { const pause = () => { if (document.hidden && context.current) { stop(); void context.current.suspend().catch(() => undefined); } }; document.addEventListener('visibilitychange', pause); return () => { document.removeEventListener('visibilitychange', pause); stop(); if (context.current) void context.current.close().catch(() => undefined); context.current = null; }; }, [stop]);
  const pause = useCallback(() => { stop(); if (context.current?.state === 'running') void context.current.suspend().catch(() => undefined); }, [stop]);
  return { unlock, play, pause };
}
