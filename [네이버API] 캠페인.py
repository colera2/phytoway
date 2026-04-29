"""
네이버 검색광고 API - 캠페인 데이터 수집 스크립트

[동작 순서]
1. 네이버 검색광고 API로 캠페인 목록 조회
2. 조회한 데이터를 PostgreSQL DB에 삽입 (중복 시 업데이트)

[사전 준비]
- .env 파일에 API 키 및 DB 연결 정보 입력 필요 (.env.example 참고)
- pip install requests psycopg2 python-dotenv
- signaturehelper.py 파일 필요 (네이버 검색광고 API 공식 제공)
"""

import time
import requests
import psycopg2
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
    signature = signaturehelper.Signature.generate(timestamp, method, uri, secret_key)
    return {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Timestamp': timestamp,
        'X-API-KEY': API_KEY,
        'X-Customer': str(CUSTOMER_ID),
        'X-Signature': signature
    }


def naver_campaign_data():
    """
    네이버 검색광고 API를 통해 캠페인 목록을 조회.

    Returns:
        list: 캠페인 데이터 리스트. 실패 시 None 반환.
    """
    uri = '/ncc/campaigns'
    method = 'GET'
    headers = get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID)
    response = requests.get(BASE_URL + uri, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print("API 호출에 실패했습니다.")
        print("상태 코드:", response.status_code)
        return None


def insert_data_into_sql(db_info, data):
    """
    캠페인 데이터를 naverapi_campaign 테이블에 삽입.
    동일한 nccCampaignId가 이미 존재하면 전체 필드를 최신값으로 업데이트 (upsert).

    Args:
        db_info (dict): DB 연결 정보 (host, user, password, database)
        data (list): 네이버 API에서 받은 캠페인 데이터 리스트
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

        # 중복 시 업데이트하는 upsert 쿼리 (ON CONFLICT)
        insert_query = """
            INSERT INTO naverapi_campaign (
                "nccCampaignId", "customerId", "name", "userLock", "campaignTp",
                "deliveryMethod", "trackingUrl", "trackingMode", "usePeriod",
                "dailyBudget", "useDailyBudget", "totalChargeCost", "status",
                "statusReason", "expectCost", "migType", "delFlag", "regTm", "editTm"
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("nccCampaignId") DO UPDATE SET
                "customerId" = EXCLUDED."customerId",
                "name" = EXCLUDED."name",
                "userLock" = EXCLUDED."userLock",
                "campaignTp" = EXCLUDED."campaignTp",
                "deliveryMethod" = EXCLUDED."deliveryMethod",
                "trackingUrl" = EXCLUDED."trackingUrl",
                "trackingMode" = EXCLUDED."trackingMode",
                "usePeriod" = EXCLUDED."usePeriod",
                "dailyBudget" = EXCLUDED."dailyBudget",
                "useDailyBudget" = EXCLUDED."useDailyBudget",
                "totalChargeCost" = EXCLUDED."totalChargeCost",
                "status" = EXCLUDED."status",
                "statusReason" = EXCLUDED."statusReason",
                "expectCost" = EXCLUDED."expectCost",
                "migType" = EXCLUDED."migType",
                "delFlag" = EXCLUDED."delFlag",
                "regTm" = EXCLUDED."regTm",
                "editTm" = EXCLUDED."editTm";
        """

        for record in data:
            # ISO 형식 날짜를 DB 저장 형식으로 변환 (예: '2024-11-25T00:00:00Z' → '2024-11-25 00:00:00')
            reg_tm = record.get('regTm')
            edit_tm = record.get('editTm')
            if reg_tm:
                reg_tm = reg_tm.replace('T', ' ').replace('Z', '')
            if edit_tm:
                edit_tm = edit_tm.replace('T', ' ').replace('Z', '')

            # trackingUrl 필드가 없을 경우 빈 문자열로 처리
            tracking_url = record.get('trackingUrl', '')

            try:
                cursor.execute(insert_query, (
                    record['nccCampaignId'],
                    record['customerId'],
                    record['name'],
                    record['userLock'],
                    record['campaignTp'],
                    record['deliveryMethod'],
                    tracking_url,
                    record['trackingMode'],
                    record['usePeriod'],
                    record['dailyBudget'],
                    record['useDailyBudget'],
                    record['totalChargeCost'],
                    record['status'],
                    record['statusReason'],
                    record['expectCost'],
                    record['migType'],
                    record['delFlag'],
                    reg_tm,
                    edit_tm
                ))
            except Exception as e:
                print(f"데이터 삽입 오류 발생: {e}")

        connection.commit()
        print("데이터가 커밋되었습니다.")

    except (Exception, psycopg2.DatabaseError) as error:
        print("데이터베이스 오류 발생:", error)
    finally:
        # 오류 여부와 관계없이 항상 커서 및 연결 종료
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


# 스크립트 실행 진입점
if __name__ == "__main__":
    naver_ads_data = naver_campaign_data()

    if naver_ads_data:
        print("가져온 데이터:", naver_ads_data)
        insert_data_into_sql(db_info, naver_ads_data)
        print("데이터 삽입 완료")
    else:
        print("데이터가 없어서 삽입하지 못했습니다.")
