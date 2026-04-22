import time
import requests
import psycopg2
from datetime import datetime
import signaturehelper

#api 연결 정보
BASE_URL = 'https://api.searchad.naver.com'
API_KEY = '0100000000035ba1cc76db8c4cba24a05c3386d0f6d65e4245c883e3e70d24d46fd57193bb'
SECRET_KEY = 'AQAAAAADW6HMdtuMTLokoFwzhtD2hVgWxTOrgKQdi8s+So+KlA=='
CUSTOMER_ID = '1673134'

# 데이터베이스 연결 정보
db_info = {
    'host': 'db1-dev.postgres.database.azure.com',
    'user': 'dev',
    'password': '@Vkdlxhdnpdl0',
    'database': 'testDB_241128'
}


def get_header(method, uri, api_key, secret_key, customer_id):
    timestamp = str(round(time.time() * 1000))
    signature = signaturehelper.Signature.generate(timestamp, method, uri, SECRET_KEY)
    return {'Content-Type': 'application/json; charset=UTF-8', 'X-Timestamp': timestamp, 'X-API-KEY': API_KEY, 'X-Customer': str(CUSTOMER_ID), 'X-Signature': signature}


# 네이버 검색광고 대용량 다운로드 보고서 생성
uri = '/stat-reports'
method = 'POST'
headers = get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID)
paras = {
    'reportTp': 'SHOPPINGKEYWORD_DETAIL',
    'statDt': '20241125'
}
r2 = requests.post(BASE_URL + uri, headers=headers, json=paras)

print("response status_code = {}".format(r2.status_code))
print("response body = {}".format(r2.json()))


reportJobId = r2.json()['reportJobId']

# 네이버 검색광고 대용량 다운로드 보고서 다운로드
uri = '/stat-reports/' + str(reportJobId)
method = 'GET'
headers = get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID)

r2 = requests.get(BASE_URL + uri, headers=headers)

print("response status_code = {}".format(r2.status_code))
print("response body = {}".format(r2.json()))


downloadUrl = r2.json()['downloadUrl']
authtoken = downloadUrl.split('?')[-1].split('=')[-1]

print(downloadUrl)
print(authtoken)


# 복원된 코드 - 다운로드 URL로 실제 보고서 데이터 가져오기
uri = '/report-download/'
method = 'GET'
headers = get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID)
params = {
    'authtoken': authtoken
}

r2 = requests.get(BASE_URL + uri, headers=headers, params=params)

print("response status_code = {}".format(r2.status_code))
print("response body = {}".format(r2.text))


def get_shoppingkeyword_detail_data():
    try:
        # 네이버 검색광고 대용량 다운로드 보고서 생성
        uri = '/stat-reports'
        method = 'POST'
        headers = get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID)
        paras = {
            'reportTp': 'SHOPPINGKEYWORD_DETAIL',
            'statDt': '20241125'
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

        # 보고서가 준비될 때까지 대기
        print("보고서 준비 중입니다...")
        for attempt in range(30):  # 최대 30번까지 시도 (대기 시간 포함)
            uri = f'/stat-reports/{report_job_id}'
            headers = get_header('GET', uri, API_KEY, SECRET_KEY, CUSTOMER_ID)
            response = requests.get(BASE_URL + uri, headers=headers)

            if response.status_code == 200:
                status = response.json().get('status')
                print(f"현재 보고서 상태: {status} (시도 횟수: {attempt + 1})")
                if status == 'BUILT':
                    download_url = response.json().get('downloadUrl')
                    if download_url:
                        print("보고서 준비 완료. 다운로드 URL 확보.")
                        break
                elif status in ['REGIST', 'RUNNING']:
                    time.sleep(10)  # 보고서 준비 중, 10초 대기 후 재시도
                else:
                    print(f"보고서 상태 오류: {status}")
                    return None
            else:
                print("보고서 다운로드 API 호출에 실패했습니다.")
                print("상태 코드:", response.status_code)
                return None

        # 다운로드 URL을 사용하여 데이터 가져오기
        print("보고서 다운로드 중...")
        uri = '/report-download/'
        method = 'GET'
        headers = get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID)
        params = {
            'authtoken': download_url.split('?')[-1].split('=')[-1]
        }
        response = requests.get(BASE_URL + uri, headers=headers, params=params)

        if response.status_code == 200:
            print("보고서 다운로드 성공.")
            return response.text.splitlines()
        else:
            print("보고서 다운로드 실패.")
            print("상태 코드:", response.status_code)
            return None
    except Exception as e:
        print(f"get_shopping_conversion_data 함수에서 오류 발생: {e}")
        return None


def insert_data_into_sql(db_info, table_name, data, insert_query):
    connection = None
    cursor = None
    try:
        # 데이터베이스 연결
        connection = psycopg2.connect(
            host=db_info['host'],
            user=db_info['user'],
            password=db_info['password'],
            dbname=db_info['database']
        )
        cursor = connection.cursor()
        print(f"{table_name} 테이블에 데이터 삽입 시작...")

        # 데이터를 반복하면서 삽입
        for record in data:
            try:
                print(record)
                reg_tm = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                edit_tm = reg_tm
                # record.extend([reg_tm, edit_tm])
                cursor.execute(insert_query, record)
                print(f"{table_name} 테이블에 데이터 삽입 성공: {record}")
            except psycopg2.IntegrityError as e:
                connection.rollback()
                print(f"{table_name} 테이블에 중복된 데이터가 있습니다: {e}")
            except Exception as e:
                connection.rollback()
                print(f"{table_name} 테이블에 데이터 삽입 오류 발생: {e}")

        connection.commit()
        print(f"{table_name} 테이블에 데이터 삽입 성공")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"데이터베이스 오류 발생: {error}")
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
        print(f"{table_name} 테이블에 대한 데이터베이스 연결 종료")


# 쇼핑 검색어 데이터 삽입 함수
def insert_shopping_keyword_detail_table(data):
    if not data:
        print("삽입할 데이터가 없습니다.")
        return

    print("쇼핑 검색어 데이터 삽입 시작...")
    parsed_data = []
    for idx, line in enumerate(data):
        columns = line.split('\t')

        if len(columns) != 16:
            print(f"데이터 형식 오류 (줄 번호 {idx + 1}): 예상 필드 개수는 16개인데, {len(columns)}개를 받았습니다. 데이터: {line}")
            continue

        try:
            transformed_data = [
                columns[0],  # date
                int(columns[1]),  # customerId
                columns[2],  # nccCampaignId
                columns[3],  # adGroupId
                columns[4] if columns[4] != '-' else None,  # searchKeyword
                columns[5],  # adId
                columns[6],  # businessId
                int(columns[7]),  # hours
                columns[8],  # regionCode
                columns[9],  # mediaCode
                columns[10].strip(),  # pcMobileType
                int(columns[11]),  # impression
                int(columns[12]),  # click
                float(columns[13]),  # cost
                int(columns[14]),  # sumAdRank
                int(columns[15]),  # viewCount
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
        INSERT INTO naverapi_shopping_keyword_details (
            date, "customerId", "nccCampaignId", "adGroupId", "searchKeyword",
            "adId", "businessId", "hours", "regionCode", "mediaCode", "pcMobileType",
            impression, click, cost, "sumAdRank", "viewCount"
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    insert_data_into_sql(db_info, 'naverapi_shopping_keyword_details', parsed_data, insert_query)
    print("쇼핑 검색어 데이터 삽입 완료.")


data = get_shoppingkeyword_detail_data()
insert_shopping_keyword_detail_table(data)
