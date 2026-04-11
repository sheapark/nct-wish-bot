# 🌸 NCT WISH Chart Bot

K-pop 음원 차트 순위와 유튜브 조회수를 자동으로 트위터에 올려주는 봇 입니다.

<br>

## 📁 프로젝트 구조

```
nct-wish-bot/
├── bot/                    # Python 봇 (크론)
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── admin/                  # React 어드민 페이지 (Render Static)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx   # 순위 & 조회수 차트
│   │   │   ├── LogsPage.tsx        # 트윗 발행 이력
│   │   │   └── SettingsPage.tsx    # 봇 설정
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── types/
│   ├── package.json
│   └── .env.example
└── README.md
```

<br>

## ✨ 기능

- 🎵 멜론 TOP100 / HOT100 / 실시간, 지니, 플로, 벅스, 바이브 차트 크롤링
- 🎬 유튜브 조회수 자동 조회
- 🐦 트위터 자동 발행 (매시 10분)
- 📊 어드민 페이지에서 순위 추이 확인
- ⚙️ 어드민 페이지에서 타깃 곡 / 아티스트 설정 변경
- 💾 Supabase에 발행 이력 저장

<br>

## 🛠 기술 스택

| 파트   | 스택                                       |
| ------ | ------------------------------------------ |
| 봇     | Python, APScheduler, BeautifulSoup, Tweepy |
| 어드민 | React, TypeScript, Vite, Recharts          |
| DB     | Supabase (PostgreSQL)                      |
| 배포   | Render (Static Site + Cron Job)            |

<br>

## 🚀 배포 구조

| 서비스        | 종류               | 비용   |
| ------------- | ------------------ | ------ |
| 어드민 페이지 | Render Static Site | 무료   |
| 봇 크론잡     | Render Cron Job    | ~$1/월 |
| DB            | Supabase Free      | 무료   |

<br>

## ⚙️ 설정 방법

### 1. Supabase 세팅

1. [supabase.com](https://supabase.com) 에서 프로젝트 생성
2. SQL Editor에서 아래 쿼리 실행:

```sql
create table tweet_logs (
  id             bigserial primary key,
  posted_at      timestamptz not null default now(),
  tweet_text     text        not null,
  success        boolean     not null default true,
  error_msg      text,
  youtube_views  bigint
);

create table rank_history (
  id           bigserial primary key,
  checked_at   timestamptz not null default now(),
  site         text        not null,
  rank         int,
  delta        int
);

create table bot_config (
  key   text primary key,
  value text not null
);

insert into bot_config (key, value) values
  ('target_title',   'COLOR'),
  ('target_artist',  'NCT WISH'),
  ('yt_video_id',    '28dAfmIAlCo'),
  ('paused',         'false'),
  ('guyseom_cookie', '');

alter table tweet_logs   enable row level security;
alter table rank_history enable row level security;
alter table bot_config   enable row level security;

create policy "anon_read_tweet_logs"   on tweet_logs   for select using (true);
create policy "anon_read_rank_history" on rank_history for select using (true);
create policy "anon_read_bot_config"   on bot_config   for select using (true);
create policy "anon_write_bot_config"  on bot_config   for all using (true) with check (true);
```

### 2. 봇 로컬 실행

```bash
cd bot
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env 파일에 키 입력 후

python main.py --once          # 테스트 1회 실행
python main.py                 # 스케줄러 실행
```

### 3. 어드민 로컬 실행

```bash
cd admin
npm install
cp .env.example .env.local
# .env.local에 Supabase 키 입력 후

npm run dev
# → http://localhost:5173
```

<br>

## 🔑 환경변수

### bot/.env

```env
# 트위터
API_KEY=
API_KEY_SECRET=
ACCESS_TOKEN=
ACCESS_TOKEN_SECRET=

# 유튜브
YOUTUBE_API_KEY=
YT_VIDEO_ID=

# 타깃 곡 (.env 기본값 — Supabase bot_config로 덮어씌워짐)
TARGET_TITLE=COLOR
TARGET_ARTIST=NCT WISH

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

### admin/.env.local

```env
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_RENDER_WEBHOOK_URL=
```

<br>

## 📅 크론잡 스케줄

```
10 22-23,0-16 * * *
```

한국시간(KST) 기준 매일:
`07:10 08:10 09:10 10:10 11:10 12:10 13:10 14:10 15:10 16:10 17:10 18:10 19:10 20:10 21:10 22:10 23:10 00:10 01:10`

총 **19회** 실행

<br>

## 📝 트윗 형식

```
🎨COLOR  | 2026-04-11 19:00

•멜론 TOP100 3 (🔺1)
•멜론 HOT100 5 (-)
•멜론 실시간 2 (🔺2)
•지니 7 (🔻1)
•플로 10 (-)
•벅스 4 (🔺1)
•바이브 9 (-)

🎬 1,234,567

#NCTWISH #COLOR #NCTWISH_COLOR
#위시의COLOR로_세상을물들여
#ウィシのCOLORで世界を染めよう
```
