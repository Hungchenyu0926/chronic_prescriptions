import streamlit as st
import pandas as pd
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 頁面基本設定
# ==========================================
st.set_page_config(page_title="慢箋提醒管理系統", page_icon="💊", layout="wide")

# ==========================================
# 2. 強制修復 UI (CSS + Header)
# ==========================================
st.markdown("""
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;900&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
    
    <style>
        /* 1. 全域字型與背景 */
        html, body, [class*="css"] {
            font-family: 'Inter', 'Noto Sans TC', sans-serif;
            background-color: #f6f7f8;
        }
        
        /* 2. 徹底隱藏 Streamlit 原生 Header 與 Footer (關鍵修正) */
        header[data-testid="stHeader"] { display: none !important; }
        .stAppHeader { display: none !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        
        /* 3. 調整主內容區塊，避免內容被切掉 */
        .block-container {
            padding-top: 1rem !important; /* 原本可能是 6rem，改小一點因為我們有自製 Header */
            padding-bottom: 5rem !important;
            max-width: 1440px;
        }

        /* 4. Streamlit 元件美化 */
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
        
        /* 表格區塊美化 */
        div[data-testid="stDataFrame"] {
            background-color: white;
            padding: 1rem;
            border-radius: 0.75rem;
            border: 1px solid #e7edf3;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
    </style>

    <div style="position: fixed; top: 0; left: 0; width: 100%; z-index: 999999; background-color: white; border-bottom: 1px solid #e7edf3; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);">
        <div style="display: flex; height: 4rem; align-items: center; justify-content: space-between; padding: 0 1.5rem; max-width: 1440px; margin: 0 auto;">
            
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div style="display: flex; align-items: center; justify-content: center; width: 2.5rem; height: 2.5rem; border-radius: 0.5rem; background-color: rgba(25, 127, 230, 0.1); color: #197fe6;">
                    <span class="material-symbols-outlined" style="font-size: 28px;">medication_liquid</span>
                </div>
                <h1 style="font-size: 1.25rem; font-weight: 700; color: #0e141b; margin: 0;">慢箋提醒管理</h1>
            </div>
            
            <nav style="display: flex; align-items: center; gap: 2rem;">
                <span style="font-size: 0.875rem; font-weight: 700; color: #197fe6; cursor: pointer;">個案管理</span>
                <span style="font-size: 0.875rem; font-weight: 500; color: #4e7397; cursor: pointer;">領藥排程</span>
                <span style="font-size: 0.875rem; font-weight: 500; color: #4e7397; cursor: pointer;">報表分析</span>
            </nav>
            
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div style="display: flex; align-items: center; gap: 0.75rem; padding-left: 0.75rem; border-left: 1px solid #e7edf3;">
                    <div style="text-align: right; display: block;">
                        <p style="font-size: 0.875rem; font-weight: 700; color: #0e141b; margin: 0;">管理員</p>
                        <p style="font-size: 0.75rem; color: #4e7397; margin: 0;">線上藥師</p>
                    </div>
                    <div style="width: 2.25rem; height: 2.25rem; border-radius: 9999px; background-color: #e5e7eb; display: flex; align-items: center; justify-content: center; color: #6b7280;">
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
    second_end = end_cycle_1 
    end_cycle_2 = end_cycle_1 + timedelta(days=duration)
    third_start = end_cycle_2 - timedelta(days=9)
    third_end = end_cycle_2
    end_cycle_3 = end_cycle_2 + timedelta(days=duration)
    return_visit = end_cycle_3 + timedelta(days=1)
    
    return {
        "2nd_start": second_start, "2nd_end": second_end,
        "3rd_start": third_start, "3rd_end": third_end,
        "return_visit": return_visit
    }

def check_status(row):
    """判斷目前的狀態並給予提醒標籤"""
    if pd.isna(row['第一次領藥日']): return "資料不全"
    today = date.today()
    
    # 檢查第二次
    if not row['已領第二次']:
        remind_start = row['2nd_start'] - timedelta(days=7)
        if remind_start <= today <= row['2nd_end']:
            if today < row['2nd_start']: return "⚠️ 即將進入第二次領藥期"
            return "🔴 請領取第二次藥物"
        elif today > row['2nd_end']: return "❌ 第二次領藥已過期"

    # 檢查第三次
    if not row['已領第三次']:
        remind_start = row['3rd_start'] - timedelta(days=7)
        if remind_start <= today <= row['3rd_end']:
            if today < row['3rd_start']: return "⚠️ 即將進入第三次領藥期"
            return "🔴 請領取第三次藥物"
        elif today > row['3rd_end'] and row['已領第二次']: return "❌ 第三次領藥已過期"
             
    if row['已領第二次'] and row['已領第三次']:
        if today >= row['return_visit'] - timedelta(days=7): return "🏥 建議準備回診"
        return "✅ 完成領藥"
    return "🔵 一般追蹤中"

# Google Sheets 連線
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Qu_f2aStXeasb4yW4GsSWTURUnXrIexFSoaDZ13CBME/edit?hl=zh-TW&gid=0#gid=0"

def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="工作表1", ttl=0)
        if df.empty:
            return pd.DataFrame(columns=['個案姓名', '出生年月日', '性別', '第一次領藥日', '處方天數', '居住里別', '已領第二次', '已領第三次'])
        date_cols = ['出生年月日', '第一次領藥日']
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        df['已領第二次'] = df['已領第二次'].fillna(False).astype(bool)
        df['已領第三次'] = df['已領第三次'].fillna(False).astype(bool)
        return df
    except Exception as e:
        st.error(f"讀取資料失敗: {e}")
        return pd.DataFrame()

def save_data(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="工作表1", data=df)
        st.toast("資料已儲存至雲端！", icon="☁️")
    except Exception as e:
        st.error(f"寫入資料失敗: {e}")

if 'df' not in st.session_state:
    st.session_state.df = load_data()

# ==========================================
# 4. 主內容區域 (Main Content)
# ==========================================

col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.markdown("""
        <h2 class="text-3xl font-black text-[#0e141b] tracking-tight mb-2">個案管理儀表板</h2>
        <p class="text-[#4e7397] text-base mb-6">管理慢性病連續處方箋個案資料與自動計算領藥提醒</p>
    """, unsafe_allow_html=True)

# --- 新增個案表單 ---
st.markdown("""
<div class="bg-white rounded-xl border border-[#e7edf3] shadow-sm overflow-hidden mb-8">
    <div class="px-6 py-4 border-b border-[#e7edf3] flex items-center gap-2 bg-gray-50/50">
        <span class="material-symbols-outlined text-[#197fe6]">person_add</span>
        <h3 class="text-lg font-bold text-[#0e141b]">新增個案資料</h3>
    </div>
</div>
""", unsafe_allow_html=True)

with st.container():
    with st.form("add_patient_form", border=True): 
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("個案姓名", placeholder="請輸入姓名")
            district = st.text_input("居住里別", placeholder="例如：大安里")
        with c2:
            dob = st.date_input("出生年月日", min_value=date(1900, 1, 1), max_value=date.today(), value=date(2025, 1, 1))
            first_date = st.date_input("第一次領藥日期", value=date.today())
        with c3:
            gender = st.selectbox("性別", ["男", "女"])
            duration = st.selectbox("處方箋週期", [28, 30], index=0)

        st.markdown("<br>", unsafe_allow_html=True)
        col_submit_L, col_submit_R = st.columns([4, 1])
        with col_submit_R:
            submitted = st.form_submit_button("💾 新增個案", type="primary", use_container_width=True)

        if submitted and name:
            new_data = {
                '個案姓名': name, '出生年月日': dob, '性別': gender,
                '第一次領藥日': first_date, '處方天數': duration,
                '居住里別': district, '已領第二次': False, '已領第三次': False
            }
            new_df = pd.DataFrame([new_data])
            st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True)
            save_data(st.session_state.df)
            st.success(f"已成功新增：{name}")
            st.rerun()

# --- 資料列表區塊 ---
st.markdown("""
<div class="bg-white rounded-t-xl border-t border-l border-r border-[#e7edf3] shadow-sm mt-8">
    <div class="px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-gray-50/50 border-b border-[#e7edf3]">
        <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-[#197fe6]">list_alt</span>
            <h3 class="text-lg font-bold text-[#0e141b]">個案資料列表</h3>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.df.empty:
    display_df = st.session_state.df.copy()
    
    display_df['年齡'] = display_df['出生年月日'].apply(calculate_age)
    display_df['第一次領藥日'] = pd.to_datetime(display_df['第一次領藥日']).dt.date
    date_calculations = display_df.apply(lambda row: calculate_dates(row['第一次領藥日'], row['處方天數']), axis=1)
    dates_df = pd.DataFrame(date_calculations.tolist())
    display_df = display_df.reset_index(drop=True)
    dates_df = dates_df.reset_index(drop=True)
    display_df = pd.concat([display_df, dates_df], axis=1)
    display_df['目前狀態'] = display_df.apply(check_status, axis=1)
    
    edited_df = st.data_editor(
        display_df,
        column_config={
            "個案姓名": st.column_config.TextColumn("個案姓名", help="病患姓名", width="small"),
            "年齡": st.column_config.NumberColumn("年齡", format="%d 歲", width="small"),
            "性別": st.column_config.TextColumn("性別", width="small"),
            "目前狀態": st.column_config.TextColumn("目前狀態", width="medium"),
            "已領第二次": st.column_config.CheckboxColumn("已領2次"),
            "已領第三次": st.column_config.CheckboxColumn("已領3次"),
            "2nd_start": st.column_config.DateColumn("2次起始", format="MM/DD"),
            "2nd_end": st.column_config.DateColumn("2次結束", format="MM/DD"),
            "3rd_start": st.column_config.DateColumn("3次起始", format="MM/DD"),
            "3rd_end": st.column_config.DateColumn("3次結束", format="MM/DD"),
            "return_visit": st.column_config.DateColumn("回診日", format="YYYY/MM/DD"),
            "出生年月日": None, "處方天數": None
        },
        disabled=["個案姓名", "年齡", "性別", "目前狀態", "2nd_start", "2nd_end", "3rd_start", "3rd_end", "return_visit"],
        use_container_width=True,
        hide_index=True,
        height=500
    )

    cols_to_check = ['已領第二次', '已領第三次']
    original_check = st.session_state.df[cols_to_check].fillna(False).reset_index(drop=True)
    new_check = edited_df[cols_to_check].fillna(False).reset_index(drop=True)
    
    if not new_check.equals(original_check):
        st.session_state.df['已領第二次'] = edited_df['已領第二次']
        st.session_state.df['已領第三次'] = edited_df['已領第三次']
        save_data(st.session_state.df)
        st.rerun()

    st.markdown("<div class='mt-4'></div>", unsafe_allow_html=True)
    with st.expander("🗑️ 進階管理：刪除個案"):
        col_del_1, col_del_2 = st.columns([4, 1])
        with col_del_1:
            patients_to_delete = st.multiselect(
                "選擇要刪除的姓名", 
                options=st.session_state.df['個案姓名'].tolist(),
                placeholder="搜尋姓名..."
            )
        with col_del_2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("確認刪除", type="secondary", use_container_width=True):
                if patients_to_delete:
                    st.session_state.df = st.session_state.df[~st.session_state.df['個案姓名'].isin(patients_to_delete)]
                    save_data(st.session_state.df)
                    st.success(f"已刪除: {', '.join(patients_to_delete)}")
                    st.rerun()
else:
    st.info("目前尚無資料，請從上方新增個案。")
