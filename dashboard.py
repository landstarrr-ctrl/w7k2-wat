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
  --mss:#2F64C8; --mss-bg:#E3ECFB; --motie:#C0610E; --motie-bg:#FBEBDC; --msit:#0E7C70; --msit-bg:#DDF2EE;
  --multi:#6E48B8; --multi-bg:#ECE5F8; --local:#5B6774; --local-bg:#E6EAEE;
  --open:#1F7A3D; --open-bg:#DFF3E5; --soon:#2F64C8; --soon-bg:#E3ECFB; --shut:#6B7480; --shut-bg:#E9ECEF;
  color-scheme:light;
}
:root[data-theme="dark"]{
    --paper:#11161C; --sheet:#182029; --ink:#E4E9EE; --muted:#93A0AD; --rule:#2A3440;
    --seal:#E5534B; --link:#8EB6F2; --chip:#232D38; --chip-on:#E4E9EE; --chip-on-ink:#11161C;
    --mss:#7FA9F5; --mss-bg:#1C2B45; --motie:#F2A25A; --motie-bg:#3A2716; --msit:#5CC9BB; --msit-bg:#15332F;
    --multi:#B79AF0; --multi-bg:#2C2342; --local:#A3AEBA; --local-bg:#26303B;
    --open:#6FD08F; --open-bg:#173322; --soon:#7FA9F5; --soon-bg:#1C2B45; --shut:#97A1AC; --shut-bg:#262E37;
    color-scheme:dark;
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--paper);color:var(--ink);
  font-family:"IBM Plex Sans KR",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto;padding:40px 20px 80px}
header h1{font-size:30px;line-height:1.25;font-weight:700;letter-spacing:-.02em;margin:0 0 8px}
.top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:20px;
  padding-bottom:12px;border-bottom:1px solid var(--rule)}
.clock{font-variant-numeric:tabular-nums;font-size:14px;color:var(--muted);letter-spacing:.01em}
.clock b{color:var(--ink);font-weight:600;margin-left:6px}
.theme{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;padding:0;
  color:var(--ink);background:var(--sheet);border:1px solid var(--rule);border-radius:50%;cursor:pointer}
.theme:hover{border-color:var(--muted)}
.theme:focus-visible{outline:2px solid var(--link);outline-offset:2px}
.theme svg{width:18px;height:18px}
.theme .sun{display:none}
:root[data-mode="dark"] .theme .sun{display:inline}
:root[data-mode="dark"] .theme .moon{display:none}
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
li.row{border-left:4px solid transparent}
li.m-mss{border-left-color:var(--mss)} li.m-motie{border-left-color:var(--motie)}
li.m-msit{border-left-color:var(--msit)} li.m-multi{border-left-color:var(--multi)} li.m-local{border-left-color:var(--local)}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:5px}
.pill{font-size:12px;font-weight:600;line-height:1.5;padding:1px 8px;border-radius:4px;white-space:nowrap}
.pill.mss{color:var(--mss);background:var(--mss-bg)} .pill.motie{color:var(--motie);background:var(--motie-bg)}
.pill.msit{color:var(--msit);background:var(--msit-bg)} .pill.multi{color:var(--multi);background:var(--multi-bg)}
.pill.local,.pill.etc{color:var(--local);background:var(--local-bg)}
.st{display:none}
.st.open{display:inline-block;color:var(--open);background:var(--open-bg)}
.st.soon{display:inline-block;color:var(--soon);background:var(--soon-bg);outline:1px dashed var(--soon);outline-offset:-1px}
.st.shut{display:inline-block;color:var(--shut);background:var(--shut-bg)}
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
  .top{flex-wrap:wrap}
  .clock{font-size:13px}
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
  function day(s){return s?new Date(s+'T00:00:00'):null;}
  rows.forEach(function(r){
    var t=Date.parse(r.dataset.found||'');
    if(!isNaN(t)&&now-t<NEW_MS){r.classList.add('is-new');}
    var st=r.querySelector('.st'), b=day(r.dataset.start), e=day(r.dataset.end), label='', cls='';
    if(e&&e<today){label='마감';cls='shut';}
    else if(b&&b>today){var n=Math.round((b-today)/864e5);label='접수예정 · '+(n===0?'오늘':n+'일 뒤')+' 시작';cls='soon';}
    else if(e){var left=Math.round((e-today)/864e5);label='접수중 · '+(left===0?'오늘 마감':'D-'+left);cls='open';}
    else if(b){label='접수중';cls='open';}
    else if(r.dataset.status){label=r.dataset.status+' (확인 시점)';
      cls=r.dataset.status.indexOf('마감')>-1?'shut':r.dataset.status.indexOf('예정')>-1?'soon':'open';}
    if(cls==='shut'){r.classList.add('is-closed');}
    if(st&&label){st.textContent=label;st.className='pill st '+cls;}
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


LOCAL = ("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충청", "충북", "충남",
         "전라", "전북", "전남", "경상", "경북", "경남", "제주", "테크노파크", "특별자치", "광역시")


def ministry_badge(it):
    """공고의 소관 부처를 짧은 이름과 색 이름으로 바꿉니다."""
    m = it.get("ministry") or ""
    if not m:
        if it.get("source") in ("중기부 누리집",) or str(it.get("source", "")).startswith("KOSMO"):
            m = "중소벤처기업부"
        else:
            m = (it.get("org") or "").split(" / ")[0]
    if "중소벤처" in m or "중기청" in m or "중소기업청" in m:
        return "중기부", "mss"
    if "산업통상" in m:
        return "산업부", "motie"
    if "과학기술정보통신" in m:
        return "과기정통부", "msit"
    if "다부처" in m or "범부처" in m:
        return "다부처", "multi"
    if any(k in m for k in LOCAL) or m.endswith(("도", "시", "군", "구")):
        return "지자체", "local"
    if m:
        short = m.replace("부처", "")
        return (short[:6], "etc")
    return "", "none"


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
    period = it.get("period", "")
    found = re.findall(r"\d{4}-\d{2}-\d{2}", period)
    if len(found) >= 2:
        start, end = found[0], found[-1]
    elif len(found) == 1:
        start, end = ("", found[0]) if period.strip().startswith("~") else (found[0], "")
    else:
        start = end = ""
    mname, mcls = ministry_badge(it)
    mpill = f'<span class="pill {mcls}">{E(mname)}</span>' if mname else ""
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
        f'<li class="row m-{mcls}" data-found="{"" if it.get("baseline") else E(it.get("found_at", ""), quote=True)}" '
        f'data-text="{E(text, quote=True)}" data-groups="{E("|".join(groups), quote=True)}" '
        f'data-start="{E(start, quote=True)}" data-end="{E(end, quote=True)}" '
        f'data-status="{E(it.get("status", ""), quote=True)}">'
        f'<div class="date">{E(md)}<small>{E(year)}</small></div>'
        f'<div><div class="badges">{mpill}'
        f'<span class="pill st"></span></div>'
        f'<a class="title" href="{E(it["url"], quote=True)}" target="_blank" rel="noopener">{E(it["title"])}</a>'
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
<html lang="ko" data-mode="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📮</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<script>
(function(){{try{{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();
</script>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<div class="top">
  <div class="clock" aria-live="off">현재 시각<b id="clock">—</b></div>
  <button type="button" class="theme" id="themeBtn" aria-label="다크 모드로 바꾸기" title="다크 모드로 바꾸기">
    <svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
    <svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
  </button>
</div>
<header>
  <h1>{E(title)}</h1>
  <p>기업마당·중소벤처기업부·KOSMO·IRIS의 스마트공장·제조AI·자율형공장·피지컬AI 관련 공고를 분류별로 모았습니다. 새 공고는 텔레그램으로도 알려 드립니다.</p>
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
<script>
(function(){{
  var root=document.documentElement, btn=document.getElementById('themeBtn');
  function mode(){{return root.getAttribute('data-theme')==='dark'?'dark':'light';}}
  function paint(){{var m=mode(), tip=m==='dark'?'라이트 모드로 바꾸기':'다크 모드로 바꾸기';
    root.setAttribute('data-mode',m);btn.setAttribute('aria-label',tip);btn.setAttribute('title',tip);}}
  btn.addEventListener('click',function(){{var next=mode()==='dark'?'light':'dark';
    root.setAttribute('data-theme',next);try{{localStorage.setItem('theme',next);}}catch(e){{}}paint();}});
  paint();
  var el=document.getElementById('clock'), days=['일','월','화','수','목','금','토'];
  var fmt=new Intl.DateTimeFormat('ko-KR',{{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',
    weekday:'short',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}});
  function tick(){{var p={{}};fmt.formatToParts(new Date()).forEach(function(x){{p[x.type]=x.value;}});
    var h=p.hour==='24'?'00':p.hour;
    el.textContent=p.year+'년 '+p.month+'월 '+p.day+'일 ('+p.weekday+') '+h+':'+p.minute+':'+p.second;}}
  tick();setInterval(tick,1000);
}})();
</script>
<script>{JS % new_hours}
</script>
</body>
</html>
"""
