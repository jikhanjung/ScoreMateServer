// 들어보기 — 악보 인식 결과(MusicXML)를 브라우저에서 소리로. 외부 라이브러리 없이 Web Audio. 쪽 보기 창의 막대에 있다.
// 적힌 순서대로 재생한다(도돌이표 · D.S. 는 따르지 않는다). 붙임줄은 한 음으로 이어 소리 낸다.
// 시작 마디는 root.dataset.startMeasure(보기 창이 지금 쪽의 첫 마디를 넣는다). 마디가 바뀌면 'player:measure' 를 알린다
// (보기 창이 그 쪽으로 넘긴다). 'player:stop' 을 받으면 멈춘다(보기 창을 닫을 때).
(function () {
  'use strict';
  var root = document.querySelector('[data-player]');
  if (!root) return;
  var STEPS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  var play = root.querySelector('[data-play]'), stop = root.querySelector('[data-stop]');
  var tempoInput = root.querySelector('[data-tempo]'), tempoLabel = root.querySelector('[data-tempo-label]');
  var status = root.querySelector('[data-status]'), lastMeasure = null;
  var partsBox = root.querySelector('[data-parts]');
  var score = null, audio = null, master = null, timer = null, state = 'stopped';
  var cursor = 0, playedFrom = 0, startedAt = 0, muted = {};

  function text(el, tag) { var x = el.querySelector(tag); return x ? x.textContent.trim() : null; }

  // MusicXML → {parts: [{id, name}], measures: [{number, start}], notes: [{part, start, length, midi}]} — 시간 단위는 4분음표
  function parse(xml) {
    var doc = new DOMParser().parseFromString(xml, 'application/xml');
    var names = {};
    doc.querySelectorAll('score-part').forEach(function (sp) { names[sp.getAttribute('id')] = text(sp, 'part-name') || sp.getAttribute('id'); });
    var parts = [], notes = [], measures = [];
    doc.querySelectorAll('part').forEach(function (part, partIndex) {
      var id = part.getAttribute('id');
      parts.push({ id: id, name: names[id] || id });
      var divisions = 1, measureStart = 0, measureLength = 4, open = {};
      part.querySelectorAll(':scope > measure').forEach(function (measure, index) {
        var position = 0, lastStart = 0, longest = 0;
        if (partIndex === 0) measures.push({ number: measure.getAttribute('number'), start: measureStart });
        Array.prototype.forEach.call(measure.children, function (el) {
          if (el.tagName === 'attributes') {
            var d = text(el, 'divisions'); if (d) divisions = Number(d);
            var beats = text(el, 'time > beats'), type = text(el, 'time > beat-type');
            if (beats && type) measureLength = Number(beats) * 4 / Number(type);
          } else if (el.tagName === 'backup' || el.tagName === 'forward') {
            var amount = Number(text(el, 'duration') || 0) / divisions;
            position += el.tagName === 'backup' ? -amount : amount;
          } else if (el.tagName === 'note') {
            if (el.querySelector('grace')) return;
            var length = Number(text(el, 'duration') || 0) / divisions;
            var chord = !!el.querySelector('chord');
            var start = chord ? lastStart : position;
            if (!chord) { lastStart = position; position += length; }
            longest = Math.max(longest, position);
            var pitch = el.querySelector('pitch');
            if (!pitch || el.querySelector('rest')) return;
            var midi = (Number(text(pitch, 'octave')) + 1) * 12 + STEPS[text(pitch, 'step')] + Number(text(pitch, 'alter') || 0);
            var voice = text(el, 'voice') || '1', key = voice + ':' + midi;
            var ties = Array.prototype.map.call(el.querySelectorAll('tie'), function (t) { return t.getAttribute('type'); });
            if (ties.indexOf('stop') >= 0 && open[key]) {
              open[key].length += length;                       // 붙임줄 — 앞 음을 늘린다
              if (ties.indexOf('start') < 0) delete open[key];
              return;
            }
            var note = { part: id, start: measureStart + start, length: length, midi: midi, index: partIndex };
            notes.push(note);
            if (ties.indexOf('start') >= 0) open[key] = note;
          }
        });
        measureStart += measure.getAttribute('implicit') === 'yes' ? Math.max(longest, 0) || measureLength : measureLength;
      });
    });
    notes.sort(function (a, b) { return a.start - b.start; });
    return { parts: parts, measures: measures, notes: notes, end: notes.length ? Math.max.apply(null, notes.map(function (n) { return n.start + n.length; })) : 0 };
  }

  function secondsPerQuarter() { return 60 / Number(tempoInput.value); }

  // 여러 음이 겹쳐도 깨지지 않게 — 컴프레서 한 번 거쳐 내보낸다
  function output() {
    if (!master) {
      master = audio.createDynamicsCompressor();
      master.threshold.value = -18; master.knee.value = 12; master.ratio.value = 4;
      master.attack.value = 0.005; master.release.value = 0.2;
      master.connect(audio.destination);
    }
    return master;
  }

  // 음 하나 — 부드러운 어택, 적힌 길이 동안 이어지다(천천히 조금 줄어든다) 끝에서 자연스럽게 사라진다.
  // (전엔 0.12초 만에 1/4 로 떨어져 모든 음이 스타카토처럼 들렸다)
  function voice(midi, when, length, index) {
    var frequency = 440 * Math.pow(2, (midi - 69) / 12);
    var gain = audio.createGain(), out = audio.createGain();
    var body = audio.createOscillator(), overtone = audio.createOscillator();
    body.type = 'triangle';
    body.frequency.value = frequency;
    body.detune.value = index % 2 ? 4 : -4;               // 파트마다 살짝 달리 — 겹쳐도 구분되게
    overtone.type = 'sine';
    overtone.frequency.value = frequency * 2;
    var overtoneGain = audio.createGain();
    overtoneGain.gain.value = 0.18;
    var filter = audio.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = Math.min(5000, frequency * (index % 2 ? 5 : 7));
    body.connect(gain); overtone.connect(overtoneGain); overtoneGain.connect(gain);
    gain.connect(filter); filter.connect(out); out.connect(output());
    out.gain.value = 0.16;
    var end = when + Math.max(length, 0.06);
    var release = 0.18;
    gain.gain.setValueAtTime(0.0001, when);
    gain.gain.linearRampToValueAtTime(1, when + 0.012);
    gain.gain.setTargetAtTime(0.7, when + 0.012, 0.25);          // 조금 줄어들어 이어진다
    gain.gain.setTargetAtTime(0.0001, end, release / 3);         // 적힌 길이가 끝나면 사라진다
    body.start(when); overtone.start(when);
    body.stop(end + release * 2); overtone.stop(end + release * 2);
  }

  function beatNow() { return playedFrom + (audio.currentTime - startedAt) / secondsPerQuarter(); }

  function measureAt(beat) {
    var current = score.measures[0];
    for (var i = 0; i < score.measures.length && score.measures[i].start <= beat + 1e-6; i++) current = score.measures[i];
    return current;
  }

  function tick() {                                // 앞으로 0.25초 안의 음을 예약한다
    var horizon = beatNow() + 0.25 / secondsPerQuarter();
    while (cursor < score.notes.length && score.notes[cursor].start < horizon) {
      var note = score.notes[cursor++];
      if (note.start < playedFrom - 1e-6 || muted[note.part]) continue;
      var when = startedAt + (note.start - playedFrom) * secondsPerQuarter();
      voice(note.midi, Math.max(when, audio.currentTime), note.length * secondsPerQuarter(), note.index);
    }
    var beat = beatNow();
    var measure = measureAt(beat);
    status.textContent = beat >= score.end ? '끝' : measure.number + '마디';
    if (measure.number !== lastMeasure) {
      lastMeasure = measure.number;
      root.dispatchEvent(new CustomEvent('player:measure', { detail: { number: measure.number } }));
    }
    if (beat >= score.end + 1) finish();
  }

  function begin(fromBeat) {
    playedFrom = fromBeat;
    cursor = 0;
    while (cursor < score.notes.length && score.notes[cursor].start < fromBeat - 1e-6) cursor++;
    startedAt = audio.currentTime + 0.1;
    timer = setInterval(tick, 25);
    state = 'playing';
    play.textContent = '⏸ 일시정지';
  }

  function halt() { clearInterval(timer); timer = null; }

  function finish() {
    halt();
    state = 'stopped';
    lastMeasure = null;
    play.textContent = '▶ 재생';
    if (audio) { audio.close(); audio = null; master = null; }
  }

  function startBeat() {
    var wanted = String(root.dataset.startMeasure || '').trim();
    var found = score.measures.filter(function (m) { return m.number === wanted; })[0];
    return found ? found.start : 0;
  }

  function load() {
    if (score) return Promise.resolve(score);
    status.textContent = '불러오는 중…';
    return fetch(root.dataset.url, { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.text();
    }).then(function (xml) {
      score = parse(xml);
      partsBox.innerHTML = '';
      score.parts.forEach(function (part) {
        var label = document.createElement('label');
        label.className = 'choice small';
        var box = document.createElement('input');
        box.type = 'checkbox'; box.checked = true;
        box.addEventListener('change', function () { muted[part.id] = !box.checked; });
        label.appendChild(box);
        label.appendChild(document.createTextNode(' ' + part.name));
        partsBox.appendChild(label);
      });
      status.textContent = score.measures.length + '마디 · 준비';
      return score;
    });
  }

  play.addEventListener('click', function () {
    load().then(function () {
      if (state === 'playing') {                     // 일시정지 — 지금 박에서 멈추고 기억
        var at = beatNow();
        halt(); audio.suspend();
        state = 'paused'; play.textContent = '▶ 이어서';
        playedFrom = at;
        return;
      }
      if (state === 'paused') {
        audio.resume().then(function () { begin(playedFrom); });
        return;
      }
      audio = new (window.AudioContext || window.webkitAudioContext)();
      begin(startBeat());
    }).catch(function () { status.textContent = '불러오지 못했습니다'; });
  });
  stop.addEventListener('click', function () { if (score) { finish(); status.textContent = '정지'; } });
  root.addEventListener('player:stop', function () { if (score && state !== 'stopped') { finish(); status.textContent = ''; } });
  tempoInput.addEventListener('input', function () {
    tempoLabel.textContent = tempoInput.value;
    if (state === 'playing') { var at = beatNow(); halt(); audio && begin(at); }   // 빠르기를 바꾸면 지금 박부터 새로
  });
  tempoLabel.textContent = tempoInput.value;
})();
