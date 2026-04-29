"""
네이버 검색광고 API - 쇼핑 검색어 전환 상세 보고서 수집 스크립트

[동작 순서]
1. 네이버 검색광고 API로 쇼핑 검색어 전환 상세 보고서 생성 요청
2. 보고서가 준비될 때까지 최대 30회 상태 확인 (10초 간격)
3. 보고서 다운로드
4. 데이터를 파싱하여 PostgreSQL DB에 삽입

[사전 준비]
- .env 파일에 API 키 및 DB 연결 정보 입력 필요 (.env.example 참고)
- pip install requests psycopg2 python-dotenv
- signaturehelper.py 파일 필요 (네이버 검색광고 API 공식 제공)
"""

import time
import requests
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import signaturehelper

# .env 파일에서 환경변수 로드
load_dotenv()

# 네이버 검색광고 API 연결 정보 (.env에서 불러옴)
BASE_URL = os.getenv('BASE_URL')
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
CUSTOMER_ID = os.getenv('CUSTOMER_ID')

# PostgreSQL 데이터베이스 연결 정보 (.env에서 불러옴)
db_info = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
}


def get_header(method, uri, api_key, secret_key, customer_id):
    """네이버 검색광고 API 요청에 필요한 인증 헤더를 생성하여 반환"""
    timestamp = str(round(time.time() * 1000))
    signature = signaturehelper.Signature.generate(timestamp, method, uri, SECRET_KEY)
    return {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Timestamp': timestamp,
        'X-API-KEY': API_KEY,
        'X-Customer': str(CUSTOMER_ID),
        'X-Signature': signature
    }


def get_shopping_conversion_data():
    """
    네이버 검색광고 API를 통해 쇼핑 검색어 전환 상세 보고서를 생성하고 다운로드.
    조회 날짜는 자동으로 전날 날짜를 사용합니다.

    Returns:
        list: 보고서 데이터의 각 줄을 담은 리스트. 실패 시 None 반환.
    """
    try:
        # 1단계: 보고서 생성 요청
        uri = '/stat-reports'
        method = 'POST'
        headers = get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID)

        # 전날 날짜를 YYYYMMDD 형식으로 자동 계산
        stat_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        print(f"조회 날짜: {stat_date}")

        paras = {
            'reportTp': 'SHOPPINGKEYWORD_CONVERSION_DETAIL',  # 보고서 유형
            'statDt': stat_date                               # 전날 날짜 자동 적용
        }
        print("보고서 생성 요청 중...")
        response = requests.post(BASE_URL + uri, headers=headers, json=paras)

        if response.status_code == 200:
            report_job_id = response.json().get('reportJobId')
            if not report_job_id:
                print("reportJobId를 가져오지 못했습니다.")
                return None
            print(f"보고서 생성 성공. Report Job ID: {report_job_id}")
        else:
            print("보고서 생성 API 호출에 실패했습니다.")
            print("상태 코드:", response.status_code)
            return None

        # 2단계: 보고서 준비 완료까지 대기 (최대 30회 x 10초 = 5분)
        print("보고서 준비 중입니다...")
        download_url = None  # 루프 전 미리 초기화 (루프 실패 시 None 체크를 위해)
        for attempt in range(30):
            uri = f'/stat-reports/{report_job_id}'
            headers = get_header('GET', uri, API_KEY, SECRET_KEY, CUSTOMER_ID)
            response = requests.get(BASE_URL + uri, headers=headers)

            if response.status_code == 200:
                status = response.json().get('status')
                print(f"현재 보고서 상태: {status} (시도 횟수: {attempt + 1})")

                if status == 'BUILT':
                    # 보고서 준비 완료 → 다운로드 URL 확보 후 루프 종료
                    download_url = response.json().get('downloadUrl')
                    if download_url:
                        print("보고서 준비 완료. 다운로드 URL 확보.")
                        break
                elif status in ['REGIST', 'RUNNING']:
                    # 아직 준비 중 → 10초 대기 후 재시도
                    time.sleep(10)
                else:
                    print(f"보고서 상태 오류: {status}")
                    return None
            else:
                print("보고서 상태 확인 API 호출에 실패했습니다.")
                print("상태 코드:", response.status_code)
                return None

        # 30회 시도 후에도 준비되지 않은 경우 종료
        if download_url is None:
            print("30번 시도 후에도 보고서가 준비되지 않았습니다.")
            return None

        # 3단계: 보고서 다운로드
        print("보고서 다운로드 중...")
        uri = '/report-download/'
        method = 'GET'
        headers = get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID)
        params = {
            'authtoken': download_url.split('?')[-1].split('=')[-1]  # URL에서 토큰 추출
        }
        response = requests.get(BASE_URL + uri, headers=headers, params=params)

        if response.status_code == 200:
            print("보고서 다운로드 성공.")
            return response.text.splitlines()  # 줄 단위 리스트로 반환
        else:
            print("보고서 다운로드 실패.")
            print("상태 코드:", response.status_code)
            return None

    except Exception as e:
        print(f"get_shopping_conversion_data 함수에서 오류 발생: {e}")
        return None


def insert_data_into_sql(db_info, table_name, data, insert_query):
    """
    파싱된 데이터를 PostgreSQL 테이블에 삽입.
    중복 데이터는 건너뛰고, 오류 발생 시 해당 레코드만 롤백 후 계속 진행.

    Args:
        db_info (dict): DB 연결 정보 (host, user, password, database)
        table_name (str): 삽입 대상 테이블명
        data (list): 삽입할 데이터 리스트
        insert_query (str): INSERT SQL 쿼리
    """
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(
            host=db_info['host'],
            user=db_info['user'],
            password=db_info['password'],
            dbname=db_info['database']
        )
        cursor = connection.cursor()
        print(f"{table_name} 테이블에 데이터 삽입 시작...")

        for record in data:
            try:
                # 현재 시간을 reg_tm, edit_tm으로 추가
                reg_tm = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                edit_tm = reg_tm
                record.extend([reg_tm, edit_tm])
                cursor.execute(insert_query, record)
                print(f"{table_name} 테이블에 데이터 삽입 성공: {record}")
            except psycopg2.IntegrityError as e:
                # 중복 키 오류 → 해당 레코드만 롤백 후 다음 레코드 계속 진행
                connection.rollback()
                print(f"{table_name} 테이블에 중복된 데이터가 있습니다: {e}")
            except Exception as e:
                # 그 외 오류 → 해당 레코드만 롤백 후 다음 레코드 계속 진행
                connection.rollback()
                print(f"{table_name} 테이블에 데이터 삽입 오류 발생: {e}")

        # 모든 데이터 삽입 후 변경 사항 커밋
        connection.commit()
        print(f"{table_name} 테이블에 데이터 삽입 성공")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"데이터베이스 오류 발생: {error}")
    finally:
        # 오류 여부와 관계없이 항상 커서 및 연결 종료
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
        print(f"{table_name} 테이블에 대한 데이터베이스 연결 종료")


def insert_shopping_conversion_table(data):
    """
    보고서 데이터를 파싱하여 naverapi_shoppingkeyword_conversion_detail 테이블에 삽입.

    Args:
        data (list): 보고서 줄 단위 리스트 (탭 구분자, 15개 컬럼)
    """
    if not data:
        print("삽입할 데이터가 없습니다.")
        return

    print("쇼핑 검색어 전환 데이터 삽입 시작...")
    parsed_data = []

    for idx, line in enumerate(data):
        columns = line.split('\t')  # 탭 구분자로 분리

        # 컬럼 수가 15개가 아니면 해당 줄 건너뜀
        if len(columns) != 15:
            print(f"데이터 형식 오류 (줄 번호 {idx + 1}): 예상 15개, 실제 {len(columns)}개. 데이터: {line}")
            continue

        try:
            # 각 컬럼을 DB 저장에 맞는 타입으로 변환
            transformed_data = [
                columns[0],                                      # date (날짜)
                int(columns[1]),                                 # customerId (고객 ID)
                columns[2],                                      # nccCampaignId (캠페인 ID)
                columns[3],                                      # adGroupId (광고그룹 ID)
                columns[4] if columns[4] != '-' else None,      # searchKeyword (검색어, '-'는 None 처리)
                columns[5],                                      # adId (광고 ID)
                columns[6],                                      # businessId (비즈니스 ID)
                columns[7],                                      # hour (시간대)
                columns[8],                                      # regionCode (지역 코드)
                columns[9],                                      # mediaCode (매체 코드)
                columns[10].strip(),                             # pcMobileType (PC/모바일 구분)
                int(columns[11]),                                # conversionMethod (전환 방법)
                columns[12],                                     # conversionType (전환 유형)
                int(columns[13]),                                # conversionCount (전환 수)
                float(columns[14]),                              # salesbyConversion (전환 매출)
            ]
            parsed_data.append(transformed_data)  

        except Exception as e:
            print(f"데이터 변환 오류 (줄 번호 {idx + 1}): {e}, 데이터: {line}")
            continue

    print(f"파싱된 데이터 개수: {len(parsed_data)}")
    if len(parsed_data) == 0:
        print("파싱된 데이터가 없습니다. 데이터 형식에 문제가 있을 수 있습니다.")
        return

    insert_query = """
        INSERT INTO naverapi_shoppingkeyword_conversion_detail (
            date, customerId, nccCampaignId, adGroupId, searchKeyword,
            adId, businessId, hour, regionCode, mediaCode, pcMobileType,
            conversionMethod, conversionType, conversionCount, salesConversion,
            reg_tm, edit_tm
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    insert_data_into_sql(db_info, 'naverapi_shoppingkeyword_conversion_detail', parsed_data, insert_query)
    print("쇼핑 검색어 전환 데이터 삽입 완료.")


# 스크립트 실행 진입점
if __name__ == "__main__":
    data = get_shopping_conversion_data()
    insert_shopping_conversion_table(data)
