import streamlit as st
import pandas as pd
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 頁面基本設定
# ==========================================
st.set_page_config(page_title="慢箋提醒管理系統", page_icon="💊", layout="wide")

# ==========================================
# 2. UI 介面注入 (CSS + Header) - 修正版
# ==========================================
# 請注意：這是一個完整的 Python 函數呼叫，請勿修改內部的引號
st.markdown("""
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;900&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
    
    <style>
        /* 全域樣式設定 */
        html, body, [class*="css"] {
            font-family: 'Inter', 'Noto Sans TC', sans-serif;
            background-color: #f6f7f8;
        }
        
        /* 隱藏 Streamlit 預設元件 */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;} 
        
        /* 修正主內容區塊，避免被自訂 Header 遮擋 */
        .block-container {
            padding-top: 0rem !important;
            padding-bottom: 5rem !important;
            max-width: 1440px;
        }

        /* Streamlit 輸入框美化 */
        .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
            border-radius: 0.5rem;
            border: 1px solid #e7edf3;
            background-color: white;
            color: #0e141b;
            padding: 0.5rem;
        }
        
        /* 按鈕美化 */
        .stButton button[kind="primary"] {
            background-color: #197fe6;
            border: none;
            color: white;
            border-radius: 0.5rem;
            padding: 0.5rem 1.5rem;
            font-weight: bold;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .stButton button[kind="primary"]:hover {
            background-color: #1466b8;
        }
        
        /* 表格美化 */
        div[data-testid="stDataFrame"] {
            background-color: white;
            padding: 1rem;
            border-radius: 0.75rem;
            border: 1px solid #e7edf3;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
    </style>

    <div class="fixed top-0 left-0 w-full bg-white border-b border-[#e7edf3] shadow-sm mb-6" style="z-index: 99999;">
        <div class="flex h-16 items-center justify-between px-6 lg:px-10 max-w-[1440px] mx-auto">
            <div class="flex items-center gap-4">
                <div class="flex items-center justify-center w-10 h-10 rounded-lg bg-[#197fe6]/10 text-[#197fe6]">
                    <span class="material-symbols-outlined text-[28px]">medication_liquid</span>
                </div>
                <h1 class="text-xl font-bold tracking-tight text-[#0e141b]">慢箋提醒管理</h1>
            </div>
            
            <nav class="flex items-center gap-8">
                <span class="text-sm font-bold text-[#197fe6] cursor-pointer hover:opacity-80">個案管理</span>
                <span class="text-sm font-medium text-[#4e7397] hover:text-[#197fe6] transition-colors cursor-pointer">領藥排程</span>
                <span class="text-sm font-medium text-[#4e7397] hover:text-[#197fe6] transition-colors cursor-pointer">報表分析</span>
            </nav>
            
            <div class="flex items-center gap-4">
                <div class="flex items-center gap-3 pl-2 border-l border-[#e7edf3]">
                    <div class="text-right hidden sm:block">
                        <p class="text-sm font-bold text-[#0e141b]">管理員</p>
                        <p class="text-xs text-[#4e7397]">線上藥師</p>
                    </div>
                    <div class="w-9 h-9 rounded-full bg-gray-200 flex items-center justify-center text-gray-500">
                        <span class="material-symbols-outlined">person</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div style="height: 5rem;"></div>
""", unsafe_allow_html=True)


# ==========================================
# 3. 核心邏輯 (Python Backend)
# ==========================================

def calculate_age(born):
    """根據出生年月日計算年齡"""
    if not born: return 0
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def calculate_dates(start_date, duration):
    """計算慢箋的各個關鍵日期"""
    if not start_date: return {}
    end_cycle_1 = start_date + timedelta(days=duration)
    second_start = end_cycle_1 - timedelta(days=9)
    second_end = end
