import os
import re
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# DB 접속 정보
DB_HOST = "db1-dev.postgres.database.azure.com"
DB_USER = "dev"
DB_PASSWORD = "@Vkdlxhdnpdl0"
DB_PORT = 5432
DB_NAME = "dainDB"

# 파일 경로
FILE_DIR = r"C:\Users\dshin\dbdata"

# 정규식 패턴: 파일명은 "사용자정의채널_yyyy-mm-dd_yyyy-mm-dd" 또는 "검색채널_yyyy-mm-dd_yyyy-mm-dd"
FILE_PATTERN = re.compile(r"^(사용자정의채널|검색채널)_(\d{4}-\d{2}-\d{2})_\d{4}-\d{2}-\d{2}")

# 테이블별 컬럼 정의
CUSTOM_ORDER_COLUMNS = [
    "yymmdd", "device", "nt_source", "nt_medium", "nt_detail", "nt_keyword",
    "customer_cnt", "inflow_cnt", "page_cnt", "page_inflow_cnt", "order_cnt",
    "order_inflow_per", "order_price", "order_inflow_price", "contribute_cnt",
    "contribute_inflow_per", "contribute_price", "contribute_inflow_price"
]

SEARCH_CHANNEL_COLUMNS = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P",
    "yymmdd"
]

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

def get_latest_date(conn, table_name):
    with conn.cursor() as cur:
        query = f'SELECT MAX("yymmdd") FROM "{table_name}";'
        cur.execute(query)
        result = cur.fetchone()[0]
        if result is not None:
            return result
    return None

def insert_dataframe(conn, df, table_name, columns):
    df = df[columns]
    data_tuples = [tuple(x) for x in df.to_numpy()]
    cols_str = ', '.join([f'"{col}"' for col in columns])
    query = f'INSERT INTO "{table_name}" ({cols_str}) VALUES %s;'
    with conn.cursor() as cur:
        execute_values(cur, query, data_tuples)
    conn.commit()

def process_file(conn, file_path, channel_type, file_date):
    print(f"Processing {file_path} for date {file_date}...")
    
    # 우선 header=0으로 읽음
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return

    if channel_type == "사용자정의채널":
        table_name = "Naver_Custom_Order"
        expected_full_columns = CUSTOM_ORDER_COLUMNS
        expected_data_columns = CUSTOM_ORDER_COLUMNS[1:]  # yymmdd 제외
    elif channel_type == "검색채널":
        table_name = "Naver_Search_Channel"
        expected_full_columns = SEARCH_CHANNEL_COLUMNS
        expected_data_columns = SEARCH_CHANNEL_COLUMNS[:-1]  # yymmdd 제외
    else:
        print(f"Unknown channel type in file {file_path}.")
        return

    # 파일에 저장된 컬럼명이 예상과 다르면, header 없이 읽고 첫 행(실제 헤더)을 건너뜁니다.
    if not set(expected_data_columns).issubset(df.columns):
        df = pd.read_excel(file_path, header=None, skiprows=1)
        if df.shape[1] == len(expected_data_columns):
            df.columns = expected_data_columns
        else:
            print(f"Column mismatch in {file_path}. Expected {len(expected_data_columns)} columns, got {df.shape[1]}.")
            return

    # 파일 데이터에는 날짜 정보가 없으므로 추가(덮어쓰기)
    df["yymmdd"] = file_date
    df = df[expected_full_columns]

    try:
        insert_dataframe(conn, df, table_name, expected_full_columns)
        print(f"Data from {file_path} inserted into {table_name}.")
    except Exception as e:
        print(f"Error inserting data from {file_path}: {e}")
        conn.rollback()

def main():
    conn = get_db_connection()

    for filename in os.listdir(FILE_DIR):
        if not filename.endswith(".xlsx"):
            continue

        match = FILE_PATTERN.match(filename)
        if not match:
            print(f"File {filename} does not match expected pattern. Skipping.")
            continue

        channel_type, file_date = match.groups()

        if channel_type == "사용자정의채널":
            table_name = "Naver_Custom_Order"
        elif channel_type == "검색채널":
            table_name = "Naver_Search_Channel"
        else:
            print(f"Unexpected channel type in file {filename}.")
            continue

        latest_date = get_latest_date(conn, table_name)
        if latest_date is not None and file_date <= latest_date:
            print(f"File {filename} (date: {file_date}) is not newer than latest date ({latest_date}) in {table_name}. Skipping.")
            continue

        file_path = os.path.join(FILE_DIR, filename)
        process_file(conn, file_path, channel_type, file_date)

    conn.close()
    print("Processing complete.")

if __name__ == "__main__":
    main()
