const HELPER_ZH = { none: "none", mixed: "含实体", partial: "残缺" };
const LEVEL_ZH = { sentence: "句子", clause: "分隔符", enclosure: "括号引号", space: "空格", window: "窗口", propagate: "全文补全" };
const SOURCE_ZH = { segment: "标点切分", window: "窗口选择", merged: "合并", fallback: "兜底", propagated: "全文补全" };
const PALETTE = [
  ["#e7efff", "#1d4ed8"], ["#efe9ff", "#6d28d9"], ["#fff3dc", "#b45309"],
  ["#e3f7ec", "#047857"], ["#ffe8ec", "#be123c"], ["#e6f6fb", "#0e7490"],
];
const SAMPLES = {
  default: [
    ["快递单", "收件人：李秀英，电话：13800138000，地址：浙江省杭州市西湖区文三路90号东部软件园3号楼。"],
    ["新闻", "昨天下午，张伟教授在清华大学主楼作了报告，随后前往北京市海淀区中关村大街27号参观。马云创办了阿里巴巴。"],
    ["合同", "甲方：阿里巴巴（中国）有限公司，乙方：杭州海康威视数字技术股份有限公司。"],
    ["英文", "Tim Cook announced that Apple will open a new office in Austin, Texas."],
    ["无实体", "今天天气不错，我们下午三点开会讨论第二季度的预算。"],
  ],
  medical: [
    ["病历", "患者对青霉素过敏，改用阿奇霉素治疗肺炎支原体肺炎。建议完善血常规及胸部CT检查。"],
    ["慢病", "既往有高血压病史十年，长期服用硝苯地平控释片，定期监测糖化血红蛋白。"],
    ["无实体", "饭后记得散步半小时，保持心情愉快。"],
  ],
  ecommerce: [
    ["商品", "耐克Air Force 1白色款，原价899元，现价599元。"],
    ["数码", "佳能EOS R6 Mark II机身价格约14999元，索尼WH-1000XM5的降噪效果更好。"],
    ["无实体", "请问这个包邮吗？什么时候发货？"],
  ],
};

const $ = (id) => document.getElementById(id);
const textEl = $("text");
const schemaEl = $("schema");
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
let presets = {};
let labels = {};

function colorOf(label) {
  const i = Object.keys(labels).indexOf(label);
  return i < 0 ? ["#f2f4f7", "#475467"] : PALETTE[i % PALETTE.length];
}
function titleOf(label) { return labels[label] || HELPER_ZH[label] || label; }
function tag(label, extra = "") {
  const [bg, ink] = colorOf(label);
  return `<span class="tag" style="background:${bg};color:${ink}">${esc(titleOf(label))}${extra}</span>`;
}

function schemaFromEditor() {
  const data = JSON.parse(schemaEl.value);
  const ents = data.entities || data;
  labels = Object.fromEntries(Object.entries(ents).map(([k, v]) => [k, (typeof v === "object" && v.title) || k]));
  return data;
}
function renderLegend() {
  $("legend").innerHTML = Object.keys(labels).map((k) => tag(k)).join("");
}
function renderSamples(key) {
  $("samples").innerHTML = "";
  for (const [name, text] of SAMPLES[key] || []) {
    const b = document.createElement("button");
    b.className = "chip";
    b.textContent = name;
    b.onclick = () => { textEl.value = text; updateCount(); };
    $("samples").appendChild(b);
  }
}
function selectPreset(key) {
  const { name, ...schema } = presets[key];
  schemaEl.value = JSON.stringify(schema, null, 2);
  schemaFromEditor();
  renderLegend();
  renderSamples(key);
  const first = (SAMPLES[key] || [])[key === "default" ? 1 : 0];
  if (first) { textEl.value = first[1]; updateCount(); }
}

function updateCount() { $("count").textContent = `${textEl.value.length} / 5000`; }
textEl.addEventListener("input", updateCount);
textEl.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") run(); });
schemaEl.addEventListener("input", () => { try { schemaFromEditor(); renderLegend(); setStatus(""); } catch { setStatus("实体类型 JSON 格式有误", true); } });
$("preset").addEventListener("change", (e) => selectPreset(e.target.value));

function setStatus(msg, isError = false) {
  $("status").textContent = msg;
  $("status").classList.toggle("error", isError);
}

async function init() {
  const [h, p] = await Promise.all([fetch("/api/health").then((r) => r.json()), fetch("/api/presets").then((r) => r.json())]);
  presets = p;
  $("preset").innerHTML = Object.entries(presets).map(([k, v]) => `<option value="${k}">${esc(v.name)}</option>`).join("");
  selectPreset("default");
  if (!h.ok) setStatus(`后端未就绪：${h.error}（请在 .env 设置 TYPESAFE_API_KEY）`, true);
}

function renderHighlight(text, entities) {
  const el = $("highlight");
  el.classList.remove("empty");
  if (!entities.length) {
    el.innerHTML = `${esc(text)}<p class="empty">没有识别到${esc(Object.values(labels).join("、"))}（每个片段都是 none 或非实体得分最高）。</p>`;
    return;
  }
  let html = "", pos = 0;
  for (const e of entities) {
    if (e.start < pos) continue;
    const [bg, ink] = colorOf(e.label);
    html += esc(text.slice(pos, e.start));
    html += `<mark style="background:${bg};color:${ink}" data-label="${esc(titleOf(e.label))}" title="${e.score.toFixed(2)}">${esc(text.slice(e.start, e.end))}</mark>`;
    pos = e.end;
  }
  el.innerHTML = html + esc(text.slice(pos));
}

function renderTable(entities) {
  const table = $("table");
  table.hidden = !entities.length;
  table.querySelector("tbody").innerHTML = entities.map((e) => `
    <tr><td>${tag(e.label)}</td><td>${esc(e.text)}</td><td>${e.start}–${e.end}</td>
    <td class="score">${e.score.toFixed(2)}</td><td>${SOURCE_ZH[e.source] || e.source}</td></tr>`).join("");
}

function decisionZh(d) {
  if (!d) return "";
  if (d === "entity") return "✔ 采纳为实体";
  if (d.startsWith("entity (whole")) return "✔ 验证：标点属于名称，整体采纳";
  if (d === "none") return "丢弃";
  if (d === "rejected") return "未采纳";
  if (d === "part-of-parent") return "属于上层实体";
  if (d === "verify") return "验证中";
  if (d === "window") return "↓ 标点切不开，窗口选择题";
  if (d === "fallback") return "兜底";
  if (d.startsWith("split:verified")) return "↓ 验证：标点在分隔内容，采用子片段";
  if (d.startsWith("split:")) return `↓ 继续按${LEVEL_ZH[d.slice(6)] || d.slice(6)}切分`;
  return d;
}

function renderNode(n) {
  const probs = Object.entries(n.probabilities || {})
    .filter(([k]) => !k.startsWith("boundary:"))
    .sort((a, b) => b[1] - a[1]).slice(0, 4)
    .map(([k, v], i) => `<span class="bar ${i === 0 ? "win" : ""}">${esc(titleOf(k))} ${v.toFixed(2)}</span>`).join("");
  const t = n.label ? tag(n.label, ` ${n.score.toFixed(2)}`) : "";
  const kids = (n.children || []).map(renderNode).join("");
  return `<div class="node ${n.decision === "rejected" ? "rejected" : ""}">
    <div class="node-row"><span class="lvl">${LEVEL_ZH[n.level] || n.level}</span>
    <span class="frag">${esc(n.text)}</span>${t}<span class="dec">${decisionZh(n.decision)}</span>
    <span class="probs">${probs}</span></div>${kids}</div>`;
}

async function run() {
  const text = textEl.value;
  if (!text.trim()) { setStatus("请先输入文本。", true); return; }
  let schema;
  try { schema = schemaFromEditor(); } catch { setStatus("实体类型 JSON 格式有误，请检查。", true); return; }
  $("run").disabled = true;
  setStatus("正在逐层询问 Jev……");
  $("highlight").innerHTML = '<div class="skeleton"></div><div class="skeleton" style="width:70%"></div>';
  $("trace").innerHTML = '<div class="skeleton"></div><div class="skeleton" style="width:50%"></div>';
  const t0 = performance.now();
  try {
    const r = await fetch("/api/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text, schema,
        use_context: $("ctx").checked, window: $("win").checked,
        propagate: $("prop").checked, refine: $("refine").value,
      }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    labels = data.labels;
    renderLegend();
    renderHighlight(data.text, data.entities);
    renderTable(data.entities);
    $("trace").classList.remove("empty");
    $("trace").innerHTML = data.trace.map(renderNode).join("") || "没有可分析的片段。";
    const u = data.usage;
    $("usage").textContent = `模型 ${data.model.join(", ") || "-"} · 请求 ${u.requests} 次 · 问题 ${u.questions} 个 · 缓存命中 ${u.cache_hits} · 输入 ${u.input_tokens} tokens · 约 $${u.cost_usd.toFixed(5)}`;
    setStatus(`完成，用时 ${((performance.now() - t0) / 1000).toFixed(2)} 秒，识别出 ${data.entities.length} 个实体。`);
  } catch (err) {
    $("highlight").innerHTML = "";
    $("highlight").classList.add("empty");
    $("trace").innerHTML = "";
    setStatus(`识别失败：${err.message}`, true);
  } finally {
    $("run").disabled = false;
  }
}
$("run").onclick = run;
init();
