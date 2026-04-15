
## 네이버 광고 데이터 자동화

건강기능식품 스타트업 **크로노웨이**의 네이버 광고 성과 데이터를 자동으로 수집·가공해 사내 PostgreSQL DB에 적재하는 파이프라인입니다.

#### 배경

기존에는 매일 담당자가 네이버 검색광고 사이트에 접속하여 보고서를 수동 다운로드하고, 엑셀로 가공한 뒤, DB에 직접 삽입했습니다. 이 과정에서 일 평균 1~2시간의 반복 업무와 휴먼 에러가 발생했습니다. Naver API를 연동해 이 전 과정을 자동화했습니다.

#### 구조

```
phytoway/
├── [네이버API] 캠페인.py                     # 캠페인 성과 데이터 수집 → DB 적재
├── [네이버API] 쇼검 검색어 상세.py            # 쇼핑 검색 키워드 데이터 수집
├── [네이버API] 쇼검 검색어 전환 상세.py       # 검색어 전환 성과 데이터 수집
├── 데이터 DB 업로드 자동화.py                 # 로컬 파일 → DB 자동 삽입 (배치용)
├── signaturehelper.py                       # 네이버 API 인증 서명 생성 유틸
├── DB upload/                               # DB 삽입 관련 스크립트 모음
└── adreport_upload_web/                     # 웹 업로드 솔루션 초기 버전
```

#### 주요 흐름

```
Naver API 호출 (캠페인 / 검색어 / 전환 데이터)
    ↓
데이터 가공 (사내 DB 컬럼 규격에 맞게 변환)
    ↓
PostgreSQL DB 자동 적재
```

#### 설정 방법

> ⚠️ 실행 전 반드시 환경변수 설정이 필요합니다.

`.env` 파일을 프로젝트 루트에 생성하고 아래 항목을 입력하세요.

```
DB_HOST=your_db_host
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
NAVER_API_KEY=your_api_key
NAVER_SECRET_KEY=your_secret_key
CUSTOMER_ID=your_customer_id
```

#### 성과

- 데일리 데이터 수집 시간: **120분 → 10분 (90% 단축)**
- 휴먼 에러 발생률: **0건** (자동 가공·삽입으로 수작업 제거)
