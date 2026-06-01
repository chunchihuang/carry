import streamlit as st
import psychrolib as psy
import plotly.graph_objects as go
import numpy as np

# 設定 Psychrolib 使用 SI 公制單位
psy.SetUnitSystem(psy.SI)

st.set_page_config(page_title="現代化空氣線圖 (動態縮放版)", layout="wide")
st.title("現代化空氣線圖 (自動動態縮放版)")

# ==========================================
# 上半部：控制面板
# ==========================================
st.markdown("### ⚙️ 參數輸入區")
col_p, col_mode, col_p1, col_p2 = st.columns(4)

with col_p:
    P = st.number_input("大氣壓力 (Pa)", value=101325.0, step=500.0)
with col_mode:
    calc_mode = st.selectbox("選擇輸入模式", ["乾球 + 相對溼度", "乾球 + 溼球", "乾球 + 露點"])
with col_p1:
    db_temp = st.number_input("乾球溫度 (°C)", value=25.0, step=0.5, min_value=-50.0, max_value=200.0)
with col_p2:
    if calc_mode == "乾球 + 相對溼度":
        rh_input = st.number_input("相對溼度 (%)", value=50.0, step=1.0, min_value=0.0, max_value=100.0)
    elif calc_mode == "乾球 + 溼球":
        wb_temp = st.number_input("溼球溫度 (°C)", value=18.0, step=0.5, max_value=db_temp)
    else:
        TDewPoint = st.number_input("露點溫度 (°C)", value=14.0, step=0.5, max_value=db_temp)

# ==========================================
# 計算熱力學參數
# ==========================================
rh_display, W, wb_temp_out, TDewPoint_out, H, V = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

try:
    if calc_mode == "乾球 + 相對溼度":
        rh = rh_input / 100.0
        W, TDewPoint_out, _, _, H, V, _ = psy.CalcPsychrometricsFromRelHum(db_temp, rh, P)
        wb_temp_out = psy.GetTWetBulbFromRelHum(db_temp, rh, P)
        rh_display = rh_input
    elif calc_mode == "乾球 + 溼球":
        W, TDewPoint_out, rh, _, H, V, _ = psy.CalcPsychrometricsFromTWetBulb(db_temp, wb_temp, P)
        wb_temp_out = wb_temp
        rh_display = rh * 100.0
    else:
        W, _, rh, _, H, V, _ = psy.CalcPsychrometricsFromTDewPoint(db_temp, TDewPoint, P)
        wb_temp_out = psy.GetTWetBulbFromTDewPoint(db_temp, TDewPoint, P)
        TDewPoint_out = TDewPoint
        rh_display = rh * 100.0
        
except Exception as e:
    st.error(f"數值計算超出物理極限或不合理！\n系統訊息：{e}")

# ==========================================
# 下半部：繪製 Plotly 圖表
# ==========================================
st.markdown("---")

if W > 0:
    fig = go.Figure()
    
    # ------------------------------------------
    # 【動態縮放邏輯 Auto-Scaling】
    # 基準顯示範圍：X軸(0~45°C), Y軸(0~32 g/kg)
    # 若輸入值超出，自動向外擴張邊界，確保畫面完美包覆狀態點
    # ------------------------------------------
    view_x_min = min(0.0, db_temp - 5.0)
    view_x_max = max(45.0, db_temp + 10.0)
    view_y_max = max(32.0, (W * 1000) * 1.5)
    
    # 為了讓線條畫滿邊緣，實際計算範圍要比顯示範圍稍大一點
    calc_x_max = view_x_max + 5.0
    T_range = np.linspace(view_x_min, calc_x_max, 300)
    
    # 1. 繪製背景網格線 (等溼球溫度線)
    # 動態決定溼球溫度的繪製間距 (低溫密一點，高溫疏一點)
    wb_step = 5 if view_x_max <= 60 else 10
    wb_start = int(view_x_min / wb_step) * wb_step
    
    for wb_val in range(wb_start, int(calc_x_max), wb_step):
        t_db_arr = np.linspace(wb_val, calc_x_max, 50) 
        w_arr = []
        valid_t = []
        for t in t_db_arr:
            try:
                w_val = psy.CalcPsychrometricsFromTWetBulb(t, wb_val, P)[0] * 1000
                if 0 <= w_val <= view_y_max * 1.2: 
                    w_arr.append(w_val)
                    valid_t.append(t)
            except:
                pass
        
        if valid_t:
            fig.add_trace(go.Scatter(
                x=valid_t, y=w_arr, 
                mode='lines', line=dict(color='#d4edda', width=1), 
                showlegend=False, hoverinfo='skip'
            ))
            # 標籤放在飽和線上
            fig.add_annotation(
                x=valid_t[0], y=w_arr[0],
                text=f"{wb_val}°C",
                showarrow=False,
                xanchor='right', yanchor='bottom',
                font=dict(color='#28a745', size=10),
                xshift=-2, yshift=2
            )

    # 2. 繪製背景網格線 (10% ~ 90% 相對溼度線)
    for rh_pct in range(10, 100, 10):
        rh_val = rh_pct / 100.0
        w_curve = []
        valid_t_rh = []
        for t in T_range:
            try:
                w_val = psy.CalcPsychrometricsFromRelHum(t, rh_val, P)[0] * 1000
                w_curve.append(w_val)
                valid_t_rh.append(t)
            except:
                pass

        if valid_t_rh:
            fig.add_trace(go.Scatter(
                x=valid_t_rh, y=w_curve, 
                mode='lines', line=dict(color='#b8d4f2', width=1.5), 
                name=f'RH {rh_pct}%',
                hovertemplate=f'RH: {rh_pct}%<br>乾球: %{{x:.1f}}°C<br>絕對溼度: %{{y:.1f}} g/kg<extra></extra>'
            ))
            
            # 動態找尋標籤位置 (不能超過當前 Y 軸上限)
            valid_label_points = [(t, w) for t, w in zip(valid_t_rh, w_curve) if w <= view_y_max * 0.95]
            if valid_label_points:
                last_t, last_w = valid_label_points[-1]
                x_anchor = 'left' if last_t >= (view_x_max - 2) else 'right'
                fig.add_annotation(
                    x=last_t, y=last_w, text=f"{rh_pct}%", showarrow=False,
                    xanchor=x_anchor, yanchor='bottom', font=dict(color='#82aadd', size=11),
                    xshift=5 if x_anchor == 'left' else -5
                )

    # 3. 繪製 100% 飽和曲線 (粗藍線)
    w_sat = []
    valid_t_sat = []
    for t in T_range:
        try:
            w_val = psy.CalcPsychrometricsFromRelHum(t, 1.0, P)[0] * 1000
            w_sat.append(w_val)
            valid_t_sat.append(t)
        except:
            pass
            
    fig.add_trace(go.Scatter(
        x=valid_t_sat, y=w_sat, 
        mode='lines', line=dict(color='#0d6efd', width=3), 
        name='飽和曲線 (100% RH)'
    ))

    # 4. 繪製當前狀態點的三大指標線
    # (A) 露點 / 絕對溼度 (水平虛線)
    fig.add_trace(go.Scatter(
        x=[TDewPoint_out, calc_x_max], y=[W*1000, W*1000], 
        mode='lines', line=dict(color='gray', width=1, dash='dash'), 
        showlegend=False, hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=[TDewPoint_out], y=[W*1000], 
        mode='markers+text', marker=dict(color='green', size=8), 
        text=[f'露點: {TDewPoint_out:.1f}°C'], textposition='middle left', 
        name='露點', hoverinfo='skip'
    ))

    # (B) 乾球溫度 (垂直虛線)
    fig.add_trace(go.Scatter(
        x=[db_temp, db_temp], y=[0, W*1000], 
        mode='lines', line=dict(color='gray', width=1, dash='dash'), 
        showlegend=False, hoverinfo='skip'
    ))

    # (C) 溼球溫度 (傾斜虛線)
    t_db_wb_line = np.linspace(wb_temp_out, calc_x_max, 50)
    w_wb_line = []
    valid_t_wb = []
    for t in t_db_wb_line:
        try:
            w_val = psy.CalcPsychrometricsFromTWetBulb(t, wb_temp_out, P)[0] * 1000
            if w_val >= 0:
                w_wb_line.append(w_val)
                valid_t_wb.append(t)
        except:
            pass
    
    if valid_t_wb:
        fig.add_trace(go.Scatter(
            x=valid_t_wb, y=w_wb_line, 
            mode='lines', line=dict(color='#ff7f0e', width=1.5, dash='dash'), 
            showlegend=False, hoverinfo='skip'
        ))
        fig.add_trace(go.Scatter(
            x=[wb_temp_out], y=[w_wb_line[0]], 
            mode='markers+text', marker=dict(color='#ff7f0e', size=8), 
            text=[f'溼球: {wb_temp_out:.1f}°C'], textposition='top left', 
            name='溼球', hoverinfo='skip'
        ))

    # 當前狀態點標記 (大藍點)
    fig.add_trace(go.Scatter(
        x=[db_temp], y=[W*1000], 
        mode='markers+text', marker=dict(color='royalblue', size=12, line=dict(color='white', width=2)), 
        text=['狀態點'], textposition='top right', 
        name='當前狀態點', hoverinfo='skip'
    ))

    # 5. 圖表版面設定 (套用動態範圍 range)
    fig.update_layout(
        plot_bgcolor='white',
        height=600,
        margin=dict(l=20, r=60, t=30, b=50), 
        xaxis=dict(
            showgrid=True, gridcolor='#f2f2f2', zeroline=False,
            range=[view_x_min, view_x_max], # 動態設定 X 軸可視範圍
            showticklabels=True,
            title='乾球溫度 (°C)'
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#f2f2f2', zeroline=False,
            range=[0, view_y_max], # 動態設定 Y 軸可視範圍
            side='right',
            title='絕對溼度 (g/kg)',
            ticksuffix=' g/kg'
        ),
        showlegend=True,
        legend=dict(
            orientation='h', yanchor='bottom', y=0.03, xanchor='left', x=0.03,
            bgcolor='rgba(248, 249, 250, 0.9)', bordercolor='#e9ecef', borderwidth=1
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    # 圖表下方的數據面板
    st.markdown("<hr style='margin-top: 0px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    with col1:
        st.markdown(f"<div style='text-align: center; color: #555;'>乾球溫度<br><br><b style='font-size: 1.2em;'>{db_temp:.1f} °C</b></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align: center; color: #ff7f0e;'>溼球溫度<br><br><b style='font-size: 1.2em;'>{wb_temp_out:.1f} °C</b></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div style='text-align: center; color: #28a745;'>露點溫度<br><br><b style='font-size: 1.2em;'>{TDewPoint_out:.1f} °C</b></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div style='text-align: center; color: #555;'>相對溼度<br><br><b style='font-size: 1.2em;'>{rh_display:.0f} %</b></div>", unsafe_allow_html=True)
    with col5:
        st.markdown(f"<div style='text-align: center; color: #555;'>絕對溼度<br><br><b style='font-size: 1.2em;'>{W*1000:.2f} g/kg</b></div>", unsafe_allow_html=True)
    with col6:
        st.markdown(f"<div style='text-align: center; color: #555;'>焓值<br><br><b style='font-size: 1.2em;'>{H/1000:.1f} kJ/kg</b></div>", unsafe_allow_html=True)
    with col7:
        st.markdown(f"<div style='text-align: center; color: #555;'>大氣壓力<br><br><b style='font-size: 1.2em;'>{int(P)} Pa</b></div>", unsafe_allow_html=True)