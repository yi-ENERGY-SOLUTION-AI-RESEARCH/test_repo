# 입찰공고 알림 (Bid Alert)

공공데이터포털 OPEN API로 한전·나라장터 입찰공고를 조회하고, 사용자 키워드에 매칭되면 Slack·이메일·카카오(나에게 보내기)로 알림을 보내는 Streamlit 앱입니다.

## 기능

- Supabase 이메일/비밀번호 회원가입·로그인 (다중 사용자)
- 키워드 알림 규칙 (AND/OR, 한전/나라장터)
- 이메일(SMTP), Slack Webhook, 카카오 나에게 보내기
- 중복 발송 방지 (`sent_notices`)
- GitHub Actions 매일 자동 실행

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
