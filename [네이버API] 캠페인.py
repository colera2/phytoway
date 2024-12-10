#캠페인 database에 불러오기 성공
 
 
import time
import random
import requests
import psycopg2
import signaturehelper

# 네이버 API 요청에 필요한 HTTP 헤더를 생성
def get_header(method, uri, api_key, secret_key, customer_id):
    timestamp = str(round(time.time() * 1000))
    signature = signaturehelper.Signature.generate(timestamp, method, uri, secret_key)
    return {'Content-Type': 'application/json; charset=UTF-8', 'X-Timestamp': timestamp, 'X-API-KEY': API_KEY, 'X-Customer': str(CUSTOMER_ID), 'X-Signature': signature}


BASE_URL = 'https://api.searchad.naver.com'
API_KEY = '0100000000035ba1cc76db8c4cba24a05c3386d0f6d65e4245c883e3e70d24d46fd57193bb'
SECRET_KEY = 'AQAAAAADW6HMdtuMTLokoFwzhtD2hVgWxTOrgKQdi8s+So+KlA=='
CUSTOMER_ID = '1673134'

def naver_campaign_data():
    # 네이버 검색광고 API 호출 URL 및 헤더 설정
    uri = '/ncc/campaigns'
    method = 'GET'
    headers = get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID)
    response = requests.get(BASE_URL + uri, headers=headers)
    
    if response.status_code == 200:
        data = response.json()  # API로부터 받은 데이터를 JSON 형태로 파싱
        return data
    else:
        print("API 호출에 실패했습니다.")
        print("상태 코드:", response.status_code)
        return None

def insert_data_into_sql(db_info, data):
    # PostgreSQL 데이터베이스에 연결
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
        
        # 데이터 삽입 또는 업데이트 쿼리 작성
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

        
        # 데이터 삽입 반복
        for record in data:
            # 날짜 데이터 타입 변환
            reg_tm = record.get('regTm')
            edit_tm = record.get('editTm')
            
            if reg_tm:
                reg_tm = reg_tm.replace('T', ' ').replace('Z', '')
            if edit_tm:
                edit_tm = edit_tm.replace('T', ' ').replace('Z', '')
            
            # trackingUrl 필드가 없을 경우 빈 문자열로 설정
            tracking_url = record.get('trackingUrl', '')
            
            # 데이터 삽입 또는 업데이트 실행
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
        
        # 변경 사항을 실제 데이터베이스에 반영
        connection.commit()
        print("데이터가 커밋되었습니다.")
    except (Exception, psycopg2.DatabaseError) as error:
        print("데이터베이스 오류 발생:", error)
    finally:
        # 커서 종료 및 연결 종료
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

# SQL 데이터베이스 연결 정보 입력
db_info = {
    'host': 'db1-dev.postgres.database.azure.com',
    'user': 'dev',
    'password': '@Vkdlxhdnpdl0',
    'database': 'testDB_241128'
}

# 네이버 API 데이터 가져오기
naver_ads_data = naver_campaign_data()

if naver_ads_data:
    print("가져온 데이터:", naver_ads_data)  # 데이터 출력하여 확인
    # SQL 테이블에 데이터 삽입
    insert_data_into_sql(db_info, naver_ads_data)
    print("데이터 삽입 완료")
else:
    print("데이터가 없어서 삽입하지 못했습니다.")
