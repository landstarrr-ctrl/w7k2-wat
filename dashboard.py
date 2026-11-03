"""docs/index.html 대시보드를 만듭니다. monitor.py에서 불러 씁니다."""
from __future__ import annotations

import html
import json
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
.search:focus-visible,.chip:focus-visible,a:focus-visible{outline:2px solid var(--link);outline-offset:2px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font:inherit;font-size:13px;border:0;border-radius:999px;padding:5px 12px;cursor:pointer;
  background:var(--chip);color:var(--ink)}
.chip[aria-pressed="true"]{background:var(--chip-on);color:var(--chip-on-ink)}
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
  rows.forEach(function(r){
    var t=Date.parse(r.dataset.found||'');
    if(!isNaN(t)&&now-t<NEW_MS){r.classList.add('is-new');}
  });
  var q=document.getElementById('q'), chips=[].slice.call(document.querySelectorAll('.chip'));
  var count=document.getElementById('count'), active=null;
  function apply(){
    var term=(q.value||'').replace(/\\s+/g,'').toLowerCase(), shown=0;
    rows.forEach(function(r){
      var ok=(!term||r.dataset.text.indexOf(term)>-1)&&(!active||r.dataset.kw.split('|').indexOf(active)>-1);
      r.hidden=!ok; if(ok)shown++;
    });
    document.querySelectorAll('section.month').forEach(function(s){
      s.hidden=!s.querySelector('li.row:not([hidden])');
    });
    count.textContent=shown===rows.length?'전체 '+rows.length+'건':rows.length+'건 중 '+shown+'건 표시';
  }
  q.addEventListener('input',apply);
  chips.forEach(function(c){c.addEventListener('click',function(){
    active=(active===c.dataset.kw)?null:c.dataset.kw;
    chips.forEach(function(x){x.setAttribute('aria-pressed',String(x.dataset.kw===active));});
    apply();
  });});
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
    meta = []
    if it.get("org"):
        meta.append(f"<span><b>기관</b>{E(it['org'])}</span>")
    if it.get("period"):
        meta.append(f"<span><b>신청</b>{E(it['period'])}</span>")
    src = [f'<a href="{E(it["url"], quote=True)}" target="_blank" rel="noopener">{E(it["source"])}</a>']
    for l in it.get("links") or []:
        src.append(f'<a href="{E(l["url"], quote=True)}" target="_blank" rel="noopener">{E(l["source"])}</a>')
    meta.append(f"<span><b>출처</b>{', '.join(src)}</span>")
    return (
        f'<li class="row" data-found="{"" if it.get("baseline") else E(it.get("found_at", ""), quote=True)}" '
        f'data-text="{E(text, quote=True)}" data-kw="{E("|".join(kws), quote=True)}">'
        f'<div class="date">{E(md)}<small>{E(year)}</small></div>'
        f'<div><a class="title" href="{E(it["url"], quote=True)}" target="_blank" rel="noopener">{E(it["title"])}</a>'
        f'<div class="meta">{"".join(meta)}</div>'
        f'<div class="kw">{"".join(f"<span>{E(k)}</span>" for k in kws)}</div></div>'
        f'<div class="seal" aria-label="최근 3일 안에 새로 발견">신규</div></li>'
    )


def render(*, title, items, keywords, sources, updated, repo, new_hours, now) -> str:
    groups: "OrderedDict[str, list]" = OrderedDict()
    for it in items:
        groups.setdefault(_date_parts(it)[0], []).append(it)

    used = []
    for it in items:
        for k in it.get("keywords") or []:
            if k not in used:
                used.append(k)
    ordered_kw = [k for k in keywords if k in used] + [k for k in used if k not in keywords]

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
            for ym, rows in groups.items())
        body += ('<div class="empty" id="nomatch" hidden>조건에 맞는 공고가 없습니다. '
                 '검색어를 지우거나 키워드 선택을 해제해 보세요.</div>')
    else:
        body = ('<div class="empty">아직 기록된 공고가 없습니다. 첫 확인이 끝나면 키워드에 맞는 '
                '공고가 이곳에 쌓입니다.</div>')

    chips = "".join(
        f'<button type="button" class="chip" data-kw="{E(k, quote=True)}" aria-pressed="false">{E(k)}</button>'
        for k in ordered_kw)

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
  <p>기업마당과 중소벤처기업부 사업공고 중 설정한 키워드에 맞는 공고만 모았습니다. 새 공고는 텔레그램·이메일로도 알려 드립니다.</p>
  <div class="status">{''.join(status)}</div>
</header>
<div class="tools">
  <input id="q" class="search" type="search" placeholder="공고명·기관으로 찾기" aria-label="공고 검색">
  <div class="chips" role="group" aria-label="키워드로 거르기">{chips}</div>
  <p class="count" id="count" aria-live="polite"></p>
</div>
{body}
<footer>최근 {new_hours}시간 안에 새로 발견한 공고에는 <b>신규</b> 도장이 찍힙니다. 신청 전에는 반드시 원문 공고를 확인하세요.</footer>
</div>
<script>{JS % new_hours}
(function(){{var n=document.getElementById('nomatch');if(!n)return;var o=new MutationObserver(function(){{n.hidden=!!document.querySelector('li.row:not([hidden])');}});document.querySelectorAll('li.row').forEach(function(r){{o.observe(r,{{attributes:true,attributeFilter:['hidden']}});}});}})();
</script>
</body>
</html>
"""
