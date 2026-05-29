// QA browser shim.
//
// Installed via context.add_init_script() so it runs before any page JS.
//
// Responsibilities (post-pivot 2026-05-29):
//   - Capture INBOUND audio (the bot's voice) on every RTCPeerConnection by
//     attaching a MediaRecorder to each inbound audio track and accumulating
//     chunks into window.__qa_bot_audio_chunks.
//   - Still expose the legacy getUserMedia override + per-PC instrumentation
//     for debugging; with --use-file-for-fake-audio-capture the gUM override
//     is a no-op pass-through unless a test explicitly toggles it off.
(() => {
  if (window.__qa_fake_mic_installed) return;
  window.__qa_fake_mic_installed = true;

  const AC = window.AudioContext || window.webkitAudioContext;
  const ctx = new AC({ sampleRate: 48000 });
  const dest = ctx.createMediaStreamDestination();
  // Keep the destination "warm" so getAudioTracks()[0].enabled stays true.
  const keepAlive = ctx.createConstantSource();
  const muteGain = ctx.createGain();
  muteGain.gain.value = 0; // inaudible
  keepAlive.connect(muteGain).connect(dest);
  try { keepAlive.start(); } catch (_) {}

  window.__qa_audio_ctx = ctx;
  window.__qa_audio_dest = dest;
  window.__qa_audio_log = [];

  // gUM is left as PASS-THROUGH by default so --use-file-for-fake-audio-capture
  // can supply the synthetic mic. Tests that want to override the mic stream
  // can set window.__qa_override_gum = true BEFORE the page makes its first
  // gUM call (e.g. via add_init_script in a separate ctx that toggles it).
  const origGUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia = async (constraints) => {
    window.__qa_audio_log.push({ ts: Date.now(), evt: 'gUM', constraints });
    if (window.__qa_override_gum && constraints && constraints.audio) {
      try {
        if (constraints.video) {
          const real = await origGUM({ video: constraints.video });
          return new MediaStream([
            ...real.getVideoTracks(),
            ...dest.stream.getAudioTracks(),
          ]);
        }
        return dest.stream;
      } catch (e) {
        window.__qa_audio_log.push({ ts: Date.now(), evt: 'gUM_error', error: String(e) });
        throw e;
      }
    }
    return origGUM(constraints);
  };

  // Base64 -> Float32Array (PCM, little-endian, mono).
  function b64ToFloat32(b64) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    // Reinterpret as Float32 little-endian (Chromium is LE).
    return new Float32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4);
  }

  window.__qa_speakPcm = async (b64, sampleRate, gain = 1.0) => {
    if (ctx.state === 'suspended') {
      try { await ctx.resume(); } catch (_) {}
    }
    const pcm = b64ToFloat32(b64);
    // Compute peak to log it (so we can spot near-silent inputs).
    let peak = 0;
    for (let i = 0; i < pcm.length; i++) {
      const a = Math.abs(pcm[i]);
      if (a > peak) peak = a;
    }
    const buf = ctx.createBuffer(1, pcm.length, sampleRate);
    buf.copyToChannel(pcm, 0);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const gainNode = ctx.createGain();
    gainNode.gain.value = gain;
    src.connect(gainNode).connect(dest);
    const started = Date.now();
    src.start();
    const tracks = dest.stream.getAudioTracks();
    window.__qa_audio_log.push({
      ts: started,
      evt: 'speak',
      samples: pcm.length,
      sampleRate,
      peak,
      gain,
      ctxState: ctx.state,
      destTrackCount: tracks.length,
      destTrackEnabled: tracks[0] && tracks[0].enabled,
      destTrackMuted: tracks[0] && tracks[0].muted,
    });
    return new Promise((resolve) => { src.onended = () => resolve({ ts: Date.now(), samples: pcm.length, peak }); });
  };

  // Test convenience: synth tone for connectivity PoC.
  window.__qa_speakTone = async (freqHz, durSec, gain = 0.25) => {
    if (ctx.state === 'suspended') {
      try { await ctx.resume(); } catch (_) {}
    }
    const sr = ctx.sampleRate;
    const samples = Math.floor(sr * durSec);
    const pcm = new Float32Array(samples);
    for (let i = 0; i < samples; i++) {
      pcm[i] = Math.sin(2 * Math.PI * freqHz * i / sr) * gain;
    }
    const buf = ctx.createBuffer(1, samples, sr);
    buf.copyToChannel(pcm, 0);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(dest);
    src.start();
    return new Promise((resolve) => { src.onended = () => resolve({ samples }); });
  };

  // ── Bot audio capture ─────────────────────────────────────────────────
  window.__qa_bot_recorders = [];
  window.__qa_bot_chunks_b64 = [];  // accumulated base64 webm chunks
  window.__qa_bot_mime = null;
  window.__qa_recorded_track_ids = new Set();

  function __qa_attach_recorder(track) {
    if (!track) return;
    if (window.__qa_recorded_track_ids.has(track.id)) {
      window.__qa_audio_log.push({ ts: Date.now(), evt: 'recorder_dedup', id: track.id });
      return;
    }
    window.__qa_recorded_track_ids.add(track.id);
    const ms = new MediaStream([track]);
    // Prefer audio/webm with opus, fallback to whatever the browser supports.
    let mime = '';
    if (window.MediaRecorder) {
      const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'];
      for (const c of candidates) {
        if (MediaRecorder.isTypeSupported(c)) { mime = c; break; }
      }
    } else {
      window.__qa_audio_log.push({ ts: Date.now(), evt: 'no_media_recorder' });
      return;
    }
    const rec = new MediaRecorder(ms, mime ? { mimeType: mime } : undefined);
    window.__qa_bot_mime = rec.mimeType;
    window.__qa_bot_recorders.push(rec);
    rec.ondataavailable = async (ev) => {
      if (!ev.data || ev.data.size === 0) return;
      const buf = await ev.data.arrayBuffer();
      const bytes = new Uint8Array(buf);
      let bin = '';
      // Convert in chunks to keep stack happy.
      const CH = 0x8000;
      for (let i = 0; i < bytes.length; i += CH) {
        bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
      }
      window.__qa_bot_chunks_b64.push(btoa(bin));
      window.__qa_audio_log.push({ ts: Date.now(), evt: 'chunk', bytes: bytes.length });
    };
    rec.onerror = (e) => window.__qa_audio_log.push({ ts: Date.now(), evt: 'recorder_error', error: String(e.error || e) });
    rec.onstart = () => window.__qa_audio_log.push({ ts: Date.now(), evt: 'recorder_start', mime: rec.mimeType });
    rec.onstop = () => window.__qa_audio_log.push({ ts: Date.now(), evt: 'recorder_stop' });
    // 500ms timeslice so we get incremental chunks.
    rec.start(500);
  }

  window.__qa_stop_bot_recording = async () => {
    for (const r of window.__qa_bot_recorders) {
      try {
        if (r.state !== 'inactive') {
          await new Promise((resolve) => { r.onstop = () => resolve(); r.stop(); });
        }
      } catch (_) {}
    }
    return { count: window.__qa_bot_chunks_b64.length, mime: window.__qa_bot_mime };
  };

  // First user gesture resumes the AudioContext if Chrome left it suspended.
  const resumeOnce = () => { if (ctx.state === 'suspended') ctx.resume(); };
  document.addEventListener('click', resumeOnce, { once: true, capture: true });
  document.addEventListener('keydown', resumeOnce, { once: true, capture: true });

  // ── RTCPeerConnection instrumentation ──────────────────────────────────
  // Daily may bypass our gUM and call addTrack/addTransceiver with a track
  // sourced elsewhere. We log everything and remember any audio sender so
  // window.__qa_force_inject_track() can replace it with our dest track.
  // Track ALL RTCPeerConnections ever created. At force-inject time we iterate
  // the live ones (signalingState !== 'closed' and connectionState !== 'closed')
  // and replace each audio sender's track. Daily creates >1 PC and we need to
  // hit the live one without guessing which.
  window.__qa_pcs = [];
  const RealPC = window.RTCPeerConnection;
  if (RealPC && !window.__qa_pc_wrapped) {
    window.__qa_pc_wrapped = true;
    const Wrapped = function (...args) {
      const pc = new RealPC(...args);
      window.__qa_pcs.push(pc);
      window.__qa_audio_log.push({ ts: Date.now(), evt: 'pc_new', index: window.__qa_pcs.length - 1 });
      pc.addEventListener('connectionstatechange', () => {
        window.__qa_audio_log.push({
          ts: Date.now(), evt: 'pc_state', connectionState: pc.connectionState, signalingState: pc.signalingState,
        });
      });
      pc.addEventListener('track', (e) => {
        const trk = e.track;
        const kind = trk && trk.kind;
        window.__qa_audio_log.push({ ts: Date.now(), evt: 'pc_track', kind, id: trk && trk.id, label: trk && trk.label });
        if (kind === 'audio') {
          try {
            __qa_attach_recorder(trk);
          } catch (err) {
            window.__qa_audio_log.push({ ts: Date.now(), evt: 'recorder_attach_error', error: String(err) });
          }
        }
      });
      return pc;
    };
    Wrapped.prototype = RealPC.prototype;
    window.RTCPeerConnection = Wrapped;
  }

  // Force-swap every live PC's audio sender tracks for ours.
  // Iterates BOTH getSenders() and getTransceivers() so we catch recvonly
  // transceivers whose senders have no current track. Also tries
  // pc.addTrack(ourTrack) as a last resort when no audio sender exists.
  window.__qa_force_inject_track = async () => {
    const ourTrack = dest.stream.getAudioTracks()[0];
    if (!ourTrack) return { ok: false, reason: 'no-dest-track' };
    const results = [];
    for (let i = 0; i < window.__qa_pcs.length; i++) {
      const pc = window.__qa_pcs[i];
      const closed = pc.signalingState === 'closed' || pc.connectionState === 'closed';
      if (closed) {
        results.push({ pc: i, skipped: 'pc-closed' });
        continue;
      }
      const transceivers = pc.getTransceivers ? pc.getTransceivers() : [];
      let anyAudioSenderTried = false;
      for (let j = 0; j < transceivers.length; j++) {
        const t = transceivers[j];
        const recvKind = t.receiver && t.receiver.track && t.receiver.track.kind;
        const sendKind = t.sender && t.sender.track && t.sender.track.kind;
        const mid = t.mid;
        const dir = t.currentDirection || t.direction;
        // Heuristic: a transceiver is "audio-ish" if either the recv or send
        // track is audio, or mid hints audio (Daily often uses "0" for audio).
        const isAudio = recvKind === 'audio' || sendKind === 'audio';
        const entry = { pc: i, mid, dir, recvKind, sendKind };
        if (!isAudio) {
          entry.skipped = 'not-audio';
          results.push(entry);
          continue;
        }
        anyAudioSenderTried = true;
        if (t.sender.track === ourTrack) {
          entry.skipped = 'already-ours';
          results.push(entry);
          continue;
        }
        try {
          await t.sender.replaceTrack(ourTrack);
          entry.replaced = true;
          // If direction was recvonly, flip to sendrecv so the packet actually goes out
          if (t.direction && t.direction.indexOf('send') === -1) {
            try {
              t.direction = 'sendrecv';
              entry.directionChanged = 'sendrecv';
            } catch (e) {
              entry.directionChangeError = String(e);
            }
          }
          results.push(entry);
        } catch (e) {
          entry.error = String(e);
          results.push(entry);
        }
      }
      if (!anyAudioSenderTried) {
        // Last resort: addTrack on the PC. This will trigger renegotiation.
        try {
          const sender = pc.addTrack(ourTrack, dest.stream);
          results.push({ pc: i, addedTrack: true, senderTrackKind: sender.track && sender.track.kind });
        } catch (e) {
          results.push({ pc: i, addTrackError: String(e) });
        }
      }
    }
    window.__qa_audio_log.push({ ts: Date.now(), evt: 'force_inject', pc_count: window.__qa_pcs.length, results });
    return { ok: true, pc_count: window.__qa_pcs.length, results };
  };
})();
