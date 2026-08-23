export function fmtTime(t: number): string {
  const s = Math.max(0, Math.floor(t));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}

type Phase = { t: number; title: string };

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

export function playerMarkup(id: string, phases: Phase[], hasAudio: boolean): string {
  if (!hasAudio) {
    return `<div class="player player-empty">音声ファイルはない</div>`;
  }
  const marks = phases
    .map(
      (p) =>
        `<button type="button" class="player-mark" data-mark="${p.t}" title="${esc(p.title)}" aria-label="${esc(p.title)}"></button>`,
    )
    .join("");
  return `<div class="player" id="player-ui">
    <audio id="player" src="/m/${id}/audio" preload="metadata"></audio>
    <button type="button" class="player-play" data-play aria-label="再生">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
    </button>
    <div class="player-body">
      <div class="player-track" data-track role="slider" aria-label="再生位置" aria-valuemin="0" aria-valuemax="0" aria-valuenow="0" tabindex="0">
        <div class="player-fill" data-fill></div>
        <div class="player-head" data-head></div>
        <div class="player-marks">${marks}</div>
      </div>
      <div class="player-times"><time data-cur>00:00</time><time data-dur>--:--</time></div>
    </div>
  </div>`;
}

export function bindPlayer(root: HTMLElement): HTMLAudioElement | null {
  const audio = root.querySelector("#player") as HTMLAudioElement | null;
  if (!audio) return null;
  const play = root.querySelector("[data-play]") as HTMLButtonElement | null;
  const track = root.querySelector("[data-track]") as HTMLElement | null;
  const fill = root.querySelector("[data-fill]") as HTMLElement | null;
  const head = root.querySelector("[data-head]") as HTMLElement | null;
  const cur = root.querySelector("[data-cur]") as HTMLElement | null;
  const durEl = root.querySelector("[data-dur]") as HTMLElement | null;

  const duration = () => (Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : 0);

  const placeMarks = () => {
    const d = duration();
    if (!d) return;
    root.querySelectorAll<HTMLElement>("[data-mark]").forEach((el) => {
      const t = Number(el.dataset.mark || 0);
      el.style.left = `${(t / d) * 100}%`;
    });
    if (track) track.setAttribute("aria-valuemax", String(Math.floor(d)));
    if (durEl) durEl.textContent = fmtTime(d);
  };

  const paint = () => {
    const d = duration();
    const t = audio.currentTime || 0;
    const pct = d ? (t / d) * 100 : 0;
    if (fill) fill.style.width = `${pct}%`;
    if (head) head.style.left = `${pct}%`;
    if (cur) cur.textContent = fmtTime(t);
    if (track) track.setAttribute("aria-valuenow", String(Math.floor(t)));
  };

  const seekAt = (clientX: number) => {
    if (!track) return;
    const d = duration();
    if (!d) return;
    const rect = track.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    audio.currentTime = ratio * d;
    paint();
  };

  const syncPlay = () => {
    if (!play) return;
    const on = !audio.paused;
    play.classList.toggle("on", on);
    play.setAttribute("aria-label", on ? "一時停止" : "再生");
    play.innerHTML = on
      ? `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h4v14H7zm6 0h4v14h-4z"/></svg>`
      : `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>`;
  };

  play?.addEventListener("click", () => {
    if (audio.paused) void audio.play();
    else audio.pause();
  });
  audio.addEventListener("play", syncPlay);
  audio.addEventListener("pause", syncPlay);
  audio.addEventListener("timeupdate", paint);
  audio.addEventListener("seeked", paint);
  audio.addEventListener("loadedmetadata", () => {
    placeMarks();
    paint();
  });
  track?.addEventListener("click", (e) => {
    if ((e.target as HTMLElement).closest("[data-mark]")) return;
    seekAt(e.clientX);
  });
  track?.addEventListener("keydown", (e) => {
    const d = duration();
    if (!d) return;
    if (e.key === "ArrowRight") {
      audio.currentTime = Math.min(d, audio.currentTime + 5);
      e.preventDefault();
    }
    if (e.key === "ArrowLeft") {
      audio.currentTime = Math.max(0, audio.currentTime - 5);
      e.preventDefault();
    }
  });
  root.querySelectorAll<HTMLElement>("[data-mark]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      audio.currentTime = Number(el.dataset.mark || 0);
      paint();
    });
  });
  placeMarks();
  paint();
  syncPlay();
  return audio;
}
