export function bindTranscriptSeek(root, player) {
  if (!player) return;
  for (const el of root.querySelectorAll("[data-t]")) {
    el.addEventListener("click", () => {
      player.currentTime = Number(el.dataset.t || 0);
    });
  }
}

export function followPlayback(root, player) {
  if (!player) return;
  const tick = () => {
    const t = player.currentTime;
    const segs = [...root.querySelectorAll(".seg[data-t]")];
    let now = null;
    for (const el of segs) {
      if (Number(el.dataset.t || 0) <= t + 0.05) now = el;
    }
    for (const el of segs) el.classList.toggle("now", el === now);
    const jumps = [...root.querySelectorAll("[data-jump]")];
    let active = null;
    for (const a of jumps) {
      if (Number(a.dataset.pt || 0) <= t + 0.05) active = a;
    }
    for (const a of jumps) a.classList.toggle("on", a === active);
  };
  player.addEventListener("timeupdate", tick);
  player.addEventListener("seeked", tick);
  tick();
}
