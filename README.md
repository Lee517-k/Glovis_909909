# Multimodal Logistics Agent

복합운송 경로 탐색과 운영 의사결정을 지원하는 멀티모달 물류 에이전트 프로젝트입니다.

현재 저장소는 팀 개발을 시작하기 위한 초기 골격 단계입니다. API, 웹 클라이언트, 에이전트 모듈의 경계를 먼저 정의하고 세부 기능과 데이터 연동은 이슈 단위로 구현합니다.

## 구성

```text
.
├─ backend/      # FastAPI API 및 도메인 로직
├─ frontend/     # React 기반 웹 클라이언트
├─ llm-agent/    # LLM 에이전트 실험 및 프롬프트
├─ Data/         # 로컬 개발 데이터(원본 데이터는 Git 제외)
└─ docs/         # 설계 및 팀 문서
```

## 시작하기

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

서버 실행 후 `http://localhost:8000/health`에서 상태를 확인할 수 있습니다.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

기본 개발 주소는 `http://localhost:5173`입니다.

## 개발 원칙

- 기능 브랜치에서 작업하고 작은 단위로 커밋합니다.
- API 계약이 바뀌면 관련 문서를 함께 수정합니다.
- 비밀키와 운영 데이터는 커밋하지 않습니다.
- 기능 구현 시 테스트 또는 검증 방법을 PR에 기록합니다.

## 초기 개발 범위

- [ ] 운송 요청 입력 모델 정의
- [ ] 해상·항공·철도·도로 에이전트 인터페이스 정의
- [ ] 후보 경로 생성 및 평가 기준 설계
- [ ] 시나리오 조회 API 구현
- [ ] 기본 대시보드 및 경로 비교 화면 구현
- [ ] 개발용 샘플 데이터 작성

세부 구조와 결정 사항은 [`docs/architecture.md`](docs/architecture.md)에서 관리합니다.

