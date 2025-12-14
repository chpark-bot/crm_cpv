import streamlit as st
import pandas as pd
from datetime import timedelta
import numpy as np
import re
import io 
import base64 

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
    df_formatted = df.copy()
    
    # final_detailed_df에만 존재하는 컬럼 이름 확인
    if '조회수' in df_formatted.columns:
        # 상세 성과 테이블용 포맷팅
        df_formatted['조회수'] = df_formatted['조회수'].apply(lambda x: f"{int(x):,.0f}")
        df_formatted['조회수 증감량'] = df_formatted['조회수 증감량'].apply(lambda x: f"{int(x):+,}")
        df_formatted['조회수 증감률(%)'] = df_formatted['조회수 증감률(%)'].apply(lambda x: f"{x:+.2f}%")
        
        # CPV매출 관련 포맷팅
        df_formatted['CPV매출'] = df_formatted['CPV매출'].apply(lambda x: f"{int(x):,} 원")
        df_formatted['CPV매출 증감액'] = df_formatted['CPV매출 증감액'].apply(lambda x: f"{int(x):+} 원")
        df_formatted['CPV매출 증감률(%)'] = df_formatted['CPV매출 증감률(%)'].apply(lambda x: f"{x:+.2f}%")
        
        # **********************************************
        # 💡 [이벤트 할인가] 포맷팅 추가
        # **********************************************
        if '이벤트 할인가' in df_formatted.columns:
            df_formatted['이벤트 할인가'] = df_formatted['이벤트 할인가'].apply(lambda x: f"{int(x):,} 원")
        
    return df_formatted.to_csv(index=False, encoding='utf-8-sig')


# --- 2. 데이터 업로드 및 예시 파일 제공 ---

# 2-1. 예시 CSV 파일 데이터 생성 (새로운 컬럼 추가)
example_data = {
    '병원명': ['A병원', 'B병원', 'A병원', 'C병원'],
    '이벤트 ID': [1001, 1002, 1001, 1003],
    '이벤트명': ['리프팅 런칭 이벤트', '필러 3CC 특가', '리프팅 런칭 이벤트', '여름 맞이 이벤트'],
    '대상일': ['2025-08-01', '2025-08-01', '2025-08-02', '2025-09-15'],
    'CPV 조회 수': [5000, 3000, 6500, 1000],
    'CPV 매출': ['1,500,000', '2,000,000', '1,800,000', '500,000'],
    
    # **********************************************
    # 💡 예시 데이터에 새 컬럼 추가
    # **********************************************
    '이벤트 할인가': ['300,000', '100,000', '300,000', '50,000'],
    '대카테고리명': ['리프팅', '필러', '리프팅', '이벤트'],
    '중카테고리명': ['전체', '입술', '전체', '전체'],
    '소카테고리명': ['포텐자', '국산', '포텐자', '윤곽']
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

    # **********************************************
    # 💡 required_cols에 새 컬럼 추가
    # **********************************************
    required_cols = ['병원명', '이벤트 ID', '이벤트명', '대상일', 'CPV 조회 수', 'CPV 매출', 
                     '이벤트 할인가', '대카테고리명', '중카테고리명', '소카테고리명']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"CSV 파일에 다음 필수 컬럼이 누락되었습니다: {', '.join(missing_cols)}")
        st.info(":warning: CSV 파일을 열어 컬럼명(대소문자, 띄어쓰기 포함)이 정확한지 확인해주세요.")
        st.stop()

    # 3-2. 숫자 처리 (CPV 조회 수, CPV 매출, 이벤트 할인가)
    # **********************************************
    # 💡 숫자 처리 대상에 '이벤트 할인가' 추가
    # **********************************************
    for col in ['CPV 조회 수', 'CPV 매출', '이벤트 할인가']:
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
    st.sidebar.header(":calendar:기간 설정")

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

    current_df = df[
        (df['대상일'] >= start_date) &
        (df['대상일'] <= end_date)
    ].copy()

    prev_df = df[
        (df['대상일'] >= prev_start_date) &
        (df['대상일'] <= prev_end_date)
    ].copy()

    if current_df.empty:
        st.warning("선택하신 기획전 기간에 해당하는 데이터가 없습니다.")
        st.stop()

    # --- 7. 통합 분석 데이터프레임 생성 ---

    # **********************************************
    # 💡 group_keys에 새 컬럼 추가 (이벤트의 고유 속성이므로 그룹 키에 포함)
    # **********************************************
    group_keys = ['이벤트명', '병원명', '이벤트 ID', 
                  '이벤트 할인가', '대카테고리명', '중카테고리명', '소카테고리명']

    current_event_summary = current_df.groupby(group_keys).agg(
        {'CPV 조회 수': 'sum', 'CPV 매출': 'sum'}
    ).reset_index().rename(columns={'CPV 조회 수': '현재 조회 수', 'CPV 매출': '현재 매출'})

    prev_event_summary = prev_df.groupby(group_keys).agg(
        {'CPV 조회 수': 'sum', 'CPV 매출': 'sum'}
    ).reset_index().rename(columns={'CPV 조회 수': '이전 조회 수', 'CPV 매출': '이전 매출'})
    
    # 이전 df에서 병합할 키 목록
    prev_merge_keys = group_keys + ['이전 조회 수', '이전 매출']

    event_analysis = pd.merge(
        current_event_summary,
        prev_event_summary[prev_merge_keys], # 전체 그룹키 포함
        on=group_keys,
        how='left'
    ).fillna(0)

    event_analysis['조회수 증감액'] = event_analysis['현재 조회 수'] - event_analysis['이전 조회 수']
    event_analysis['매출 증감액'] = event_analysis['현재 매출'] - event_analysis['이전 매출']

    event_analysis['조회수 증감률 (%)'] = event_analysis.apply(
        lambda row: calculate_rate_num(row['현재 조회 수'], row['이전 조회 수'], row['조회수 증감액']),
        axis=1
    )
    event_analysis['매출 증감률 (%)'] = event_analysis.apply(
        lambda row: calculate_rate_num(row['현재 매출'], row['이전 매출'], row['매출 증감액']),
        axis=1
    )

    # --- 8. 핵심 지표 시각화 (상단 총합) ---

    current_views = event_analysis['현재 조회 수'].sum()
    current_revenue = event_analysis['현재 매출'].sum()

    prev_views = event_analysis['이전 조회 수'].sum()
    prev_revenue = event_analysis['이전 매출'].sum()

    views_change = current_views - prev_views
    revenue_change = current_revenue - prev_revenue

    views_rate_str = calculate_rate_str(current_views, prev_views, views_change)
    revenue_rate_str = calculate_rate_str(current_revenue, prev_revenue, revenue_change)

    st.header(":chart_with_upwards_trend: 기획전 기간 성과 증감 분석")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            label="총 CPV 조회 수",
            value=f"{int(current_views):,}",
            delta=f"{int(views_change):,} ({views_rate_str})"
        )

    with col2:
        st.metric(
            label="총 CPV 매출",
            value=f"{int(current_revenue):,} 원",
            delta=f"{int(revenue_change):,} 원 ({revenue_rate_str})"
        )

    st.markdown("---")

    # --- 9. TOP 3 랭킹 ---

    st.header(":trophy: 이벤트 TOP 3 랭킹 (기획전 기간)")

    # 랭킹 테이블 출력을 위한 포맷된 컬럼 생성
    event_analysis['CPV 조회 수 (랭킹용)'] = event_analysis.apply(
        lambda row: f"{int(row['현재 조회 수']):,} ({calculate_rate_str(row['현재 조회 수'], row['이전 조회 수'], row['조회수 증감액'])})",
        axis=1
    )
    event_analysis['CPV 매출 (랭킹용)'] = event_analysis.apply(
        lambda row: f"{int(row['현재 매출']):,} 원 ({calculate_rate_str(row['현재 매출'], row['이전 매출'], row['매출 증감액'])})",
        axis=1
    )

    ranking_cols_views = ['이벤트명', '병원명', 'CPV 조회 수 (랭킹용)']
    ranking_cols_revenue = ['이벤트명', '병원명', 'CPV 매출 (랭킹용)']

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("조회 수 TOP 3 이벤트")
        top3_views = event_analysis.sort_values(by='현재 조회 수', ascending=False).head(3)[ranking_cols_views]
        st.dataframe(top3_views, use_container_width=True, hide_index=True)

    with col4:
        st.subheader("CPV 매출 TOP 3 이벤트")
        top3_revenue = event_analysis.sort_values(by='현재 매출', ascending=False).head(3)[ranking_cols_revenue]
        st.dataframe(top3_revenue, use_container_width=True, hide_index=True)

    st.markdown("---")


    # --- 10. 이벤트별 상세 성과 테이블 (NEW) ---
    st.header(":clipboard: 이벤트별 상세 성과")

    # **********************************************
    # 💡 최종 테이블 컬럼 매핑에 새 컬럼 추가
    # **********************************************
    detailed_cols_map = {
        '이벤트명': '이벤트명',
        '병원명': '병원명',
        '이벤트 ID': '이벤트 ID',
        '이벤트 할인가': '이벤트 할인가',
        '대카테고리명': '대카테고리명',
        '중카테고리명': '중카테고리명',
        '소카테고리명': '소카테고리명',
        '현재 조회 수': '조회수',
        '조회수 증감액': '조회수 증감량',
        '조회수 증감률 (%)': '조회수 증감률(%)',
        '현재 매출': 'CPV매출',
        '매출 증감액': 'CPV매출 증감액',
        '매출 증감률 (%)': 'CPV매출 증감률(%)'
    }

    final_detailed_df = event_analysis[detailed_cols_map.keys()].rename(columns=detailed_cols_map)

    # DataFrame 포맷팅: CPV매출 컬럼 포맷 추가 반영 (CPV매출 증감액에 천단위 콤마 추가)
    st.dataframe(
        final_detailed_df.style.format({
            '조회수': "{:,.0f}",
            '조회수 증감량': "{:+.0f}",
            '조회수 증감률(%)': "{:+.2f}%",
            'CPV매출': "{:,.0f} 원",
            'CPV매출 증감액': "{:+,.0f} 원",
            'CPV매출 증감률(%)': "{:+.2f}%",
            # **********************************************
            # 💡 [이벤트 할인가] 포맷팅 추가
            # **********************************************
            '이벤트 할인가': "{:,.0f} 원"
        }),
        use_container_width=True,
        hide_index=True
    )

    # ----------------------------------------------------
    # :sparkles: CSV 다운로드 버튼 (리프레시 방지용)
    # ----------------------------------------------------
    
    # 1. CSV 데이터 생성
    csv_data = convert_df_to_csv(final_detailed_df)
    b64 = base64.b64encode(csv_data.encode()).decode()
    
    # 2. 파일 이름 생성
    file_name = f'CRM_CPV_상세성과_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.csv'
    
    # 3. HTML 링크 생성
    href = f'''
    <a href="data:file/csv;base64,{b64}" download="{file_name}"
       style="display: inline-flex; align-items: center; justify-content: center; 
              background-color: rgb(240, 242, 246); color: rgb(38, 39, 48); 
              padding: 0.25rem 0.75rem; border-radius: 0.5rem; border: 1px solid rgba(49, 51, 63, 0.2); 
              text-decoration: none; font-size: 14px; margin-top: 1rem;">
        ⬇️ 상세 성과 테이블 CSV 다운로드
    </a>
    '''
    
    # 4. Streamlit에 HTML 렌더링
    st.markdown(href, unsafe_allow_html=True)
    
    st.markdown("---")


# 데이터가 업로드되지 않았을 때 안내 메시지
else:
    st.info(":arrow_up: 상단의 'Browse files' 버튼을 눌러 CSV 파일을 업로드하고 대시보드를 시작하세요.")