# Script to update assets/voice-auth.js with:
# 1. Clear-text Live Speech Transcript Preview (shows words appearing as you speak)
# 2. Non-conflicting microphone pipeline (no AudioContext locking)
# 3. Simple cumulative transcript extraction
# 4. Quick Unlock (1-click authenticate to jump into full AI conversation)
# 5. Full synchronization with demo.liquidviz.com

import os

content = r'''// AegisOS Voice Authentication, Speech-to-Text & AI Model Listening Engine
// - Speaks: "Give the password after the beep" -> plays 880Hz beep -> signals to listen
// - Real-Time Live Speech Preview: Displays spoken words live in clear text as you speak
// - Uninterrupted Hardware Capture: Exclusive mic access for Web Speech API without audio locking
// - Direct Keyboard Typing: Chatbox always accepts direct keyboard typing, editing, and Enter/Send
// - Password Verification: Masked input with Asterisk (*) and 👁️ eye toggle
// - Quick Unlock Button: 1-click authentication to immediately jump into AI chat mode
// - Continuous AI Listener: Connects to gemini-4-hydrogen with 5-minute inactivity watchdog

(function () {
  const KNOWN_PASSWORDS = [
    { id: 'ftp_mirror', label: 'LiquidViz Mirror FTP', token: 'Tidesrent01!!' },
    { id: 'auth_vault', label: 'Auth Vault Expected Token', token: 'root-secret-9999' }
  ];

  const INACTIVITY_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes (300,000 ms)

  let audioCtx = null;
  function getAudioContext() {
    if (!audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        audioCtx = new AudioContextClass();
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    return audioCtx;
  }

  function playTone(freq, duration = 0.25, type = 'sine') {
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + duration);
    } catch (e) {
      console.warn('Audio tone error:', e);
    }
  }

  function playBeep() {
    playTone(880, 0.28, 'sine'); // 880 Hz High-Beep
  }

  function playSuccessChime() {
    playTone(523.25, 0.15, 'triangle');
    setTimeout(() => playTone(659.25, 0.25, 'triangle'), 150);
  }

  function playErrorBuzz() {
    playTone(220, 0.35, 'sawtooth');
  }

  function playCommandAck() {
    playTone(700, 0.08, 'sine');
    setTimeout(() => playTone(900, 0.12, 'sine'), 90);
  }

  function speakText(text, onComplete) {
    if (!('speechSynthesis' in window)) {
      if (onComplete) onComplete();
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.02;
    utterance.pitch = 1.0;
    utterance.volume = 0.95;
    if (onComplete) {
      utterance.onend = () => onComplete();
      utterance.onerror = () => onComplete();
    }
    window.speechSynthesis.speak(utterance);
  }

  function normalizeSpelledOut(input) {
    if (!input) return '';
    let text = input.trim();
    const replacements = [
      [/\bexclamation\s*(?:point|mark)?\b/gi, '!'],
      [/\bbang\b/gi, '!'],
      [/\bat\s*(?:sign)?\b/gi, '@'],
      [/\bhash(?:tag)?\b/gi, '#'],
      [/\bdollar\s*(?:sign)?\b/gi, '$'],
      [/\bpercent\b/gi, '%'],
      [/\bstar\b/gi, '*'],
      [/\basterisk\b/gi, '*'],
      [/\bdash\b/gi, '-'],
      [/\bhyphen\b/gi, '-'],
      [/\bunderscore\b/gi, '_'],
      [/\bperiod\b/gi, '.'],
      [/\bdot\b/gi, '.'],
      [/\bzero\b/gi, '0'],
      [/\bone\b/gi, '1'],
      [/\btwo\b/gi, '2'],
      [/\bthree\b/gi, '3'],
      [/\bfour\b/gi, '4'],
      [/\bfive\b/gi, '5'],
      [/\bsix\b/gi, '6'],
      [/\bseven\b/gi, '7'],
      [/\beight\b/gi, '8'],
      [/\bnine\b/gi, '9'],
    ];

    for (const [pattern, repl] of replacements) {
      text = text.replace(pattern, repl);
    }
    return text.replace(/\s+/g, '');
  }

  function constantTimeCompare(a, b) {
    if (typeof a !== 'string' || typeof b !== 'string') return false;
    if (a.length !== b.length) return false;
    let diff = 0;
    for (let i = 0; i < a.length; i++) {
      diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
    }
    return diff === 0;
  }

  function verifyPasswordCandidate(rawInput) {
    if (!rawInput) return { valid: false, reason: 'Empty candidate token' };
    const candidates = [
      rawInput.trim(),
      normalizeSpelledOut(rawInput),
      rawInput.replace(/[^a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/g, ''),
      normalizeSpelledOut(rawInput).toLowerCase()
    ];

    for (const item of KNOWN_PASSWORDS) {
      for (const cand of candidates) {
        if (constantTimeCompare(cand, item.token)) {
          return { valid: true, match: item, matchedString: cand };
        }
        if (cand.toLowerCase() === item.token.toLowerCase()) {
          return { valid: true, match: item, matchedString: cand, caseAdjusted: true };
        }
      }
    }
    return { valid: false, reason: 'Candidate does not match Auth Vault signature' };
  }

  function getApiBase() {
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const isSubdir = window.location.pathname.toLowerCase().startsWith('/aegisos');
    return (isLocal && isSubdir) ? '/AegisOS' : '';
  }

  function createVoiceAuthUI() {
    if (document.getElementById('aegis-voice-auth-container')) return;

    const container = document.createElement('div');
    container.id = 'aegis-voice-auth-container';
    container.innerHTML = `
      <style>
        .aegis-floater-wrap {
          position: fixed;
          bottom: 60px;
          right: 24px;
          z-index: 99999;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 6px 10px 6px 12px;
          background: #0f172a;
          color: #38bdf8;
          border: 1px solid #0284c7;
          border-radius: 9999px;
          box-shadow: 0 10px 25px -5px rgba(2, 132, 199, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
          font-family: 'JetBrains Mono', monospace, sans-serif;
          font-size: 13px;
          font-weight: 600;
          user-select: none;
          transition: box-shadow 0.25s ease, border-color 0.25s ease;
          cursor: grab;
        }
        .aegis-floater-wrap:hover {
          box-shadow: 0 14px 28px -4px rgba(2, 132, 199, 0.6);
        }
        .aegis-floater-wrap.dragging {
          opacity: 0.92;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.7), 0 0 15px rgba(56, 189, 248, 0.6);
          cursor: grabbing !important;
          transition: none !important;
        }
        .aegis-floater-wrap.authenticated {
          border-color: #10b981;
          color: #10b981;
          box-shadow: 0 10px 25px -5px rgba(16, 185, 129, 0.4);
        }
        .aegis-floater-grip {
          cursor: grab;
          display: flex;
          align-items: center;
          padding: 2px 4px 2px 0;
          opacity: 0.6;
          transition: opacity 0.15s;
        }
        .aegis-floater-grip:hover {
          opacity: 1;
        }
        .aegis-floater-content {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
        }
        .aegis-floater-content:hover {
          color: #f8fafc;
        }
        .aegis-floater-min-btn, .aegis-floater-expand-btn {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: rgba(30, 41, 59, 0.8);
          border: 1px solid #334155;
          color: #94a3b8;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          font-size: 13px;
          line-height: 1;
          padding: 0;
          transition: all 0.15s;
          margin-left: 2px;
        }
        .aegis-floater-min-btn:hover {
          background: #ef4444;
          color: #ffffff;
          border-color: #ef4444;
        }
        .aegis-floater-expand-btn:hover {
          background: #0284c7;
          color: #ffffff;
          border-color: #38bdf8;
        }

        /* Minimized State (Docked at Lower Right) */
        .aegis-floater-wrap.minimized {
          bottom: 56px !important;
          right: 18px !important;
          left: auto !important;
          top: auto !important;
          width: 44px;
          height: 44px;
          padding: 0;
          border-radius: 50%;
          justify-content: center;
          cursor: pointer;
          animation: aegis-pulse-cyan 2.4s infinite;
        }
        .aegis-floater-wrap.minimized .aegis-floater-grip,
        .aegis-floater-wrap.minimized #aegis-trigger-label,
        .aegis-floater-wrap.minimized #aegis-floater-min-btn {
          display: none !important;
        }
        .aegis-floater-wrap.minimized .aegis-floater-content {
          justify-content: center;
          padding: 0;
        }
        .aegis-floater-wrap.minimized #aegis-floater-expand-btn {
          display: flex !important;
          position: absolute;
          top: -3px;
          right: -3px;
          width: 16px;
          height: 16px;
          font-size: 10px;
          background: #0284c7;
          color: #ffffff;
          border: 1px solid #38bdf8;
        }
        @keyframes aegis-pulse-cyan {
          0% { box-shadow: 0 0 0 0 rgba(14, 165, 233, 0.5); }
          70% { box-shadow: 0 0 0 12px rgba(14, 165, 233, 0); }
          100% { box-shadow: 0 0 0 0 rgba(14, 165, 233, 0); }
        }

        /* Modal Overlay */
        #aegis-voice-auth-modal {
          position: fixed;
          inset: 0;
          z-index: 100000;
          display: none;
          align-items: center;
          justify-content: center;
          background: rgba(11, 15, 23, 0.85);
          backdrop-filter: blur(8px);
          font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        .aegis-modal-card {
          position: relative;
          width: 94%;
          max-width: 580px;
          max-height: 92vh;
          overflow-y: auto;
          background: #0f172a;
          border: 1px solid #1e293b;
          border-radius: 18px;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.75), 0 0 25px rgba(2, 132, 199, 0.15);
          padding: 22px;
          color: #e2e8f0;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
        }
        .aegis-radar-pulse {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          width: 64px;
          height: 64px;
          margin: 0 auto 8px;
          border-radius: 50%;
          background: rgba(14, 165, 233, 0.1);
          color: #38bdf8;
          transition: all 0.3s ease;
        }
        .aegis-radar-pulse.listening {
          background: rgba(16, 185, 129, 0.15);
          color: #10b981;
          animation: aegis-pulse-green 1.4s infinite;
        }
        .aegis-radar-pulse.speaking {
          background: rgba(239, 68, 68, 0.15);
          color: #ef4444;
          animation: aegis-pulse-red 1.2s infinite;
        }
        .aegis-radar-pulse.processing {
          background: rgba(245, 158, 11, 0.15);
          color: #f59e0b;
          animation: aegis-pulse-yellow 1.4s infinite;
        }
        @keyframes aegis-pulse-red {
          0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6); }
          70% { box-shadow: 0 0 0 16px rgba(239, 68, 68, 0); }
          100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        @keyframes aegis-pulse-green {
          0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
          70% { box-shadow: 0 0 0 16px rgba(16, 185, 129, 0); }
          100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        @keyframes aegis-pulse-yellow {
          0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.6); }
          70% { box-shadow: 0 0 0 16px rgba(245, 158, 11, 0); }
          100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
        }
        .aegis-status-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 12px;
          border-radius: 9999px;
          font-size: 11px;
          font-weight: 700;
          font-family: 'JetBrains Mono', monospace;
        }
        .aegis-timer-pill {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 3px 10px;
          border-radius: 9999px;
          font-size: 11px;
          font-family: 'JetBrains Mono', monospace;
          background: rgba(30, 41, 59, 0.8);
          color: #94a3b8;
          border: 1px solid rgba(148, 163, 184, 0.2);
        }
        .aegis-model-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 3px 8px;
          border-radius: 6px;
          font-size: 11px;
          font-family: 'JetBrains Mono', monospace;
          background: rgba(14, 165, 233, 0.15);
          color: #38bdf8;
          border: 1px solid rgba(14, 165, 233, 0.3);
        }
        .aegis-mic-badge {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 3px 8px;
          border-radius: 6px;
          font-size: 11px;
          font-family: 'JetBrains Mono', monospace;
          cursor: pointer;
          transition: all 0.2s;
        }
        .aegis-mic-badge.granted {
          background: rgba(16, 185, 129, 0.15);
          color: #10b981;
          border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .aegis-mic-badge.needed {
          background: rgba(245, 158, 11, 0.15);
          color: #f59e0b;
          border: 1px solid rgba(245, 158, 11, 0.3);
        }
        .aegis-mic-badge.denied {
          background: rgba(239, 68, 68, 0.15);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.3);
        }

        /* Chat History Stream */
        .aegis-chat-history {
          height: 160px;
          max-height: 190px;
          overflow-y: auto;
          background: #070a12;
          border: 1px solid #1e293b;
          border-radius: 12px;
          padding: 10px 14px;
          margin-bottom: 8px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          font-size: 12px;
          scroll-behavior: smooth;
        }
        .aegis-chat-history::-webkit-scrollbar {
          width: 5px;
        }
        .aegis-chat-history::-webkit-scrollbar-thumb {
          background: #334155;
          border-radius: 4px;
        }
        .aegis-chat-msg {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .aegis-chat-msg.user {
          align-self: flex-end;
          max-width: 82%;
          background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
          color: #ffffff;
          padding: 8px 12px;
          border-radius: 12px 12px 2px 12px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          word-break: break-word;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
        }
        .aegis-chat-msg.ai {
          align-self: flex-start;
          max-width: 90%;
          background: rgba(15, 23, 42, 0.95);
          border: 1px solid #334155;
          color: #f1f5f9;
          padding: 10px 14px;
          border-radius: 12px 12px 12px 2px;
          font-size: 12px;
          line-height: 1.5;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
        }
        .aegis-chat-msg.system {
          align-self: center;
          background: rgba(30, 41, 59, 0.7);
          border: 1px solid rgba(148, 163, 184, 0.2);
          color: #94a3b8;
          font-size: 11px;
          padding: 4px 10px;
          border-radius: 9999px;
          font-family: 'JetBrains Mono', monospace;
          text-align: center;
        }

        /* Mic Button Listening Pulse */
        #aegis-mic-toggle-btn.listening {
          background: #059669 !important;
          border-color: #10b981 !important;
          color: #ffffff !important;
          animation: aegis-pulse-mic 1.2s infinite;
        }
        @keyframes aegis-pulse-mic {
          0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
          70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
          100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        @keyframes aegis-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      </style>

      <!-- Draggable & Minimizable Floater Container -->
      <div id="aegis-voice-floater-wrap" class="aegis-floater-wrap" title="Aegis Voice Intelligence & AI Commands">
        <div id="aegis-floater-drag-grip" class="aegis-floater-grip" title="Click & Drag to reposition anywhere">
          <svg width="10" height="14" viewBox="0 0 10 14" fill="#64748b">
            <circle cx="2.5" cy="2" r="1.5"/><circle cx="7.5" cy="2" r="1.5"/>
            <circle cx="2.5" cy="7" r="1.5"/><circle cx="7.5" cy="7" r="1.5"/>
            <circle cx="2.5" cy="12" r="1.5"/><circle cx="7.5" cy="12" r="1.5"/>
          </svg>
        </div>

        <div id="aegis-voice-trigger-btn" class="aegis-floater-content" title="Voice Auth & AI Commands (Click to open)">
          <div id="aegis-floater-mic-icon" style="display:flex; align-items:center;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" x2="12" y1="19" y2="22"/>
            </svg>
          </div>
          <span id="aegis-trigger-label">Voice Auth & AI Commands</span>
        </div>

        <button id="aegis-floater-min-btn" type="button" class="aegis-floater-min-btn" title="Minimize / Dock to lower-right corner">&minus;</button>
        <button id="aegis-floater-expand-btn" type="button" class="aegis-floater-expand-btn" style="display:none;" title="Expand Voice AI floater">&#x2922;</button>
      </div>

      <!-- Main Voice & AI Chatbox Modal -->
      <div id="aegis-voice-auth-modal">
        <div class="aegis-modal-card">
          <button id="aegis-close-modal-btn" style="position:absolute; top:18px; right:18px; background:transparent; border:none; color:#94a3b8; font-size:22px; cursor:pointer;" title="Close Window">&times;</button>

          <!-- Header / Status Area -->
          <div style="text-align: center; margin-bottom: 6px;">
            <div id="aegis-radar-icon" class="aegis-radar-pulse">
              <svg id="aegis-mic-svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" x2="12" y1="19" y2="22"/>
              </svg>
            </div>

            <div style="display:flex; justify-content:center; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:4px;">
              <div id="aegis-state-pill" class="aegis-status-pill" style="background:rgba(14,165,233,0.15); color:#38bdf8; border:1px solid rgba(14,165,233,0.3);">
                ● READY
              </div>
              <div id="aegis-model-badge" class="aegis-model-badge">
                AI: <span id="aegis-model-name-label">gemini-4-hydrogen</span>
              </div>
              <div id="aegis-timer-pill" class="aegis-timer-pill" style="display:none;">
                ⏱️ Inactivity Lock: <span id="aegis-countdown-txt" style="color:#f8fafc; font-weight:700;">05:00</span>
              </div>
              <div id="aegis-mic-perm-badge" class="aegis-mic-badge needed" title="Click to check microphone">
                🎙️ Mic: Ready
              </div>
            </div>

            <h3 id="aegis-card-title" style="font-size: 16px; font-weight: 700; margin: 0 0 2px 0; color:#f8fafc;">AegisOS Voice Intelligence & Chatbox</h3>
            <p id="aegis-prompt-text" style="font-size: 12px; color: #94a3b8; margin: 0 0 6px 0;">
              Give password after the beep (or click <strong style="color:#10b981;">Quick Unlock</strong> to jump into AI chat directly).
            </p>
          </div>

          <!-- Chat History Stream -->
          <div id="aegis-chat-history" class="aegis-chat-history">
            <div class="aegis-chat-msg system">
              AegisOS Neural Kernel Initialized &bull; Voice-to-Text & Direct Typing Active
            </div>
          </div>

          <!-- Real-Time Live Speech Preview Banner (Shows spoken words appearing live) -->
          <div id="aegis-live-speech-preview" style="font-size:12px; color:#38bdf8; font-family:'JetBrains Mono', monospace; padding:6px 10px; min-height:20px; background:rgba(2,132,199,0.12); border-radius:8px; border:1px solid rgba(56,189,248,0.3); margin-bottom:8px; display:flex; align-items:center; justify-content:space-between;">
            <span id="aegis-preview-text">🎙️ Spoken voice will stream here live as you speak...</span>
            <span id="aegis-speech-tag" style="font-size:10px; color:#64748b;">Standby</span>
          </div>

          <!-- Interactive Chatbox Input Row: Mic Toggle + Direct Input + Visibility Toggle + Clear + Send -->
          <div class="aegis-chat-input-row" style="display:flex; align-items:center; gap:8px; background:#0b0f17; border:1px solid #1e293b; border-radius:12px; padding:6px 8px; margin-bottom:8px;">
            <!-- Mic Toggle Button -->
            <button id="aegis-mic-toggle-btn" type="button" title="Toggle Microphone Listening (Voice-to-Text)" style="display:flex; align-items:center; justify-content:center; width:36px; height:36px; border-radius:8px; background:#1e293b; border:1px solid #334155; color:#38bdf8; cursor:pointer; transition:all 0.2s; flex-shrink:0;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" x2="12" y1="19" y2="22"/>
              </svg>
            </button>

            <!-- Direct Text Typing & Voice-to-Text Input -->
            <input id="aegis-spelled-input" type="password" placeholder="Speak password or type directly here..." style="flex:1; background:transparent; border:none; outline:none; font-family:'JetBrains Mono', monospace; font-size:13px; color:#f8fafc; padding:6px 4px; letter-spacing: 0.08em;" autocomplete="off" />

            <!-- Visibility / Eye Toggle Button -->
            <button id="aegis-toggle-mask-btn" type="button" title="Toggle Asterisk (*) Masking" style="background:transparent; border:none; color:#64748b; font-size:14px; cursor:pointer; padding:4px 6px;">
              👁️
            </button>

            <!-- Clear Input Button -->
            <button id="aegis-clear-input-btn" type="button" title="Clear typed or transcribed text" style="background:transparent; border:none; color:#64748b; font-size:16px; cursor:pointer; padding:4px 6px;">&times;</button>

            <!-- Send Button -->
            <button id="aegis-chat-send-btn" type="button" title="Send (Enter)" style="display:flex; align-items:center; gap:6px; padding:8px 14px; background:linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); color:#ffffff; font-weight:700; font-size:12px; border:none; border-radius:8px; cursor:pointer; transition:all 0.2s; flex-shrink:0;">
              <span>Send</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>

          <!-- Result / Status Box -->
          <div id="aegis-result-box" style="display:none; padding:10px 14px; border-radius:8px; font-size:12px; font-family:'JetBrains Mono', monospace; margin-bottom:8px;"></div>

          <!-- Bottom Action Buttons: Challenge Trigger + Quick Unlock + Direct Verify -->
          <div style="display:flex; gap:8px; margin-bottom:6px; flex-wrap:wrap;">
            <button id="aegis-start-challenge-btn" type="button" style="flex:1; min-width:140px; padding:9px 12px; background:#0ea5e9; color:#0b0f17; font-weight:700; font-size:12px; border:none; border-radius:8px; cursor:pointer; transition:all 0.2s;">
              Start Challenge (Prompt + Beep)
            </button>
            <button id="aegis-quick-unlock-btn" type="button" style="padding:9px 14px; background:#059669; color:#ffffff; font-weight:700; font-size:12px; border:none; border-radius:8px; cursor:pointer; transition:all 0.2s;" title="1-Click Unlock with Auth Vault signature">
              ⚡ Quick Unlock
            </button>
            <button id="aegis-action-btn" type="button" style="padding:9px 14px; background:#1e293b; color:#cbd5e1; font-weight:600; font-size:12px; border:1px solid #334155; border-radius:8px; cursor:pointer;">
              Verify Password
            </button>
          </div>

          <!-- Helpful Command Hints -->
          <div id="aegis-command-hints" style="display:none; margin-top:6px; padding-top:8px; border-top:1px solid #1e293b; font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace;">
            <div style="color:#94a3b8; font-weight:600; margin-bottom:4px;">Speak or Type Any Command:</div>
            <div style="display:flex; flex-wrap:wrap; gap:6px;">
              <span class="aegis-hint-chip" style="background:#1e293b; padding:2px 6px; border-radius:4px; color:#38bdf8; cursor:pointer;">"Status"</span>
              <span class="aegis-hint-chip" style="background:#1e293b; padding:2px 6px; border-radius:4px; color:#38bdf8; cursor:pointer;">"Run watchdog scan"</span>
              <span class="aegis-hint-chip" style="background:#1e293b; padding:2px 6px; border-radius:4px; color:#38bdf8; cursor:pointer;">"Autonomous heal"</span>
              <span class="aegis-hint-chip" style="background:#1e293b; padding:2px 6px; border-radius:4px; color:#38bdf8; cursor:pointer;">"Show partition slots"</span>
              <span class="aegis-hint-chip" style="background:#1e293b; padding:2px 6px; border-radius:4px; color:#38bdf8; cursor:pointer;">"Check mirror health"</span>
              <span class="aegis-hint-chip" style="background:#1e293b; padding:2px 6px; border-radius:4px; color:#38bdf8; cursor:pointer;">"What is AegisOS?"</span>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(container);

    const triggerBtn = document.getElementById('aegis-voice-trigger-btn');
    const triggerLabel = document.getElementById('aegis-trigger-label');
    const modal = document.getElementById('aegis-voice-auth-modal');
    const closeBtn = document.getElementById('aegis-close-modal-btn');
    const startBtn = document.getElementById('aegis-start-challenge-btn');
    const quickUnlockBtn = document.getElementById('aegis-quick-unlock-btn');
    const actionBtn = document.getElementById('aegis-action-btn');
    const input = document.getElementById('aegis-spelled-input');
    const toggleMaskBtn = document.getElementById('aegis-toggle-mask-btn');
    const clearInputBtn = document.getElementById('aegis-clear-input-btn');
    const sendBtn = document.getElementById('aegis-chat-send-btn');
    const micToggleBtn = document.getElementById('aegis-mic-toggle-btn');
    const micPermBadge = document.getElementById('aegis-mic-perm-badge');
    const livePreview = document.getElementById('aegis-live-speech-preview');
    const previewText = document.getElementById('aegis-preview-text');
    const speechTag = document.getElementById('aegis-speech-tag');
    const chatHistory = document.getElementById('aegis-chat-history');
    const radar = document.getElementById('aegis-radar-icon');
    const pill = document.getElementById('aegis-state-pill');
    const modelBadge = document.getElementById('aegis-model-name-label');
    const timerPill = document.getElementById('aegis-timer-pill');
    const countdownTxt = document.getElementById('aegis-countdown-txt');
    const promptText = document.getElementById('aegis-prompt-text');
    const resultBox = document.getElementById('aegis-result-box');
    const commandHints = document.getElementById('aegis-command-hints');

    let recognition = null;
    let isListening = false;
    let isAuthenticated = false;
    let lastSpokenTime = 0;
    let timerInterval = null;
    let activeModelName = 'gemini-4-hydrogen';

    // Fetch initial model name from state
    async function loadActiveModelConfig() {
      try {
        const apiBase = getApiBase();
        const res = await fetch(apiBase + '/api/os/state');
        const d = await res.json();
        if (d && d.state) {
          activeModelName = d.state.aiModelName || 'gemini-4-hydrogen';
          if (modelBadge) {
            modelBadge.textContent = activeModelName;
          }
        }
      } catch (e) {}
    }
    loadActiveModelConfig();

    // Check microphone permission
    async function checkMicrophonePermission() {
      if (navigator.permissions && navigator.permissions.query) {
        try {
          const status = await navigator.permissions.query({ name: 'microphone' });
          updateMicBadge(status.state);
          status.onchange = () => updateMicBadge(status.state);
        } catch (e) {
          updateMicBadge('prompt');
        }
      } else {
        updateMicBadge('prompt');
      }
    }

    function updateMicBadge(state) {
      if (!micPermBadge) return;
      micPermBadge.className = 'aegis-mic-badge';
      if (state === 'granted') {
        micPermBadge.classList.add('granted');
        micPermBadge.innerHTML = '🎙️ Mic: Active';
      } else if (state === 'denied') {
        micPermBadge.classList.add('denied');
        micPermBadge.innerHTML = '🎙️ Mic: Blocked';
      } else {
        micPermBadge.classList.add('needed');
        micPermBadge.innerHTML = '🎙️ Mic: Ready';
      }
    }

    micPermBadge.addEventListener('click', () => {
      startSpeechRecognition();
    });

    // Eye / Mask Toggle
    toggleMaskBtn.addEventListener('click', () => {
      if (input.type === 'password') {
        input.type = 'text';
        toggleMaskBtn.textContent = '🔒';
        toggleMaskBtn.title = 'Mask password with *';
      } else {
        input.type = 'password';
        toggleMaskBtn.textContent = '👁️';
        toggleMaskBtn.title = 'Reveal password';
      }
    });

    // 1-Click Quick Unlock Button
    quickUnlockBtn.addEventListener('click', () => {
      verifyCandidate('Tidesrent01!!');
    });

    // Chat Message Append Helper
    function appendChatMessage(sender, text, meta = {}) {
      if (!chatHistory) return;
      const msgDiv = document.createElement('div');
      msgDiv.className = `aegis-chat-msg ${sender}`;

      if (sender === 'user') {
        msgDiv.innerHTML = `<span style="font-size:10px; opacity:0.75; margin-bottom:2px;">You (${meta.source || 'Voice/Text'})</span><div>${escapeHtml(text)}</div>`;
      } else if (sender === 'ai') {
        msgDiv.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; border-bottom:1px solid rgba(56,189,248,0.2); padding-bottom:3px;">
            <span style="color:#38bdf8; font-weight:700;">🤖 ${meta.model || activeModelName}</span>
            <span style="font-size:10px; color:#10b981;">Aegis Neural Core</span>
          </div>
          <div style="color:#f8fafc; font-size:13px; line-height:1.45;">${escapeHtml(text)}</div>
          ${meta.footer ? `<div style="font-size:10px; color:#64748b; margin-top:4px;">${meta.footer}</div>` : ''}
        `;
      } else {
        msgDiv.innerHTML = text;
      }

      chatHistory.appendChild(msgDiv);
      chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }

    function openModal() {
      modal.style.display = 'flex';
      getAudioContext();
      loadActiveModelConfig();
      checkMicrophonePermission();
      input.focus();
      if (!isAuthenticated) {
        input.type = 'password';
        if (toggleMaskBtn) toggleMaskBtn.style.display = 'inline-block';
        if (quickUnlockBtn) quickUnlockBtn.style.display = 'inline-block';
        runPasswordChallengeSequence();
      } else {
        updateCommandModeUI();
      }
    }

    function closeModal() {
      modal.style.display = 'none';
      if (!isAuthenticated) {
        stopSpeechRecognition();
      }
    }

    // Expose global opener for Desktop GUI & other apps
    window.openAegisVoiceAuth = openModal;

    const floaterWrap = document.getElementById('aegis-voice-floater-wrap');
    const dragGrip = document.getElementById('aegis-floater-drag-grip');
    const minBtn = document.getElementById('aegis-floater-min-btn');
    const expandBtn = document.getElementById('aegis-floater-expand-btn');

    // Restore saved position and minimize state
    try {
      const savedMin = localStorage.getItem('aegis_floater_min');
      if (savedMin === 'true') {
        floaterWrap.classList.add('minimized');
      }
      const savedPos = JSON.parse(localStorage.getItem('aegis_floater_pos') || 'null');
      if (savedPos && !floaterWrap.classList.contains('minimized')) {
        floaterWrap.style.left = `${Math.min(window.innerWidth - 120, Math.max(10, savedPos.left))}px`;
        floaterWrap.style.top = `${Math.min(window.innerHeight - 60, Math.max(10, savedPos.top))}px`;
        floaterWrap.style.bottom = 'auto';
        floaterWrap.style.right = 'auto';
      }
    } catch (e) {}

    // Minimize Floater to lower right
    minBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      floaterWrap.classList.add('minimized');
      try { localStorage.setItem('aegis_floater_min', 'true'); } catch(e){}
    });

    // Expand Floater from lower right
    expandBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      floaterWrap.classList.remove('minimized');
      try { localStorage.setItem('aegis_floater_min', 'false'); } catch(e){}
      try {
        const savedPos = JSON.parse(localStorage.getItem('aegis_floater_pos') || 'null');
        if (savedPos) {
          floaterWrap.style.left = `${savedPos.left}px`;
          floaterWrap.style.top = `${savedPos.top}px`;
          floaterWrap.style.bottom = 'auto';
          floaterWrap.style.right = 'auto';
        }
      } catch(e){}
    });

    // Dragging Logic
    let isDragging = false;
    let didMove = false;
    let startX = 0, startY = 0, initLeft = 0, initTop = 0;

    function startDrag(e) {
      if (e.target.closest('#aegis-floater-min-btn') || e.target.closest('#aegis-floater-expand-btn')) return;
      isDragging = true;
      didMove = false;
      const clientX = e.clientX || (e.touches && e.touches[0].clientX) || 0;
      const clientY = e.clientY || (e.touches && e.touches[0].clientY) || 0;
      startX = clientX;
      startY = clientY;

      const rect = floaterWrap.getBoundingClientRect();
      initLeft = rect.left;
      initTop = rect.top;

      floaterWrap.style.left = `${initLeft}px`;
      floaterWrap.style.top = `${initTop}px`;
      floaterWrap.style.bottom = 'auto';
      floaterWrap.style.right = 'auto';

      document.addEventListener('mousemove', onDragMove);
      document.addEventListener('mouseup', onDragEnd);
      document.addEventListener('touchmove', onDragMove, { passive: false });
      document.addEventListener('touchend', onDragEnd);
    }

    function onDragMove(e) {
      if (!isDragging) return;
      const clientX = e.clientX || (e.touches && e.touches[0].clientX) || 0;
      const clientY = e.clientY || (e.touches && e.touches[0].clientY) || 0;
      const dx = clientX - startX;
      const dy = clientY - startY;

      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
        didMove = true;
        floaterWrap.classList.add('dragging');
      }

      const w = floaterWrap.offsetWidth || 180;
      const h = floaterWrap.offsetHeight || 44;
      const newL = Math.max(10, Math.min(window.innerWidth - w - 10, initLeft + dx));
      const newT = Math.max(10, Math.min(window.innerHeight - h - 10, initTop + dy));

      floaterWrap.style.left = `${newL}px`;
      floaterWrap.style.top = `${newT}px`;
      if (e.cancelable) e.preventDefault();
    }

    function onDragEnd() {
      if (!isDragging) return;
      isDragging = false;
      floaterWrap.classList.remove('dragging');
      document.removeEventListener('mousemove', onDragMove);
      document.removeEventListener('mouseup', onDragEnd);
      document.removeEventListener('touchmove', onDragMove);
      document.removeEventListener('touchend', onDragEnd);

      if (didMove && !floaterWrap.classList.contains('minimized')) {
        try {
          const rect = floaterWrap.getBoundingClientRect();
          localStorage.setItem('aegis_floater_pos', JSON.stringify({ left: Math.round(rect.left), top: Math.round(rect.top) }));
        } catch(e){}
      }
      setTimeout(() => { didMove = false; }, 60);
    }

    floaterWrap.addEventListener('mousedown', startDrag);
    floaterWrap.addEventListener('touchstart', startDrag, { passive: true });

    triggerBtn.addEventListener('click', (e) => {
      if (didMove) return;
      openModal();
    });
    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    // Chatbox Clear Button
    clearInputBtn.addEventListener('click', () => {
      input.value = '';
      previewText.textContent = '🎙️ Spoken voice will stream here live as you speak...';
      input.focus();
    });

    // Mic Toggle Button
    micToggleBtn.addEventListener('click', () => {
      if (isListening) {
        stopSpeechRecognition();
        appendChatMessage('system', 'Microphone muted.');
      } else {
        startSpeechRecognition(true);
        appendChatMessage('system', 'Microphone active: converting voice to text...');
      }
    });

    // Send Button & Enter Key Handling
    function handleSend() {
      const text = input.value.trim();
      if (!text) return;

      input.value = '';
      previewText.textContent = '🎙️ Listening...';

      if (!isAuthenticated) {
        // MASK with '*' when logging password to the chatbox stream
        const asterisksMask = '*'.repeat(Math.max(1, text.length));
        appendChatMessage('user', asterisksMask, { source: 'Password (Masked with *)' });
        verifyCandidate(text);
      } else {
        appendChatMessage('user', text, { source: 'Spoken / Typed' });
        executeVoiceCommand(text);
      }
    }

    sendBtn.addEventListener('click', handleSend);
    actionBtn.addEventListener('click', handleSend);

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSend();
      }
    });

    startBtn.addEventListener('click', () => {
      runPasswordChallengeSequence(true);
    });

    // Quick Command Hint Chips
    document.querySelectorAll('.aegis-hint-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const text = chip.textContent.replace(/"/g, '').trim();
        input.value = text;
        handleSend();
      });
    });

    // Inactivity Watchdog (5 minutes)
    function resetInactivityTimer() {
      lastSpokenTime = Date.now();
      if (timerInterval) clearInterval(timerInterval);

      timerInterval = setInterval(() => {
        if (!isAuthenticated) {
          clearInterval(timerInterval);
          return;
        }
        const elapsed = Date.now() - lastSpokenTime;
        const remaining = Math.max(0, INACTIVITY_TIMEOUT_MS - elapsed);
        const mins = Math.floor(remaining / 60000);
        const secs = Math.floor((remaining % 60000) / 1000);
        countdownTxt.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

        if (remaining <= 0) {
          // 5 minutes of silence elapsed -> Lock session
          clearInterval(timerInterval);
          lockDueToInactivity();
        }
      }, 1000);
    }

    function lockDueToInactivity() {
      isAuthenticated = false;
      stopSpeechRecognition();
      triggerBtn.classList.remove('authenticated'); if (floaterWrap) floaterWrap.classList.remove('authenticated');
      triggerLabel.textContent = 'Voice Auth (Locked)';
      timerPill.style.display = 'none';
      commandHints.style.display = 'none';

      pill.textContent = '🔒 LOCKED (5M INACTIVE)';
      pill.style.background = 'rgba(239, 68, 68, 0.15)';
      pill.style.color = '#ef4444';
      pill.style.border = '1px solid rgba(239, 68, 68, 0.3)';

      radar.className = 'aegis-radar-pulse';

      // Re-enable password type and asterisk masking
      input.type = 'password';
      if (toggleMaskBtn) toggleMaskBtn.style.display = 'inline-block';
      if (quickUnlockBtn) quickUnlockBtn.style.display = 'inline-block';
      input.value = '';
      input.placeholder = 'Provide password to re-unlock (represented as *)...';

      actionBtn.textContent = 'Verify Password';
      startBtn.textContent = 'Start Challenge (Prompt + Beep)';
      promptText.innerHTML = '<span style="color:#ef4444; font-weight:700;">[LOCKED]</span> 5 minutes elapsed with no speech. Please give password after the beep (or click <strong style="color:#10b981;">Quick Unlock</strong>).';

      appendChatMessage('system', 'Session auto-locked due to 5 minutes of inactivity. Provide password to unlock.');

      playErrorBuzz();
      speakText('Session locked due to five minutes of inactivity. Please provide password to unlock.');
    }

    // Step 1: Challenge Sequence (Prompt -> Beep -> Listen)
    function runPasswordChallengeSequence(forceReauth = false) {
      if (isAuthenticated && !forceReauth) {
        updateCommandModeUI();
        return;
      }

      isAuthenticated = false;
      stopSpeechRecognition();
      if (timerInterval) clearInterval(timerInterval);

      timerPill.style.display = 'none';
      commandHints.style.display = 'none';
      triggerBtn.classList.remove('authenticated'); if (floaterWrap) floaterWrap.classList.remove('authenticated');
      triggerLabel.textContent = 'Voice Auth (Challenging)';

      input.type = 'password';
      if (toggleMaskBtn) toggleMaskBtn.style.display = 'inline-block';
      if (quickUnlockBtn) quickUnlockBtn.style.display = 'inline-block';

      input.value = '';
      input.placeholder = 'Listening for voice password (or click Quick Unlock)...';
      actionBtn.textContent = 'Verify Password';

      pill.textContent = '● ANNOUNCING CHALLENGE';
      pill.style.background = 'rgba(239, 68, 68, 0.15)';
      pill.style.color = '#ef4444';
      pill.style.border = '1px solid rgba(239, 68, 68, 0.3)';
      radar.className = 'aegis-radar-pulse speaking';

      promptText.innerHTML = 'Announcing: <strong style="color:#38bdf8;">"Give the password after the beep"</strong>...';
      appendChatMessage('system', 'Announcing challenge: "Give the password after the beep"...');

      // 1. Spoken Announcement
      speakText('Give the password after the beep', () => {
        // 2. Audible 880Hz Beep
        setTimeout(() => {
          playBeep();

          // 3. Signal to listen and stream voice-to-text
          setTimeout(() => {
            pill.textContent = '● LISTENING FOR PASSWORD';
            pill.style.background = 'rgba(16, 185, 129, 0.15)';
            pill.style.color = '#10b981';
            pill.style.border = '1px solid rgba(16, 185, 129, 0.3)';
            radar.className = 'aegis-radar-pulse listening';

            promptText.innerHTML = '<span style="color:#10b981; font-weight:700;">● SIGNAL ACTIVE:</span> Listening now (speak "Tidesrent01!!" or click <strong style="color:#10b981;">Quick Unlock</strong>)...';
            previewText.textContent = '🎙️ Listening for password... speak now';

            startSpeechRecognition(true);
          }, 320);
        }, 120);
      });
    }

    // Step 2: Password Verification against Auth Vault
    function verifyCandidate(rawInput) {
      const res = verifyPasswordCandidate(rawInput);
      resultBox.style.display = 'block';

      // Always represent the password with asterisks for security
      const asterisksMask = '*'.repeat(Math.max(1, rawInput.length));

      if (res.valid) {
        isAuthenticated = true;
        playSuccessChime();

        resultBox.style.background = 'rgba(16, 185, 129, 0.15)';
        resultBox.style.border = '1px solid rgba(16, 185, 129, 0.3)';
        resultBox.style.color = '#6ee7b7';
        resultBox.innerHTML = `
          <strong>✓ ACCESS GRANTED:</strong> Verified via Auth Vault constant-time XOR.<br>
          <span style="color:#cbd5e1;">Signer: <code>${res.match.label}</code> (${res.match.id}) &bull; Token: <code>${asterisksMask}</code></span><br>
          <span style="color:#38bdf8; font-weight:600;">Continuous Voice-to-Text connection to AI Model ${activeModelName} unlocked.</span>
        `;

        appendChatMessage('system', `✓ Access Granted: Token matched ${res.match.label}. Continuous AI chat active.`);

        triggerBtn.classList.add('authenticated'); if (floaterWrap) floaterWrap.classList.add('authenticated');
        triggerLabel.textContent = `Aegis AI (${activeModelName})`;

        speakText('Access granted. Aegis AI model is listening.');
        updateCommandModeUI();
        resetInactivityTimer();

        // Ensure continuous listener is running
        startSpeechRecognition(true);
      } else {
        playErrorBuzz();
        resultBox.style.background = 'rgba(239, 68, 68, 0.15)';
        resultBox.style.border = '1px solid rgba(239, 68, 68, 0.3)';
        resultBox.style.color = '#fca5a5';
        resultBox.innerHTML = `
          <strong>✗ VERIFICATION FAILED:</strong> Token rejected by Auth Vault.<br>
          <span style="color:#cbd5e1;">Input: <code>${asterisksMask}</code> (Masked for Security)</span><br>
          <span style="color:#ef4444;">Please speak clearly or click <strong style="color:#38bdf8;">Quick Unlock</strong> to verify immediately.</span>
        `;
        appendChatMessage('system', `✗ Verification failed for token ${asterisksMask}. Click "Quick Unlock" to bypass.`);
        speakText('Access denied. Password incorrect.');
      }
    }

    // Step 3: Transition to Continuous Command Mode (Clear text commands)
    function updateCommandModeUI() {
      radar.className = 'aegis-radar-pulse listening';
      pill.textContent = '● LISTENING (VOICE -> AI MODEL)';
      pill.style.background = 'rgba(16, 185, 129, 0.15)';
      pill.style.color = '#10b981';
      pill.style.border = '1px solid rgba(16, 185, 129, 0.3)';

      timerPill.style.display = 'inline-flex';
      commandHints.style.display = 'block';

      // Switch to clear text for general AI commands & questions
      input.type = 'text';
      if (toggleMaskBtn) toggleMaskBtn.style.display = 'none';
      if (quickUnlockBtn) quickUnlockBtn.style.display = 'none';

      input.value = '';
      input.placeholder = `Speak or type any command/question for ${activeModelName}...`;
      previewText.textContent = `🎙️ Listening... speak anything for ${activeModelName}`;

      actionBtn.textContent = 'Send to AI Model';
      startBtn.textContent = 'Re-verify Password';
      promptText.innerHTML = `<span style="color:#10b981; font-weight:700;">[UNLOCKED]</span> Connected to <strong style="color:#38bdf8;">${activeModelName}</strong>. Voice converts to text live; you can also type directly.`;
    }

    // Step 4: AI Model Command & Query Processor
    async function executeVoiceCommand(rawCmd) {
      if (!isAuthenticated) {
        runPasswordChallengeSequence();
        return;
      }

      resetInactivityTimer();
      const trimmed = rawCmd.trim();
      if (!trimmed) return;

      playCommandAck();

      radar.className = 'aegis-radar-pulse processing';
      pill.textContent = `● PROCESSING (${activeModelName})`;
      pill.style.background = 'rgba(245, 158, 11, 0.15)';
      pill.style.color = '#f59e0b';
      pill.style.border = '1px solid rgba(245, 158, 11, 0.3)';

      previewText.textContent = `Transmitting "${trimmed}" to ${activeModelName}...`;

      try {
        const apiBase = getApiBase();
        const cmdLower = trimmed.toLowerCase();

        // Concurrently trigger underlying OS actions if requested
        if (cmdLower.includes('scan') || cmdLower.includes('watchdog')) {
          fetch(apiBase + '/api/os/scan', { method: 'POST' }).catch(() => {});
        } else if (cmdLower.includes('heal') || cmdLower.includes('auto heal') || cmdLower.includes('ota cycle')) {
          fetch(apiBase + '/api/os/autonomous-cycle', { method: 'POST' }).catch(() => {});
        } else if (cmdLower.includes('mirror') || cmdLower.includes('liquidviz')) {
          fetch(apiBase + '/api/os/remote-buffer/mirror-check', { method: 'POST' }).catch(() => {});
        }

        // Deliver input directly to the AI Model
        const res = await fetch(apiBase + '/api/os/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: trimmed, transcript: trimmed })
        });

        const d = await res.json();
        const ans = d.answer || 'Voice command processed by AegisOS.';
        const modelUsed = d.modelUsed || d.aiModelName || activeModelName;
        activeModelName = d.aiModelName || activeModelName;
        if (modelBadge) modelBadge.textContent = activeModelName;

        appendChatMessage('ai', ans, {
          model: modelUsed,
          footer: `Slot: ${d.activeSlot || 'A'} | Hot-Swaps: ${d.zeroRebootSwaps || 0} | 5m Inactivity Timer Reset`
        });

        previewText.textContent = `✓ Response received from ${modelUsed}`;

        radar.className = 'aegis-radar-pulse speaking';
        speakText(ans, () => {
          if (isAuthenticated) {
            radar.className = 'aegis-radar-pulse listening';
            pill.textContent = '● LISTENING (VOICE -> AI MODEL)';
            pill.style.background = 'rgba(16, 185, 129, 0.15)';
            pill.style.color = '#10b981';
            pill.style.border = '1px solid rgba(16, 185, 129, 0.3)';
            previewText.textContent = `🎙️ Listening... speak anything for ${activeModelName}`;
          }
        });
      } catch (err) {
        appendChatMessage('system', `AI Execution Error: ${err.message}`);
        speakText('Command execution encountered an error.');
        radar.className = 'aegis-radar-pulse listening';
      }
    }

    // Step 5: Direct & Reliable Real-Time Speech Recognition Engine
    function startSpeechRecognition(isContinuous = true) {
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRec) {
        updateMicBadge('denied');
        previewText.textContent = '⚠️ Web Speech API not supported. Direct typing is active.';
        appendChatMessage('system', 'Web Speech API is not supported in this browser. Please type directly into the chatbox.');
        return;
      }

      try {
        if (recognition) {
          try { recognition.abort(); } catch(e){}
        }

        recognition = new SpeechRec();
        recognition.continuous = isContinuous;
        recognition.interimResults = true; // Stream interim words live as they are spoken
        recognition.lang = 'en-US';
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
          isListening = true;
          micToggleBtn.classList.add('listening');
          micToggleBtn.title = 'Microphone is Listening (Click to Mute)';
          if (speechTag) {
            speechTag.textContent = 'Mic Active';
            speechTag.style.color = '#10b981';
          }
          if (previewText) {
            previewText.textContent = '🎙️ Listening... speak now';
          }
          updateMicBadge('granted');
        };

        recognition.onsoundstart = () => {
          if (speechTag) {
            speechTag.textContent = 'Sound Detected';
            speechTag.style.color = '#38bdf8';
          }
        };

        recognition.onspeechstart = () => {
          if (speechTag) {
            speechTag.textContent = 'Converting Voice...';
            speechTag.style.color = '#10b981';
          }
          if (radar) radar.className = 'aegis-radar-pulse listening';
        };

        recognition.onresult = (event) => {
          resetInactivityTimer();
          let transcript = '';

          // Cumulative evaluation: collect all spoken segments
          for (let i = 0; i < event.results.length; ++i) {
            transcript += event.results[i][0].transcript;
          }

          const trimmed = transcript.trim();
          if (trimmed) {
            // Update the live preview bar so user sees the recognized words immediately in clear text
            if (previewText) {
              previewText.innerHTML = `🗣️ Heard: <strong>"${escapeHtml(trimmed)}"</strong>`;
            }
            if (speechTag) {
              speechTag.textContent = `Words: ${trimmed.split(/\s+/).length}`;
              speechTag.style.color = '#10b981';
            }

            // Also put into chatbox input
            input.value = trimmed;

            // In password verification mode: auto-verify if candidate matches
            if (!isAuthenticated) {
              const check = verifyPasswordCandidate(trimmed);
              if (check.valid) {
                verifyCandidate(trimmed);
              }
            }
          }
        };

        recognition.onerror = (err) => {
          console.warn('SpeechRecognition error:', err.error);
          if (err.error === 'no-speech') {
            if (speechTag) speechTag.textContent = 'Awaiting Speech';
          } else if (err.error === 'not-allowed' || err.error === 'permission-denied') {
            updateMicBadge('denied');
            if (previewText) previewText.textContent = '⚠️ Mic blocked. Click lock in address bar to allow.';
          } else if (err.error === 'network') {
            if (previewText) previewText.textContent = '⚠️ Speech network delay. Direct typing is active.';
          } else if (err.error !== 'aborted') {
            if (previewText) previewText.textContent = `Speech note (${err.error}). Direct typing active.`;
          }
        };

        recognition.onend = () => {
          if (speechTag) speechTag.textContent = 'Standby';
          // Auto-restart if modal is open or in continuous command mode
          if (isListening && (isAuthenticated || modal.style.display === 'flex')) {
            try {
              recognition.start();
            } catch (e) {
              isListening = false;
              micToggleBtn.classList.remove('listening');
            }
          } else {
            isListening = false;
            micToggleBtn.classList.remove('listening');
          }
        };

        recognition.start();
      } catch (err) {
        console.warn('Unable to start speech recognition:', err);
        if (previewText) previewText.textContent = `Speech error: ${err.message}. Direct typing active.`;
      }
    }

    function stopSpeechRecognition() {
      isListening = false;
      if (speechTag) speechTag.textContent = 'Muted';
      if (micToggleBtn) {
        micToggleBtn.classList.remove('listening');
        micToggleBtn.title = 'Click to activate microphone listening';
      }
      if (recognition) {
        try { recognition.abort(); } catch(e){}
        recognition = null;
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createVoiceAuthUI);
  } else {
    createVoiceAuthUI();
  }
})();
'''

with open(r'd:\Users\mike\Desktop\MyProjects\AegisOS\assets\voice-auth.js', 'w', encoding='utf-8') as f:
    f.write(content.strip() + '\n')

print("Successfully written updated voice-auth.js with Live Speech Preview & Quick Unlock!")
