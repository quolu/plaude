type MeetingListItem = {
  id: string;
  title: string;
  started_at: string;
  duration: string;
};
type Segment = { t: number; speaker?: string; text: string };
type Phase = { t: number; title: string };
type Meeting = MeetingListItem & {
  transcript: Segment[];
  summary: string;
  has_audio: boolean;
  template_id?: string;
  phases: Phase[];
};
type Template = {
  id: string;
  title: string;
  when: string;
  category: string;
  body: string;
};

import { bindTranscriptSeek, followPlayback } from "./seek";
import { newTemplateFields } from "./template-create";
import { shell } from "./shell";
import { bindPlayer, fmtTime, playerMarkup } from "./player";

const app = document.getElementById("app")!;

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json() as Promise<T>;
}

function dateLabel(iso: string): string {
  const day = (iso || "").slice(0, 10);
  return day || "日付なし";
}

function bindFilter(rows: MeetingListItem[]) {
  const input = document.getElementById("q") as HTMLInputElement | null;
  if (!input) return;
  const apply = () => {
    const q = input.value.trim().toLowerCase();
    app.querySelectorAll<HTMLElement>("[data-meeting]").forEach((el) => {
      const hay = (el.dataset.meeting || "").toLowerCase();
      el.hidden = Boolean(q) && !hay.includes(q);
    });
    app.querySelectorAll<HTMLElement>("[data-day]").forEach((group) => {
      const visible = [...group.querySelectorAll<HTMLElement>("[data-meeting]")].some((el) => !el.hidden);
      group.hidden = !visible;
    });
  };
  input.addEventListener("input", apply);
  void rows;
}

function renderList(title: string, rows: MeetingListItem[], active: string) {
  if (!rows.length) {
    app.innerHTML = shell(
      active,
      `<h2>${esc(title)}</h2><p class="empty">まだ公開された会議はない。</p>`,
    );
    return;
  }
  const days = [...new Set(rows.map((r) => dateLabel(r.started_at)))];
  const groups = days
    .map((day) => {
      const items = rows
        .filter((r) => dateLabel(r.started_at) === day)
        .map(
          (r) =>
            `<a class="file" href="/m/${esc(r.id)}" data-meeting="${esc(r.title)}"><span class="file-title">${esc(r.title)}</span><span class="file-meta"><span class="label">${esc(r.duration || "")}</span><time>${esc((r.started_at || "").replace("T", " "))}</time></span></a>`,
        )
        .join("");
      return `<section class="day" data-day><h3>${esc(day)}</h3>${items}</section>`;
    })
    .join("");
  app.innerHTML = shell(
    active,
    `<div class="page-head"><h2>${esc(title)}</h2><label class="filter">絞り込み<input id="q" type="search" placeholder="タイトル" /></label></div>${groups}`,
  );
  bindFilter(rows);
}

function headings(md: string): { id: string; text: string }[] {
  return md
    .split("\n")
    .filter((l) => l.startsWith("## "))
    .map((l, i) => ({ id: `h-${i}`, text: l.replace(/^##+ /, "") }));
}

function inlineMd(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderLine(raw: string): string {
  const line = raw.replace(/^\s+/, "");
  const depth = Math.min(3, Math.floor((raw.length - line.length) / 2));
  if (line.startsWith("# ")) return `<h2>${inlineMd(line.slice(2))}</h2>`;
  if (line.startsWith("- [ ] ")) return `<li class="ind-${depth}">☐ ${inlineMd(line.slice(6))}</li>`;
  if (line.startsWith("- ") || line.startsWith("* ")) return `<li class="ind-${depth}">${inlineMd(line.slice(2))}</li>`;
  if (/^\d+\. /.test(line)) return `<li class="ind-${depth}">${inlineMd(line.replace(/^\d+\. /, ""))}</li>`;
  if (line.startsWith("> ")) return `<blockquote>${inlineMd(line.slice(2))}</blockquote>`;
  return line ? `<p>${inlineMd(line)}</p>` : "";
}

function renderMd(md: string): string {
  let h = 0;
  let open = false;
  const out: string[] = [];
  for (const raw of md.split("\n")) {
    const line = raw.replace(/^\s+/, "");
    if (line.startsWith("## ")) {
      if (open) out.push("</article>");
      out.push(`<article class="sum-card" id="h-${h++}"><h3>${inlineMd(line.slice(3))}</h3>`);
      open = true;
      continue;
    }
    out.push(renderLine(raw));
  }
  if (open) out.push("</article>");
  return out.join("\n") || `<p class="empty">（未記入）</p>`;
}

function transcriptHtml(segs: Segment[], phases: Phase[]): string {
  let lastSpeaker: string | null = null;
  const seg = (s: Segment) => {
    const speaker = s.speaker || "";
    const changed = speaker && speaker !== lastSpeaker;
    lastSpeaker = speaker || lastSpeaker;
    const tag = changed ? `<span class="who">${esc(speaker)}</span>` : "";
    return `<div class="seg${changed ? " turn" : ""}" data-t="${s.t}"><time>${fmtTime(s.t)}</time><div>${tag}${esc(s.text)}</div></div>`;
  };
  if (!phases.length) return segs.map(seg).join("");
  return phases
    .map((p, i) => {
      const end = i + 1 < phases.length ? phases[i + 1].t : Infinity;
      lastSpeaker = null;
      const body = segs.filter((s) => s.t >= p.t && s.t < end).map(seg).join("");
      return `<section class="phase" id="p-${i}"><h3 class="phase-head" data-t="${p.t}"><time>${fmtTime(p.t)}</time>${esc(p.title)}</h3>${body}</section>`;
    })
    .join("");
}

async function renderMeeting(id: string, tab: string) {
  const m = await getJson<Meeting>(`/api/meetings/${id}`);
  const toc = headings(m.summary || "");
  const segs = m.transcript || [];
  const phases = m.phases || [];
  const transcript = transcriptHtml(segs, phases);
  const phaseNav = phases
    .map(
      (p, i) =>
        `<a href="/m/${esc(id)}?p=${i}" data-jump="${i}" data-pt="${p.t}"><time>${fmtTime(p.t)}</time>${esc(p.title)}</a>`,
    )
    .join("");
  const summaryNav = toc.map((h) => `<a href="#${h.id}">${esc(h.text)}</a>`).join("");
  const pane = tab === "summary" ? renderMd(m.summary || "（未記入）") : transcript;
  const tocBody = tab === "summary" ? summaryNav : phaseNav;
  app.innerHTML = shell(
    "files",
    `<div class="hero">
      <p class="eyebrow">${esc((m.started_at || "").replace("T", " "))} · ${esc(m.duration || "")}</p>
      <h2>${esc(m.title)}</h2>
    </div>
    <div class="player-wrap">${playerMarkup(id, phases, m.has_audio)}</div>
    <div class="tabs">
      <button type="button" data-tab="transcript" class="${tab === "transcript" ? "on" : ""}">文字起こし</button>
      <button type="button" data-tab="summary" class="${tab === "summary" ? "on" : ""}">要約</button>
    </div>
    <div class="layout">
      <div id="pane">${pane}</div>
      <aside class="toc" data-toc>${tocBody || `<p class="muted">目次はない</p>`}</aside>
    </div>
    <button type="button" class="toc-open" data-toc-open>目次</button>`,
    true,
  );
  app.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = (btn as HTMLElement).dataset.tab || "transcript";
      const params = new URLSearchParams(location.search);
      params.set("tab", next);
      history.replaceState({}, "", `/m/${id}?${params.toString()}`);
      void route();
    });
  });
  const player = bindPlayer(app);
  bindTranscriptSeek(app, player);
  followPlayback(app, player);
  const jumpTo = (i: number) => {
    const target = document.getElementById(`p-${i}`);
    if (target) target.scrollIntoView({ block: "start" });
    if (player && phases[i]) player.currentTime = phases[i].t;
  };
  app.querySelectorAll("[data-jump]").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const i = Number((a as HTMLElement).dataset.jump);
      const params = new URLSearchParams(location.search);
      params.set("p", String(i));
      history.replaceState({}, "", `/m/${id}?${params.toString()}`);
      jumpTo(i);
    });
  });
  const sheet = app.querySelector("[data-toc]");
  app.querySelector("[data-toc-open]")?.addEventListener("click", () => {
    sheet?.classList.toggle("open");
  });
  const want = new URLSearchParams(location.search).get("p");
  if (want !== null && phases[Number(want)]) jumpTo(Number(want));
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
    app.innerHTML = shell(
      "templates",
      `<h2>${esc(t.title || t.id)}</h2>
      <p class="muted">${esc(t.when)}</p>
      <form class="edit" id="edit-template">
        <label>名前<input id="title" value="${esc(t.title)}" /></label>
        <label>いつ使うか<input id="when" value="${esc(t.when)}" /></label>
        <label>本文<textarea id="body" rows="16">${esc(t.body)}</textarea></label>
        <p><button type="button" id="save">保存</button></p>
      </form>`,
    );
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
  app.innerHTML = shell(
    "templates",
    `<h2>テンプレート</h2>
    <form id="create-template" class="create">
      <label>ID<input id="new-id" name="id" placeholder="lecture-notes" required /></label>
      <label>名前<input id="new-title" name="title" placeholder="講義ノート" /></label>
      <label>いつ使うか<input id="new-when" name="when" placeholder="講義のあと" /></label>
      <button id="create" type="submit">作成</button>
    </form>
    ${cats
      .map(
        (c) =>
          `<h3 class="cat">${esc(c)}</h3><div class="cards">${rows
            .filter((r) => (r.category || "一般") === c)
            .map(
              (r) =>
                `<a class="card" href="/templates/${esc(r.id)}"><h3>${esc(r.title)}</h3><p class="muted">${esc(r.when)}</p></a>`,
            )
            .join("")}</div>`,
      )
      .join("")}`,
  );
  document.getElementById("create-template")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fields = newTemplateFields(
      (document.getElementById("new-id") as HTMLInputElement).value,
      (document.getElementById("new-title") as HTMLInputElement).value,
      (document.getElementById("new-when") as HTMLInputElement).value,
      "",
    );
    const res = await fetch(`/api/templates/${fields.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!res.ok) throw new Error(`create ${res.status}`);
    history.pushState({}, "", `/templates/${fields.id}`);
    void route();
  });
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
  app.innerHTML = shell("home", "<p class=\"empty\">ページがない。</p>");
}

window.addEventListener("popstate", () => void route());
document.addEventListener("click", (e) => {
  const ev = e as MouseEvent;
  if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
  const a = (ev.target as HTMLElement).closest("a");
  if (!a || a.target || a.origin !== location.origin) return;
  const href = a.getAttribute("href") || "";
  if (href.startsWith("#")) return;
  if (a.hasAttribute("data-jump")) return;
  e.preventDefault();
  history.pushState({}, "", a.href);
  void route();
});
void route();
