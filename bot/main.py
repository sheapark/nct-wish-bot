# -*- coding: utf-8 -*-
import os, re
from datetime import datetime
import pytz, requests
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup
from supabase import create_client
import tweepy


# ═══════════════════════════════════════════════
#  환경변수 로드
# ═══════════════════════════════════════════════
load_dotenv()

API_KEY             = os.environ["API_KEY"]
API_KEY_SECRET      = os.environ["API_KEY_SECRET"]
ACCESS_TOKEN        = os.environ["ACCESS_TOKEN"]
ACCESS_TOKEN_SECRET = os.environ["ACCESS_TOKEN_SECRET"]

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
YT_VIDEO_ID     = os.environ["YT_VIDEO_ID"]

# Supabase bot_config가 없을 때 사용하는 기본값
_DEFAULT_TITLE  = os.environ.get("TARGET_TITLE",  "COLOR").strip()
_DEFAULT_ARTIST = os.environ.get("TARGET_ARTIST", "NCT WISH").strip()

KST = pytz.timezone("Asia/Seoul")

SITES = [
    ("멜론 TOP100", "melon_top100"),
    ("멜론 HOT100", "melon_hot100"),
    ("멜론 실시간", "guyseom"),
    ("지니",        "genie"),
    ("플로",        "flo"),
    ("벅스",        "bugs"),
    ("바이브",      "vibe_top300"),
]


# ═══════════════════════════════════════════════
#  Supabase — 설정 / 상태 / 저장
# ═══════════════════════════════════════════════

def load_config() -> dict:
    """bot_config 테이블에서 설정값 읽기. 실패 시 .env 기본값 사용."""
    try:
        rows = sb.table("bot_config").select("*").execute().data or []
        return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        print("⚠️ load_config 실패, .env 기본값 사용:", e)
        return {}


def load_state() -> dict:
    """rank_history에서 site별 가장 최근 순위를 읽어 이전값으로 사용."""
    try:
        rows = (
            sb.table("rank_history")
            .select("site, rank")
            .order("checked_at", desc=True)
            .limit(len(SITES) * 2)
            .execute()
            .data or []
        )
        seen = {}
        for r in rows:
            if r["site"] not in seen:
                seen[r["site"]] = r["rank"]
        return {"ranks": seen}
    except Exception as e:
        print("⚠️ load_state 실패:", e)
        return {}


def save_to_supabase(now, ranks, site_changes, views, tweet_text, success, error_msg=None):
    """rank_history + tweet_logs 동시 저장."""
    now_iso = now.isoformat()
    try:
        rank_rows = [
            {
                "checked_at": now_iso,
                "site":       site_key,
                "rank":       ranks.get(site_key),
                "delta":      site_changes.get(site_key),
            }
            for _, site_key in SITES
        ]
        sb.table("rank_history").insert(rank_rows).execute()
        sb.table("tweet_logs").insert({
            "posted_at":     now_iso,
            "tweet_text":    tweet_text,
            "success":       success,
            "error_msg":     error_msg,
            "youtube_views": views,
        }).execute()
        print("✅ Supabase 저장 완료")
    except Exception as e:
        print("❌ Supabase 저장 실패:", e)


# ═══════════════════════════════════════════════
#  유틸
# ═══════════════════════════════════════════════

def normalize(s: str) -> str:
    """곡명/아티스트 비교를 위한 정규화."""
    s = s.lower()
    s = re.sub(r"\(feat\.?.*?\)|\(prod\.?.*?\)", "", s)
    s = re.sub(r"feat\.?|featuring|prod\.?", "", s)
    s = re.sub(r"[\[\]\(\)\-–—·~_:/.,!?']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_match(title, artist, target_title, target_artist) -> bool:
    """크롤링된 곡/아티스트가 타깃과 일치하는지 확인."""
    t1, a1 = normalize(title), normalize(artist)
    t2, a2 = normalize(target_title), normalize(target_artist)
    if t2 in t1 or t1 in t2:
        return len(set(a1.split()) & set(a2.split())) > 0
    return False


def delta_text(prev, curr) -> str:
    """이전 순위와 현재 순위를 비교해 등락 텍스트 반환.
    이전값이 없으면 (-) 표시."""
    if prev is None or curr is None: return " (-)"
    if curr < prev: return f" (🔺{prev - curr})"
    if curr > prev: return f" (🔻{curr - prev})"
    return " (-)"


def format_views(n) -> str:
    return "❌" if n is None else f"{n:,}"


def as_int(x):
    if isinstance(x, (list, tuple)):
        try: return int(x[0])
        except: return None
    try: return int(x) if x is not None else None
    except: return None


# ═══════════════════════════════════════════════
#  Twitter
# ═══════════════════════════════════════════════

def tweet(text: str) -> tuple:
    """트윗 발행. (status_code, error_msg) 반환."""
    try:
        client = tweepy.Client(
            consumer_key=API_KEY,
            consumer_secret=API_KEY_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET,
        )
        response = client.create_tweet(text=text, reply_settings="mentionedUsers")
        print("✅ Tweet 성공:", response.data)
        return 200, None
    except tweepy.TweepyException as e:
        err = str(e)
        print("❌ Tweet 실패:", err)
        return -1, err


# ═══════════════════════════════════════════════
#  YouTube 조회수
# ═══════════════════════════════════════════════

def fetch_youtube_views(video_id: str = YT_VIDEO_ID):
    """YouTube Data API로 조회수 가져오기.
    video_id는 Supabase bot_config에서 읽은 값 사용."""
    if not (YOUTUBE_API_KEY and video_id):
        return None
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": video_id, "key": YOUTUBE_API_KEY},
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        return int(items[0]["statistics"]["viewCount"]) if items else None
    except Exception as e:
        print("YouTube fetch error:", e)
        return None


# ═══════════════════════════════════════════════
#  차트 크롤링
# ═══════════════════════════════════════════════

def fetch_melon_chart(url, title, artist):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for row in soup.select("tr.lst50, tr.lst100"):
            rank_el   = row.select_one(".rank")
            title_el  = row.select_one(".rank01 a")
            artist_el = row.select_one(".rank02 a")
            if not (rank_el and title_el and artist_el): continue
            digits = "".join(c for c in rank_el.get_text(strip=True) if c.isdigit())
            if not digits: continue
            rank = int(digits)
            change_val = None
            rw = row.select_one(".rank_wrap")
            if rw:
                if rw.select_one(".rank_up"):
                    num = "".join(c for c in rw.select_one(".up").get_text(strip=True) if c.isdigit())
                    change_val = +int(num) if num else 0
                elif rw.select_one(".rank_down"):
                    num = "".join(c for c in rw.select_one(".down").get_text(strip=True) if c.isdigit())
                    change_val = -int(num) if num else 0
                else:
                    change_val = 0
            if is_match(title_el.get_text(" ", strip=True), artist_el.get_text(" ", strip=True), title, artist):
                return rank, change_val
        return None, None
    except Exception as e:
        print("melon fetch error:", e); return None, None

def fetch_melon_top100(title, artist):
    return fetch_melon_chart("https://www.melon.com/chart/index.htm", title, artist)

def fetch_melon_hot100(title, artist):
    return fetch_melon_chart("https://www.melon.com/chart/hot100/index.htm", title, artist)


def fetch_guyseom_rank(title, artist, when):
    try:
        url = f"https://xn--o39an51b2re.com/chart/melon/realtime/{when.strftime('%Y%m%d')}/{when.strftime('%H')}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for row in soup.select("tr"):
            rank_el   = row.select_one("td.ranking span[class^=no]")
            title_el  = row.select_one("td.subject p[title]")
            artist_el = row.select_one("td.subject p.singer span")
            change_el = row.select_one("td.ranking p.change span")
            if not (rank_el and title_el and artist_el): continue
            rank = int("".join(c for c in rank_el.get_text(strip=True) if c.isdigit()))
            if not is_match(title_el.get_text(strip=True), artist_el.get_text(strip=True), title, artist): continue
            sign, abs_ = 0, 0
            if change_el:
                num = int("".join(c for c in change_el.get_text(strip=True) if c.isdigit()) or "0")
                if "up"   in change_el.get("class", []): sign, abs_ = +1, num
                elif "down" in change_el.get("class", []): sign, abs_ = -1, num
            return rank, sign, abs_
        return None, None, None
    except Exception as e:
        print("guyseom fetch error:", e); return None, None, None


def fetch_genie_rank(title, artist):
    try:
        for page in range(1, 5):
            r = requests.get(f"https://www.genie.co.kr/chart/top200?pg={page}",
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            for row in soup.select("tr.list"):
                num_td = row.select_one("td.number")
                if not num_td: continue
                raw = num_td.find(string=True, recursive=False)
                rank = int(raw.strip()) if raw and raw.strip().isdigit() else None
                sign, abs_ = 0, 0
                if row.select_one("span.rank-up"):
                    m = re.search(r"\d+", row.select_one("span.rank-up").get_text(strip=True))
                    if m: sign, abs_ = +1, int(m.group())
                elif row.select_one("span.rank-down"):
                    m = re.search(r"\d+", row.select_one("span.rank-down").get_text(strip=True))
                    if m: sign, abs_ = -1, int(m.group())
                title_el  = row.select_one("a.title.ellipsis")
                artist_el = row.select_one("a.artist.ellipsis")
                if not (title_el and artist_el): continue
                if is_match(title_el.get_text(" ", strip=True), artist_el.get_text(" ", strip=True), title, artist):
                    return rank, sign, abs_
        return None, None, None
    except Exception as e:
        print("genie error:", e); return None, None, None


def fetch_bugs_rank(title, artist):
    try:
        r = requests.get(
            "https://music.bugs.co.kr/chart",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/114.0.0.0 Safari/537.36"},
            timeout=10,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for tr in soup.select("tr[rowtype='track']"):
            rank_el = tr.select_one("div.ranking strong")
            if not rank_el: continue
            rank = int(rank_el.get_text(strip=True))
            sign, abs_ = None, None
            cp = tr.select_one("div.ranking p.change")
            if cp:
                em = cp.select_one("em")
                if em:
                    m = re.search(r"\d+", em.get_text(strip=True))
                    if m: abs_ = int(m.group())
                sign = +1 if "up" in cp.get("class", []) else -1 if "down" in cp.get("class", []) else 0
            title_el  = tr.select_one("p.title a")
            artist_el = tr.select_one("p.artist a")
            if not (title_el and artist_el): continue
            if is_match(title_el.get_text(strip=True), artist_el.get_text(strip=True), title, artist):
                return rank, sign, abs_
        return None, None, None
    except Exception as e:
        print("bugs error:", e); return None, None, None


def fetch_flo_rank(title, artist):
    try:
        r = requests.get(
            "https://www.music-flo.com/api/display/v1/browser/chart/1/track/list?size=100",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.music-flo.com/browse?chartId=1"},
            timeout=20,
        )
        r.raise_for_status()
        for idx, track in enumerate(r.json().get("data", {}).get("trackList", []), start=1):
            if is_match(track.get("name", ""), track.get("representationArtist", {}).get("name", ""), title, artist):
                rb = track.get("rank", {}).get("rankBadge", 0)
                sign = +1 if rb > 0 else -1 if rb < 0 else 0
                return idx, sign, abs(rb)
        return None, None, None
    except Exception as e:
        print("flo error:", e); return None, None, None


def fetch_vibe_top300(title, artist):
    try:
        session = requests.Session()
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/139.0.0.0 Safari/537.36"
        session.get(
            "https://vibe.naver.com/chart/total",
            headers={"User-Agent": ua, "Referer": "https://vibe.naver.com/", "Accept-Language": "ko,en-US;q=0.9"},
            timeout=10,
        )
        headers = {
            "Accept": "application/json",
            "Origin": "https://vibe.naver.com",
            "Referer": "https://vibe.naver.com/chart/total",
            "User-Agent": ua,
        }
        for start, display in [(1, 100), (101, 200)]:
            r = session.get(
                f"https://apis.naver.com/vibeWeb/musicapiweb/vibe/v1/chart/track/total?start={start}&display={display}",
                headers=headers, timeout=15,
            )
            r.raise_for_status()
            tracks = r.json().get("response", {}).get("result", {}).get("chart", {}).get("items", {}).get("tracks", [])
            for idx, track in enumerate(tracks, start=start):
                al = track.get("artists", [])
                if is_match(track.get("trackTitle", ""), al[0].get("artistName", "") if al else "", title, artist):
                    if idx > 200: return None, None, None
                    v = track.get("rank", {}).get("rankVariation", 0)
                    return idx, (+1 if v > 0 else -1 if v < 0 else 0), abs(v)
        return None, None, None
    except Exception as e:
        print("vibe top300 error:", e); return None, None, None


# ═══════════════════════════════════════════════
#  트윗 본문 생성
# ═══════════════════════════════════════════════

def build_text(now_kst, ranks, views, prev_state, site_changes=None) -> str:
    """순위 + 조회수로 트윗 본문 생성.
    등락은 DB에 저장된 이전 시간 값과 직접 비교해서 계산."""
    site_changes = site_changes or {}

    def sd(signed):
        if signed is None: return " (-)"
        if signed > 0: return f" (🔺{signed})"
        if signed < 0: return f" (🔻{abs(signed)})"
        return " (-)"

    lines = [f"Ode to Love  | {now_kst.strftime('%Y-%m-%d %H:00')}", ""]
    prev_ranks = prev_state.get("ranks", {})

    for label, key in SITES:
        curr = as_int(ranks.get(key))
        prev = as_int(prev_ranks.get(key))
        if curr is None:
            lines.append(f"•{label} ❌")
        else:
            # 항상 DB 이전값과 비교해서 등락 계산
            lines.append(f"•{label} {curr}{delta_text(prev, curr)}")

    lines += [
        "",
        f"🎬 {format_views(views)}",
        "",
        "#NCTWISH #OdetoLove",
        "#다정함을전할게_오드투러브",
        "#NCTWISH_DDUDDURUDUDAY",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════
#  메인 실행
# ═══════════════════════════════════════════════

def run_once():
    now = datetime.now(KST)
    print(f"[DEBUG] 실행 시각: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # 1. Supabase에서 설정 로드
    cfg = load_config()

    # 2. 봇 일시정지 체크
    if cfg.get("paused") == "true":
        print("⏸️  봇 일시정지 중 (어드민에서 해제 가능)")
        return

    # 3. 설정값 (Supabase 우선 → .env fallback)
    title  = cfg.get("target_title",  _DEFAULT_TITLE).strip()
    artist = cfg.get("target_artist", _DEFAULT_ARTIST).strip()
    yt_id  = cfg.get("yt_video_id",   YT_VIDEO_ID).strip()
    print(f"🎵 타깃: {title} / {artist}")
    print(f"🎬 YouTube ID: {yt_id}")

    # 4. 이전 순위 로드 (등락 계산용)
    state = load_state()
    ranks, site_changes = {}, {}
    now = datetime.now(KST)

    # 5. 차트 크롤링
    try:
        rank, change = fetch_melon_top100(title, artist)
        ranks["melon_top100"] = rank
        if change is not None: site_changes["melon_top100"] = change
    except: ranks["melon_top100"] = None

    try:
        rank, change = fetch_melon_hot100(title, artist)
        ranks["melon_hot100"] = rank
        if change is not None: site_changes["melon_hot100"] = change
    except: ranks["melon_hot100"] = None

    try:
        rank, sign, abs_ = fetch_guyseom_rank(title, artist, now)
        ranks["guyseom"] = rank
        if sign is not None: site_changes["guyseom"] = sign * (abs_ or 0)
    except Exception as e:
        print("guyseom error:", e); ranks["guyseom"] = None

    try:
        rank, sign, abs_ = fetch_genie_rank(title, artist)
        ranks["genie"] = rank
        if sign is not None: site_changes["genie"] = sign * (abs_ or 0)
    except Exception as e:
        print("genie error:", e); ranks["genie"] = None

    try:
        rank, sign, abs_ = fetch_flo_rank(title, artist)
        ranks["flo"] = rank
        if sign is not None: site_changes["flo"] = sign * (abs_ or 0)
    except Exception as e:
        print("flo error:", e); ranks["flo"] = None

    try:
        rank, sign, abs_ = fetch_bugs_rank(title, artist)
        ranks["bugs"] = rank
        if sign is not None: site_changes["bugs"] = sign * (abs_ or 0)
    except Exception as e:
        print("bugs error:", e); ranks["bugs"] = None

    try:
        rank, sign, abs_ = fetch_vibe_top300(title, artist)
        ranks["vibe_top300"] = rank
        if sign is not None: site_changes["vibe_top300"] = sign * (abs_ or 0)
    except Exception as e:
        print("vibe top300 error:", e); ranks["vibe_top300"] = None

    # 6. 트윗 발행
    views = fetch_youtube_views(yt_id)
    text  = build_text(now, ranks, views, state, site_changes)
    print("----- Tweet body -----\n" + text + "\n----------------------")

    code, err_msg = tweet(text)
    success = 200 <= code < 300

    # 7. Supabase 저장
    save_to_supabase(now, ranks, site_changes, views, text, success, err_msg)


# ═══════════════════════════════════════════════
#  스케줄러
# ═══════════════════════════════════════════════

def main():
    sched = BlockingScheduler(timezone="Asia/Seoul")
    sched.add_job(run_once, CronTrigger(minute=10, timezone="Asia/Seoul"))
    print("🚀 Scheduler started. (KST 매시 10분 자동 트윗)")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass


def lambda_handler(event=None, context=None):
    run_once()
    return {"statusCode": 200, "body": "Tweet posted"}


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv: run_once()
    else: main()