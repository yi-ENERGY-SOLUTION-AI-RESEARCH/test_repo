# 공공데이터 입찰공고 알림 Streamlit 앱 — 구현 계획

본 문서는 프로젝트 구현 계획서입니다. 코드는 `bid-alert/` 디렉터리에 구현되어 있습니다.

## 1. 목표

사용자가 Streamlit 앱에서 **관심 키워드**(예: `전력계통 해석`, `PSS/E`, `전력계통영향평가`)와 **알림 채널**(Slack, 이메일, 카카오)을 설정하면, 매일 자동으로 공공데이터 OPEN API에서 입찰공고를 조회·필터링하고 **신규/미발송 공고만** 알림으로 전달하는 서비스.

**확정된 요구사항**

- 다중 사용자: 각자 로그인 후 개별 키워드·채널 설정
- 카카오: OAuth + **나에게 보내기** API (푸시 없음, 나와의 채팅에 메모)
- 데이터 소스: 공공데이터포털 OPEN API (한전 입찰 중심, 나라장터 용역 확장 가능)

## 2. 시스템 아키텍처

- **UI**: Streamlit (`app.py`, `pages/`)
- **DB/Auth**: Supabase (PostgreSQL + Auth + RLS)
- **Scheduler**: GitHub Actions (`.github/workflows/daily-alert.yml`)
- **Worker**: `jobs/daily_alert.py`

## 3. 활용 OPEN API

| 소스 | API | 용도 |
|------|-----|------|
| 한전 | [전자입찰계약정보](https://www.data.go.kr/data/15148223/openapi.do) | 한전 입찰공고 |
| 나라장터 | [입찰공고정보서비스](https://www.data.go.kr/data/15129394/openapi.do) | 용역 입찰 (한전 키워드 필터) |

## 4. 알림 채널

- **이메일**: SMTP (Gmail App Password 등)
- **Slack**: Incoming Webhook URL
- **카카오**: OAuth + 나에게 보내기 (푸시 없음)

## 5. Streamlit UI

| 페이지 | 파일 |
|--------|------|
| 대시보드 / 로그인 | `app.py` |
| 알림 규칙 | `pages/1_알림규칙.py` |
| 채널 연결 | `pages/2_채널연결.py` |
| 알림 이력 | `pages/3_알림이력.py` |

## 6. DB 스키마

마이그레이션: `supabase/migrations/001_initial.sql`

- `alert_rules` — 키워드·소스·알림 시각
- `notification_channels` — email / slack / kakao
- `sent_notices` — 중복 발송 방지
- `oauth_tokens` — 카카오 토큰

## 7. 일일 자동 실행

GitHub Actions cron: UTC 23:00 (= KST 08:00), `workflow_dispatch` 수동 실행 가능.

## 8. 사전 준비

1. Supabase 프로젝트 + SQL 마이그레이션 실행
2. data.go.kr API 키 (나라장터)
3. bigdata.kepco.co.kr API 키 (한전, 40자리)
4. SMTP, Kakao Developers, Slack Webhook (사용자별)
5. GitHub Secrets + Streamlit Cloud secrets

## 9. 리스크

1. 카카오 나에게 보내기 — 푸시 알림 없음
2. API 트래픽 제한 (개발계정 1,000건/일)
3. 키워드는 클라이언트 측 필터
4. 한전 API URL은 `KEPCO_API_URL`로 환경별 설정

## 10. 검증 시나리오

1. 키워드 `PSS/E` → 매칭 미리보기
2. 동일 공고 재발송 차단 (dedup)
3. Slack / 이메일 / 카카오 테스트 발송
4. GitHub Actions 수동 trigger
