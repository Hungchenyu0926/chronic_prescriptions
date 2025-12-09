import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
from streamlit_gsheets import GSheetsConnection

# --- 設定頁面資訊 ---
st.set_page_config(page_title="慢箋領藥提醒系統", layout="wide")

# --- 核心邏輯函數 ---

def calculate_age(born):
    """根據出生年月日計算年齡"""
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def calculate_dates(start_date, duration):
    """
    計算慢箋的各個關鍵日期
    回傳: 字典 (包含所有計算出的日期)
    """
    # 第一次週期結束 (即第二次可領藥的最後一天)
    end_cycle_1 = start_date + timedelta(days=duration)
    
    # 第二次領藥區間 (前10天開始 ~ 週期1結束)
    second_start = end_cycle_1 - timedelta(days=10)
    second_end = end_cycle_1 # 通常領藥期限到藥吃完那天
    
    # 第二次週期結束 (即第三次可領藥的最後一天)
    end_cycle_2 = end_cycle_1 + timedelta(days=duration)
    
    # 第三次領藥區間
    third_start = end_cycle_2 - timedelta(days=10)
    third_end = end_cycle_2
    
    # 建議回診日 (第三次週期結束，藥吃完那天)
    return_visit = end_cycle_2 + timedelta(days=duration)
    
    return {
        "2nd_start": second_start,
        "2nd_end": second_end,
        "3rd_start": third_start,
        "3rd_end": third_end,
        "return_visit": return_visit
    }

def check_status(row):
    """判斷目前的狀態並給予提醒標籤"""
    today = date.today()
    
    # 檢查第二次
    if not row['已領第二次']:
        # 如果今天在 (開始領藥前7天) 到 (結束領藥日) 之間
        remind_start = row['2nd_start'] - timedelta(days=7)
        if remind_start <= today <= row['2nd_end']:
            if today < row['2nd_start']:
                return "⚠️ 即將進入第二次領藥期 (前7天預告)"
            return "🔴 請領取第二次藥物"
        elif today > row['2nd_end']:
            return "❌ 第二次領藥已過期"

    # 檢查第三次 (前提是第二次領了，或者時間到了)
    if not row['已領第三次']:
        remind_start = row['3rd_start'] - timedelta(days=7)
        if remind_start <= today <= row['3rd_end']:
            if today < row['3rd_start']:
                return "⚠️ 即將進入第三次領藥期 (前7天預告)"
            return "🔴 請領取第三次藥物"
        elif today > row['3rd_end'] and row['已領第二次']: # 只有在第二次領過才顯示第三次過期
             return "❌ 第三次領藥已過期"
             
    if row['已領第二次'] and row['已領第三次']:
        if today >= row['return_visit'] - timedelta(days=7):
             return "🏥 建議準備回診"
        return "✅ 完成領藥"
        
    return "一般追蹤中"

# --- 資料處理 ---

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Qu_f2aStXeasb4yW4GsSWTURUnXrIexFSoaDZ13CBME/edit"

def load_data():
    """從 Google Sheets 讀取資料"""
    # 建立連線物件
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 讀取資料，ttl=0 代表不快取，每次都抓最新資料
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="工作表1", ttl=0)
        
        # 如果是空的或欄位不對，處理一下
        if df.empty:
            return pd.DataFrame(columns=[
                '個案姓名', '出生年月日', '性別', '第一次領藥日', 
                '處方天數', '居住里別', '已領第二次', '已領第三次'
            ])
            
        # 轉換日期格式 (Google Sheet 讀下來通常是字串)
        date_cols = ['出生年月日', '第一次領藥日']
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
            
        # 確保布林值欄位正確
        df['已領第二次'] = df['已領第二次'].fillna(False).astype(bool)
        df['已領第三次'] = df['已領第三次'].fillna(False).astype(bool)
            
        return df
    except Exception as e:
        st.error(f"讀取資料失敗: {e}")
        return pd.DataFrame()

def save_data(df):
    """將資料寫回 Google Sheets"""
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # update 方法會直接覆蓋整張工作表內容
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="工作表1", data=df)
        st.toast("資料已儲存至雲端！", icon="☁️") # 顯示一個小通知
    except Exception as e:
        st.error(f"寫入資料失敗: {e}")

# --- 介面設計 (UI) ---

st.title("🏥 慢箋領藥管理與提醒系統")

# 初始化資料
if 'df' not in st.session_state:
    st.session_state.df = load_data()

# 側邊欄：新增個案
with st.sidebar:
    st.header("📝 新增個案資料")
    with st.form("add_patient_form"):
        name = st.text_input("個案姓名")
        dob = st.date_input("出生年月日", min_value=date(1920, 1, 1))
        gender = st.selectbox("性別", ["男", "女"])
        district = st.text_input("居住里別")
        first_date = st.date_input("第一次領藥年月日", value=date.today())
        duration = st.selectbox("處方箋時間", [28, 30])
        
        submitted = st.form_submit_button("新增資料")
        
        if submitted and name:
            new_data = {
                '個案姓名': name,
                '出生年月日': dob,
                '性別': gender,
                '第一次領藥日': first_date,
                '處方天數': duration,
                '居住里別': district,
                '已領第二次': False,
                '已領第三次': False
            }
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
            save_data(st.session_state.df)
            st.success(f"已新增 {name}")

# 主畫面：資料運算與顯示
if not st.session_state.df.empty:
    
    display_df = st.session_state.df.copy()
    
    # 1. 自動計算年齡
    display_df['年齡'] = display_df['出生年月日'].apply(calculate_age)
    
    # 2. 計算所有日期區間
    date_calculations = display_df.apply(
        lambda row: calculate_dates(row['第一次領藥日'], row['處方天數']), axis=1
    )
    
    # 將計算結果展開到 DataFrame
    dates_df = pd.DataFrame(date_calculations.tolist())
    display_df = pd.concat([display_df, dates_df], axis=1)
    
    # 3. 產生提醒狀態
    display_df['目前狀態'] = display_df.apply(check_status, axis=1)
    
    # 4. 顯示重點提醒區塊 (Dashboard)
    st.subheader("🔔 需要關注的名單 (前一週提醒)")
    urgent_cases = display_df[display_df['目前狀態'].str.contains("🔴|⚠️|🏥")]
    
    if not urgent_cases.empty:
        st.warning(f"共有 {len(urgent_cases)} 位個案需要通知！")
        # 精簡顯示重點欄位
        st.dataframe(
            urgent_cases[['個案姓名', '目前狀態', '2nd_start', '2nd_end', '3rd_start', '3rd_end', '居住里別']],
            use_container_width=True
        )
    else:
        st.info("目前沒有需要緊急通知的個案。")

    st.markdown("---")
    
    # 5. 完整資料管理與編輯
    st.subheader("📋 所有個案資料管理")
    st.caption("您可以直接在下方表格勾選「已領藥」來更新狀態")
    
    # 使用 data_editor 讓使用者可以直接編輯 Checkbox
    edited_df = st.data_editor(
        display_df,
        column_config={
            "已領第二次": st.column_config.CheckboxColumn("已領第二次", help="勾選代表已完成領藥"),
            "已領第三次": st.column_config.CheckboxColumn("已領第三次", help="勾選代表已完成領藥"),
            "出生年月日": None, # 隱藏原始欄位，只看年齡
            "2nd_start": st.column_config.DateColumn("2次起始", format="MM/DD"),
            "2nd_end": st.column_config.DateColumn("2次結束", format="MM/DD"),
            "3rd_start": st.column_config.DateColumn("3次起始", format="MM/DD"),
            "3rd_end": st.column_config.DateColumn("3次結束", format="MM/DD"),
            "return_visit": st.column_config.DateColumn("建議回診", format="YYYY/MM/DD"),
        },
        disabled=["個案姓名", "年齡", "目前狀態", "2nd_start", "2nd_end", "3rd_start", "3rd_end", "return_visit"], # 禁止編輯計算欄位
        use_container_width=True,
        hide_index=True
    )
    
    # 檢查是否有更動，若有則存檔
    # 比對原始 checkbox 狀態與編輯後的狀態
    cols_to_check = ['已領第二次', '已領第三次']
    if not edited_df[cols_to_check].equals(st.session_state.df[cols_to_check]):
        # 更新 session_state
        st.session_state.df['已領第二次'] = edited_df['已領第二次']
        st.session_state.df['已領第三次'] = edited_df['已領第三次']
        # 存入檔案 (CSV 或 Google Sheets)
        save_data(st.session_state.df)
        st.rerun() # 重新整理頁面以更新「目前狀態」

else:
    st.info("目前尚無資料，請從左側新增個案。")
