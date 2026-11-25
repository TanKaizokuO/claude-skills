#!/usr/bin/env python3
"""Post-build patch: when the 1d range is active, the Overview "Activity" chart shows
the rolling last 24 hours, one bar per hour (hour-of-day in DATA.timezone, from DATA.hours).
Only the Activity chart changes; tiles, tables and the other charts keep the 1d day range.
Fails loudly if main's template stops matching, like the card-hiding step in build.sh."""
import sys

p = sys.argv[1]
h = open(p, encoding="utf-8").read()


def swap(old, new):
    global h
    if h.count(old) != 1:
        sys.exit("hourly patch failed: anchor not found exactly once: " + old[:70])
    h = h.replace(old, new)


# 1. Subtitle gets an id so the renderer can switch "Per day" / "Per hour".
swap('<div class="card-title">Activity</div>\n              <div class="card-description">Per day</div>',
     '<div class="card-title">Activity</div>\n              <div class="card-description" id="activity-desc">Per day</div>')

# 2. Pick the hourly renderer when 1d is active.
swap("renderStackedChart('overview-activity-chart', daily, getA, getB, fmtFunc, 260, fmtType);",
     "if (!renderHourlyActivity('overview-activity-chart', getA, getB, fmtFunc, 260, fmtType)) "
     "renderStackedChart('overview-activity-chart', daily, getA, getB, fmtFunc, 260, fmtType);")

# 3. Tooltip title: hourly bars carry data-label instead of data-day (so a click does not open a day).
swap("<div class=\"chart-tooltip-title\">${col.dataset.day}${col.dataset.partial",
     "<div class=\"chart-tooltip-title\">${col.dataset.label || col.dataset.day}${col.dataset.partial")

# 4. The hourly renderer. Returns false when it does not apply, so the daily chart renders as before.
FUNC = r"""
// Rolling last 24 hours, hourly bars, when the 1d range button is active.
function renderHourlyActivity(containerId, valA, valB, fmtFunc, height, fmtType) {
  const desc = document.getElementById('activity-desc');
  const oneDay = document.querySelector('#periods [data-range="1"]');
  const on = !!oneDay && oneDay.getAttribute('data-active') === 'true' && TZ_KNOWN && GEN_OK && (DATA.hours || []).length > 0;
  if (desc) desc.textContent = on ? 'Per hour, last 24 hours' : 'Per day';
  if (!on) return false;
  const hourIn = date => +new Intl.DateTimeFormat('en-GB', {timeZone: TZ, hour: '2-digit', hourCycle: 'h23'}).format(date);
  const slots = [], byKey = new Map();
  for (let k = 23; k >= 0; k--) {
    const t = new Date(GEN.getTime() - k * 36e5);
    const s = {day: dayIn(t, TZ), hour: hourIn(t), ccMsg: 0, ompMsg: 0, ccTok: 0, ompTok: 0, ccCost: 0, ompCost: 0, partial: k === 0};
    slots.push(s); byKey.set(s.day + '|' + s.hour, s);
  }
  for (const r of DATA.hours) {
    if (hideRetired && RETIRED_MODELS.includes(r[3])) continue;
    const s = byKey.get(r[0] + '|' + r[1]);
    if (!s) continue;
    const toks = r[5] + r[6] + r[7] + r[8];
    if (r[2] === 'claude-code') { s.ccMsg += r[4]; s.ccTok += toks; s.ccCost += r[9]; }
    else { s.ompMsg += r[4]; s.ompTok += toks; s.ompCost += r[9]; }
  }
  const pad = n => String(n).padStart(2, '0');
  const container = document.getElementById(containerId);
  const nt = niceTicks(Math.max(...slots.map(s => valA(s) + valB(s))));
  const peak = nt.peak;
  let gridHtml = '';
  for (let i = 0; i < nt.ticks.length; i++) {
    const bot = (i / (nt.ticks.length - 1)) * 100;
    gridHtml += `<div style="position:absolute; bottom:${bot}%; left:48px; right:0; height:1px; background:var(--line-1);"></div>`;
    gridHtml += `<div style="position:absolute; bottom:${bot}%; left:0; font-family:var(--font-mono); font-size:10px; color:var(--ink-3); transform:translateY(50%);">${fmtFunc(nt.ticks[i])}</div>`;
  }
  const colsHtml = slots.map(s => {
    const vA = valA(s), vB = valB(s);
    const hA = peak ? 100 * vA / peak : 0, hB = peak ? 100 * vB / peak : 0;
    const label = `${dateLabel(s.day)}, ${pad(s.hour)}:00-${pad((s.hour + 1) % 24)}:00`;
    return `<div class="col" data-label="${label}" data-partial="${s.partial}" data-a="${vA}" data-b="${vB}" data-tot="${vA + vB}" style="position:relative;">
      ${hB > 0 ? `<div class="seg" style="height:${hB}%;background:var(--accent-b)"></div>` : ''}
      ${hA > 0 ? `<div class="seg" style="height:${hA}%;background:var(--accent-a)"></div>` : ''}
    </div>`;
  }).join('');
  let xLabels = '';
  for (let i = 0; i < 6; i++) { const s = slots[Math.floor(i * 23 / 5)]; xLabels += `<span>${pad(s.hour)}:00</span>`; }
  container.innerHTML = `
    <div data-fmt="${fmtType}">
      <div class="chart chart-bar" style="height: ${height}px; position: relative;">
         <div style="position: absolute; inset: 0; pointer-events: none;">${gridHtml}</div>
         <div class="daily" style="height: 100%; margin-left: 48px; width: calc(100% - 48px);">${colsHtml}</div>
      </div>
      <div style="display:flex; justify-content: space-between; font-size: 11px; font-family: var(--font-mono); color: var(--ink-3); margin-top: 8px; margin-left: 48px;">${xLabels}</div>
    </div>`;
  return true;
}

"""
swap("function updateSortHeaders(containerId, action, currentSortBy, currentSortDesc) {",
     FUNC + "function updateSortHeaders(containerId, action, currentSortBy, currentSortDesc) {")

open(p, "w", encoding="utf-8").write(h)
print("patched: hourly Activity chart for 1d")
