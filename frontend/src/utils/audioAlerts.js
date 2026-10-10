/**
 * Audio Chimes & Speech Synthesis Alert Engine
 * Uses Web Audio API for instant crystal alert sounds (0 network latency)
 * and HTML5 Speech Synthesis for voice trade announcements.
 */

class AudioAlertEngine {
  constructor() {
    this.audioCtx = null;
    this.isMuted = localStorage.getItem('trade_intel_audio_muted') === 'true';
    this.isVoiceEnabled = localStorage.getItem('trade_intel_voice_enabled') !== 'false';
  }

  _initContext() {
    if (!this.audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.audioCtx = new AudioContext();
      }
    }
    if (this.audioCtx && this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }
  }

  toggleMute() {
    this.isMuted = !this.isMuted;
    localStorage.setItem('trade_intel_audio_muted', this.isMuted ? 'true' : 'false');
    if (!this.isMuted) {
      this.playChime('SUCCESS');
    }
    return this.isMuted;
  }

  /**
   * Plays a synthesized chime tone:
   * - 'ALERT': Dual-tone alert for new trade discovery (880Hz -> 1320Hz)
   * - 'SUCCESS': Uplifting harmonic chime for Target Hit (523Hz -> 659Hz -> 784Hz)
   * - 'WARNING': Soft descending tone for Stop Loss hit
   */
  playChime(type = 'ALERT') {
    if (this.isMuted) return;
    try {
      this._initContext();
      if (!this.audioCtx) return;

      const now = this.audioCtx.currentTime;

      if (type === 'ALERT') {
        // High-conviction dual bell
        const osc1 = this.audioCtx.createOscillator();
        const gain1 = this.audioCtx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(880, now);
        osc1.frequency.exponentialRampToValueAtTime(1320, now + 0.15);
        gain1.gain.setValueAtTime(0.18, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
        osc1.connect(gain1);
        gain1.connect(this.audioCtx.destination);
        osc1.start(now);
        osc1.stop(now + 0.5);
      } else if (type === 'SUCCESS') {
        // Target achieved triple chime
        [523.25, 659.25, 783.99].forEach((freq, i) => {
          const osc = this.audioCtx.createOscillator();
          const gain = this.audioCtx.createGain();
          const startTime = now + i * 0.1;
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(freq, startTime);
          gain.gain.setValueAtTime(0.15, startTime);
          gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.6);
          osc.connect(gain);
          gain.connect(this.audioCtx.destination);
          osc.start(startTime);
          osc.stop(startTime + 0.6);
        });
      } else if (type === 'WARNING') {
        // Descending SL alert
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(220, now + 0.35);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        osc.connect(gain);
        gain.connect(this.audioCtx.destination);
        osc.start(now);
        osc.stop(now + 0.35);
      }
    } catch (e) {
      console.warn('Audio chime error:', e);
    }
  }

  /**
   * Speaks trade announcement aloud via Speech Synthesis
   */
  speak(text) {
    if (this.isMuted || !this.isVoiceEnabled) return;
    if ('speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel(); // cancel previous
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;
        utterance.volume = 0.85;
        window.speechSynthesis.speak(utterance);
      } catch (e) {
        console.warn('Speech synthesis error:', e);
      }
    }
  }

  announceTradeSignal(symbol, action, price) {
    this.playChime('ALERT');
    this.speak(`New ${action} pick on ${symbol} at rupees ${price}`);
  }

  announcePaperExit(symbol, outcome, pnl) {
    if (outcome.includes('TARGET')) {
      this.playChime('SUCCESS');
      this.speak(`Target achieved on ${symbol}! Profit of ${Math.round(pnl)} rupees.`);
    } else {
      this.playChime('WARNING');
      this.speak(`Stop loss triggered on ${symbol}. Loss of ${Math.round(Math.abs(pnl))} rupees.`);
    }
  }
}

export const audioAlerts = new AudioAlertEngine();
