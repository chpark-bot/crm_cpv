import streamlit as st
import pandas as pd
from datetime import timedelta
import numpy as np
import re
import io # 파일 다운로드를 위해 io 모듈 추가

# --- 1. 대시보드 기본 설정 ---
st.set_page_config(layout="wide", page_title="[CRM] 이벤트별 CPV 성과분석 대시보드")
st.title("[CRM] 이벤트별 CPV 성과분석 대시보드")
st.markdown("---")

# 증감율 계산 함수 (문자열 포맷: +10.00%)
def calculate_rate_str(current, previous, change):
    if previous == 0 and current > 0:
        return "+100.00%" 
    elif previous == 0 and current == 0:
        return "0.00%"
    else:
        rate = (change / previous) * 100
        return f"{rate:+.2f}%" 

# 증감율 계산 함수 (순수 숫자 값: 10.00)
def calculate_rate_num(current, previous, change):
    if previous == 0 and current > 0:
        return 100.0
    elif previous == 0 and current == 0:
        return 0.0
    else:
        return (change / previous) * 100

# CSV 파일 다운로드를 위한 변환 함수 (새로운 캐시 함수 정의)
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False, encoding='utf-8-sig')


# --- 2. 데이터 업로드 및 예시 파일 제공 ---

# 2-1. 예시 CSV 파일 데이터 생성
example_data = {
    '병원명': ['A병원', 'B병원', 'A병원', 'C병원'],
    '이벤트 ID': [1001, 1002, 1001, 1003],
    '이벤트명': ['리프팅 런칭 이벤트', '필러 3CC 특가', '리프팅 런칭 이벤트', '여름 맞이 이벤트'],
    '대상일': ['2025-08-01', '2025-08-01', '2025-08-02', '2025-09-15'],
    'CPV 조회 수': [5000, 3000, 6500, 1000],
    'CPV 매출': ['1,500,000', '2,000,000', '1,800,000', '500,000']
}
example_df = pd.DataFrame(example_data)

example_csv = convert_df_to_csv(example_df)

st.header("데이터 업로드")
uploaded_file = st.file_uploader("분석할 CSV 파일을 업로드해주세요.", type=["csv"])

# 2-2. 예시 CSV 다운로드 버튼 추가
st.download_button(
    label=":arrow_down: 예시 CSV 파일 양식 다운로드",
    data=example_csv,
    file_name='CRM_CPV_성과분석_양식.csv',
    mime='text/csv',
    help="다운로드 후 이 양식에 맞춰 데이터를 입력하여 업로드하세요."
)
st.markdown("---") # 시각적 구분선 추가


if uploaded_file is not None:
    # 데이터 로드
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"CSV 파일을 읽는 중 오류가 발생했습니다. 파일 인코딩(UTF-8 추천) 또는 형식을 확인해주세요: {e}")
        st.stop()


    # --- 3. 데이터 전처리 (오류 방지 및 컬럼명 정리 강화) ---
    
    # 3-1. 컬럼명 정리 및 확인
    df.columns = df.columns.str.strip() # 컬럼명 앞뒤 공백 제거
    
    required_cols = ['병원명', '이벤트 ID', '이벤트명', '대상일', 'CPV 조회 수', 'CPV 매출']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"CSV 파일에 다음 필수 컬럼이 누락되었습니다: {', '.join(missing_cols)}")
        st.info(":warning: CSV 파일을 열어 컬럼명(대소문자, 띄어쓰기 포함)이 정확한지 확인해주세요.")
        st.stop()

    # 3-2. 숫자 처리 (CPV 조회 수, CPV 매출)
    for col in ['CPV 조회 수', 'CPV 매출']:
        try:
            # 쉼표, 한글('원' 등), 특수문자 제거 후 숫자로 변환
            df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        except Exception:
            df[col] = 0
            
    # 3-3. 날짜 처리 (대상일)
    try:
        df['대상일'] = pd.to_datetime(df['대상일'], errors='coerce')
        df.dropna(subset=['대상일'], inplace=True)
        
        if df.empty:
            st.warning("유효한 날짜 데이터가 없어 분석을 진행할 수 없습니다.")
            st.stop()
            
        min_date_data = df['대상일'].min().date()
        max_date_data = df['대상일'].max().date()
        
    except Exception as e:
        st.error(f"날짜 컬럼('대상일') 처리 중 오류가 발생했습니다. 날짜 형식을 확인해주세요: {e}")
        st.stop()
    
    
    # --- 4. 기획전 기간 설정 필터 (사이드바) ---
    st.sidebar.header("📆기간 설정")

    start_date_input, end_date_input = st.sidebar.date_input(
        "기획전 진행 기간을 선택하세요:",
        [min_date_data, max_date_data],
        min_value=min_date_data,
        max_value=max_date_data
    )

    start_date = pd.to_datetime(start_date_input)
    end_date = pd.to_datetime(end_date_input)
    
    if start_date > end_date:
        st.error("시작일은 종료일보다 빨라야 합니다. 날짜를 다시 선택해주세요.")
        st.stop()
        
    # --- 5. 이전 동기간 계산 ---
    
    period_duration = end_date - start_date
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - period_duration
    
    st.sidebar.markdown(f"**선택 기간:** {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    st.sidebar.markdown(f"**이전 동기간:** {prev_start_date.strftime('%Y-%m-%d')} ~ {prev_end_date.strftime('%Y-%m-%d')}")


    # --- 6. 기간별 데이터 필터링 ---
    
    current_df = df