import streamlit as st
import pandas as pd
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection
import textwrap
from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.exceptions import LineBotApiError

# ==========================================
# 1. 頁面基本設定
# ==========================================
st.set_page_config(page_title="慢箋提醒管理系統", page_icon="💊", layout="wide")

# ==========================================
# 2. UI 風格設定 (CSS)
# ==========================================
st.markdown("""<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;900&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
<style>
    html, body, [class*="css"] { font-family: 'Inter', 'Noto Sans TC', sans-serif; background-color: #f6f7f8; }
    header[data-testid="stHeader"] { visibility: hidden; }
    .stAppHeader { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; max-width: 1440px; }
    .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        border-radius: 0.5rem; border: 1px solid #e7edf3; background-color: white; color: #0e141b; padding: 0.5rem;
    }
    .stButton button[kind="primary"] {
        background-color: #197fe6; border: none; color: white; border-radius: 0.5rem; padding: 0.5rem 1.5rem; font-weight: bold;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .stButton button[kind="primary"]:hover { background-color: #1466b8; }
    div[data-testid="stDataFrame"] {
        background-color: white; padding: 1rem; border-radius: 0.75rem; border: 1px solid #e7edf3; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 自定義簡潔標題 (Header)
# ==========================================
st.markdown("""<div style="background-color: white; border-bottom: 1px solid #e7edf3; padding: 1.5rem 2rem; margin-bottom: 2rem; border-radius: 0.5rem; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); display: flex; align-items: center; gap: 1rem;">
    <div style="width: 3.5rem; height: 3.5rem; background-color: rgba(25, 127, 230, 0.1); border-radius: 0.5rem; display: flex; align-items: center; justify-content: center; color: #197fe6;">
        <span class="material-symbols-outlined" style="font-size: 36px;">medication_liquid</span>
    </div>
    <div>
        <h1 style="font-size: 1.75rem; font-weight: 800; color: #0e141b; margin: 0; line-height: 1.2;">慢箋提醒管理系統</h1>
        <p style="font-size: 0.95rem; color: #4e7397; margin: 0;">自動計算領藥區間與回診提醒</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 4. 核心邏輯 (Backend Logic)
# ==========================================

def calculate_age(born):
    if not born: return 0
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def calculate_dates(start_date, duration):
    if not start_date: return {}
    end_cycle_1 = start_date + timedelta(days=duration)
    second_start = end_cycle_1 -
