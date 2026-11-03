"""docs/index.html 대시보드를 만듭니다. monitor.py에서 불러 씁니다."""
from __future__ import annotations

import html
import json
import re
from collections import OrderedDict

E = html.escape

CSS = """
:root{
  --paper:#EEF1F4; --sheet:#FFFFFF; --ink:#18212B; --muted:#5B6774; --rule:#D3DAE1;
  --seal:#C22E28; --link:#1D4C89; --chip:#E2E8EE; --chip-on:#18212B; --chip-on-ink:#FFFFFF;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){
  :root{
    --paper:#11161C; --sheet:#182029; --ink:#E4E9EE; --muted:#93A0AD; --rule:#2A3440;
    --seal:#E5534B; --link:#8EB6F2; --chip:#232D38; --chip-on:#E4E9EE; --chip-on-ink:#11161C;
    color-scheme:dark;
  }
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--paper);color:var(--ink);
  font-family:"IBM Plex Sans KR",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto;padding:40px 20px 80px}
header h1{font-size:30px;line-height:1.25;font-weight:700;letter-spacing:-.02em;margin:0 0 8px}
header p{margin:0;color:var(--muted);max-width:60ch}
.status{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center;margin:18px 0 0;
  font-size:14px;color:var(--muted)}
.status img{height:20px;vertical-align:middle}
.status .bad{color:var(--seal)}
.tools{margin:32px 0 8px;display:flex;flex-direction:column;gap:12px}
.search{width:100%;font:inherit;padding:12px 14px;border:1px solid var(--rule);border-radius:6px;
  background:var(--sheet);color:var(--ink)}
.search:focus-visible,a:focus-visible{outline:2px solid var(--link);outline-offset:2px}
.tabs{display:flex;flex-wrap:wrap;gap:2px;overflow-x:auto;border-bottom:1px solid var(--rule);
  scrollbar-width:none;-webkit-overflow-scrolling:touch}
.tabs::-webkit-scrollbar{display:none}
.tab{font:inherit;font-size:14px;font-weight:500;white-space:nowrap;border:0;background:none;
  color:var(--muted);padding:10px 12px 9px;border-bottom:3px solid transparent;cursor:pointer}
.tab span{font-variant-numeric:tabular-nums;font-size:12px;margin-left:5px;padding:1px 7px;
  border-radius:999px;background:var(--chip);color:var(--muted)}
.tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--ink);font-weight:600}
.tab.zero{opacity:.55}
.tab[aria-selected="true"] span{background:var(--chip-on);color:var(--chip-on-ink)}
.tab:focus-visible{outline:2px solid var(--link);outline-offset:-2px}
.opts{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--muted)}
.opts input{width:16px;height:16px;accent-color:var(--ink)}
li.is-closed .title,li.is-closed .date{opacity:.5}
.closed{display:none;font-style:normal;font-size:12px;font-weight:600;color:var(--muted);border:1px solid var(--rule);
  border-radius:4px;padding:0 5px;margin-left:6px}
li.is-closed .closed{display:inline-block}
.count{font-size:14px;color:var(--muted);margin:4px 0 0}
section.month{margin-top:36px}
section.month h2{font-size:15px;font-weight:600;color:var(--muted);margin:0 0 6px;
  padding-bottom:6px;border-bottom:2px solid var(--ink)}
ol.list{list-style:none;margin:0;padding:0;background:var(--sheet);border-radius:0 0 6px 6px}
li.row{position:relative;display:grid;grid-template-columns:64px 1fr;gap:14px;
  padding:16px 88px 16px 14px;border-bottom:1px solid var(--rule)}
li.row:last-child{border-bottom:0}
.date{font-variant-numeric:tabular-nums;font-size:20px;font-weight:600;line-height:1.2;color:var(--ink)}
.date small{display:block;font-size:12px;font-weight:400;color:var(--muted)}
.title{font-size:16px;font-weight:600;color:var(--link);text-decoration:none}
.title:hover{text-decoration:underline}
.meta{display:flex;flex-wrap:wrap;gap:2px 16px;margin-top:4px;font-size:13px;color:var(--muted)}
.meta b{font-weight:500;color:var(--ink);margin-right:4px}
.meta a{color:var(--muted)}
.kw{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}
.kw span{font-size:12px;padding:1px 8px;border-radius:4px;background:var(--chip);color:var(--muted)}
.seal{display:none;position:absolute;right:18px;top:16px;width:54px;height:54px;border-radius:50%;
  border:2.5px solid var(--seal);color:var(--seal);font-weight:700;font-size:14px;
  align-items:center;justify-content:center;transform:rotate(-12deg);letter-spacing:.08em}
.seal::after{content:"";position:absolute;inset:3px;border-radius:50%;border:1px solid var(--seal);opacity:.6}
li.is-new .seal{display:flex}
.empty{background:var(--sheet);border-radius:6px;padding:32px 20px;color:var(--muted);margin-top:36px}
[hidden]{display:none!important}
footer{margin-top:48px;font-size:13px;color:var(--muted)}
footer a{color:var(--muted)}
@media (max-width:560px){
  .tabs{flex-wrap:nowrap}
  .wrap{padding:28px 14px 64px}
  header h1{font-size:24px}
  li.row{grid-template-columns:1fr;gap:4px;padding:14px 70px 14px 12px}
  .date{font-size:15px}.date small{display:inline;margin-left:6px}
  .seal{width:46px;height:46px;font-size:12px;right:12px}
}
@media (prefers-reduced-motion:no-preference){
  li.is-new .seal{animation:stamp .5s cubic-bezier(.3,1.6,.5,1) both}
  @keyframes stamp{from{transform:rotate(-12deg) scale(1.8);opacity:0}to{transform:rotate(-12deg) scale(1);opacity:1}}
}
"""

JS = """
(function(){
  var rows=[].slice.call(document.querySelectorAll('li.row'));
  var NEW_MS=%d*3600*1000, now=Date.now();
  var today=new Date(); today.setHours(0,0,0,0);
  rows.forEach(function(r){
    var t=Date.parse(r.dataset.found||'');
    if(!isNaN(t)&&now-t<NEW_MS){r.classList.add('is-new');}
    var e=r.dataset.end; if(e){var d=new Date(e+'T23:59:59'); if(d<today){r.classList.add('is-closed');}}
  });
  var q=document.getElementById('q'), tabs=[].slice.call(document.querySelectorAll('.tab'));
  var hide=document.getElementById('hideClosed'), count=document.getElementById('count');
  var empty=document.getElementById('nomatch');
  var active=decodeURIComponent((location.hash||'').slice(1));
  if(!tabs.some(function(t){return t.dataset.g===active;})) active='';
  try{ if(localStorage.getItem('hideClosed')==='1') hide.checked=true; }catch(e){}
  function apply(){
    var term=(q.value||'').replace(/\\s+/g,'').toLowerCase(), shown=0;
    tabs.forEach(function(t){t.setAttribute('aria-selected',String(t.dataset.g===active));});
    rows.forEach(function(r){
      var ok=(!active||r.dataset.groups.split('|').indexOf(active)>-1)
        &&(!term||r.dataset.text.indexOf(term)>-1)
        &&!(hide.checked&&r.classList.contains('is-closed'));
      r.hidden=!ok; if(ok)shown++;
    });
    document.querySelectorAll('section.month').forEach(function(s){
      s.hidden=!s.querySelector('li.row:not([hidden])');
    });
    if(empty) empty.hidden=shown>0;
    count.textContent=shown+'건 표시';
  }
  tabs.forEach(function(t){t.addEventListener('click',function(){
    active=t.dataset.g;
    try{history.replaceState(null,'',active?'#'+encodeURIComponent(active):location.pathname);}catch(e){}
    apply();
  });});
  q.addEventListener('input',apply);
  hide.addEventListener('change',function(){
    try{localStorage.setItem('hideClosed',hide.checked?'1':'0');}catch(e){}
    apply();
  });
  window.addEventListener('hashchange',function(){
    var h=decodeURIComponent((location.hash||'').slice(1));
    active=tabs.some(function(t){return t.dataset.g===h;})?h:''; apply();
  });
  apply();
})();
"""


def _date_parts(it):
    d = (it.get("posted") or it.get("found_at", ""))[:10]
    if len(d) == 10:
        return d[:7], f"{d[5:7]}.{d[8:10]}", d[:4]
    return "날짜 미상", "—", ""


def _month_label(ym: str) -> str:
    if len(ym) == 7 and ym[4] == "-":
        return f"{ym[:4]}년 {int(ym[5:7])}월"
    return ym


def _row(it) -> str:
    _, md, year = _date_parts(it)
    kws = it.get("keywords") or []
    text = "".join([it.get("title", ""), it.get("org", ""), it.get("source", "")]).replace(" ", "").lower()
    groups = it.get("groups") or []
    ends = re.findall(r"\d{4}-\d{2}-\d{2}", it.get("period", ""))
    end = ends[-1] if len(ends) >= 2 else ""
    meta = []
    if it.get("org"):
        meta.append(f"<span><b>기관</b>{E(it['org'])}</span>")
    if it.get("period"):
        meta.append(f"<span><b>신청</b>{E(it['period'])}<em class=\"closed\">마감</em></span>")
    src = [f'<a href="{E(it["url"], quote=True)}" target="_blank" rel="noopener">{E(it["source"])}</a>']
    for l in it.get("links") or []:
        src.append(f'<a href="{E(l["url"], quote=True)}" target="_blank" rel="noopener">{E(l["source"])}</a>')
    meta.append(f"<span><b>출처</b>{', '.join(src)}</span>")
    return (
        f'<li class="row" data-found="{"" if it.get("baseline") else E(it.get("found_at", ""), quote=True)}" '
        f'data-text="{E(text, quote=True)}" data-groups="{E("|".join(groups), quote=True)}" '
        f'data-end="{E(end, quote=True)}">'
        f'<div class="date">{E(md)}<small>{E(year)}</small></div>'
        f'<div><a class="title" href="{E(it["url"], quote=True)}" target="_blank" rel="noopener">{E(it["title"])}</a>'
        f'<div class="meta">{"".join(meta)}</div>'
        f'<div class="kw">{"".join(f"<span>{E(k)}</span>" for k in kws)}</div></div>'
        f'<div class="seal" aria-label="최근 3일 안에 새로 발견">신규</div></li>'
    )


def render(*, title, items, groups, sources, updated, repo, new_hours, now) -> str:
    months: "OrderedDict[str, list]" = OrderedDict()
    for it in items:
        months.setdefault(_date_parts(it)[0], []).append(it)

    counts = {g: 0 for g in groups}
    for it in items:
        for g in it.get("groups") or []:
            counts[g] = counts.get(g, 0) + 1
    status = []
    if repo:
        status.append(
            f'<a href="https://github.com/{E(repo)}/actions" target="_blank" rel="noopener">'
            f'<img src="https://github.com/{E(repo)}/actions/workflows/monitor.yml/badge.svg" alt="감시 작동 상태"></a>')
    for name, st in (sources or {}).items():
        if st.get("error"):
            status.append(f'<span class="bad">{E(name)} 확인 실패 {st.get("fails", 0)}회</span>')
        elif st.get("ok_at"):
            status.append(f"<span>{E(name)} 정상</span>")
    if updated:
        status.append(f"<span>마지막 변동 {E(updated.replace('T', ' ')[:16])}</span>")

    if items:
        body = "".join(
            f'<section class="month"><h2>{E(_month_label(ym))}</h2><ol class="list">'
            + "".join(_row(it) for it in rows) + "</ol></section>"
            for ym, rows in months.items())
        body += ('<div class="empty" id="nomatch" hidden>이 조건에 맞는 공고가 없습니다. '
                 '다른 탭을 고르거나 검색어를 지워 보세요.</div>')
    else:
        body = ('<div class="empty">아직 기록된 공고가 없습니다. 첫 확인이 끝나면 키워드에 맞는 '
                '공고가 이곳에 쌓입니다.</div>')

    tabs = [f'<button type="button" class="tab" role="tab" data-g="" aria-selected="true">'
            f'전체<span>{len(items)}</span></button>']
    for g, n in counts.items():
        tabs.append(f'<button type="button" class="tab{" zero" if not n else ""}" role="tab" data-g="{E(g, quote=True)}" '
                    f'aria-selected="false">{E(g)}<span>{n}</span></button>')
    tabs_html = "".join(tabs)

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📮</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>{E(title)}</h1>
  <p>기업마당과 중소벤처기업부 사업공고 중 스마트공장·제조AI·자율형공장·피지컬AI 관련 공고를 분류별로 모았습니다. 새 공고는 텔레그램으로도 알려 드립니다.</p>
  <div class="status">{''.join(status)}</div>
</header>
<div class="tools">
  <input id="q" class="search" type="search" placeholder="공고명·기관으로 찾기" aria-label="공고 검색">
  <div class="tabs" role="tablist" aria-label="분류">{tabs_html}</div>
  <div class="opts"><label class="opts"><input type="checkbox" id="hideClosed">마감된 공고 숨기기</label>
    <span id="count" aria-live="polite" style="margin-left:auto"></span></div>
</div>
{body}
<footer>최근 {new_hours}시간 안에 새로 발견한 공고에는 <b>신규</b> 도장이 찍힙니다. 신청 전에는 반드시 원문 공고를 확인하세요.</footer>
</div>
<script>{JS % new_hours}
</script>
</body>
</html>
"""
