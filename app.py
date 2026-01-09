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
    if row.get('已結案', False): return "🏁 已結案"
    if pd.isna(row['第一次領藥日']): return "資料不全"
    today = date.today()
    
    if not row['已領第二次']:
        remind_start = row['2nd_start'] - timedelta(days=7)
        if remind_start <= today <= row['2nd_end']:
            if today < row['2nd_start']: return "⚠️ 即將進入第二次領藥期"
            return "🔴 請領取第二次藥物"
        elif today > row['2nd_end']: return "❌ 第二次領藥已過期"

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

# --- LINE 推播函數 (改為發送給管理員) ---
def send_admin_notification(message_text):
    try:
        token = st.secrets["line_bot"]["channel_access_token"]
        admin_id = st.secrets["line_bot"]["admin_user_id"] 
        
        line_bot_api = LineBotApi(token)
        line_bot_api.push_message(admin_id, TextSendMessage(text=message_text))
        return True, "發送成功"
    except KeyError:
        return False, "Secrets 設定不完整"
    except Exception as e:
        return False, f"發送失敗: {e}"

# Google Sheets 連線
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Qu_f2aStXeasb4yW4GsSWTURUnXrIexFSoaDZ13CBME/edit?hl=zh-TW&gid=0#gid=0"

def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="工作表1", ttl=0)
        
        required_columns = [
            '個案姓名', '個案電話', '出生年月日', '性別', 
            '第一次領藥日', '處方天數', '居住里別', 
            '已領第二次', '已領第三次', '已結案'
        ]
        
        if df.empty:
            return pd.DataFrame(columns=required_columns)
            
        for col in required_columns:
            if col not in df.columns:
                if col in ['已領第二次', '已領第三次', '已結案']:
                    df[col] = False
                else:
                    df[col] = ""

        date_cols = ['出生年月日', '第一次領藥日']
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
            
        bool_cols = ['已領第二次', '已領第三次', '已結案']
        for col in bool_cols:
            df[col] = df[col].fillna(False).astype(bool)
            
        df['個案電話'] = df['個案電話'].astype(str).replace('nan', '')

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
# 5. 主內容區域 (Main Content)
# ==========================================

# --- 新增個案表單 (標題) ---
st.markdown("""<div style="background-color: white; border: 1px solid #e7edf3; border-radius: 10px 10px 0 0; padding: 15px 24px; display: flex; align-items: center; gap: 8px; margin-bottom: -1px;">
    <span class="material-symbols-outlined" style="color: #197fe6;">person_add</span>
    <span style="font-weight: 700; color: #0e141b; font-size: 1.125rem;">新增個案資料</span>
</div>""", unsafe_allow_html=True)

# --- 新增個案表單 (內容) ---
with st.container():
    with st.form("add_patient_form", border=True): 
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("個案姓名", placeholder="請輸入姓名")
            phone = st.text_input("個案電話", placeholder="例如：0912-345678")
        with c2:
            dob = st.date_input("出生年月日", min_value=date(1900, 1, 1), max_value=date.today(), value=date(2025, 1, 1))
            district = st.text_input("居住里別", placeholder="例如：大安里")
        with c3:
            r1_c1, r1_c2 = st.columns(2)
            with r1_c1: gender = st.selectbox("性別", ["男", "女"])
            with r1_c2: duration = st.selectbox("處方箋週期", [28, 30], index=0)
            first_date = st.date_input("第一次領藥日期", value=date.today())

        st.markdown("<br>", unsafe_allow_html=True)
        col_submit_L, col_submit_R = st.columns([4, 1])
        with col_submit_R:
            submitted = st.form_submit_button("💾 新增個案", type="primary", use_container_width=True)

        if submitted and name:
            new_data = {
                '個案姓名': name, '個案電話': phone,
                '出生年月日': dob, '性別': gender,
                '第一次領藥日': first_date, '處方天數': duration,
                '居住里別': district, 
                '已領第二次': False, '已領第三次': False, '已結案': False
            }
            new_df = pd.DataFrame([new_data])
            st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True)
            save_data(st.session_state.df)
            st.success(f"已成功新增：{name}")
            st.rerun()

# --- 資料列表區塊 (標題) ---
st.markdown("""<div style="margin-top: 2rem; background-color: white; border: 1px solid #e7edf3; border-radius: 10px 10px 0 0; padding: 15px 24px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #e7edf3;">
    <span class="material-symbols-outlined" style="color: #197fe6;">list_alt</span>
    <span style="font-weight: 700; color: #0e141b; font-size: 1.125rem;">個案資料列表</span>
</div>""", unsafe_allow_html=True)

if not st.session_state.df.empty:
    display_df = st.session_state.df.copy()
    
    # 運算
    display_df['年齡'] = display_df['出生年月日'].apply(calculate_age)
    display_df['第一次領藥日'] = pd.to_datetime(display_df['第一次領藥日']).dt.date
    date_calculations = display_df.apply(lambda row: calculate_dates(row['第一次領藥日'], row['處方天數']), axis=1)
    dates_df = pd.DataFrame(date_calculations.tolist())
    display_df = display_df.reset_index(drop=True)
    dates_df = dates_df.reset_index(drop=True)
    display_df = pd.concat([display_df, dates_df], axis=1)
    display_df['目前狀態'] = display_df.apply(check_status, axis=1)
    
    # 顯示表格 (包含出生年月日)
    edited_df = st.data_editor(
        display_df,
        column_config={
            "個案姓名": st.column_config.TextColumn("個案姓名", width="small"),
            "出生年月日": st.column_config.DateColumn("出生日期", format="YYYY/MM/DD", width="small"), # 👈 新增顯示這欄
            "個案電話": st.column_config.TextColumn("電話", width="medium"),
            "目前狀態": st.column_config.TextColumn("目前狀態", width="medium"),
            "已領第二次": st.column_config.CheckboxColumn("已領2次"),
            "已領第三次": st.column_config.CheckboxColumn("已領3次"),
            "已結案": st.column_config.CheckboxColumn("已結案"),
            "2nd_start": st.column_config.DateColumn("2次起始", format="MM/DD"),
            "2nd_end": st.column_config.DateColumn("2次結束", format="MM/DD"),
            "3rd_start": st.column_config.DateColumn("3次起始", format="MM/DD"),
            "3rd_end": st.column_config.DateColumn("3次結束", format="MM/DD"),
            "return_visit": st.column_config.DateColumn("回診日", format="YYYY/MM/DD"),
            "處方天數": None, "性別": None, "年齡": None # 隱藏欄位
        },
        disabled=["個案姓名", "目前狀態", "2nd_start", "2nd_end", "3rd_start", "3rd_end", "return_visit"],
        use_container_width=True,
        hide_index=True,
        height=500
    )

    # 儲存邏輯
    cols_to_check = ['已領第二次', '已領第三次', '已結案', '個案電話']
    original_check = st.session_state.df[cols_to_check].copy()
    original_check[['已領第二次', '已領第三次', '已結案']] = original_check[['已領第二次', '已領第三次', '已結案']].fillna(False)
    original_check['個案電話'] = original_check['個案電話'].astype(str)
    original_check = original_check.reset_index(drop=True)
    
    new_check = edited_df[cols_to_check].copy()
    new_check[['已領第二次', '已領第三次', '已結案']] = new_check[['已領第二次', '已領第三次', '已結案']].fillna(False)
    new_check['個案電話'] = new_check['個案電話'].astype(str)
    new_check = new_check.reset_index(drop=True)
    
    if not new_check.equals(original_check):
        st.session_state.df.update(edited_df)
        save_data(st.session_state.df)
        st.rerun()

    # --- LINE 推播功能區塊 (給藥師) ---
    st.markdown("<div class='mt-6'></div>", unsafe_allow_html=True)
    
    notify_list = display_df[
        (display_df['目前狀態'].str.contains("🔴", na=False)) & 
        (~display_df['已結案'])
    ]

    with st.expander("📲 LINE 通知小幫手", expanded=True):
        col_line_1, col_line_2 = st.columns([3, 1])
        
        with col_line_1:
            st.write(f"系統偵測：目前共有 **{len(notify_list)}** 位個案需要領藥。")
            if not notify_list.empty:
                st.dataframe(notify_list[['個案姓名', '個案電話', '目前狀態', '2nd_end', '3rd_end']], hide_index=True)
        
        with col_line_2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 發送彙整名單給藥師 (我)", type="primary", use_container_width=True, disabled=notify_list.empty):
                
                current_date = date.today().strftime("%Y/%m/%d")
                msg_body = f"【慢箋領藥提醒彙整】\n日期：{current_date}\n\n以下個案需通知領藥：\n"
                
                for idx, row in enumerate(notify_list.iterrows()):
                    patient = row[1]
                    clean_status = patient['目前狀態'].replace("🔴 ", "")
                    msg_body += f"{idx+1}. {patient['個案姓名']} ({clean_status})\n   電話: {patient['個案電話']}\n"
                
                msg_body += "\n請藥師協助聯繫個案。"
                
                is_sent, log = send_admin_notification(msg_body)
                
                if is_sent:
                    st.toast("✅ 已成功發送至您的 LINE！", icon="🚀")
                else:
                    st.error(f"發送失敗: {log}")

    # 刪除功能
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
