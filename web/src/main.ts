type MeetingListItem = {
  id: string;
  title: string;
  started_at: string;
  duration: string;
};
type Segment = { t: number; speaker?: string; text: string };
type Meeting = MeetingListItem & {
  transcript: Segment[];
  summary: string;
  has_audio: boolean;
  template_id?: string;
};
type Template = {
  id: string;
  title: string;
  when: string;
  category: string;
  body: string;
};

const app = document.getElementById("app")!;

function fmtTime(t: number): string {
  const s = Math.max(0, Math.floor(t));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}

function rail(active: string): string {
  const item = (href: string, label: string, key: string) =>
    `<a href="${href}" class="${active === key ? "active" : ""}">${label}</a>`;
  return `<aside class="rail"><h1>plaude</h1>${item("/", "ホーム", "home")}${item("/files", "すべてのファイル", "files")}${item("/templates", "テンプレート", "templates")}</aside>`;
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json() as Promise<T>;
}

function renderList(title: string, rows: MeetingListItem[], active: string) {
  app.innerHTML = `<div class="app">${rail(active)}<main class="main"><h2>${title}</h2>${
    rows
      .map(
        (r) =>
          `<a class="row" href="/m/${r.id}"><span>${r.title}</span><span class="muted">${r.duration}</span><span class="muted">${r.started_at.replace("T", " ")}</span></a>`,
      )
      .join("")
  }</main></div>`;
}

function headings(md: string): { id: string; text: string }[] {
  return md
    .split("\n")
    .filter((l) => l.startsWith("## "))
    .map((l, i) => ({ id: `h-${i}`, text: l.replace(/^##+ /, "") }));
}

function renderMd(md: string): string {
  return md
    .split("\n")
    .map((line) => {
      if (line.startsWith("# ")) return `<h2>${line.slice(2)}</h2>`;
      if (line.startsWith("## ")) return `<h3>${line.slice(3)}</h3>`;
      if (line.startsWith("- ")) return `<li>${line.slice(2)}</li>`;
      if (/^\d+\. /.test(line)) return `<li>${line.replace(/^\d+\. /, "")}</li>`;
      return line ? `<p>${line}</p>` : "";
    })
    .join("\n");
}

async function renderMeeting(id: string, tab: string) {
  const m = await getJson<Meeting>(`/api/meetings/${id}`);
  const toc = headings(m.summary || "");
  const audio = m.has_audio
    ? `<audio id="player" controls src="/m/${id}/audio"></audio>`
    : "";
  const transcript = (m.transcript || [])
    .map(
      (s) =>
        `<div class="seg" data-t="${s.t}"><time>${fmtTime(s.t)}</time><div>${s.text}</div></div>`,
    )
    .join("");
  app.innerHTML = `<div class="app">${rail("files")}<main class="main">
    <div class="hero"><h2>${m.title}</h2><div class="muted">${m.started_at.replace("T", " ")} · ${m.duration}</div>${audio}</div>
    <div class="tabs">
      <button data-tab="transcript" class="${tab === "transcript" ? "on" : ""}">文字起こし</button>
      <button data-tab="summary" class="${tab === "summary" ? "on" : ""}">要約</button>
    </div>
    <div class="layout">
      <div id="pane">${tab === "summary" ? renderMd(m.summary || "（未記入）") : transcript}</div>
      <aside class="toc">${toc.map((h) => `<a href="#${h.id}">${h.text}</a>`).join("")}</aside>
    </div>
  </main></div>`;
  app.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      history.replaceState({}, "", `/m/${id}?tab=${(btn as HTMLElement).dataset.tab}`);
      void route();
    });
  });
  const player = document.getElementById("player") as HTMLAudioElement | null;
  app.querySelectorAll(".seg").forEach((el) => {
    el.addEventListener("click", () => {
      const t = Number((el as HTMLElement).dataset.t || 0);
      if (player) player.currentTime = t;
    });
  });
}

async function renderTemplates(editId?: string) {
  const rows = await getJson<Template[]>("/api/templates");
  if (editId) {
    const t = rows.find((x) => x.id === editId) || {
      id: editId,
      title: "",
      when: "",
      category: "",
      body: "",
    };
    app.innerHTML = `<div class="app">${rail("templates")}<main class="main"><h2>${t.title || t.id}</h2>
      <p class="muted">${t.when}</p>
      <p><input id="title" value="${t.title}" /></p>
      <p><input id="when" value="${t.when}" /></p>
      <p><textarea id="body" rows="16">${t.body}</textarea></p>
      <p><button id="save">保存</button></p>
    </main></div>`;
    document.getElementById("save")?.addEventListener("click", async () => {
      await fetch(`/api/templates/${t.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: (document.getElementById("title") as HTMLInputElement).value,
          when: (document.getElementById("when") as HTMLInputElement).value,
          body: (document.getElementById("body") as HTMLTextAreaElement).value,
        }),
      });
      history.pushState({}, "", "/templates");
      void route();
    });
    return;
  }
  const cats = [...new Set(rows.map((r) => r.category || "一般"))];
  app.innerHTML = `<div class="app">${rail("templates")}<main class="main"><h2>テンプレート</h2>
    ${cats
      .map(
        (c) =>
          `<h3>${c}</h3><div class="cards">${rows
            .filter((r) => (r.category || "一般") === c)
            .map(
              (r) =>
                `<a class="card" href="/templates/${r.id}"><h3>${r.title}</h3><p class="muted">${r.when}</p></a>`,
            )
            .join("")}</div>`,
      )
      .join("")}
  </main></div>`;
}

async function route() {
  const path = location.pathname;
  const tab = new URLSearchParams(location.search).get("tab") || "transcript";
  if (path === "/" || path === "") {
    renderList("最近のファイル", await getJson("/api/meetings"), "home");
    return;
  }
  if (path === "/files") {
    renderList("すべてのファイル", await getJson("/api/meetings"), "files");
    return;
  }
  const meet = path.match(/^\/m\/([^/]+)$/);
  if (meet) {
    await renderMeeting(meet[1], tab);
    return;
  }
  const tpl = path.match(/^\/templates\/([^/]+)$/);
  if (path === "/templates") {
    await renderTemplates();
    return;
  }
  if (tpl) {
    await renderTemplates(tpl[1]);
    return;
  }
  app.innerHTML = "<p>not found</p>";
}

window.addEventListener("popstate", () => void route());
document.addEventListener("click", (e) => {
  const a = (e.target as HTMLElement).closest("a");
  if (!a || a.target || a.origin !== location.origin) return;
  e.preventDefault();
  history.pushState({}, "", a.href);
  void route();
});
void route();
