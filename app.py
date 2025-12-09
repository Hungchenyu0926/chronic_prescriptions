import streamlit as st
import pandas as pd
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection

# --- 設定頁面資訊 ---
st.set_page_config(page_title="慢箋領藥提醒系統", layout="wide")

# --- 核心邏輯函數 ---

def calculate_age(born):
    """根據出生年月日計算年齡"""
    if not born: return 0
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def calculate_dates(start_date, duration):
    """
    計算慢箋的各個關鍵日期
    """
    if not start_date:
        return {}

    # 1. 第一次週期結束
    end_cycle_1 = start_date + timedelta(days=duration)
    
    # 2. 第二次領藥區間 (結束日往前推9天，共10天區間)
    second_start = end_cycle_1 - timedelta(days=9)
    second_end = end_cycle_1 
    
    # 3. 第二次週期結束
    end_cycle_2 = end_cycle_1 + timedelta(days=duration)
    
    # 4. 第三次領藥區間
    third_start = end_cycle_2 - timedelta(days=9)
    third_end = end_cycle_2
    
    # 5. 建議回診日 (藥吃完的隔天)
    end_cycle_3 = end_cycle_2 + timedelta(days=duration)
    return_visit = end_cycle_3 + timedelta(days=1)
    
    return {
        "2nd_start": second_start,
        "2nd_end": second_end,
        "3rd_start": third_start,
        "3rd_end": third_end,
        "return_visit": return_visit
    }

def check_status(row):
    """判斷目前的狀態並給予提醒標籤"""
    if pd.isna(row['第一次領藥日']):
        return "資料不全"

    today = date.today()
    
    # 檢查第二次
    if not row['已領第二次']:
        remind_start = row['2nd_start'] - timedelta(days=7)
        if remind_start <= today <= row['2nd_end']:
            if today < row['2nd_start']:
                return "⚠️ 即將進入第二次領藥期 (前7天預告)"
            return "🔴 請領取第二次藥物"
        elif today > row['2nd_end']:
            return "❌ 第二次領藥已過期"

    # 檢查第三次
    if not row['已領第三次']:
        remind_start = row['3rd_start'] - timedelta(days=7)
        if remind_start <= today <= row['3rd_end']:
            if today < row['3rd_start']:
                return "⚠️ 即將進入第三次領藥期 (前7天預告)"
            return "🔴 請領取第三次藥物"
        elif today > row['3rd_end'] and row['已領第二次']:
             return "❌ 第三次領藥已過期"
             
    if row['已領第二次'] and row['已領第三次']:
        if today >= row['return_visit'] - timedelta(days=7):
             return "🏥 建議準備回診"
        return "✅ 完成領藥"
        
    return "一般追蹤中"

# --- 資料處理 (Google Sheets) ---

# 請確保您的 Secrets 設定正確
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Qu_f2aStXeasb4yW4GsSWTURUnXrIexFSoaDZ13CBME/edit?hl=zh-TW&gid=0#gid=0"

def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="工作表1", ttl=0)
        
        if df.empty:
            return pd.DataFrame(columns=[
                '個案姓名', '出生年月日', '性別', '第一次領藥日', 
                '處方天數', '居住里別', '已領第二次', '已領第三次'
            ])
            
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

# --- 介面設計 (UI) ---

st.title("🏥 慢箋領藥管理與提醒系統")

if 'df' not in st.session_state:
    st.session_state.df = load_data()

# ==========================================
# 側邊欄：新增與刪除功能
# ==========================================
with st.sidebar:
    st.header("📝 新增個案資料")
    with st.form("add_patient_form"):
        name = st.text_input("個案姓名")
        dob = st.date_input("出生年月日", min_value=date(1920, 1, 1), value=date(1960, 1, 1))
        gender = st.selectbox("性別", ["男", "女"])
        district = st.text_input("居住里別")
        first_date = st.date_input("第一次領藥年月日", value=date.today())
        duration = st.selectbox("處方箋時間", [28, 30], index=0)
        
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
            new_df = pd.DataFrame([new_data])
            st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True)
            save_data(st.session_state.df)
            st.success(f"已新增 {name}")
            st.rerun()

    st.markdown("---")
    
    # --- 新增的刪除功能區塊 ---
    with st.expander("🗑️ 刪除個案功能"):
        if not st.session_state.df.empty:
            # 取得所有姓名列表
            patient_list = st.session_state.df['個案姓名'].tolist()
            # 讓使用者選擇要刪除的名字 (支援多選)
            patients_to_delete = st.multiselect("請選擇要刪除的姓名", patient_list)
            
            if st.button("確認刪除", type="primary"):
                if patients_to_delete:
                    # 邏輯: 保留「不在」刪除名單中的資料
                    st.session_state.df = st.session_state.df[
                        ~st.session_state.df['個案姓名'].isin(patients_to_delete)
                    ]
                    # 存檔並重整
                    save_data(st.session_state.df)
                    st.success(f"已刪除: {', '.join(patients_to_delete)}")
                    st.rerun()
                else:
                    st.warning("請先選擇要刪除的對象")
        else:
            st.info("目前無資料可刪除")

# ==========================================
# 主畫面：資料運算與顯示
# ==========================================
if not st.session_state.df.empty:
    
    display_df = st.session_state.df.copy()
    
    # 1. 自動計算年齡
    display_df['年齡'] = display_df['出生年月日'].apply(calculate_age)
    
    # 2. 計算所有日期區間
    display_df['第一次領藥日'] = pd.to_datetime(display_df['第一次領藥日']).dt.date

    date_calculations = display_df.apply(
        lambda row: calculate_dates(row['第一次領藥日'], row['處方天數']), axis=1
    )
    
    dates_df = pd.DataFrame(date_calculations.tolist())
    display_df = display_df.reset_index(drop=True)
    dates_df = dates_df.reset_index(drop=True)
    display_df = pd.concat([display_df, dates_df], axis=1)
    
    # 3. 產生提醒狀態
    display_df['目前狀態'] = display_df.apply(check_status, axis=1)
    
    # 4. 顯示重點提醒區塊
    st.subheader("🔔 需要關注的名單 (前一週提醒)")
    urgent_cases = display_df[display_df['目前狀態'].str.contains("🔴|⚠️|🏥", na=False)]
    
    if not urgent_cases.empty:
        st.warning(f"共有 {len(urgent_cases)} 位個案需要通知！")
        st.dataframe(
            urgent_cases[['個案姓名', '目前狀態', '2nd_start', '2nd_end', '3rd_start', '3rd_end', '居住里別']],
            use_container_width=True
        )
    else:
        st.info("目前沒有需要緊急通知的個案。")

    st.markdown("---")
    
    # 5. 完整資料管理與編輯
    st.subheader("📋 所有個案資料管理")
    
    edited_df = st.data_editor(
        display_df,
        column_config={
            "已領第二次": st.column_config.CheckboxColumn("已領2次", help="勾選代表已完成"),
            "已領第三次": st.column_config.CheckboxColumn("已領3次", help="勾選代表已完成"),
            "出生年月日": None, 
            "2nd_start": st.column_config.DateColumn("2次起始", format="MM/DD"),
            "2nd_end": st.column_config.DateColumn("2次結束", format="MM/DD"),
            "3rd_start": st.column_config.DateColumn("3次起始", format="MM/DD"),
            "3rd_end": st.column_config.DateColumn("3次結束", format="MM/DD"),
            "return_visit": st.column_config.DateColumn("建議回診", format="YYYY/MM/DD"),
        },
        disabled=["個案姓名", "年齡", "目前狀態", "2nd_start", "2nd_end", "3rd_start", "3rd_end", "return_visit"],
        use_container_width=True,
        hide_index=True
    )
    
    # 檢查並儲存更動
    cols_to_check = ['已領第二次', '已領第三次']
    original_check = st.session_state.df[cols_to_check].fillna(False).reset_index(drop=True)
    new_check = edited_df[cols_to_check].fillna(False).reset_index(drop=True)
    
    if not new_check.equals(original_check):
        st.session_state.df['已領第二次'] = edited_df['已領第二次']
        st.session_state.df['已領第三次'] = edited_df['已領第三次']
        save_data(st.session_state.df)
        st.rerun()

else:
    st.info("目前尚無資料，請從左側新增個案。")
