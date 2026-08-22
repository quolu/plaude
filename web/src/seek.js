export function bindTranscriptSeek(root, player) {
  if (!player) return;
  for (const el of root.querySelectorAll("[data-t]")) {
    el.addEventListener("click", () => {
      player.currentTime = Number(el.dataset.t || 0);
    });
  }
}
