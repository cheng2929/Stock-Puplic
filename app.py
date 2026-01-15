import streamlit as st
import pdfplumber
import pandas as pd
import re
import plotly.express as px
from io import BytesIO

# --- 設定頁面 (公開版) ---
st.set_page_config(page_title="永豐金帳單分析器 (公開版)", page_icon="🚀", layout="wide")

st.title("🚀 永豐金證券 - 月帳單分析工具")
st.markdown("""
### 👋 歡迎使用！
這是一個純前端的分析工具：
1. **隱私安全**：您的 PDF 僅在記憶體中運算，**不會**被儲存或上傳到任何伺服器。
2. **專屬格式**：目前僅支援 **永豐金證券** 的電子月對帳單。
3. **資料帶走**：分析結果提供 Excel/CSV 下載功能。
""")

# --- 側邊欄 ---
with st.sidebar:
    st.header("📂 檔案上傳")
    pdf_password = st.text_input("PDF 密碼", type="password", help="預設通常是身分證字號")
    uploaded_file = st.file_uploader("請上傳月結單 (PDF)", type=["pdf"])
    st.divider()
    st.info("💡 提示：此工具由 Python 社群開發者分享，非永豐金官方軟體。")

# --- 轉換 DataFrame 為 Excel 的函式 ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data

if uploaded_file and pdf_password:
    try:
        with pdfplumber.open(uploaded_file, password=pdf_password) as pdf:
            st.toast("解鎖成功！開始分析...", icon="🔓")
            
            inventory_items = []    # 庫存
            transaction_items = []  # 交易

            # --- 解析核心邏輯 (與原本相同) ---
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or not row[0]: continue
                        
                        full_row_text = " ".join([str(x) for x in row if x is not None])
                        parts = full_row_text.split()

                        # 庫存解析
                        if len(parts) > 5 and parts[0] in ["現股", "融資", "融券"] and "/" not in parts[0]:
                            try:
                                item = {
                                    "代號": parts[1], "名稱": parts[2],
                                    "庫存股數": int(float(parts[3].replace(",", ""))),
                                    "平均成本": float(parts[4].replace(",", "")),
                                    "總成本": int(float(parts[5].replace(",", ""))),
                                    "市價": float(parts[6].replace(",", "")),
                                    "市值": int(float(parts[7].replace(",", "")))
                                }
                                item["未實現損益"] = item["市值"] - item["總成本"]
                                item["報酬率(%)"] = (item["未實現損益"] / item["總成本"] * 100) if item["總成本"] != 0 else 0
                                inventory_items.append(item)
                            except: pass 

                        # 交易解析
                        elif re.match(r"\d{4}/\d{2}/\d{2}", parts[0]):
                            try:
                                date, type_str, name = parts[0], parts[1], parts[2]
                                qty = float(parts[3].replace(",", ""))
                                price = float(parts[4].replace(",", ""))
                                amount = float(parts[5].replace(",", ""))
                                fee = float(parts[6].replace(",", ""))
                                
                                tax = 0.0
                                if "賣" in type_str:
                                    try: tax = float(parts[7].replace(",", ""))
                                    except: pass

                                net_amount = -(amount + fee) if "買" in type_str else (amount - fee - tax)

                                transaction_items.append({
                                    "交易日期": date, "類別": type_str, "名稱": name,
                                    "股數": int(qty), "成交價": price, "成交金額": int(amount),
                                    "手續費": int(fee), "交易稅": int(tax), "淨收付": int(net_amount)
                                })
                            except: pass

            # --- 顯示結果與下載區 ---
            tab1, tab2, tab3 = st.tabs(["📊 庫存資產", "💰 本月交易", "📈 視覺化報告"])

            with tab1:
                if inventory_items:
                    df_inv = pd.DataFrame(inventory_items)
                    
                    # 顯示 KPI
                    c1, c2, c3 = st.columns(3)
                    c1.metric("總市值", f"${df_inv['市值'].sum():,.0f}")
                    c2.metric("總成本", f"${df_inv['總成本'].sum():,.0f}")
                    profit = df_inv['市值'].sum() - df_inv['總成本'].sum()
                    c3.metric("帳面損益", f"${profit:,.0f}")

                    st.dataframe(df_inv, use_container_width=True)
                    
                    # 下載按鈕
                    st.download_button(
                        label="📥 下載庫存清單 (Excel)",
                        data=to_excel(df_inv),
                        file_name='stock_inventory.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                else:
                    st.warning("查無庫存資料")

            with tab2:
                if transaction_items:
                    df_trans = pd.DataFrame(transaction_items)
                    
                    c1, c2 = st.columns(2)
                    c1.metric("本月淨現金流", f"${df_trans['淨收付'].sum():,.0f}")
                    c2.metric("交易筆數", f"{len(df_trans)} 筆")

                    st.dataframe(df_trans, use_container_width=True)

                    # 下載按鈕
                    st.download_button(
                        label="📥 下載交易明細 (Excel)",
                        data=to_excel(df_trans),
                        file_name='stock_transactions.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                else:
                    st.info("本月無交易紀錄")

            with tab3:
                if inventory_items:
                    df_viz = pd.DataFrame(inventory_items)
                    
                    # 視覺化邏輯 (無圖例版)
                    df_pie = df_viz.copy()
                    total_mv = df_pie["市值"].sum()
                    threshold = 0.02
                    large = df_pie[df_pie["市值"]/total_mv >= threshold]
                    small = df_pie[df_pie["市值"]/total_mv < threshold]
                    
                    if not small.empty:
                        others = pd.DataFrame([{"名稱": "其他", "市值": small["市值"].sum()}])
                        df_final = pd.concat([large, others], ignore_index=True)
                    else:
                        df_final = large

                    fig = px.pie(df_final, values='市值', names='名稱', hole=0.45, title='資產配置')
                    fig.update_traces(textposition='outside', textinfo='percent+label')
                    fig.update_layout(showlegend=False, margin=dict(t=50, b=50, l=50, r=50))
                    
                    st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"解析錯誤: {e}")
