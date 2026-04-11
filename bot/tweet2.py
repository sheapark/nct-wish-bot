# -*- coding: utf-8 -*-
import os, json, pathlib, re
from datetime import datetime
import pytz, requests
from requests_oauthlib import OAuth1
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup
from supabase import create_client
import tweepy


# ===================== 기본 설정 =====================
load_dotenv()

API_KEY = os.environ["API_KEY"]
API_KEY_SECRET = os.environ["API_KEY_SECRET"]
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
ACCESS_TOKEN_SECRET = os.environ["ACCESS_TOKEN_SECRET"]

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]  # service_role 키 사용
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

GUYSEOM_COOKIE = os.environ.get("GUYSEOM_COOKIE")
if not GUYSEOM_COOKIE:
    raise SystemExit("❌ .env에 GUYSEOM_COOKIE 필요")


# YouTube API
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
YT_VIDEO_ID = os.environ["YT_VIDEO_ID"]

# Target Song Info (기본값 설정 + 공백 제거)
TARGET_TITLE = os.environ.get("TARGET_TITLE", "Surf").strip()
TARGET_ARTIST = os.environ.get("TARGET_ARTIST", "NCT WISH").strip()

for k, v in {
    "API_KEY": API_KEY, "API_KEY_SECRET": API_KEY_SECRET,
    "ACCESS_TOKEN": ACCESS_TOKEN, "ACCESS_TOKEN_SECRET": ACCESS_TOKEN_SECRET,
}.items():
    if not v:
        raise SystemExit(f"❌ .env에 {k}가 필요합니다.")

KST = pytz.timezone("Asia/Seoul")
STATE = pathlib.Path("state.json")  # 이전 순위 저장해서 🔺/🔻 계산
SITES = [
    ("멜론 TOP100", "melon_top100"),
    ("멜론 HOT100", "melon_hot100"),
    ("멜론 실시간", "guyseom"),
    ("지니", "genie"),
    ("플로", "flo"),
    ("벅스", "bugs"),
    ("바이브", "vibe_top300"),
   # ("VIBE 급상승", "vibe"),  
]

# ===================== 유틸 =====================
def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(feat\.?.*?\)|\(prod\.?.*?\)", "", s)
    s = re.sub(r"feat\.?|featuring|prod\.?", "", s)
    s = re.sub(r"[\[\]\(\)\-–—·~_:/.,!?']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_match(title: str, artist: str, target_title: str, target_artist: str) -> bool:
    t1, a1 = normalize(title), normalize(artist)
    t2, a2 = normalize(target_title), normalize(target_artist)
    if t2 in t1 or t1 in t2:
        return len(set(a1.split()) & set(a2.split())) > 0
    return False

def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_state(d):
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def delta_text(prev, curr):
    if prev is None or curr is None:
        return ""
    if curr < prev:
        return f" (🔺{prev - curr})"
    if curr > prev:
        return f" (🔻{curr - prev})"
    return " (-)"

def format_views(n: int | None) -> str:
    return "❌" if n is None else f"{n:,}"

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_KEY_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)


def tweet(text: str) -> int:
    # url = "https://api.twitter.com/2/tweets"
    # auth = OAuth1(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    
    # payload = {
    #     "text": text,
    #     "reply_settings": "mentionedUsers"   # 내가 멘션한 계정만 답글 제한 설정함.
    # }
    
    
    # r = requests.post(url, json=payload, auth=auth, timeout=20)
    # print("Tweet:", r.status_code, r.text)
    # print("Headers:", {
    #     "x-rate-limit-limit": r.headers.get("x-rate-limit-limit"),
    #     "x-rate-limit-remaining": r.headers.get("x-rate-limit-remaining"),
    #     "x-rate-limit-reset": r.headers.get("x-rate-limit-reset"),
    #     "retry-after": r.headers.get("retry-after"),
    # })
    # return r.status_code
    
    try:
        response = client.create_tweet(
            text=text,
            reply_settings="mentionedUsers"
        )
        print("✅ Tweet 성공:", response.data)
        return 200

    except tweepy.TweepyException as e:
        print("❌ Tweet 실패!")
        # Tweepy 에러 객체는 여러 타입일 수 있음
        if hasattr(e, "response") and e.response is not None:
            try:
                err_json = e.response.json()
                print("에러 응답(JSON):", json.dumps(err_json, indent=2, ensure_ascii=False))
            except Exception:
                print("에러 응답(raw):", e.response.text)
            print("HTTP Status:", e.response.status_code)
        else:
            print("Exception:", str(e))
        return -1

def as_int(x):
    if isinstance(x, (list, tuple)):
        try:
            return int(x[0])
        except Exception:
            return None
    try:
        return int(x) if x is not None else None
    except Exception:
        return None

# ===================== YouTube 조회수 =====================
def fetch_youtube_views() -> int | None:
    if not (YOUTUBE_API_KEY and YT_VIDEO_ID):
        return None
    try:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {"part": "statistics", "id": YT_VIDEO_ID, "key": YOUTUBE_API_KEY}
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return None
        return int(items[0]["statistics"]["viewCount"])
    except Exception as e:
        print("YouTube fetch error:", e)
        return None

# ===================== 멜론 차트 =====================
def fetch_melon_chart(url: str, title: str, artist: str):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        rows = soup.select("tr.lst50, tr.lst100")
        for row in rows:
            rank_el = row.select_one(".rank")
            title_el = row.select_one(".rank01 a")
            artist_el = row.select_one(".rank02 a")
            if not (rank_el and title_el and artist_el):
                continue

            # 현재 순위
            digits = "".join(c for c in rank_el.get_text(strip=True) if c.isdigit())
            if not digits:
                continue
            rank = int(digits)

            # 변동치
            change_val = None
            rank_wrap = row.select_one(".rank_wrap")
            if rank_wrap:
                if rank_wrap.select_one(".rank_up"):
                    num = "".join(c for c in rank_wrap.select_one(".up").get_text(strip=True) if c.isdigit())
                    change_val = +int(num) if num else 0
                elif rank_wrap.select_one(".rank_down"):
                    num = "".join(c for c in rank_wrap.select_one(".down").get_text(strip=True) if c.isdigit())
                    change_val = -int(num) if num else 0
                elif rank_wrap.select_one(".rank_static"):
                    change_val = 0
                elif rank_wrap.select_one(".rank_new"):
                    change_val = 0

            # 매칭
            t = title_el.get_text(" ", strip=True)
            a = artist_el.get_text(" ", strip=True)
            if is_match(t, a, title, artist):
                return rank, change_val
        return None, None
    except Exception as e:
        print("melon fetch error:", e)
        return None, None

def fetch_melon_top100(title: str, artist: str):
    return fetch_melon_chart("https://www.melon.com/chart/index.htm", title, artist)

def fetch_melon_hot100(title: str, artist: str):
    return fetch_melon_chart("https://www.melon.com/chart/hot100/index.htm", title, artist)


# ===================== 멜론 실시간 차트 (가이섬을 사용합니다.) =====================
def fetch_guyseom_rank(title: str, artist: str, when: datetime):
    """
    가이섬 멜론 실시간 차트에서 특정 곡 순위와 변동치 가져오기
    """
    try:
        date_str = when.strftime("%Y%m%d")   # 예: 20250819
        hour_str = when.strftime("%H")       # 예: 23
        url = f"https://xn--o39an51b2re.com/chart/melon/realtime/{date_str}/{hour_str}"

        # GUYSEOM_COOKIE 값이 토큰만 들어있을 때를 기준으로 작성
        headers = {"User-Agent": "Mozilla/5.0"}
        cookies = {"__Secure-next-auth.session-token": GUYSEOM_COOKIE}

        r = requests.get(url, headers=headers, cookies=cookies, timeout=15)

        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        rows = soup.select("tr")
        for row in rows:
            rank_el = row.select_one("td.ranking span[class^=no]")
            title_el = row.select_one("td.subject p[title]")
            artist_el = row.select_one("td.subject p.singer span")
            like_el = row.select_one("td.count p.like")
            change_el = row.select_one("td.ranking p.change span")

            if not (rank_el and title_el and artist_el):
                continue

            rank = int("".join(c for c in rank_el.get_text(strip=True) if c.isdigit()))
            song = title_el.get_text(strip=True)
            art = artist_el.get_text(strip=True)

            if not is_match(song, art, title, artist):
                continue

            # 등락
            change_sign, change_abs = (0, 0)
            if change_el:
                num = int("".join(c for c in change_el.get_text(strip=True) if c.isdigit()) or "0")
                if "up" in change_el.get("class", []):
                    change_sign, change_abs = (+1, num)
                elif "down" in change_el.get("class", []):
                    change_sign, change_abs = (-1, num)

            # 좋아요 수
            likes = None
            if like_el:
                likes = int("".join(c for c in like_el.get_text(strip=True) if c.isdigit()))

            return rank, change_sign, change_abs, likes

        return None, None, None, None
    except Exception as e:
        print("guyseom fetch error:", e)
        return None, None, None, None


# ===================== 지니 차트 =====================
def fetch_genie_rank(title: str, artist: str):
    """
    지니 Top200에서 특정 곡 순위와 변동치 검색
    - 반환: (rank:int|None, change_sign:int|None, change_abs:int|None)
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    base_url = "https://www.genie.co.kr/chart/top200?pg={}"

    try:
        for page in range(1, 5):  # 1~200위
            url = base_url.format(page)
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")

            rows = soup.select("tr.list")
            for row in rows:
                num_td = row.select_one("td.number")
                if not num_td:
                    continue

                # ✅ 순위는 td.number 안의 첫 번째 텍스트만
                raw_rank = num_td.find(text=True, recursive=False)
                rank = int(raw_rank.strip()) if raw_rank and raw_rank.strip().isdigit() else None

                # ✅ 등락
                change_sign, change_abs = (0, 0)
                if row.select_one("span.rank-up"):
                    m = re.search(r"\d+", row.select_one("span.rank-up").get_text(strip=True))
                    if m:
                        change_sign, change_abs = +1, int(m.group())
                elif row.select_one("span.rank-down"):
                    m = re.search(r"\d+", row.select_one("span.rank-down").get_text(strip=True))
                    if m:
                        change_sign, change_abs = -1, int(m.group())
                elif row.select_one("span.rank-none"):
                    change_sign, change_abs = 0, 0

                # 제목/아티스트
                title_el = row.select_one("a.title.ellipsis")
                artist_el = row.select_one("a.artist.ellipsis")
                if not (title_el and artist_el):
                    continue

                t_txt = title_el.get_text(" ", strip=True)
                a_txt = artist_el.get_text(" ", strip=True)

                if is_match(t_txt, a_txt, title, artist):
                    return rank, change_sign, change_abs

        return None, None, None
    except Exception as e:
        print("genie error:", e)
        return None, None, None



# ===================== 벅스 차트 =====================
def fetch_bugs_rank(title: str, artist: str):
    """
    벅스 차트에서 특정 곡 순위와 변동치 검색
    반환: (rank:int|None, change_sign:int|None, change_abs:int|None)
    """
    url = "https://music.bugs.co.kr/chart"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print("[bugs] request error:", e)
        return (None, None, None)

    soup = BeautifulSoup(r.text, "lxml")
    rows = soup.select("tr[rowtype='track']")
    preview = []

    for tr in rows:
        try:
            # 순위
            rank_el = tr.select_one("div.ranking strong")
            if not rank_el:
                continue
            rank = int(rank_el.get_text(strip=True))

            # 변동치
            change_sign, change_abs = (None, None)
            change_p = tr.select_one("div.ranking p.change")
            if change_p:
                em = change_p.select_one("em")
                if em:
                    m = re.search(r"\d+", em.get_text(strip=True))
                    if m:
                        change_abs = int(m.group())
                if "up" in change_p.get("class", []):
                    change_sign = +1
                elif "down" in change_p.get("class", []):
                    change_sign = -1
                else:
                    change_sign = 0

            # 곡/아티스트
            title_el = tr.select_one("p.title a")
            artist_el = tr.select_one("p.artist a")
            if not (title_el and artist_el):
                continue

            song = title_el.get_text(strip=True)
            art = artist_el.get_text(strip=True)

            # 매칭
            if is_match(song, art, title, artist):
                print(f"[bugs] MATCH -> rank={rank}, change_sign={change_sign}, change_abs={change_abs}")
                return rank, change_sign, change_abs

            if len(preview) < 3:
                preview.append(f"{rank} | {song} | {art}")

        except Exception:
            continue

    if preview:
        print("[bugs 미스매치 예시]\n  " + "\n  ".join(preview))
    else:
        print("[bugs] target not found in chart")

    return None, None, None

# ===================== FLO Top100 (API) =====================
def fetch_flo_rank(title: str, artist: str):
    """
    FLO Top100에서 특정 곡 순위와 변동치 검색
    - API: https://www.music-flo.com/api/display/v1/browser/chart/1/track/list?size=100
    - 반환: (rank:int|None, change_sign:int|None, change_abs:int|None)
    """
    url = "https://www.music-flo.com/api/display/v1/browser/chart/1/track/list?size=100"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.music-flo.com/browse?chartId=1",
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()

        track_list = data.get("data", {}).get("trackList", [])
        for idx, track in enumerate(track_list, start=1):
            song_name = track.get("name", "")
            artist_name = track.get("representationArtist", {}).get("name", "")
            if is_match(song_name, artist_name, title, artist):
                # rankBadge: 양수 = 상승, 음수 = 하락, 0 = 변동 없음
                rank_badge = track.get("rank", {}).get("rankBadge", 0)
                change_sign, change_abs = (None, None)
                if rank_badge > 0:
                    change_sign = +1
                    change_abs = rank_badge
                elif rank_badge < 0:
                    change_sign = -1
                    change_abs = abs(rank_badge)
                return idx, change_sign, change_abs

        print("[flo] target not found in chart")
        return (None, None, None)
    except Exception as e:
        print("flo error:", e)
        return (None, None, None)


# ===================== VIBE TOP300 차트 (API) =====================
def fetch_vibe_top300(title: str, artist: str):
    """
    VIBE Top300 차트 (일간/실시간)에서 특정 곡 순위와 변동치 검색
    - 쿠키 만료 방지를 위해 chart/total 페이지 접속 후 API 호출
    - 1~100, 101~300 두 번 요청
    반환: (rank:int|None, change_sign:int|None, change_abs:int|None)
    """
    try:
        session = requests.Session()

        # 1) 진입: 쿠키 확보
        session.get(
            "https://vibe.naver.com/chart/total",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/139.0.0.0 Safari/537.36",
                "Referer": "https://vibe.naver.com/",
                "Accept-Language": "ko,en-US;q=0.9,en;q=0.8",
            },
            timeout=10,
        )

        # 2) Top300 API 호출 (2번)
        base_url = "https://apis.naver.com/vibeWeb/musicapiweb/vibe/v1/chart/track/total"
        headers = {
            "Accept": "application/json",
            "Origin": "https://vibe.naver.com",
            "Referer": "https://vibe.naver.com/chart/total",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/139.0.0.0 Safari/537.36",
            "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ko-KR;q=0.7",
        }

        for start, display in [(1, 100), (101, 200)]:  # 두 번만
            url = f"{base_url}?start={start}&display={display}"
            r = session.get(url, headers=headers, timeout=15)
            r.raise_for_status()

            if "{" not in r.text[:10]:
                print("[vibe top300 debug] not JSON:", r.text[:200])
                continue

            data = r.json()
            tracks = (
                data.get("response", {})
                .get("result", {})
                .get("chart", {})
                .get("items", {})
                .get("tracks", [])
            )

            for idx, track in enumerate(tracks, start=start):
                song_name = track.get("trackTitle", "")
                artist_list = track.get("artists", [])
                artist_name = artist_list[0].get("artistName", "") if artist_list else ""

                if is_match(song_name, artist_name, title, artist):
                    variation = track.get("rank", {}).get("rankVariation", 0)
                    change_sign, change_abs = (0, 0)
                    if variation > 0:
                        change_sign, change_abs = +1, variation
                    elif variation < 0:
                        change_sign, change_abs = -1, abs(variation)
                    # 200위 까지만 표시    
                    if idx > 200:
                        return None, None, None
                    return idx, change_sign, change_abs

        print("[vibe top300] target not found")
        return None, None, None

    except Exception as e:
        print("vibe top300 error:", e)
        return None, None, None


# ===================== VIBE 급상승 차트 (API) =====================
def fetch_vibe_rank(title: str, artist: str):
    """
    VIBE 국내 차트 Top100에서 특정 곡 순위와 변동치 검색
    - 쿠키 만료 방지를 위해 매 호출 시 chart/domestic 페이지 접속 후 API 호출
    """
    session = requests.Session()

    try:
        # 1) 메인 페이지 접속 → 세션 쿠키 발급
        session.get("https://vibe.naver.com/chart/domestic", headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/139.0.0.0 Safari/537.36",
            "Referer": "https://vibe.naver.com/",
            "Accept-Language": "ko,en-US;q=0.9,en;q=0.8"
        }, timeout=10)

        # 2) API 호출
        api_url = "https://apis.naver.com/vibeWeb/musicapiweb/vibe/v1/chart/track/domestic?start=1&display=100"
        headers = {
            "Accept": "application/json",
            "Origin": "https://vibe.naver.com",
            "Referer": "https://vibe.naver.com/chart/domestic",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/139.0.0.0 Safari/537.36",
            "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ko-KR;q=0.7"
        }
        r = session.get(api_url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        tracks = data.get("response", {}).get("result", {}).get("chart", {}).get("items", {}).get("tracks", [])
        for idx, track in enumerate(tracks, start=1):
            song_name = track.get("trackTitle", "")
            artist_list = track.get("artists", [])
            artist_name = artist_list[0].get("artistName", "") if artist_list else ""

            if is_match(song_name, artist_name, title, artist):
                variation = track.get("rank", {}).get("rankVariation", 0)
                change_sign, change_abs = (None, None)
                if variation > 0:
                    change_sign = +1
                    change_abs = variation
                elif variation < 0:
                    change_sign = -1
                    change_abs = abs(variation)
                return idx, change_sign, change_abs

        print("[vibe] target not found in chart")
        return (None, None, None)

    except Exception as e:
        print("vibe error:", e)
        return (None, None, None)

# ===================== 본문 생성 =====================
def build_text(now_kst: datetime,
               ranks: dict[str, int | None],
               views: int | None,
               prev_state: dict,
               site_changes: dict[str, int] | None = None) -> str:
    site_changes = site_changes or {}

    def site_delta_to_text(signed: int | None) -> str:
        if signed is None: return ""
        if signed > 0: return f" (🔺{signed})"
        if signed < 0: return f" (🔻{abs(signed)})"
        return " (-)"

    header = f"🎨COLOR  | {now_kst.strftime('%Y-%m-%d %H:00')}"
    lines = [header, ""]
    prev_ranks = prev_state.get("ranks", {})

    for label, key in SITES:
        curr = as_int(ranks.get(key))
        prev = as_int(prev_ranks.get(key))
        if curr is None:
            lines.append(f"•{label} ❌")
            continue
        if key in site_changes:
            lines.append(f"•{label} {curr}{site_delta_to_text(site_changes.get(key))}")
        else:
            lines.append(f"•{label} {curr}{delta_text(prev, curr)}")

    lines.append("")
    lines.append(f"🎬 {format_views(views)}")
    lines.append("")  
    lines.append("#NCTWISH #COLOR #NCTWISH_COLOR")
    lines.append("#위시의COLOR로_세상을물들여")
    lines.append("#ウィシのCOLORで世界を染めよう")
    return "\n".join(lines)

# ===================== 실행(한 번) =====================
def run_once():
    now = datetime.now(KST)
    print(f"[DEBUG] 실행 시각: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    state = load_state()

    ranks, site_changes = {}, {}
    title, artist = TARGET_TITLE, TARGET_ARTIST

    # 멜론 
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
    
    
    now = datetime.now(KST)

    # 가이섬
    try:
        rank, change_sign, change_abs, likes = fetch_guyseom_rank(title, artist, now)
        ranks["guyseom"] = rank
        if change_sign is not None and change_abs is not None:
            site_changes["guyseom"] = change_sign * change_abs
    except Exception as e:
        print("guyseom error:", e)
        ranks["guyseom"] = None

    # 지니
    try:
        genie_rank, genie_change_sign, genie_change_abs = fetch_genie_rank(title, artist)
        ranks["genie"] = genie_rank
        if genie_change_sign is not None and genie_change_abs is not None:
            site_changes["genie"] = genie_change_sign * genie_change_abs
    except Exception as e:
        print("genie error:", e)
        ranks["genie"] = None
    # FLO
    try:
        flo_rank, flo_change_sign, flo_change_abs = fetch_flo_rank(title, artist)
        ranks["flo"] = flo_rank
        if flo_change_sign is not None and flo_change_abs is not None:
            site_changes["flo"] = flo_change_sign * flo_change_abs
    except Exception as e:
        print("flo error:", e)
        ranks["flo"] = None

    # 벅스
    try:
        bugs_rank, bugs_change_sign, bugs_change_abs = fetch_bugs_rank(title, artist)
        ranks["bugs"] = bugs_rank
        if bugs_change_sign is not None and bugs_change_abs is not None:
            site_changes["bugs"] = bugs_change_sign * bugs_change_abs
    except Exception as e:
        print("bugs error:", e)
        ranks["bugs"] = None


        
        
    # VIBE TOP300
    try:
        vibe_rank, vibe_change_sign, vibe_change_abs = fetch_vibe_top300(title, artist)
        ranks["vibe_top300"] = vibe_rank
        if vibe_change_sign is not None and vibe_change_abs is not None:
            site_changes["vibe_top300"] = vibe_change_sign * vibe_change_abs
    except Exception as e:
        print("vibe top300 error:", e)
        ranks["vibe_top300"] = None


    # VIBE 급상승
    # try:
    #     vibe_rank, vibe_change_sign, vibe_change_abs = fetch_vibe_rank(title, artist)
    #     ranks["vibe"] = vibe_rank
    #     if vibe_change_sign is not None and vibe_change_abs is not None:
    #         site_changes["vibe"] = vibe_change_sign * vibe_change_abs
    # except Exception as e:
    #     print("vibe error:", e)
    #     ranks["vibe"] = None

    views = fetch_youtube_views()
    text = build_text(now, ranks, views, state, site_changes)
    print("----- Tweet body -----\n" + text + "\n----------------------")

    code = tweet(text)
    if 200 <= code < 300:
        state.setdefault("ranks", {})
        for _, key in SITES: state["ranks"][key] = as_int(ranks.get(key))
        state["youtube_views"] = views
        state["last_posted_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        save_state(state)

# ===================== 스케줄러 =====================
def main():
    sched = BlockingScheduler(timezone="Asia/Seoul")
    sched.add_job(run_once, CronTrigger(minute=0, timezone="Asia/Seoul"))
    print("Scheduler started. (KST 매시 정각 자동 트윗)")
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
