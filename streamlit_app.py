import streamlit as st # <-- 1. 반드시 최상단에 위치해야 합니다.
import pandas as pd
from datetime import timedelta
import numpy as np
import re
import io 

# 증감률에 따라 색상을 입히는 함수 정의
# ... (중략, highlight_growth 함수는 그대로 유지) ...

# --- 1. 대시보드 기본 설정 및 CSS Injection ---
st.set_page_config(layout="wide", page_title="[CRM] 이벤트별 CPV 성과분석 대시보드")
st.title("[CRM] 이벤트별 CPV 성과분석 대시보드")

# === 테이블 헤더 스타일 CSS Injection ===
st.markdown("""
<style>
/* ... (CSS 코드 유지) ... */
</style>
""", unsafe_allow_html=True)
# =======================================

st.markdown("---")
# ... (나머지 코드는 동일) ...