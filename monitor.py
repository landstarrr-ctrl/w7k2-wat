#!/usr/bin/env python3
"""스마트제조혁신 지원사업 공고 감시 봇.

기업마당 API와 중소벤처기업부 사업공고 게시판을 확인해서
키워드에 맞는 새 공고가 올라오면 텔레그램/이메일로 알리고,
docs/index.html 대시보드를 갱신합니다.

  python monitor.py               # 한 번 확인
  python monitor.py --dry-run     # 확인만 하고 저장·알림 안 함
  python monitor.py --test-notify # 알림 채널 테스트
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import smtplib
import sys
import time
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"
STATE_PATH = ROOT / "data" / "state.json"
DOCS_DIR = ROOT / "docs"
KST = dt.timezone(dt.timedelta(hours=9))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BIZINFO_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
MSS_VIEW = "https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=310&bcIdx={id}&parentSeq={id}"
FAIL_ALERT_AFTER = 3          # 연속 실패 몇 번째에 경고를 보낼지
NEW_BADGE_HOURS = 72          # 대시보드에서 '신규' 표시를 붙일 시간


# ───────────────────────── 공통 도구 ─────────────────────────
def load_dotenv() -> None:
    """로컬 실행용 .env 파일을 읽습니다 (GitHub Actions에서는 Secrets 사용)."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def now_kst() -> dt.datetime:
    return dt.datetime.now(KST)


def clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def norm(s) -> str:
    return re.sub(r"\s+", "", str(s or "")).lower()


def title_key(title: str) -> str:
    """출처가 달라도 같은 공고인지 비교하기 위한 제목 키."""
    return norm(re.sub(r"[「」『』\[\]()<>〈〉《》“”\"'‘’·ㆍ,.\-_~]", "", title or ""))


def fmt_period(s) -> str:
    """'20261110 ~ 20270115' 같은 표기를 '2026-11-10 ~ 2027-01-15'로 바꿉니다."""
    return re.sub(r"\b(\d{4})(\d{2})(\d{2})\b", r"\1-\2-\3", clean(s))


def short_hash(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def log(msg: str) -> None:
    print(f"[{now_kst():%H:%M:%S}] {msg}", flush=True)


def _compile_alt(alt: str):
    """키워드 하나를 검사 함수로 바꿉니다. 영어 키워드는 단어 단위로만 잡습니다."""
    if all(ord(c) < 128 for c in alt):
        chars = [re.escape(ch) for ch in alt.lower() if not ch.isspace()]
        pat = re.compile(r"(?<![a-z0-9])" + r"\s*".join(chars) + r"(?![a-z0-9])")
        return lambda spaced, nospace: bool(pat.search(spaced))
    key = norm(alt)
    return lambda spaced, nospace: key in nospace


class Rule:
    """'AI + 제조|공장' 같은 규칙: + 는 그리고, | 는 또는."""

    def __init__(self, raw):
        self.raw = str(raw)
        self.parts = []
        for part in self.raw.split("+"):
            alts = [a.strip() for a in part.split("|") if a.strip()]
            if alts:
                self.parts.append([(a, _compile_alt(a)) for a in alts])

    def match(self, spaced: str, nospace: str):
        labels = []
        for alts in self.parts:
            hit = next((a for a, f in alts if f(spaced, nospace)), None)
            if hit is None:
                return None
            labels.append(hit)
        return "·".join(labels) if labels else None


class Matcher:
    def __init__(self, cfg: dict):
        groups = cfg.get("groups")
        if not groups:  # 예전 설정 파일(keywords 목록 하나) 호환
            groups = [{"name": "키워드", "keywords": cfg.get("keywords") or []}]
        self.groups = [(clean(g["name"]), [Rule(k) for k in g.get("keywords") or []])
                       for g in groups if g and g.get("name")]
        self.exclude = [Rule(e) for e in cfg.get("exclude") or []]
        self.names = [n for n, _ in self.groups]
        self.keywords = [r.raw for _, rules in self.groups for r in rules]

    def classify(self, text: str):
        spaced = re.sub(r"\s+", " ", str(text or "")).lower()
        nospace = norm(text)
        if any(r.match(spaced, nospace) for r in self.exclude):
            return [], []
        labels, groups = [], []
        for name, rules in self.groups:
            for r in rules:
                lab = r.match(spaced, nospace)
                if lab:
                    if name not in groups:
                        groups.append(name)
                    if lab not in labels:
                        labels.append(lab)
        return labels, groups

    def __call__(self, text: str) -> list[str]:
        return self.classify(text)[0]


def config_hash(cfg: dict) -> str:
    key = {k: cfg.get(k) for k in ("groups", "keywords", "exclude", "match_summary")}
    return hashlib.sha1(json.dumps(key, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def http_get(session: requests.Session, url: str, **kw) -> requests.Response:
    last = None
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"접속 실패: {last}")


# ───────────────────────── 출처별 수집 ─────────────────────────
def fetch_bizinfo(session, cfg, match, match_summary):
    key = os.environ.get("BIZINFO_API_KEY", "").strip()
    if not key:
        return None  # 키가 없으면 건너뜀
    r = http_get(session, BIZINFO_URL, params={
        "crtfcKey": key, "dataType": "json", "searchCnt": str(cfg.get("count", 200)),
    })
    try:
        data = r.json()
    except ValueError:
        raise RuntimeError("기업마당 API가 JSON이 아닌 응답을 보냈습니다: " + clean(r.text)[:120])
    if isinstance(data, dict) and data.get("reqErr"):
        raise RuntimeError(f"기업마당 API 오류: {data['reqErr']}")
    # 응답 형태가 {"jsonArray":[...]} 또는 {"jsonArray":{"item":[...]}} 둘 다 올 수 있음
    rows = data.get("jsonArray", data) if isinstance(data, dict) else data
    if isinstance(rows, dict):
        rows = rows.get("item") or rows.get("items") or []
    if isinstance(rows, dict):          # 공고가 1건이면 목록 대신 하나만 올 수 있음
        rows = [rows]
    if not isinstance(rows, list):
        rows = []
    rows = [r for r in rows if isinstance(r, dict)]

    items = []
    for row in rows:
        title = clean(row.get("pblancNm") or row.get("title"))
        if not title:
            continue
        tags = clean(row.get("hashTags") or row.get("hashtags"))
        text = title + " " + tags
        if match_summary:
            summary_html = row.get("bsnsSumryCn") or row.get("description") or ""
            summary = BeautifulSoup(summary_html, "html.parser").get_text(" ")
            text += " " + summary
        hits = match(text)
        if not hits:
            continue
        url = row.get("pblancUrl") or row.get("link") or ""
        if url and not url.startswith("http"):
            url = urljoin("https://www.bizinfo.go.kr", url)
        orgs = [clean(row.get("jrsdInsttNm") or row.get("author")), clean(row.get("excInsttNm"))]
        items.append({
            "id": "bizinfo:" + (clean(row.get("pblancId") or row.get("seq")) or short_hash(title)),
            "source": "기업마당",
            "title": title,
            "url": url or "https://www.bizinfo.go.kr",
            "org": " / ".join(dict.fromkeys(o for o in orgs if o)),
            "period": fmt_period(row.get("reqstBeginEndDe") or row.get("reqstDt")),
            "posted": clean(row.get("creatPnttm") or row.get("pubDate"))[:10],
            "keywords": hits,
            "tags": tags,
        })
    return items


def _row_details(a):
    row = a.find_parent(["tr", "li"])
    text = clean(row.get_text(" ")) if row else clean(a.get_text(" "))
    period = re.search(r"신청기간\s*:?\s*(\d{4}[.\-]\d{2}[.\-]\d{2}\s*~\s*\d{4}[.\-]\d{2}[.\-]\d{2})", text)
    org = re.search(r"담당부서\s*:?\s*([^\s]+)", text)
    period_txt = period.group(1) if period else ""
    dates = [d for d in re.findall(r"\d{4}[.\-]\d{2}[.\-]\d{2}", text) if d not in period_txt]
    return {
        "period": period_txt,
        "org": org.group(1) if org else "",
        "posted": dates[-1].replace(".", "-") if dates else "",
    }


def fetch_mss(session, cfg, match):
    list_url = cfg.get("url") or "https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310"
    r = http_get(session, list_url)
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    items, seen = [], set()
    for a in soup.find_all("a"):
        raw = clean(a.get_text(" "))
        if len(raw) < 6:
            continue
        title = re.split(r"\s*(?:담당부서|공고번호|신청기간)\s*", raw)[0].strip()
        hits = match(title)
        if not hits:
            continue
        href = a.get("href") or ""
        # 다른 사이트로 나가는 링크(관련 사이트·배너)는 공고가 아님
        if href.startswith("http") and "mss.go.kr" not in href:
            continue
        details = _row_details(a)
        # 게시글 줄에는 등록일이 있음. 날짜 없는 링크(메뉴·바로가기)는 건너뜀
        if not details["posted"]:
            continue
        attrs = " ".join(str(v) for v in a.attrs.values())
        m = re.search(r"bcIdx=(\d+)", attrs)
        if m:
            bid = m.group(1)
            link = MSS_VIEW.format(id=bid)
        else:
            num = re.search(r"(?<!\d)(\d{6,9})(?!\d)", attrs)
            bid = num.group(1) if num else short_hash(title)
            usable = href and not href.startswith("#") and not href.lower().startswith("javascript")
            link = urljoin(list_url, href) if usable else list_url
            log(f"  (참고) 게시글 링크 형태: {str(a)[:200]}")
        if bid in seen:
            continue
        seen.add(bid)
        items.append({
            "id": f"mss:{bid}",
            "source": "중기부 누리집",
            "title": title,
            "url": link,
            "keywords": hits,
            **details,
        })
    return items


def fetch_page(session, page, match):
    url = page["url"]
    r = http_get(session, url)
    r.encoding = page.get("encoding") or r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    items, seen = [], set()
    for a in soup.find_all("a"):
        title = clean(a.get_text(" "))
        if not 6 <= len(title) <= 200:
            continue
        hits = match(title)
        if not hits:
            continue
        href = a.get("href") or ""
        usable = href and not href.startswith("#") and not href.lower().startswith("javascript")
        link = urljoin(url, href) if usable else url
        uid = short_hash(page["name"], title, link)
        if uid in seen:
            continue
        seen.add(uid)
        items.append({
            "id": f"page:{uid}", "source": page["name"], "title": title, "url": link,
            "org": "", "period": "", "posted": "", "keywords": hits,
        })
    return items


# ───────────────────────── 알림 ─────────────────────────
def dashboard_url(cfg) -> str:
    url = (cfg.get("dashboard") or {}).get("url") or ""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not url and "/" in repo:
        owner, name = repo.split("/", 1)
        url = f"https://{owner.lower()}.github.io/{name}/"
    return url


def _item_block_tg(it) -> str:
    e = html.escape
    tag = f"[{' / '.join(it.get('groups') or [])}] " if it.get("groups") else ""
    lines = [f"<b>{e(tag + it['title'])}</b>"]
    if it.get("org"):
        lines.append(e(it["org"]))
    if it.get("period"):
        lines.append(f"신청기간 {e(it['period'])}")
    lines.append(f"키워드 {e(', '.join(it.get('keywords', [])))}")
    lines.append(f'<a href="{e(it["url"], quote=True)}">공고 보기</a> ({e(it["source"])})')
    return "\n".join(lines)


def send_telegram(header: str, blocks: list[str], footer: str = ""):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return None
    messages, cur = [], header
    for b in blocks:
        if len(cur) + len(b) + 2 > 3800:
            messages.append(cur)
            cur = header + " (계속)"
        cur += "\n\n" + b
    if footer:
        cur += "\n\n" + footer
    messages.append(cur)
    for text in messages:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30, data={
            "chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true",
        })
        if r.status_code != 200:
            raise RuntimeError(f"텔레그램 전송 실패 {r.status_code}: {r.text[:200]}")
    return True


def send_email(subject: str, body_html: str):
    user = os.environ.get("SMTP_USER", "").strip()
    pw = os.environ.get("SMTP_PASSWORD", "").strip()
    to = os.environ.get("MAIL_TO", "").strip() or user
    if not user or not pw:
        return None
    host = os.environ.get("SMTP_HOST", "").strip() or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT", "").strip() or 465)
    recipients = [x.strip() for x in to.split(",") if x.strip()]
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.login(user, pw)
            s.sendmail(user, recipients, msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, pw)
            s.sendmail(user, recipients, msg.as_string())
    return True


def _email_html(header: str, items: list[dict], notes: list[str], dash: str) -> str:
    e = html.escape
    parts = [f'<div style="font-family:sans-serif;max-width:640px"><h2 style="font-size:18px">{e(header)}</h2>']
    for n in notes:
        parts.append(f"<p>{e(n)}</p>")
    for it in items:
        meta = " / ".join(x for x in [" · ".join(it.get("groups") or []), it.get("org"),
                                       it.get("period") and f"신청기간 {it['period']}", it["source"]] if x)
        parts.append(
            f'<div style="border-top:1px solid #ddd;padding:10px 0">'
            f'<a href="{e(it["url"], quote=True)}" style="font-weight:bold;font-size:15px">{e(it["title"])}</a>'
            f'<div style="color:#555;font-size:13px;margin-top:4px">{e(meta)}</div>'
            f'<div style="color:#555;font-size:13px">키워드: {e(", ".join(it.get("keywords", [])))}</div></div>')
    if dash:
        parts.append(f'<p style="margin-top:16px"><a href="{e(dash, quote=True)}">대시보드 열기</a></p>')
    parts.append("</div>")
    return "".join(parts)


def notify(cfg, header: str, items: list[dict] | None = None, notes: list[str] | None = None) -> bool:
    """설정된 채널로 보냅니다. 하나라도 성공하거나 설정된 채널이 없으면 True."""
    items, notes = items or [], notes or []
    dash = dashboard_url(cfg)
    results = []
    try:
        blocks = [html.escape(n) for n in notes] + [_item_block_tg(it) for it in items]
        footer = f'<a href="{html.escape(dash, quote=True)}">대시보드 열기</a>' if dash else ""
        results.append(send_telegram(f"🔔 <b>{html.escape(header)}</b>", blocks, footer))
    except Exception as e:  # noqa: BLE001
        log(f"텔레그램 오류: {e}")
        results.append(False)
    try:
        results.append(send_email(f"[공고 감시] {header}", _email_html(header, items, notes, dash)))
    except Exception as e:  # noqa: BLE001
        log(f"이메일 오류: {e}")
        results.append(False)

    configured = [r for r in results if r is not None]
    if not configured:
        log(f"(알림 채널 미설정) {header}")
        for n in notes:
            log(f"  {n}")
        for it in items:
            log(f"  - {it['title']} [{it['source']}] {it['url']}")
        return True
    return any(configured)


# ───────────────────────── 상태 저장 ─────────────────────────
def load_state() -> dict:
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    else:
        state = {}
    state.setdefault("seen", {})       # id -> title_key
    state.setdefault("items", [])      # 대시보드에 보여줄 고유 공고
    state.setdefault("sources", {})    # 출처별 상태
    return state


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def sort_key(it):
    return (it.get("posted") or it.get("found_at", "")[:10], it.get("found_at", ""))


# ───────────────────────── 대시보드 ─────────────────────────
def classify_item(matcher, it) -> None:
    text = " ".join([it.get("title", ""), it.get("tags", ""), " ".join(it.get("keywords") or [])])
    labels, groups = matcher.classify(text)
    it["groups"] = groups
    if labels:
        it["keywords"] = labels


def group_summary(items) -> str:
    counts = {}
    for it in items:
        for g in it.get("groups") or ["기타"]:
            counts[g] = counts.get(g, 0) + 1
    return ", ".join(f"{g} {n}건" for g, n in counts.items())


def render_dashboard(cfg, state, matcher) -> None:
    from dashboard import render  # 같은 폴더의 dashboard.py
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    page = render(
        title=(cfg.get("dashboard") or {}).get("title") or "공고 감시",
        items=state["items"],
        groups=matcher.names,
        sources=state["sources"],
        updated=state.get("updated", ""),
        repo=repo,
        new_hours=NEW_BADGE_HOURS,
        now=now_kst(),
    )
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    (DOCS_DIR / "items.json").write_text(
        json.dumps(state["items"], ensure_ascii=False, indent=1), encoding="utf-8")
    nojekyll = DOCS_DIR / ".nojekyll"
    if not nojekyll.exists():
        nojekyll.write_text("", encoding="utf-8")


# ───────────────────────── 실행 ─────────────────────────
def build_sources(cfg, session, match):
    src = cfg.get("sources") or {}
    out = []
    biz = src.get("bizinfo") or {}
    if biz.get("enabled", True):
        out.append(("기업마당", lambda: fetch_bizinfo(session, biz, match, bool(cfg.get("match_summary")))))
    mss = src.get("mss") or {}
    if mss.get("enabled", True):
        out.append(("중기부 누리집", lambda: fetch_mss(session, mss, match)))
    for page in src.get("pages") or []:
        if page and page.get("url") and page.get("name"):
            out.append((page["name"], lambda p=page: fetch_page(session, p, match)))
    return out


def run(cfg, dry_run=False) -> int:
    state = load_state()
    match = Matcher(cfg)
    cfg_id = config_hash(cfg)
    # 키워드를 바꾼 뒤 첫 실행: 새로 잡힌 기존 공고는 하나씩 알리지 않고 요약만 보냄
    backfill = (state.get("cfg_hash") != cfg_id
                and any(st.get("initialized") for st in state["sources"].values()))
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})

    stamp = now_kst().isoformat(timespec="minutes")
    changed = False
    pending: list[dict] = []        # 알림 보낼 새 공고
    baseline: list[dict] = []       # 첫 실행에서 조용히 기록할 공고
    baseline_notes: list[str] = []
    alerts: list[str] = []
    run_keys: dict[str, dict] = {}  # 이번 실행에서 처음 본 제목 키 -> 공고
    dup_links: list[tuple[str, dict]] = []

    # 한 번만 실행: 예전 버전의 오류 정리 후 중기부 게시판을 조용히 다시 기록
    if state.get("fix") != "mss-v3":
        state["items"] = [it for it in state["items"]
                          if not (it["id"].startswith("mss:") and not it.get("posted"))]
        kept = {it["id"] for it in state["items"]}
        state["seen"] = {k: v for k, v in state["seen"].items()
                         if not k.startswith("mss:") or k in kept}
        state["sources"].setdefault("중기부 누리집", {})["initialized"] = False
        state["fix"] = "mss-v3"
        changed = True
        log("중기부 게시판 기록을 정리하고 다시 확인합니다.")

    existing_by_key = {it.get("tkey"): it for it in state["items"] if it.get("tkey")}

    for name, fetch in build_sources(cfg, session, match):
        st = state["sources"].setdefault(name, {"initialized": False, "fails": 0})
        try:
            items = fetch()
        except Exception as e:  # noqa: BLE001
            st["fails"] = st.get("fails", 0) + 1
            st["error"] = clean(e)[:200]
            changed = True
            log(f"{name}: 실패 ({st['fails']}회 연속) {e}")
            if st["fails"] == FAIL_ALERT_AFTER:
                alerts.append(f"{name} 확인이 {FAIL_ALERT_AFTER}회 연속 실패했습니다. 원인: {st['error']}")
            continue
        if items is None:
            log(f"{name}: 건너뜀 (설정 없음)")
            continue
        if st.get("fails") or st.get("error"):
            st["fails"] = 0
            st.pop("error", None)
            changed = True
        st["ok_at"] = stamp[:10]
        log(f"{name}: 키워드 일치 {len(items)}건")

        first_time = not st.get("initialized")
        count_new = 0
        for it in items:
            if it["id"] in state["seen"]:
                continue
            tk = title_key(it["title"])
            it["tkey"] = tk
            it["found_at"] = stamp
            twin = existing_by_key.get(tk) or run_keys.get(tk)
            if twin:
                dup_links.append((it["id"], {"tkey": tk, "source": it["source"], "url": it["url"], "twin": twin}))
                continue
            run_keys[tk] = it
            count_new += 1
            (baseline if first_time else pending).append(it)
        if first_time:
            st["initialized"] = True
            changed = True
            baseline_notes.append(f"{name}: 현재 게시된 관련 공고 {count_new}건을 기록했습니다.")

    # 다른 출처에서 이미 본 공고는 링크만 추가
    for iid, d in dup_links:
        twin = d["twin"]
        links = twin.setdefault("links", [])
        if all(l["url"] != d["url"] for l in links) and twin.get("url") != d["url"]:
            links.append({"source": d["source"], "url": d["url"]})
        state["seen"][iid] = d["tkey"]
        changed = True

    for it in baseline:
        it["baseline"] = True   # 감시 시작 전부터 있던 공고 ('신규' 도장 안 찍음)
        state["seen"][it["id"]] = it["tkey"]
        state["items"].append(it)

    if dry_run:
        log(f"[dry-run] 새 공고 {len(pending)}건, 첫 기록 {len(baseline)}건, 경고 {len(alerts)}건")
        for it in pending + baseline:
            log(f"  - {it['title']} [{it['source']}]")
        return 0

    for it in pending + baseline:
        classify_item(match, it)

    if pending and backfill:
        for it in pending:
            state["seen"][it["id"]] = it["tkey"]
            state["items"].append(it)
        changed = True
        notify(cfg, f"키워드 변경으로 공고 {len(pending)}건을 추가했습니다", notes=[
            f"분류: {group_summary(pending)}",
            "이미 올라와 있던 공고라 하나씩 알리지 않았습니다. 대시보드에서 '신규' 도장이 찍힌 공고를 확인하세요.",
        ])
    elif pending:
        pending.sort(key=sort_key, reverse=True)
        header = f"새 공고 {len(pending)}건 ({group_summary(pending)})"
        ok = notify(cfg, header, items=pending)
        if ok:
            for it in pending:
                state["seen"][it["id"]] = it["tkey"]
                state["items"].append(it)
            changed = True
        else:
            log("알림 전송에 실패해 이번 공고는 다음 실행 때 다시 보냅니다.")
    if state.get("cfg_hash") != cfg_id:
        state["cfg_hash"] = cfg_id
        changed = True
    # 대시보드 설정(제목 등)만 바꿔도 바로 다시 그리도록
    dash_id = hashlib.sha1(json.dumps(cfg.get("dashboard") or {}, ensure_ascii=False,
                                      sort_keys=True).encode("utf-8")).hexdigest()[:12]
    if state.get("dash_hash") != dash_id:
        state["dash_hash"] = dash_id
        changed = True
    if baseline_notes:
        notes = baseline_notes + ["지금부터 새로 올라오는 공고만 알려 드립니다."]
        notify(cfg, "공고 감시를 시작했습니다", notes=notes)
    if alerts:
        notify(cfg, "감시 경고", notes=alerts + [
            "사이트 점검·구조 변경·접속 차단일 수 있습니다. README의 문제 해결 항목을 확인하세요."])

    today = stamp[:10]
    if state.get("heartbeat") != today:   # 하루 한 번 기록해서 GitHub 스케줄이 멈추지 않게 함
        state["heartbeat"] = today
        changed = True

    if changed:
        for it in state["items"]:   # 설정이 바뀌어도 탭 분류가 최신이 되도록 다시 계산
            classify_item(match, it)
        keep = int((cfg.get("dashboard") or {}).get("keep") or 500)
        state["items"].sort(key=sort_key, reverse=True)
        state["items"] = state["items"][:keep]
        state["updated"] = stamp
        save_state(state)
        render_dashboard(cfg, state, match)
        log("상태와 대시보드를 저장했습니다.")
    else:
        log("변동 없음")
    return 0


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="스마트제조혁신 공고 감시")
    ap.add_argument("--dry-run", action="store_true", help="확인만 하고 저장·알림 안 함")
    ap.add_argument("--test-notify", action="store_true", help="알림 채널 테스트 메시지 전송")
    args = ap.parse_args()
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}

    if args.test_notify:
        sample = {
            "title": "(테스트) 2027년 스마트공장 구축 지원사업 공고", "source": "테스트",
            "url": "https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310",
            "org": "중소벤처기업부", "period": "2026-11-10 ~ 2027-01-15", "keywords": ["스마트공장"],
        }
        ok = notify(cfg, "알림 테스트", items=[sample], notes=["이 메시지가 보이면 알림 설정이 끝난 것입니다."])
        return 0 if ok else 1
    return run(cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
