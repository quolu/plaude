export function newTemplateFields(id, title, when, body) {
  const tid = String(id || "").trim();
  if (!/^[0-9A-Za-z._-]{1,128}$/.test(tid)) {
    throw new Error("bad id");
  }
  return {
    id: tid,
    title: String(title || tid).trim() || tid,
    when: String(when || "").trim(),
    body: String(body || ""),
  };
}
