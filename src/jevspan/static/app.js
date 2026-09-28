const I18N = {
  zh: {
    htmlLang: "zh-CN",
    switchTo: "English",
    subtitle: "零样本实体识别",
    intro: "全文遍历，按标点由粗到细切分，每个片段交给 Jev 打分，取最高分作为判断。实体类型只需给出名称、一句描述和几个例子（零样本）。",
    entityTypes: "实体类型",
    editSchema: "编辑实体类型定义（JSON）",
    schemaHint: "每个类型：title 名称、description 一句定义、examples 几个例子，可选 counter_examples 反例。",
    inputText: "输入文本",
    placeholder: "粘贴一段中文或英文……",
    optContext: "句子上下文",
    optWindow: "细分",
    optPropagate: "全文补全",
    refineLabel: "细分方式",
    refineChoice: "选择题提名（快、省）",
    refineScan: "逐窗口提问",
    run: "开始识别",
    results: "识别结果",
    resultsEmpty: "识别结果会在这里高亮显示。",
    colType: "类型", colEntity: "实体", colSpan: "位置", colScore: "Jev 最高分", colSource: "来源",
    trace: "逐层过程",
    traceHint: "句子 → 分隔符（，、：）→ 括号引号 → 空格 → 窗口选择题 → 全文补全，每一步取最高分",
    traceEmpty: "运行后可以看到每个片段在每一层的得分和决定。",
    traceNone: "没有可分析的片段。",
    badSchema: "实体类型 JSON 格式有误",
    badSchemaRun: "实体类型 JSON 格式有误，请检查。",
    noText: "请先输入文本。",
    backendDown: (e) => `后端未就绪：${e}（请在 .env 设置 TYPESAFE_API_KEY）`,
    running: "正在逐层询问 Jev……",
    noEntities: (titles) => `没有识别到${titles.join("、")}（每个片段都是 none 或非实体得分最高）。`,
    usage: (m, u) => `模型 ${m} · 请求 ${u.requests} 次 · 问题 ${u.questions} 个 · 缓存命中 ${u.cache_hits} · 输入 ${u.input_tokens} tokens · 约 $${u.cost_usd.toFixed(5)}`,
    done: (sec, n) => `完成，用时 ${sec} 秒，识别出 ${n} 个实体。`,
    failed: (e) => `识别失败：${e}`,
    helper: { none: "none", mixed: "含实体", partial: "残缺" },
    level: { sentence: "句子", clause: "分隔符", enclosure: "括号引号", space: "空格", window: "窗口", propagate: "全文补全" },
    source: { segment: "标点切分", window: "窗口选择", merged: "合并", fallback: "兜底", propagated: "全文补全" },
    decision: {
      entity: "✔ 采纳为实体", entityWhole: "✔ 验证：标点属于名称，整体采纳", none: "丢弃", rejected: "未采纳",
      partOfParent: "属于上层实体", verify: "验证中", window: "↓ 标点切不开，窗口选择题", fallback: "兜底",
      splitVerified: "↓ 验证：标点在分隔内容，采用子片段", split: (lvl) => `↓ 继续按${lvl}切分`,
    },
    samples: {
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
    },
  },
  en: {
    htmlLang: "en",
    switchTo: "中文",
    subtitle: "Zero-shot entity recognition",
    intro: "JevSpan walks the whole text, splits it from coarse to fine at punctuation, lets Jev score every fragment, and keeps the highest-scoring answer. An entity type needs only a name, a one-line description and a few examples (zero-shot).",
    entityTypes: "Entity types",
    editSchema: "Edit entity type definitions (JSON)",
    schemaHint: "Each type: title, a one-line description, a few examples, and optional counter_examples.",
    inputText: "Input text",
    placeholder: "Paste some English or Chinese text…",
    optContext: "Sentence context",
    optWindow: "Windows",
    optPropagate: "Document pass",
    refineLabel: "Window mode",
    refineChoice: "Multiple choice (fast, cheap)",
    refineScan: "Ask per window",
    run: "Recognize",
    results: "Results",
    resultsEmpty: "Recognized entities will be highlighted here.",
    colType: "Type", colEntity: "Entity", colSpan: "Span", colScore: "Jev top score", colSource: "Source",
    trace: "Decision trace",
    traceHint: "sentence → clause (, ; :) → brackets & quotes → spaces → window multiple choice → document pass; each step keeps the top score",
    traceEmpty: "After a run, every fragment's score and decision at each level appears here.",
    traceNone: "Nothing to analyze.",
    badSchema: "The entity type JSON is invalid",
    badSchemaRun: "The entity type JSON is invalid. Please check it.",
    noText: "Please enter some text first.",
    backendDown: (e) => `Backend not ready: ${e} You can also put it in a .env file.`,
    running: "Asking Jev, level by level…",
    noEntities: (titles) => `No ${titles.join(", ")} found (every fragment scored highest as none or non-entity).`,
    usage: (m, u) => `Model ${m} · ${u.requests} requests · ${u.questions} questions · ${u.cache_hits} cache hits · ${u.input_tokens} input tokens · about $${u.cost_usd.toFixed(5)}`,
    done: (sec, n) => `Done in ${sec} s, ${n} ${n === 1 ? "entity" : "entities"} found.`,
    failed: (e) => `Recognition failed: ${e}`,
    helper: { none: "none", mixed: "mixed", partial: "partial" },
    level: { sentence: "sentence", clause: "clause", enclosure: "brackets", space: "space", window: "window", propagate: "document" },
    source: { segment: "punctuation", window: "window choice", merged: "merged", fallback: "fallback", propagated: "document pass" },
    decision: {
      entity: "✔ accepted", entityWhole: "✔ verified: punctuation is part of the name, kept whole", none: "dropped",
      rejected: "not accepted", partOfParent: "part of a parent entity", verify: "verifying",
      window: "↓ punctuation can't split it, window multiple choice", fallback: "fallback",
      splitVerified: "↓ verified: punctuation separates items, using sub-fragments", split: (lvl) => `↓ split further by ${lvl}`,
    },
    samples: {
      default: [
        ["Shipping label", "Ship to: Sarah Johnson, phone: +1 415-555-0132, address: 500 Terry Francois Street, San Francisco, CA 94158."],
        ["News", "On Tuesday, Professor Jennifer Doudna gave a talk at Stanford University, then toured the Tesla factory in Fremont, California. Jeff Bezos founded Amazon."],
        ["Contract", "Party A: Microsoft Corporation. Party B: Contoso Pharmaceuticals Ltd., 12 King Street, Manchester."],
        ["Chinese", "昨天下午，张伟教授在清华大学主楼作了报告，随后前往北京市海淀区中关村大街27号参观。"],
        ["No entities", "The weather is nice today, so let's meet at 3 pm to go over the second-quarter budget."],
      ],
      medical: [
        ["Case note", "The patient is allergic to penicillin and was switched to azithromycin for mycoplasma pneumonia. A complete blood count and a chest CT are recommended."],
        ["Chronic care", "Ten-year history of hypertension, on nifedipine controlled-release tablets, with regular HbA1c monitoring."],
        ["No entities", "Take a 30-minute walk after meals and try to stay relaxed."],
      ],
      ecommerce: [
        ["Product", "Nike Air Force 1 in white, was $120, now $89."],
        ["Electronics", "The Canon EOS R6 Mark II body sells for about $2,499, while the Sony WH-1000XM5 has better noise cancelling."],
        ["No entities", "Is shipping free? When will my order ship?"],
      ],
    },
  },
};
const PALETTE = [
  ["#e7efff", "#1d4ed8"], ["#efe9ff", "#6d28d9"], ["#fff3dc", "#b45309"],
  ["#e3f7ec", "#047857"], ["#ffe8ec", "#be123c"], ["#e6f6fb", "#0e7490"],
];

function pickLang() {
  const q = new URLSearchParams(location.search).get("lang");
  if (q in I18N) return q;
  const saved = localStorage.getItem("jevspan-lang");
  if (saved in I18N) return saved;
  return (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
}
const LANG = pickLang();
const T = I18N[LANG];

const $ = (id) => document.getElementById(id);
const textEl = $("text");
const schemaEl = $("schema");
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
let presets = {};
let labels = {};

function applyI18n() {
  document.documentElement.lang = T.htmlLang;
  document.title = `JevSpan · ${T.subtitle}`;
  for (const el of document.querySelectorAll("[data-i18n]")) el.textContent = T[el.dataset.i18n];
  textEl.placeholder = T.placeholder;
  $("refine").setAttribute("aria-label", T.refineLabel);
  $("lang").textContent = T.switchTo;
  $("lang").onclick = () => {
    const next = LANG === "zh" ? "en" : "zh";
    localStorage.setItem("jevspan-lang", next);
    const url = new URL(location.href);
    url.searchParams.set("lang", next);
    location.href = url.toString();
  };
}

function colorOf(label) {
  const i = Object.keys(labels).indexOf(label);
  return i < 0 ? ["#f2f4f7", "#475467"] : PALETTE[i % PALETTE.length];
}
function titleOf(label) { return labels[label] || T.helper[label] || label; }
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
  for (const [name, text] of T.samples[key] || []) {
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
  const first = (T.samples[key] || [])[key === "default" ? 1 : 0];
  if (first) { textEl.value = first[1]; updateCount(); }
}

function updateCount() { $("count").textContent = `${textEl.value.length} / 5000`; }
textEl.addEventListener("input", updateCount);
textEl.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") run(); });
schemaEl.addEventListener("input", () => { try { schemaFromEditor(); renderLegend(); setStatus(""); } catch { setStatus(T.badSchema, true); } });
$("preset").addEventListener("change", (e) => selectPreset(e.target.value));

function setStatus(msg, isError = false) {
  $("status").textContent = msg;
  $("status").classList.toggle("error", isError);
}

async function init() {
  applyI18n();
  const [h, p] = await Promise.all([
    fetch("/api/health").then((r) => r.json()),
    fetch(`/api/presets?lang=${LANG}`).then((r) => r.json()),
  ]);
  presets = p;
  $("preset").innerHTML = Object.entries(presets).map(([k, v]) => `<option value="${k}">${esc(v.name)}</option>`).join("");
  selectPreset("default");
  if (!h.ok) setStatus(T.backendDown(h.error), true);
}

function renderHighlight(text, entities) {
  const el = $("highlight");
  el.classList.remove("empty");
  if (!entities.length) {
    el.innerHTML = `${esc(text)}<p class="empty">${esc(T.noEntities(Object.values(labels)))}</p>`;
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
    <td class="score">${e.score.toFixed(2)}</td><td>${T.source[e.source] || e.source}</td></tr>`).join("");
}

function decisionText(d) {
  const D = T.decision;
  if (!d) return "";
  if (d === "entity") return D.entity;
  if (d.startsWith("entity (whole")) return D.entityWhole;
  if (d === "none") return D.none;
  if (d === "rejected") return D.rejected;
  if (d === "part-of-parent") return D.partOfParent;
  if (d === "verify") return D.verify;
  if (d === "window") return D.window;
  if (d === "fallback") return D.fallback;
  if (d.startsWith("split:verified")) return D.splitVerified;
  if (d.startsWith("split:")) return D.split(T.level[d.slice(6)] || d.slice(6));
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
    <div class="node-row"><span class="lvl">${T.level[n.level] || n.level}</span>
    <span class="frag">${esc(n.text)}</span>${t}<span class="dec">${decisionText(n.decision)}</span>
    <span class="probs">${probs}</span></div>${kids}</div>`;
}

async function run() {
  const text = textEl.value;
  if (!text.trim()) { setStatus(T.noText, true); return; }
  let schema;
  try { schema = schemaFromEditor(); } catch { setStatus(T.badSchemaRun, true); return; }
  $("run").disabled = true;
  setStatus(T.running);
  $("highlight").innerHTML = '<div class="skeleton"></div><div class="skeleton" style="width:70%"></div>';
  $("trace").innerHTML = '<div class="skeleton"></div><div class="skeleton" style="width:50%"></div>';
  const t0 = performance.now();
  try {
    const r = await fetch("/api/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text, schema, lang: LANG,
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
    $("trace").innerHTML = data.trace.map(renderNode).join("") || esc(T.traceNone);
    $("usage").textContent = T.usage(data.model.join(", ") || "-", data.usage);
    setStatus(T.done(((performance.now() - t0) / 1000).toFixed(2), data.entities.length));
  } catch (err) {
    $("highlight").innerHTML = "";
    $("highlight").classList.add("empty");
    $("trace").innerHTML = "";
    setStatus(T.failed(err.message), true);
  } finally {
    $("run").disabled = false;
  }
}
$("run").onclick = run;
init();
