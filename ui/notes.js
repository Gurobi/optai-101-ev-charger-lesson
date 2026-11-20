const escapes = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => escapes[c]);
export const num = (value, digits = 0) => Number(value).toLocaleString("en-US", {
  maximumFractionDigits: digits,
  minimumFractionDigits: digits,
});

function chartRows(body, size) {
  return body.split("\n").map((line) => line.split(",").map((cell) => cell.trim()))
    .filter((row) => row.length > size && row.slice(-size).every((cell) => cell && Number.isFinite(Number(cell))))
    .map((row) => [row.slice(0, -size).join(", "), ...row.slice(-size).map(Number)]);
}

export function figure(className, title, content, caption = "") {
  if (!content) return "";
  return `<figure class="${className}"><figcaption>${esc(title)}${caption ? `<small>${esc(caption)}</small>` : ""}</figcaption>${content}</figure>`;
}

const svg = (width, height, content) => `<svg viewBox="0 0 ${width} ${height}" role="img">${content}</svg>`;
const scale = (min, max, start, end) => (value) =>
  start + (value - min) * (end - start) / (max - min || 1);
const tick = (x, y, label, anchor = "start") =>
  `<text x="${x}" y="${y}" text-anchor="${anchor}">${esc(label)}</text>`;
const short = (value) => Math.abs(value) >= 1e6 ? num(value / 1e6, 1) + "M"
  : Math.abs(value) >= 1e4 ? num(value / 1e3) + "k" : num(value, value % 1 ? 2 : 0);

function bars(rows) {
  if (!rows.length) return "";
  const width = 480;
  const rowHeight = 24;
  const labels = Math.min(25, Math.max(...rows.map(([label]) => label.length)));
  const left = Math.max(52, labels * 7 + 12);
  const values = rows.map(([, value]) => value);
  const x = scale(Math.min(0, ...values), Math.max(0, ...values), left, width - 56);
  const zero = x(0);
  const height = rows.length * rowHeight;
  const axis = `<line x1="${zero}" y1="0" x2="${zero}" y2="${height}" stroke="var(--dot)"/>`;
  const content = rows.map(([label, value], i) => {
    const display = label.length > labels ? label.slice(0, labels - 1) + "…" : label;
    const y = i * rowHeight;
    const position = x(value);
    const color = value < 0 ? "var(--gb-red)" : "var(--blue)";
    return `<g><title>${esc(label)} · ${short(value)}</title>
      ${tick(left - 8, y + 16, display, "end")}
      <rect x="${Math.min(position, zero)}" y="${y + 5}" width="${Math.abs(position - zero)}" height="14" fill="${color}"/>
      ${tick(Math.max(position, zero) + 5, y + 16, short(value))}
    </g>`;
  });
  return svg(width, height, axis + content.join(""));
}

function line(rows) {
  if (rows.length < 2) return "";
  const width = 480, height = 210, left = 64, right = 462, top = 15, bottom = 178;
  const values = rows.map(([, value]) => value);
  const low = Math.min(0, ...values), high = Math.max(0, ...values);
  const x = scale(0, rows.length - 1, left, right);
  const y = scale(low, high, bottom, top);
  const points = rows.map(([, value], index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`);
  const tickSpacing = Math.ceil((rows.length - 1) / 6);
  const labels = rows.map(([label], i) => {
    if (i === 0) return tick(x(i), 198, label);
    if (i === rows.length - 1) return tick(x(i), 198, label, "end");
    if (i % tickSpacing === 0 && i + tickSpacing / 2 < rows.length - 1) {
      return tick(x(i), 198, label, "middle");
    }
    return "";
  });
  return svg(width, height, `
    <line x1="${left}" y1="${y(0)}" x2="${right}" y2="${y(0)}" stroke="var(--dot)"/>
    ${tick(left - 6, y(low) + 4, short(low), "end")}
    ${high === low ? "" : tick(left - 6, y(high) + 4, short(high), "end")}
    <polyline fill="none" stroke="var(--blue)" stroke-width="2" points="${points.join(" ")}"/>
    ${labels.join("")}
  `);
}

function scatter(rows, xName, yName) {
  if (rows.length < 2) return "";
  const width = 480, height = 260, left = 55, right = 464, top = 14, bottom = 221;
  const xs = rows.map(([, x]) => x), ys = rows.map(([, , y]) => y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const x = scale(minX, maxX, left, right);
  const y = scale(minY, maxY, bottom, top);
  const points = rows.map(([label, a, b]) => `
    <circle cx="${x(a).toFixed(1)}" cy="${y(b).toFixed(1)}" r="2.6" fill="var(--blue)" fill-opacity=".7">
      <title>${esc(label)} · ${short(a)}, ${short(b)}</title>
    </circle>`);
  return svg(width, height, `
    <path d="M ${left},${top} V ${bottom} H ${right}" stroke="var(--dot)" fill="none"/>
    ${tick(left - 6, bottom, short(minY), "end")}
    ${maxY === minY ? "" : tick(left - 6, top + 4, short(maxY), "end")}
    ${tick(left, bottom + 15, short(minX))}
    ${maxX === minX ? "" : tick(right, bottom + 15, short(maxX), "end")}
    ${tick((left + right) / 2, height - 5, xName, "middle")}
    <g transform="translate(11 ${(top + bottom) / 2}) rotate(-90)">${tick(0, 0, yName, "middle")}</g>
    ${points.join("")}
  `);
}

// Each map marker holds a ZIP area, a size, and a switch for DC fast charging.
export function map(areas, markers) {
  if (!areas.length) return "";
  const width = 300;
  const correction = Math.cos(44.5 * Math.PI / 180);
  const xs = areas.map(([, , lon]) => lon * correction), ys = areas.map(([, lat]) => lat);
  const left = Math.min(...xs), right = Math.max(...xs);
  const bottom = Math.min(...ys), top = Math.max(...ys);
  const height = Math.round(width * (top - bottom) / (right - left));
  const x = scale(left, right, 8, width - 8), y = scale(bottom, top, height - 8, 8);
  const projected = new Map(areas.map(([code, lat, lon]) => [code, [x(lon * correction), y(lat)]]));
  const max = Math.max(...markers.map(([, size]) => size), 0) || 1;
  const context = Array.from(projected.values(), ([x, y]) =>
    `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="1" fill="var(--dot)"/>`
  );
  const highlights = [...markers].sort((a, b) => b[1] - a[1]).map(([code, size, square]) => {
    if (!projected.has(code) || size <= 0) return "";
    const [x, y] = projected.get(code);
    const r = 2 + 6 * Math.sqrt(size / max);
    const label = `<title>${esc(code)} · ${short(size)}</title>`;
    return square
      ? `<rect x="${(x - r).toFixed(1)}" y="${(y - r).toFixed(1)}" width="${(2 * r).toFixed(1)}" height="${(2 * r).toFixed(1)}" fill="var(--purple)" stroke="var(--gb-white)">${label}</rect>`
      : `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(1)}" fill="var(--blue)" stroke="var(--gb-white)">${label}</circle>`;
  });
  return svg(width, height, context.join("") + highlights.join(""));
}

function inline(text) {
  return esc(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\s](?:[^*]*[^*\s])?)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\([^)\s]+\)/g, "$1");
}

const special = /^(?:[-*] |\d+\. |```|#+ |!\[|\|)/;
const chart = {
  bars: (body, title) => figure("", title, bars(chartRows(body, 1).slice(0, 30))),
  line: (body, title) => figure("", title, line(chartRows(body, 1))),
  map: (body, title, areas) => figure("map", title, map(areas, chartRows(body, 1))),
  scatter: (body, caption) => {
    const [title, axes = ""] = caption.split(" | ");
    const [x = "", y = ""] = axes.split(" vs ");
    return figure("", title, scatter(chartRows(body, 2), x, y));
  },
};

function notesTable(lines) {
  const rows = lines.map((line) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()))
    .filter((row) => !row.every((cell) => /^:?-+:?$/.test(cell)));
  const [head = [], ...body] = rows;
  return `<div class="scroll"><table>
    <thead><tr>${head.map((cell) => `<th scope="col">${inline(cell)}</th>`).join("")}</tr></thead>
    <tbody>${body.map((row) => "<tr>" + row.map((cell) => `<td>${inline(cell)}</td>`).join("") + "</tr>").join("")}</tbody>
  </table></div>`;
}

// Render the Markdown subset documented in AGENT_GUIDE.md.
export function renderNotes(text, areas, versions = {}) {
  const output = [];
  const lines = text.split("\n");
  let index = 0;
  const take = (test) => {
    const collected = [];
    while (index < lines.length && test(lines[index].trimStart())) collected.push(lines[index++]);
    return collected;
  };
  while (index < lines.length) {
    const current = lines[index].trimStart();
    if (!current) {
      index++;
    } else if (current.startsWith("```")) {
      const [kind, ...title] = current.slice(3).trim().split(" ");
      index++;
      const body = take((line) => !line.startsWith("```")).join("\n");
      index++;
      if (kind === "math") {
        output.push(`<pre class="equations" aria-label="Mathematical formulation">${esc(body)}</pre>`);
      } else {
        output.push(Object.hasOwn(chart, kind) ? chart[kind](body, title.join(" "), areas) : `<pre>${esc(body)}</pre>`);
      }
    } else if (/^[-*] |^\d+\. /.test(current)) {
      const ordered = /^\d/.test(current);
      const marker = ordered ? /^\d+\. / : /^[-*] /;
      const tag = ordered ? "ol" : "ul";
      const items = [];
      for (const line of take((line) => marker.test(line) || line && !special.test(line))) {
        const part = line.trimStart();
        if (marker.test(part)) items.push(part.replace(marker, ""));
        else items[items.length - 1] += " " + part;
      }
      output.push(`<${tag}>${items.map((item) => `<li>${inline(item)}</li>`).join("")}</${tag}>`);
    } else if (current.startsWith("|")) {
      output.push(notesTable(take((line) => line.startsWith("|"))));
    } else if (current.startsWith("![")) {
      const file = current.match(/^!\[([^\]]*)\]\((?:figures\/)?([A-Za-z0-9_-]+\.(png|svg|html))\)/);
      if (file) {
        const [, caption, name, type] = file;
        const version = versions[name];
        const src = `figures/${name}${version ? `?v=${encodeURIComponent(version)}` : ""}`;
        const content = type === "html"
          ? `<iframe inert tabindex="-1" src="${src}" title="${esc(caption || "Interactive figure")}" sandbox="allow-scripts allow-downloads" referrerpolicy="no-referrer" loading="lazy"></iframe>`
          : `<img src="${src}" alt="${esc(caption)}">`;
        output.push(figure("figure-file", caption, content));
      }
      index++;
    } else if (/^#+ /.test(current)) {
      output.push(`<p><strong>${inline(current.replace(/^#+ /, ""))}</strong></p>`);
      index++;
    } else {
      output.push(`<p>${inline(take((line) => line && !special.test(line)).map((line) => line.trim()).join(" "))}</p>`);
    }
  }
  return output.join("");
}
