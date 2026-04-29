### 네이버 광고 데이터 수집 자동화 파이프라인
네이버 검색광고 API를 연동해 광고 성과 데이터를 자동 수집하고 PostgreSQL DB에 적재하는 데이터 파이프라인

<br>

#### 배경 

건강기능식품 스타트업 [크로노웨이]에서 광고 데이터를 관리하며 아래와 같은 문제를 발견했습니다.

- 매일 담당자가 네이버 검색광고 사이트에 직접 접속해 보고서 **수동 다운로드**
- 엑셀로 가공한 뒤 DB에 **수작업으로 삽입** 
- 사람이 직접 처리하는 과정에서 **휴먼 에러** 및 **누락 데이터** 반복 발생

이를 해결하기 위해 네이버 검색광고 API를 연동해 전 과정을 자동화했습니다.

<br>

#### 기술 스택

- **Language**: Python 3
- **API**: 네이버 검색광고 API (HMAC-SHA256 인증)
- **Database**: PostgreSQL (Azure Database for PostgreSQL)
- **Library**: `requests`, `psycopg2`, `pandas`, `python-dotenv`

<br>

#### 프로젝트 구조

```
phytoway/
├── [네이버API] 캠페인.py                  # 캠페인 목록 수집 → DB upsert
├── [네이버API] 쇼검 검색어 상세.py         # 쇼핑 키워드 노출/클릭/비용 수집 → DB 적재
├── [네이버API] 쇼검 검색어 전환 상세.py    # 쇼핑 키워드 전환/매출 수집 → DB 적재
├── 데이터 DB 업로드 자동화.py              # 로컬 엑셀 파일 → DB 배치 업로드
├── signaturehelper.py                    # 네이버 API HMAC-SHA256 인증 서명 생성
├── env.example                           # 환경변수 설정 템플릿
└── .gitignore
```

<br>

#### 동작 흐름

##### Overview

```
Naver API 호출 (캠페인 / 검색어 / 전환 데이터)
    ↓
데이터 가공 (사내 DB 컬럼 규격에 맞게 변환)
    ↓
PostgreSQL DB 자동 적재
```

##### 흐름 A — 네이버 API → DB (자동 수집)

```
1. 네이버 검색광고 API에 보고서 생성 요청 (POST)
        ↓
2. 보고서 상태를 10초 간격으로 확인 (최대 30회 폴링)
        ↓
3. 준비 완료(BUILT) 확인 후 보고서 다운로드 (GET)
        ↓
4. 탭 구분자(\t) 텍스트 파싱 → 타입 변환
        ↓
5. PostgreSQL DB에 INSERT
```

##### 흐름 B — 로컬 엑셀 → DB (배치 업로드)

```
1. 지정 폴더에서 파일명 패턴으로 채널 종류·날짜 자동 인식
        ↓
2. DB의 최신 날짜와 비교 → 새 데이터만 선별 (중복 방지)
        ↓
3. pandas로 파싱 → PostgreSQL DB에 INSERT
```

<br>

#### 주요 구현 포인트

**HMAC-SHA256 API 인증**<br>
네이버 검색광고 API는 타임스탬프 + HTTP 메서드 + URI를 조합한 서명을 요청마다 생성해야 합니다. `signaturehelper.py`에서 이를 처리해 모든 스크립트에서 재사용합니다.

**비동기 보고서 폴링**<br>
대용량 보고서는 즉시 제공되지 않습니다. 보고서 생성 요청 후 `REGIST → RUNNING → BUILT` 상태가 될 때까지 10초 간격으로 최대 30회 상태를 확인하고, 준비 완료 시 다운로드합니다.

**Upsert 처리 (캠페인)**<br>
캠페인 데이터는 `ON CONFLICT ... DO UPDATE` 구문을 사용해 기존 레코드는 최신값으로 갱신하고 신규 레코드는 삽입합니다.

**중복 적재 방지 (엑셀 배치)**<br>
DB에 저장된 최신 날짜(`MAX(yymmdd)`)와 파일 날짜를 비교해 이미 적재된 날짜의 파일은 자동으로 건너뜁니다.

**보안 — 환경변수 분리**<br> 
API 키, DB 접속 정보 등 민감 정보는 코드에 직접 작성하지 않고 `.env` 파일로 분리해 관리합니다. `.env`는 `.gitignore`에 등록되어 있어 GitHub에 업로드되지 않습니다.

<br>

#### 시작하기

##### 1. 저장소 클론

```bash
git clone https://github.com/phytoway/phytoway.git
cd phytoway
```

##### 2. 패키지 설치

```bash
pip install requests psycopg2 python-dotenv pandas openpyxl
```

##### 3. 환경변수 설정

`env.example`을 복사해 `.env` 파일을 생성하고 값을 입력합니다.

```bash
cp env.example .env
```

```
# 네이버 검색광고 API 연결 정보
# https://searchad.naver.com 에서 발급
BASE_URL=https://api.searchad.naver.com
API_KEY=여기에_API_KEY_입력
SECRET_KEY=여기에_SECRET_KEY_입력
CUSTOMER_ID=여기에_CUSTOMER_ID_입력

# PostgreSQL 데이터베이스 연결 정보
DB_HOST=여기에_DB_HOST_입력
DB_USER=여기에_DB_USER_입력
DB_PASSWORD=여기에_DB_PASSWORD_입력
DB_NAME=여기에_DB_NAME_입력
```

##### 4. 실행

```bash
# 캠페인 데이터 수집
python "[네이버API] 캠페인.py"

# 쇼핑 키워드 노출/클릭/비용 데이터 수집
python "[네이버API] 쇼검 검색어 상세.py"

# 쇼핑 키워드 전환/매출 데이터 수집
python "[네이버API] 쇼검 검색어 전환 상세.py"

# 로컬 엑셀 파일 DB 업로드
python "데이터 DB 업로드 자동화.py"
```

<br>

#### 수집 데이터 항목

캠페인 (`naverapi_campaign`)<br>
캠페인 ID, 이름, 상태, 예산, 총 소진 비용, 운영 기간 등 캠페인 설정 전반

쇼핑 키워드 상세 (`naverapi_shopping_keyword_details`)<br>
날짜, 검색어, 노출수, 클릭수, 비용, 광고 순위, PC/모바일 구분 등

쇼핑 키워드 전환 상세 (`naverapi_shoppingkeyword_conversion_detail`)<br>
날짜, 검색어, 전환 방법, 전환 유형, 전환 수, 전환 매출 등

채널별 유입/주문 (`Naver_Custom_Order`, `Naver_Search_Channel`)<br>
유입수, 페이지뷰, 주문수, 주문금액, 기여 매출 등 채널 성과 지표

<br>

#### 참고

- [네이버 검색광고 API 공식 문서](https://naver.github.io/searchad-apidoc/)
- API 키 발급: [네이버 검색광고 시스템](https://searchad.naver.com) → 도구 → API 사용 관리
