import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai

# ==========================================
# 1. 페이지 및 디자인 기본 설정
# ==========================================
st.set_page_config(page_title="영등포시장 상권 분석 대시보드", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .reportview-container { background: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    h1, h2, h3 { color: #2C3E50; font-family: 'Pretendard', sans-serif; }
    .outlier-box-1 { background-color: #ffeaea; padding: 15px; border-radius: 8px; border-left: 5px solid #ff4b4b; margin-bottom: 10px; }
    .outlier-box-5 { background-color: #eafaf1; padding: 15px; border-radius: 8px; border-left: 5px solid #2ecc71; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# API 키 세팅 (Streamlit Secrets 활용)
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("API 키 설정에 문제가 있습니다. Streamlit Secrets 설정을 확인해 주세요.")

# ==========================================
# 2. 데이터 불러오기 및 전처리 (구글 시트 연동)
# ==========================================
@st.cache_data(ttl=600)
def load_data():
    GOOGLE_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSY59eppT8mU0O94FXc8vO9lRIf126sIRVbxhD30rMSVJeu-WTvAPDwXupJcZq9ZHHyHoM76U9sl73X/pub?gid=2099030146&single=true&output=csv"

    try:
        df = pd.read_csv(GOOGLE_SHEET_CSV_URL, encoding='utf-8')
    except Exception as e:
        st.error(f"구글 시트를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame(), []

    # [수정 1] 구글 폼 항목 이름의 앞뒤 공백을 제거하여 버그 방지
    df.columns = df.columns.str.strip()

    col_mapping = {
        '타임스탬프': '일시',
        'Q4. 오늘 방문하여 이용하신 점포(가게)의 이름은 무엇입니까? (장문형 또는 단답형)': '가게명',
        'Q6. 해당 점포의 상품(음식, 제품 등)의 품질과 맛/상태에 얼마나 만족하셨습니까?': '만족도(품질/맛)',
        'Q7. 해당 점포의 가격대는 상품의 가치 대비 적절하다고 느끼셨습니까?': '가격 적절성',
        'Q8. 해당 점포 사장님 및 직원분의 안내와 응대는 친절했습니까?': '친절도',
        'Q8. 해당 점포 내부의 청결도, 위생 상태 및 상품 진열(디스플레이)은 만족스러웠습니까?': '청결도/위생',
        'Q9. 해당 점포를 이용할 때 결제 방식(카드 결제 가능 여부, 온누리상품권 사용, 가격 정찰제 등)에 불편함이 없으셨습니까?': '결제 편의성',
        'Q10. 이 가게(점포)만의 가장 큰 매력이나 장점은 무엇이라고 생각하십니까?': '주관식(장점)',
        "Q10. [AI 리포트 연계] 해당 점포의 사장님께 전하고 싶은 '칭찬'이나 꼭 개선되었으면 하는 '매장 운영 꿀팁'을 자유롭게 한 줄 이상 적어주세요. (장문형)": '주관식(피드백)'
    }

    rename_dict = {k: v for k, v in col_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    ordinal_cols = ['만족도(품질/맛)', '가격 적절성', '친절도', '청결도/위생', '결제 편의성']

    for col in ordinal_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if '가게명' in df.columns:
        df['가게명'] = df['가게명'].astype(str).str.strip()

    if '일시' in df.columns:
        df['일시'] = pd.to_datetime(df['일시'], errors='coerce')
        df['월별'] = df['일시'].dt.strftime('%Y-%m')

    return df, ordinal_cols

df, ordinal_cols = load_data()

# ==========================================
# 3. 사이드바 네비게이션
# ==========================================
st.sidebar.title("📊 분석 메뉴")
page = st.sidebar.radio("원하시는 페이지를 선택하세요",
                        ["1️⃣ 월별 & 점포별 개별 분석", "2️⃣ 누적 전체 데이터 추이"])

if df.empty:
    st.error("데이터 파일에 응답 내용이 비어있습니다. 응답을 먼저 수집해 주세요.")
    st.stop()

# ==========================================
# 4. 페이지 1: 월별 & 점포별 개별 분석 페이지
# ==========================================
if page == "1️⃣ 월별 & 점포별 개별 분석":
    st.title("🏪 특정 달 & 점포별 결과 분석")
    st.markdown("선택한 월과 매장의 **평균 만족도**와 **1점/5점 특이점 리뷰**를 집중 분석합니다.")

    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        month_list = ["전체 기간"] + sorted(list(df['월별'].dropna().unique()))
        selected_month = st.selectbox("📅 분석할 달(Month)을 선택하세요", month_list)
    with col_filter2:
        temp_df = df if selected_month == "전체 기간" else df[df['월별'] == selected_month]
        store_list = ["전체 매장 보기"] + sorted(list(temp_df['가게명'].dropna().unique()))
        selected_store = st.selectbox("🏪 매장(가게)을 선택하세요", store_list)

    if selected_store != "전체 매장 보기":
        target_df = temp_df[temp_df['가게명'] == selected_store]
    else:
        target_df = temp_df

    if len(target_df) == 0:
        st.warning("선택하신 조건에 해당하는 데이터가 없습니다.")
    else:
        st.markdown("---")
        
        # [수정 4] 차트와 피드백을 한눈에 깔끔하게 보기 위한 탭 분리 적용
        tab1, tab2 = st.tabs(["📊 차트 및 종합 점수", "💬 상세 고객 피드백 내역"])
        
        with tab1:
            st.subheader("핵심 평가 항목 평균 (1~5점 척도)")
            avg_scores = target_df[ordinal_cols].mean().round(1)

            cols = st.columns(len(ordinal_cols))
            for i, col in enumerate(ordinal_cols):
                with cols[i]:
                    st.metric(label=col, value=f"{avg_scores[col]:.1f}점" if pd.notnull(avg_scores[col]) else "데이터 없음")

            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=avg_scores.values,
                theta=avg_scores.index,
                fill='toself',
                name=selected_store,
                line_color='#2980b9'
            ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
                showlegend=False,
                height=400
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        with tab2:
            st.subheader("특이점 분석 (1점 및 5점 피드백 모아보기)")

            is_5_star = (target_df[ordinal_cols] == 5).any(axis=1)
            df_5 = target_df[is_5_star]

            is_1_star = (target_df[ordinal_cols] == 1).any(axis=1)
            df_1 = target_df[is_1_star]

            col_feedback1, col_feedback2 = st.columns(2)

            with col_feedback1:
                st.markdown("### 😍 매우 긍정적 피드백 (항목 중 5점 포함)")
                if len(df_5) > 0:
                    for idx, row in df_5.iterrows():
                        feedback_text = row.get('주관식(피드백)', '')
                        merit_text = row.get('주관식(장점)', '')

                        if pd.notnull(feedback_text) or pd.notnull(merit_text):
                            st.markdown(f"""
                            <div class="outlier-box-5">
                                <strong>가게명:</strong> {row['가게명']}<br>
                                <strong>장점:</strong> {merit_text if pd.notnull(merit_text) else '-'}<br>
                                <strong>피드백:</strong> {feedback_text if pd.notnull(feedback_text) else '-'}
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("5점이 포함된 응답 내역이 없습니다.")

            with col_feedback2:
                st.markdown("### 🚨 매우 부정적 피드백 (항목 중 1점 포함)")
                if len(df_1) > 0:
                    for idx, row in df_1.iterrows():
                        feedback_text = row.get('주관식(피드백)', '')

                        if pd.notnull(feedback_text):
                            st.markdown(f"""
                            <div class="outlier-box-1">
                                <strong>가게명:</strong> {row['가게명']}<br>
                                <strong>개선요청:</strong> {feedback_text}
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("1점이 포함된 응답 내역이 없습니다. (훌륭합니다!)")

        # ----------------------------------------
        # AI 리뷰 통합 요약 (Gemini) - 방어 코드 및 캐싱 적용
        # ----------------------------------------
        st.markdown("---")
        st.subheader("🤖 AI 리뷰 통합 요약 (Gemini)")

        # [수정 3] API 호출을 최소화하기 위한 캐싱 함수 정의 (1시간 유지)
        @st.cache_data(ttl=3600, show_spinner=False)
        def get_ai_summary(store_name, review_text):
            # [수정 2] '영차' 페르소나 및 고령 상인 맞춤형 3단계 프롬프트 고도화
            prompt = f"""
            당신은 전통시장 소상공인을 돕는 AI 경영 컨설턴트 '영차'입니다. 
            아래는 영등포시장 '{store_name}' 매장에 쌓인 고객들의 실제 주관식 리뷰 데이터입니다. 
            전통시장 특성상 고령의 사장님들이 읽으실 확률이 높으므로, 어렵고 전문적인 경영 용어는 배제하고 따뜻하고 명확한 문체로 다음 3가지 내용을 작성해 주세요.

            1. [👍 이번 달 잘한 점] 사장님이 힘내실 수 있도록 손님들이 극찬한 매력을 구체적으로 칭찬해 주세요.
            2. [💡 손님 대응 꿀팁 및 개선점] 손님들이 아쉬워한 부분을 바탕으로, 당장 매장에서 실천할 수 있는 현실적인 개선 팁을 제안해 주세요.
            3. [✍️ 추천 홍보 문구 또는 리뷰 답글] 인스타그램에 올리거나 손님에게 보낼 수 있는 친절한 인사/홍보 문구를 하나 작성해 주세요.

            리뷰 데이터: {review_text}
            """
            response = model.generate_content(prompt)
            return response.text

        reviews_combined = " ".join(target_df['주관식(피드백)'].dropna().astype(str).tolist()).strip()

        # 세션 상태 초기화 및 관리
        summary_key = f"summary_{selected_store}_{selected_month}"
        
        if summary_key not in st.session_state:
            st.session_state[summary_key] = None

        if len(reviews_combined) > 10:
            if st.session_state[summary_key] is None:
                if st.button("✨ 현재 매장의 AI 경영 리포트 생성하기", key=f"btn_{summary_key}"):
                    with st.spinner("AI 컨설턴트 '영차'가 리뷰를 꼼꼼히 분석하고 있습니다..."):
                        try:
                            ai_result = get_ai_summary(selected_store, reviews_combined)
                            st.session_state[summary_key] = ai_result
                            st.rerun() 
                        except Exception as e:
                            st.error(f"요약 중 오류가 발생했습니다 (분당 호출 제한일 수 있습니다): {e}")
            else:
                st.success("✅ 이번 달 AI 분석 리포트가 완료되었습니다!")
                st.info("💡 본 리포트는 API 사용량 절약을 위해 1시간 동안 유지되며, 구글 폼에 새 데이터가 쌓이면 자동으로 업데이트됩니다.")
                st.write(st.session_state[summary_key])
                
                if st.button("🔄 리포트 새로고침 (API 재호출)", help="구글 폼에 새로운 응답이 실시간으로 추가되었을 때만 누르세요."):
                    st.session_state[summary_key] = None
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.warning("⚠️ 요약할 주관식 피드백 데이터가 부족합니다. (최소 10자 이상 필요)")

# ==========================================
# 5. 페이지 2: 누적 전체 데이터 추이 페이지
# ==========================================
elif page == "2️⃣ 누적 전체 데이터 추이":
    st.title("📈 누적 전체 데이터 & 트렌드 분석")
    st.markdown("전체 가게들의 누적 점수 비교와, 기간별(월별) 평균 점수 변화 추이를 확인합니다.")

    st.markdown("---")
    st.subheader("🏆 전체 가게별 평가 항목 평균 비교")

    if len(df) > 0:
        store_avg = df.groupby('가게명')[ordinal_cols].mean().reset_index()
        store_avg['종합 평균'] = store_avg[ordinal_cols].mean(axis=1)
        store_avg = store_avg.sort_values('종합 평균', ascending=False)

        st.dataframe(
            store_avg.style.format(precision=1).background_gradient(cmap='YlGn', axis=None,
                                                                    subset=ordinal_cols + ['종합 평균']),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")
        st.subheader("📅 월별 평점 변화 추이 (전체 매장 평균)")

        if df['월별'].nunique() > 0:
            trend_df = df.groupby('월별')[ordinal_cols].mean().reset_index()

            fig_trend = px.line(
                trend_df,
                x='월별',
                y=ordinal_cols,
                markers=True,
                title="시간 흐름에 따른 주요 평가 항목 변화",
                labels={'value': '평균 점수', 'variable': '평가 항목'}
            )
            fig_trend.update_layout(yaxis=dict(range=[0, 5.5]))
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("날짜(타임스탬프) 데이터가 부족하여 트렌드를 그릴 수 없습니다.")
    else:
        st.warning("분석할 데이터가 존재하지 않습니다.")
