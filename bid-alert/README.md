# 입찰공고 알림 (Bid Alert)

공공데이터포털 OPEN API로 한전·나라장터 입찰공고를 조회하고, 사용자 키워드에 매칭되면 Slack·이메일·카카오(나에게 보내기)로 알림을 보내는 Streamlit 앱입니다.

## 기능

- Supabase 이메일/비밀번호 회원가입·로그인 (다중 사용자)
- **회사 이메일(`@yesyoungin.com`)만 가입·로그인 허용**
- 키워드 알림 규칙 (AND/OR, 한전/나라장터)
- 이메일(SMTP), Slack Webhook, 카카오 나에게 보내기
- 중복 발송 방지 (`sent_notices`)
- GitHub Actions 매일 자동 실행

## 운영자 vs 사용자 설정

이 앱은 **다중 사용자** 구조입니다. 공공데이터 API·발송 인프라는 **운영자가 1세트** 등록하고, **알림 받을 채널·키워드**는 **각 사용자**가 웹앱에서 설정합니다.

| 구분 | 설정 항목 | 누가 설정 | 설정 위치 |
|------|-----------|-----------|-----------|
| 운영자 | Supabase URL / Anon Key | 운영자 | `.env`, Streamlit Secrets |
| 운영자 | Supabase Service Role Key | 운영자 | `.env`, GitHub Secrets (Worker용) |
| 운영자 | `DATA_GO_KR_API_KEY` (나라장터) | 운영자 | `.env`, Streamlit Secrets, GitHub Secrets |
| 운영자 | `KEPCO_API_KEY` (한전) | 운영자 | `.env`, Streamlit Secrets, GitHub Secrets |
| 운영자 | SMTP 발송 계정 (`SMTP_*`) | 운영자 | `.env`, Streamlit Secrets, GitHub Secrets |
| 운영자 | `KAKAO_REST_API_KEY` (OAuth 앱) | 운영자 | `.env`, Streamlit Secrets, GitHub Secrets |
| 운영자 | DB 마이그레이션, Auth 활성화 | 운영자 | Supabase 대시보드 |
| 사용자 | 회원가입 / 로그인 | 각 사용자 | Streamlit 웹앱 |
| 사용자 | 관심 키워드, AND/OR, 데이터 소스 | 각 사용자 | **알림 규칙** 페이지 → Supabase `alert_rules` |
| 사용자 | 알림 수신 이메일 주소 | 각 사용자 | **채널 연결** 페이지 → Supabase `notification_channels` |
| 사용자 | Slack Incoming Webhook URL | 각 사용자 | **채널 연결** 페이지 → Supabase `notification_channels` |
| 사용자 | 카카오톡 연결 (나에게 보내기) | 각 사용자 | **채널 연결** 페이지 OAuth → Supabase `oauth_tokens` |

**동작 흐름**

1. 운영자 Secrets로 공공데이터 API에서 입찰공고를 조회합니다.
2. 사용자별 키워드 규칙으로 매칭합니다.
3. 매칭된 공고를 **각 사용자가 연결한 채널**(이메일 주소 / Slack / 카카오)로 발송합니다.

**참고**

- 공공데이터 API 키는 **사용자마다 따로 넣지 않습니다.** 운영자 키 1개를 앱 전체가 공유합니다.
- 이메일은 운영자 SMTP로 **발송**하고, **수신 주소**만 사용자마다 다릅니다.
- 카카오는 운영자 OAuth 앱 1개 + **사용자별 카카오 계정 연결** 조합입니다.
- 매일 자동 알림은 **GitHub Actions Worker**가 실행하므로, Streamlit Secrets만 넣고 GitHub Secrets를 빠뜨리면 UI는 동작해도 **스케줄 알림은 실행되지 않습니다.**

## 빠른 시작 (로컬)

```bash
cd bid-alert
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env     # 값 입력
streamlit run app.py
```

## Supabase 설정

1. [Supabase](https://supabase.com)에서 프로젝트 생성
2. SQL Editor에서 `supabase/migrations/001_initial.sql` 실행
3. Authentication → Providers → Email 활성화
4. `.env`에 `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` 입력

## 회사 이메일 제한 (@yesyoungin.com)

회사 직원만 사용하도록 **2단계 방식**을 적용했습니다.

1. **앱 코드**: `@yesyoungin.com` 도메인만 회원가입·로그인·알림 수신 이메일 등록 허용 (`ALLOWED_EMAIL_DOMAIN`)
2. **Supabase**: **Confirm email** ON → 가입 후 메일함 인증 필요

### Supabase 대시보드 설정

1. **Authentication → Providers → Email** → **Confirm email** 활성화
2. **Authentication → URL Configuration**
   - **Site URL**: 배포 Streamlit URL (로컬: `http://localhost:8501`)
   - **Redirect URLs**에 동일 URL 추가
3. (권장) **Authentication → SMTP Settings** — 회사 메일(`@yesyoungin.com`)로 확인 메일이 안정적으로 가도록 SMTP 설정

### 환경 변수

```env
ALLOWED_EMAIL_DOMAIN=yesyoungin.com
```

Streamlit Cloud Secrets에도 동일하게 추가합니다.

### 동작

| 단계 | 내용 |
|------|------|
| 회원가입 | `kch@yesyoungin.com` 형식만 허용 |
| 이메일 확인 | Supabase 확인 메일 → 링크 클릭 후 로그인 가능 |
| 로그인 | `@yesyoungin.com` 아니면 거부 |
| 알림 수신 이메일 | 채널 연결 페이지에서도 동일 도메인만 저장 |

### 보안 참고

- 앱 UI 경로로는 외부 도메인 가입·로그인이 차단됩니다.
- Supabase API 직접 호출 우회를 막으려면 추후 **Auth Hook**(`before user created`)에서 도메인 검사를 추가할 수 있습니다.

## API 키 발급

| 키 | 발급처 |
|----|--------|
| `DATA_GO_KR_API_KEY` | [data.go.kr](https://www.data.go.kr) — 나라장터 입찰공고정보서비스 활용신청 |
| `KEPCO_API_KEY` | [전력데이터개방포털](https://bigdata.kepco.co.kr) — 전자입찰계약정보 API (40자리) |

한전 API URL은 포털 문서 기준으로 `KEPCO_API_URL`에 설정합니다. 기본값:

`https://bigdata.kepco.co.kr/openapi/v1/contract/electBidContInfo.do`

## 카카오 Developers

1. 앱 생성 → REST API 키 복사 → `KAKAO_REST_API_KEY`
2. Redirect URI: Streamlit 앱 URL (예: `https://your-app.streamlit.app`)
3. 동의항목: 카카오톡 메시지 전송 (`talk_message`)
4. **참고**: 나에게 보내기는 푸시 알림이 없습니다.

## Streamlit Community Cloud 배포

1. GitHub에 저장소 푸시
2. [share.streamlit.io](https://share.streamlit.io) → New app
   - **Main file path**: `bid-alert/app.py`
   - **Requirements**: `bid-alert/requirements.txt`
3. Secrets (`.streamlit/secrets.toml` 예시는 `.streamlit/secrets.toml.example` 참고)

## GitHub Actions (매일 알림)

Repository → Settings → Secrets:

- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `DATA_GO_KR_API_KEY`, `KEPCO_API_KEY`, `KEPCO_API_URL`
- `SMTP_*`, `KAKAO_REST_API_KEY`

Actions 탭에서 **Daily Bid Alert** 워크플로를 `workflow_dispatch`로 수동 실행해 테스트할 수 있습니다.

## 프로젝트 구조

```
bid-alert/
├── app.py                 # 대시보드 + 로그인
├── pages/                 # 규칙, 채널, 이력
├── src/                   # API, 매칭, 알림, DB
├── jobs/daily_alert.py    # Cron worker
├── supabase/migrations/
└── docs/PLAN.md
```

## 테스트

```bash
pip install pytest
pytest tests/ -q
```

## 라이선스

MIT (필요 시 변경)
