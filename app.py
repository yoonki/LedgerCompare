import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# ============================================================================
# 설정: 페이지 configuration
# ============================================================================
st.set_page_config(
    page_title="거래 비교 분석 시스템",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# 유틸리티 함수들 (데이터 처리 및 형식 변환)
# ============================================================================

def extract_date(date_string):
    """
    날짜 문자열에서 YYYY/MM/DD 부분만 추출

    입력 예시: "2022/01/03 -13" → "2022/01/03"
    NaN이나 빈 값이면 NaT 반환

    Args:
        date_string: 날짜 문자열

    Returns:
        datetime 객체 또는 NaT
    """
    # NaN이나 None 체크
    if pd.isna(date_string) or date_string == "":
        return pd.NaT

    # 문자열 변환
    date_string = str(date_string).strip()

    # 공백으로 분할하여 첫 번째 부분만 추출
    date_part = date_string.split()[0] if date_string else None

    if not date_part:
        return pd.NaT

    try:
        # datetime 객체로 변환
        return pd.to_datetime(date_part, format="%Y/%m/%d")
    except:
        return pd.NaT


def clean_amount(value):
    """
    금액 문자열을 숫자로 변환

    입력 예시: "1,000,000" 또는 1000000 또는 NaN
    쉼표 제거, 공백 제거, 숫자로 변환

    Args:
        value: 금액 값 (문자열 또는 숫자)

    Returns:
        float 숫자 (변환 불가시 0)
    """
    # NaN 체크
    if pd.isna(value) or value == "":
        return 0.0

    # 문자열로 변환 후 쉼표와 공백 제거
    value_str = str(value).strip().replace(",", "")

    try:
        return float(value_str)
    except:
        return 0.0


def format_currency(amount):
    """
    숫자를 천 단위 쉼표가 포함된 문자열로 형식화

    입력 예시: 1234567 → "1,234,567"

    Args:
        amount: 숫자

    Returns:
        천 단위 쉼표가 포함된 문자열
    """
    if pd.isna(amount) or amount == 0:
        return "0"
    return f"{int(amount):,}"


def load_and_prepare_data(file_path):
    """
    엑셀 파일을 읽어서 데이터를 전처리

    1. 4행부터 데이터 읽기 (0-3행은 헤더/제목)
    2. 컬럼명 설정
    3. 날짜 추출 및 NaN 행 제외
    4. 금액 데이터 정제

    파일 구조:
    - 0열: 일자
    - 1열: 적요 (제품명)
    - 2열: 판매 (채권판매)
    - 3열: 수금 (채권수금)
    - 4열: 구매 (채무구매)
    - 5열: 지급 (채무지급)
    - 6열: 잔액

    Args:
        file_path: 엑셀 파일 경로

    Returns:
        전처리된 DataFrame
    """
    try:
        # 엑셀 파일 읽기 (4행부터 = skiprows=3)
        df = pd.read_excel(file_path, sheet_name=0, header=None, skiprows=3)

        # 필요한 컬럼 선택 (0-6열)
        df = df.iloc[:, [0, 1, 2, 3, 4, 5, 6]]

        # 컬럼명 설정
        df.columns = ["date", "product_info", "sale_amount", "collection_amount",
                      "purchase_amount", "payment_amount", "balance"]

        # 날짜 추출
        df["date"] = df["date"].apply(extract_date)

        # 날짜가 NaT인 행 제외 (상세정보 행 제거)
        df = df.dropna(subset=["date"])

        # 금액 데이터 정제
        for amount_col in ["sale_amount", "collection_amount", "purchase_amount",
                          "payment_amount", "balance"]:
            df[amount_col] = df[amount_col].apply(clean_amount)

        # 인덱스 초기화
        df = df.reset_index(drop=True)

        return df

    except Exception as e:
        st.error(f"파일 로드 실패: {str(e)}")
        return None


def compare_by_date(df_file1, df_file2):
    """
    두 파일의 데이터를 날짜별로 비교

    파일1의 채권판매(3열) vs 파일2의 채무구매(5열)를 비교

    Args:
        df_file1: 소닉밸류 관점 DataFrame
        df_file2: 잼뮤직 관점 DataFrame

    Returns:
        일자별 비교 DataFrame
    """
    # 날짜별 합계 계산
    # 파일1에서 날짜별 채권판매(sale_amount) 합계
    file1_sales = df_file1.groupby("date")["sale_amount"].sum().reset_index()
    file1_sales.columns = ["date", "sale_amount_file1"]

    # 파일2에서 날짜별 채무구매(purchase_amount) 합계
    file2_purchases = df_file2.groupby("date")["purchase_amount"].sum().reset_index()
    file2_purchases.columns = ["date", "purchase_amount_file2"]

    # 데이터 머지 (full outer join)
    comparison = pd.merge(file1_sales, file2_purchases, on="date", how="outer")

    # NaN을 0으로 채우기
    comparison = comparison.fillna(0)

    # 편차 계산
    comparison["difference"] = comparison["sale_amount_file1"] - comparison["purchase_amount_file2"]

    # 일치 여부 판정 (차이가 0이면 일치)
    comparison["is_match"] = comparison["difference"] == 0

    # 날짜 기준으로 정렬
    comparison = comparison.sort_values("date").reset_index(drop=True)

    return comparison


def compare_transactions_detail(df_file1, df_file2, date_selected, compare_type, match_filter, perspective1="파일1", perspective2="파일2"):
    """
    선택된 날짜의 거래를 상세하게 비교

    Args:
        df_file1: 파일1 관점 DataFrame
        df_file2: 파일2 관점 DataFrame
        date_selected: 선택된 날짜
        compare_type: 비교 유형 문자열 (예: "파일1_판매 vs 파일2_구매")
        match_filter: "모두" / "일치" / "불일치"
        perspective1: 파일1 이름
        perspective2: 파일2 이름

    Returns:
        상세 비교 DataFrame
    """
    # 선택된 날짜의 거래만 필터링
    df1_filtered = df_file1[df_file1["date"] == date_selected].copy()
    df2_filtered = df_file2[df_file2["date"] == date_selected].copy()

    # 비교 대상 컬럼 선택
    # compare_type: "파일1_판매 vs 파일2_구매", "파일1_수금 vs 파일2_지급",
    #               "파일2_판매 vs 파일1_구매", "파일2_수금 vs 파일1_지급"
    if "판매" in compare_type and "구매" in compare_type:
        # 판매vs구매 비교
        if f"{perspective1}_판매" in compare_type and f"{perspective2}_구매" in compare_type:
            # 정방향: 파일1_판매 vs 파일2_구매
            col1_file1 = "sale_amount"  # 파일1: 판매
            col1_file2 = "purchase_amount"  # 파일2: 구매
        else:
            # 역방향: 파일2_판매 vs 파일1_구매
            col1_file1 = "purchase_amount"  # 파일1: 구매
            col1_file2 = "sale_amount"  # 파일2: 판매
    else:  # "수금vs지급"
        # 수금vs지급 비교
        if f"{perspective1}_수금" in compare_type and f"{perspective2}_지급" in compare_type:
            # 정방향: 파일1_수금 vs 파일2_지급
            col1_file1 = "collection_amount"  # 파일1: 수금
            col1_file2 = "payment_amount"  # 파일2: 지급
        else:
            # 역방향: 파일2_수금 vs 파일1_지급
            col1_file1 = "payment_amount"  # 파일1: 지급
            col1_file2 = "collection_amount"  # 파일2: 수금

    # 결과 리스트
    result_rows = []

    # 파일1의 거래 처리
    processed_indices = []
    for idx1, row1 in df1_filtered.iterrows():
        # 파일2에서 일치하는 거래 찾기 (같은 금액)
        matching_rows = df2_filtered[df2_filtered[col1_file2] == row1[col1_file1]]

        if len(matching_rows) > 0:
            # 일치하는 거래가 있는 경우
            for idx2, row2 in matching_rows.iterrows():
                result_rows.append({
                    "거래번호": len(result_rows) + 1,
                    "파일1_적요": row1["product_info"],
                    "파일1_금액": row1[col1_file1],
                    "파일2_적요": row2["product_info"],
                    "파일2_금액": row2[col1_file2],
                    "상태": "일치" if row1[col1_file1] == row2[col1_file2] else "불일치"
                })
                # 처리된 인덱스 저장
                processed_indices.append(idx2)
        else:
            # 일치하는 거래가 없는 경우 (미매칭)
            result_rows.append({
                "거래번호": len(result_rows) + 1,
                "파일1_적요": row1["product_info"],
                "파일1_금액": row1[col1_file1],
                "파일2_적요": "-",
                "파일2_금액": 0,
                "상태": "미매칭"
            })

    # 파일2에서 처리된 거래 제거 (중복 처리 방지)
    df2_filtered = df2_filtered.drop(processed_indices, errors='ignore')

    # 파일2에 남은 거래 처리 (파일1에는 없는 거래)
    for idx2, row2 in df2_filtered.iterrows():
        result_rows.append({
            "거래번호": len(result_rows) + 1,
            "파일1_적요": "-",
            "파일1_금액": 0,
            "파일2_적요": row2["product_info"],
            "파일2_금액": row2[col1_file2],
            "상태": "미매칭"
        })

    # DataFrame으로 변환
    if result_rows:
        detail_df = pd.DataFrame(result_rows)
    else:
        # 빈 DataFrame 생성
        detail_df = pd.DataFrame(columns=["거래번호", "파일1_적요", "파일1_금액",
                                          "파일2_적요", "파일2_금액", "상태"])

    # 필터링 적용
    if match_filter == "일치":
        detail_df = detail_df[detail_df["상태"] == "일치"]
    elif match_filter == "불일치":
        detail_df = detail_df[detail_df["상태"] != "일치"]

    # 불일치를 먼저 표시하도록 정렬
    status_order = {"불일치": 0, "미매칭": 1, "일치": 2}
    detail_df["sort_key"] = detail_df["상태"].map(status_order)
    detail_df = detail_df.sort_values("sort_key").reset_index(drop=True)
    detail_df = detail_df.drop("sort_key", axis=1)

    return detail_df


def get_row_color(status):
    """
    상태에 따라 행 배경색 결정

    Args:
        status: 상태 문자열 ("일치" / "불일치" / "미매칭")

    Returns:
        CSS 색상 코드
    """
    if status == "일치":
        return "background-color: #90EE90;"  # 초록색
    elif status == "불일치":
        return "background-color: #FFB6C6;"  # 빨강색
    else:  # 미매칭
        return "background-color: #E8E8E8;"  # 회색


# ============================================================================
# Streamlit 세션 상태 초기화
# ============================================================================

# 세션 상태 변수 초기화
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
    st.session_state.df_file1 = None
    st.session_state.df_file2 = None
    st.session_state.comparison_result = None
    st.session_state.file1_name = None
    st.session_state.file2_name = None
    st.session_state.perspective1 = None  # 파일1의 관점
    st.session_state.perspective2 = None  # 파일2의 관점

# 상세 분석용 세션 상태 초기화
if "selected_date" not in st.session_state:
    st.session_state.selected_date = None
    st.session_state.compare_type = None
    st.session_state.match_filter = None

# 필터 변경 감지 함수
def on_filter_change():
    """필터값이 변경되면 자동으로 비교를 실행"""
    # 세션 상태에 현재 필터값 저장
    st.session_state.filter_changed = True


# ============================================================================
# 메인 제목
# ============================================================================

st.title("📊 거래 비교 분석 시스템")


# ============================================================================
# 사이드바: 페이지 선택 및 파일 로드
# ============================================================================

with st.sidebar:
    st.header("⚙️ 설정")

    # 파일 업로드 영역
    st.subheader("📁 파일 업로드")

    # 파일1 업로드
    st.text("파일1 (회사 이름 입력)")
    perspective1 = st.text_input(
        "회사 이름 입력",
        value="",
        help="예: 소닉밸류, 판매자, A회사 등",
        key="perspective1_input"
    )
    file1 = st.file_uploader(
        "파일1 선택 (.xlsx)",
        type="xlsx",
        key="file1_upload",
        help="첫 번째 엑셀 파일을 선택하세요"
    )

    st.divider()

    # 파일2 업로드
    st.text("파일2 (비교회사 이름 입력)")
    perspective2 = st.text_input(
        "비교회사 이름 입력",
        value="",
        help="예: 잼뮤직, 구매자, B회사 등",
        key="perspective2_input"
    )
    file2 = st.file_uploader(
        "파일2 선택 (.xlsx)",
        type="xlsx",
        key="file2_upload",
        help="두 번째 엑셀 파일을 선택하세요"
    )

    st.divider()

    # 데이터 로드 버튼
    if st.button("📥 데이터 로드", use_container_width=True):
        if file1 is None or file2 is None:
            st.error("⚠️ 두 파일을 모두 선택해주세요.")
        elif not perspective1 or not perspective2:
            st.error("⚠️ 두 관점을 모두 입력해주세요.")
        else:
            with st.spinner("데이터를 로드하는 중입니다..."):
                # 파일을 임시 저장
                import tempfile
                import os

                with tempfile.TemporaryDirectory() as tmpdir:
                    # 파일1 저장 및 로드
                    file1_path = os.path.join(tmpdir, file1.name)
                    with open(file1_path, "wb") as f:
                        f.write(file1.getbuffer())
                    df1 = load_and_prepare_data(file1_path)

                    # 파일2 저장 및 로드
                    file2_path = os.path.join(tmpdir, file2.name)
                    with open(file2_path, "wb") as f:
                        f.write(file2.getbuffer())
                    df2 = load_and_prepare_data(file2_path)

                    if df1 is not None and df2 is not None:
                        st.session_state.df_file1 = df1
                        st.session_state.df_file2 = df2
                        st.session_state.file1_name = file1.name
                        st.session_state.file2_name = file2.name
                        st.session_state.perspective1 = perspective1
                        st.session_state.perspective2 = perspective2
                        st.session_state.data_loaded = True
                        st.success("✅ 데이터 로드 완료!")
                    else:
                        st.error("파일 로드에 실패했습니다. 올바른 형식의 .xlsx 파일인지 확인하세요.")

    st.divider()

    # 페이지 선택
    st.subheader("📄 페이지 선택")
    page = st.radio(
        "페이지를 선택하세요",
        options=["📊 대시보드", "🔍 상세 분석"],
        label_visibility="collapsed"
    )


# ============================================================================
# 데이터 로드 확인
# ============================================================================

if not st.session_state.data_loaded:
    st.warning("⚠️ 사이드바에서 파일을 선택하고 '데이터 로드' 버튼을 클릭하세요.")
    st.stop()


# ============================================================================
# 페이지1: 대시보드 (요약 분석)
# ============================================================================

if page == "📊 대시보드":
    df1 = st.session_state.df_file1
    df2 = st.session_state.df_file2
    perspective1 = st.session_state.perspective1
    perspective2 = st.session_state.perspective2

    st.header("📊 거래 비교 분석 대시보드")

    # 파일명 표시 (확장자 제거)
    file1_display = st.session_state.file1_name
    file2_display = st.session_state.file2_name

    # ".xlsx" 확장자 제거
    import re
    file1_display = re.sub(r'\.xlsx$', '', file1_display)
    file2_display = re.sub(r'\.xlsx$', '', file2_display)

    st.text(f"{perspective1} ↔ {perspective2} | 파일1: {file1_display} | 파일2: {file2_display}")

    # 1. 요약 통계 계산
    total_sale = df1["sale_amount"].sum()
    total_collection = df1["collection_amount"].sum()
    total_purchase = df1["purchase_amount"].sum()
    total_payment = df1["payment_amount"].sum()

    uncollected = total_sale - total_collection
    unpaid = total_purchase - total_payment

    # 2. 요약 통계 영역 (4개 메트릭)
    st.subheader("💰 거래 요약 통계")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="전체 판매 금액",
            value=format_currency(total_sale),
            label_visibility="visible"
        )

    with col2:
        st.metric(
            label="전체 수금 금액",
            value=format_currency(total_collection),
            label_visibility="visible"
        )

    with col3:
        st.metric(
            label="전체 구매 금액",
            value=format_currency(total_purchase),
            label_visibility="visible"
        )

    with col4:
        st.metric(
            label="전체 지급 금액",
            value=format_currency(total_payment),
            label_visibility="visible"
        )

    # 3. 미수금/미지급 표시
    st.subheader("⚠️ 미수금/미지급 현황")
    col1, col2 = st.columns(2)

    with col1:
        if uncollected > 0:
            st.error(f"**미수금**: {format_currency(uncollected)} 원")
        else:
            st.success(f"**미수금**: {format_currency(uncollected)} 원 (수금 완료)")

    with col2:
        if unpaid > 0:
            st.error(f"**미지급**: {format_currency(unpaid)} 원")
        else:
            st.success(f"**미지급**: {format_currency(unpaid)} 원 (지급 완료)")

    st.divider()

    # 4. 일자별 비교 분석
    st.subheader("📈 일자별 거래 비교 분석")

    # 비교 데이터 생성
    comparison_df = compare_by_date(df1, df2)

    # 역방향 비교 데이터 생성 (파일2 판매 vs 파일1 구매)
    # 날짜별 합계 계산
    file2_sales = df2.groupby("date")["sale_amount"].sum().reset_index()
    file2_sales.columns = ["date", "sale_amount_file2"]

    file1_purchases = df1.groupby("date")["purchase_amount"].sum().reset_index()
    file1_purchases.columns = ["date", "purchase_amount_file1"]

    # 데이터 머지
    comparison_reverse = pd.merge(file2_sales, file1_purchases, on="date", how="outer")
    comparison_reverse = comparison_reverse.fillna(0)

    # 편차 계산 (file2 판매 - file1 구매)
    comparison_reverse["difference"] = comparison_reverse["sale_amount_file2"] - comparison_reverse["purchase_amount_file1"]
    comparison_reverse["is_match"] = comparison_reverse["difference"] == 0
    comparison_reverse = comparison_reverse.sort_values("date").reset_index(drop=True)

    # 불일치 거래일만 보기 토글
    show_mismatch_only = st.checkbox("🔴 불일치만 보기", value=False)

    # 탭 생성
    compare_tab1, compare_tab2 = st.tabs([
        f"📊 {perspective1}_판매 vs {perspective2}_구매",
        f"📊 {perspective2}_판매 vs {perspective1}_구매"
    ])

    # ====================================================================
    # 탭1: 파일1 판매 vs 파일2 구매
    # ====================================================================
    with compare_tab1:
        if show_mismatch_only:
            comparison_display = comparison_df[comparison_df["is_match"] == False].copy()
        else:
            comparison_display = comparison_df.copy()

        # 표시용 DataFrame 생성
        display_df = comparison_display.copy()
        display_df["일자"] = display_df["date"].dt.strftime("%Y/%m/%d")
        display_df[f"{perspective1}_판매(합)"] = display_df["sale_amount_file1"].apply(format_currency)
        display_df[f"{perspective2}_구매(합)"] = display_df["purchase_amount_file2"].apply(format_currency)
        display_df["편차"] = display_df["difference"].apply(lambda x: f"({format_currency(abs(x))})" if x < 0 else format_currency(x))
        display_df["일치여부"] = display_df["is_match"].apply(lambda x: "✅ 일치" if x else "❌ 불일치")

        # 테이블 표시 (색상 강조)
        column_names = ["일자", f"{perspective1}_판매(합)", f"{perspective2}_구매(합)", "편차", "일치여부"]

        def style_match_rows_tab1(row):
            # 원본 comparison_display의 is_match 값으로 색상 결정
            if comparison_display.loc[row.name, "is_match"]:
                return ["background-color: #E8F5E9"] * len(row)
            else:
                return ["background-color: #FFEBEE"] * len(row)

        styled_df = display_df[column_names].style.apply(
            style_match_rows_tab1, axis=1
        )

        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # 불일치 거래 상세 정보 (전개 가능한 섹션)
        with st.expander("❌ 불일치 거래 상세 정보 확인"):
            mismatch_dates_tab1 = comparison_df[comparison_df["is_match"] == False]["date"].tolist()

            if len(mismatch_dates_tab1) > 0:
                st.warning(f"""
                **불일치 거래 설명**

                아래는 {perspective1}과 {perspective2} 간의 거래 기록이 일치하지 않는 날짜들입니다.
                - **{perspective1}_판매(합)**: {perspective1}이 기록한 판매 금액의 합
                - **{perspective2}_구매(합)**: {perspective2}이 기록한 구매 금액의 합
                - **편차**: 두 금액의 차이 (양수: {perspective1} 기록이 더 큼, 음수: {perspective2} 기록이 더 큼)

                각 불일치 거래일의 원본 데이터를 아래에서 확인하세요.
                """)

                # 각 불일치 날짜에 대해 원본 데이터 표시
                for mismatch_date in sorted(mismatch_dates_tab1):
                    date_str = mismatch_date.strftime("%Y/%m/%d")

                    # 해당 날짜의 두 파일 데이터 필터링
                    df1_date = df1[df1["date"] == mismatch_date].copy()
                    df2_date = df2[df2["date"] == mismatch_date].copy()

                    # 비교 데이터 가져오기
                    mismatch_row = comparison_df[comparison_df["date"] == mismatch_date].iloc[0]

                    with st.expander(f"📅 {date_str} - {perspective1}_{format_currency(mismatch_row['sale_amount_file1'])} vs {perspective2}_{format_currency(mismatch_row['purchase_amount_file2'])} (편차: {format_currency(abs(mismatch_row['difference']))})"):

                        # 2개 컬럼으로 나누어 표시
                        col1, col2 = st.columns(2)

                        with col1:
                            st.subheader(f"📋 {perspective1} 거래 기록")
                            if len(df1_date) > 0:
                                display_df1_detail = df1_date.copy()
                                display_df1_detail["일자"] = display_df1_detail["date"].dt.strftime("%Y/%m/%d")
                                display_df1_detail["판매"] = display_df1_detail["sale_amount"].apply(format_currency)
                                display_df1_detail["수금"] = display_df1_detail["collection_amount"].apply(format_currency)
                                display_df1_detail["구매"] = display_df1_detail["purchase_amount"].apply(format_currency)
                                display_df1_detail["지급"] = display_df1_detail["payment_amount"].apply(format_currency)

                                show_col = ["일자", "product_info", "판매", "수금", "구매", "지급"]
                                display_df1_detail[show_col].columns = ["일자", "적요", "판매", "수금", "구매", "지급"]
                                st.dataframe(display_df1_detail[[c for c in ["일자", "적요", "판매", "수금", "구매", "지급"] if c in display_df1_detail.columns]], use_container_width=True, hide_index=True)

                                st.caption(f"**합계** - 판매: {format_currency(df1_date['sale_amount'].sum())} | 수금: {format_currency(df1_date['collection_amount'].sum())} | 구매: {format_currency(df1_date['purchase_amount'].sum())} | 지급: {format_currency(df1_date['payment_amount'].sum())}")
                            else:
                                st.info(f"해당 날짜 {perspective1} 거래 없음")

                        with col2:
                            st.subheader(f"📋 {perspective2} 거래 기록")
                            if len(df2_date) > 0:
                                display_df2_detail = df2_date.copy()
                                display_df2_detail["일자"] = display_df2_detail["date"].dt.strftime("%Y/%m/%d")
                                display_df2_detail["판매"] = display_df2_detail["sale_amount"].apply(format_currency)
                                display_df2_detail["수금"] = display_df2_detail["collection_amount"].apply(format_currency)
                                display_df2_detail["구매"] = display_df2_detail["purchase_amount"].apply(format_currency)
                                display_df2_detail["지급"] = display_df2_detail["payment_amount"].apply(format_currency)

                                show_col = ["일자", "product_info", "판매", "수금", "구매", "지급"]
                                st.dataframe(display_df2_detail[[c for c in ["일자", "적요", "판매", "수금", "구매", "지급"] if c in display_df2_detail.columns]], use_container_width=True, hide_index=True)

                                st.caption(f"**합계** - 판매: {format_currency(df2_date['sale_amount'].sum())} | 수금: {format_currency(df2_date['collection_amount'].sum())} | 구매: {format_currency(df2_date['purchase_amount'].sum())} | 지급: {format_currency(df2_date['payment_amount'].sum())}")
                            else:
                                st.info(f"해당 날짜 {perspective2} 거래 없음")

        # 탭1 CSV 다운로드
        st.divider()
        st.subheader("💾 다운로드")

        csv_data_tab1 = comparison_df.copy()
        csv_data_tab1["일자"] = csv_data_tab1["date"].dt.strftime("%Y/%m/%d")
        csv_data_tab1["일치여부"] = csv_data_tab1["is_match"].apply(lambda x: "일치" if x else "불일치")
        csv_export_tab1 = csv_data_tab1[["일자", "sale_amount_file1", "purchase_amount_file2", "difference", "일치여부"]]
        csv_export_tab1.columns = [f"일자", f"{perspective1}_판매", f"{perspective2}_구매", "편차", "일치여부"]

        csv_buffer_tab1 = csv_export_tab1.to_csv(index=False, encoding="utf-8-sig")

        st.download_button(
            label="📥 비교 분석 결과 CSV 다운로드",
            data=csv_buffer_tab1,
            file_name=f"comparison_{perspective1}_vs_{perspective2}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # ====================================================================
    # 탭2: 파일2 판매 vs 파일1 구매
    # ====================================================================
    with compare_tab2:
        if show_mismatch_only:
            comparison_display_reverse = comparison_reverse[comparison_reverse["is_match"] == False].copy()
        else:
            comparison_display_reverse = comparison_reverse.copy()

        # 표시용 DataFrame 생성
        display_df_reverse = comparison_display_reverse.copy()
        display_df_reverse["일자"] = display_df_reverse["date"].dt.strftime("%Y/%m/%d")
        display_df_reverse[f"{perspective2}_판매(합)"] = display_df_reverse["sale_amount_file2"].apply(format_currency)
        display_df_reverse[f"{perspective1}_구매(합)"] = display_df_reverse["purchase_amount_file1"].apply(format_currency)
        display_df_reverse["편차"] = display_df_reverse["difference"].apply(lambda x: f"({format_currency(abs(x))})" if x < 0 else format_currency(x))
        display_df_reverse["일치여부"] = display_df_reverse["is_match"].apply(lambda x: "✅ 일치" if x else "❌ 불일치")

        # 테이블 표시 (색상 강조)
        column_names_reverse = ["일자", f"{perspective2}_판매(합)", f"{perspective1}_구매(합)", "편차", "일치여부"]

        def style_match_rows_tab2(row):
            # 원본 comparison_display_reverse의 is_match 값으로 색상 결정
            if comparison_display_reverse.loc[row.name, "is_match"]:
                return ["background-color: #E8F5E9"] * len(row)
            else:
                return ["background-color: #FFEBEE"] * len(row)

        styled_df_reverse = display_df_reverse[column_names_reverse].style.apply(
            style_match_rows_tab2, axis=1
        )

        st.dataframe(styled_df_reverse, use_container_width=True, hide_index=True)

        # 불일치 거래 상세 정보 (전개 가능한 섹션)
        with st.expander("❌ 불일치 거래 상세 정보 확인"):
            mismatch_dates_tab2 = comparison_reverse[comparison_reverse["is_match"] == False]["date"].tolist()

            if len(mismatch_dates_tab2) > 0:
                st.warning(f"""
                **불일치 거래 설명**

                아래는 {perspective2}과 {perspective1} 간의 거래 기록이 일치하지 않는 날짜들입니다.
                - **{perspective2}_판매(합)**: {perspective2}이 기록한 판매 금액의 합
                - **{perspective1}_구매(합)**: {perspective1}이 기록한 구매 금액의 합
                - **편차**: 두 금액의 차이 (양수: {perspective2} 기록이 더 큼, 음수: {perspective1} 기록이 더 큼)

                각 불일치 거래일의 원본 데이터를 아래에서 확인하세요.
                """)

                # 각 불일치 날짜에 대해 원본 데이터 표시
                for mismatch_date in sorted(mismatch_dates_tab2):
                    date_str = mismatch_date.strftime("%Y/%m/%d")

                    # 해당 날짜의 두 파일 데이터 필터링
                    df1_date = df1[df1["date"] == mismatch_date].copy()
                    df2_date = df2[df2["date"] == mismatch_date].copy()

                    # 비교 데이터 가져오기
                    mismatch_row = comparison_reverse[comparison_reverse["date"] == mismatch_date].iloc[0]

                    with st.expander(f"📅 {date_str} - {perspective2}_{format_currency(mismatch_row['sale_amount_file2'])} vs {perspective1}_{format_currency(mismatch_row['purchase_amount_file1'])} (편차: {format_currency(abs(mismatch_row['difference']))})"):

                        # 2개 컬럼으로 나누어 표시
                        col1, col2 = st.columns(2)

                        with col1:
                            st.subheader(f"📋 {perspective2} 거래 기록")
                            if len(df2_date) > 0:
                                display_df2_detail = df2_date.copy()
                                display_df2_detail["일자"] = display_df2_detail["date"].dt.strftime("%Y/%m/%d")
                                display_df2_detail["판매"] = display_df2_detail["sale_amount"].apply(format_currency)
                                display_df2_detail["수금"] = display_df2_detail["collection_amount"].apply(format_currency)
                                display_df2_detail["구매"] = display_df2_detail["purchase_amount"].apply(format_currency)
                                display_df2_detail["지급"] = display_df2_detail["payment_amount"].apply(format_currency)

                                show_col = ["일자", "product_info", "판매", "수금", "구매", "지급"]
                                display_df2_detail[show_col].columns = ["일자", "적요", "판매", "수금", "구매", "지급"]
                                st.dataframe(display_df2_detail[[c for c in ["일자", "적요", "판매", "수금", "구매", "지급"] if c in display_df2_detail.columns]], use_container_width=True, hide_index=True)

                                st.caption(f"**합계** - 판매: {format_currency(df2_date['sale_amount'].sum())} | 수금: {format_currency(df2_date['collection_amount'].sum())} | 구매: {format_currency(df2_date['purchase_amount'].sum())} | 지급: {format_currency(df2_date['payment_amount'].sum())}")
                            else:
                                st.info(f"해당 날짜 {perspective2} 거래 없음")

                        with col2:
                            st.subheader(f"📋 {perspective1} 거래 기록")
                            if len(df1_date) > 0:
                                display_df1_detail = df1_date.copy()
                                display_df1_detail["일자"] = display_df1_detail["date"].dt.strftime("%Y/%m/%d")
                                display_df1_detail["판매"] = display_df1_detail["sale_amount"].apply(format_currency)
                                display_df1_detail["수금"] = display_df1_detail["collection_amount"].apply(format_currency)
                                display_df1_detail["구매"] = display_df1_detail["purchase_amount"].apply(format_currency)
                                display_df1_detail["지급"] = display_df1_detail["payment_amount"].apply(format_currency)

                                show_col = ["일자", "product_info", "판매", "수금", "구매", "지급"]
                                st.dataframe(display_df1_detail[[c for c in ["일자", "적요", "판매", "수금", "구매", "지급"] if c in display_df1_detail.columns]], use_container_width=True, hide_index=True)

                                st.caption(f"**합계** - 판매: {format_currency(df1_date['sale_amount'].sum())} | 수금: {format_currency(df1_date['collection_amount'].sum())} | 구매: {format_currency(df1_date['purchase_amount'].sum())} | 지급: {format_currency(df1_date['payment_amount'].sum())}")
                            else:
                                st.info(f"해당 날짜 {perspective1} 거래 없음")

        # 탭2 CSV 다운로드
        st.divider()
        st.subheader("💾 다운로드")

        csv_data_tab2 = comparison_reverse.copy()
        csv_data_tab2["일자"] = csv_data_tab2["date"].dt.strftime("%Y/%m/%d")
        csv_data_tab2["일치여부"] = csv_data_tab2["is_match"].apply(lambda x: "일치" if x else "불일치")
        csv_export_tab2 = csv_data_tab2[["일자", "sale_amount_file2", "purchase_amount_file1", "difference", "일치여부"]]
        csv_export_tab2.columns = [f"일자", f"{perspective2}_판매", f"{perspective1}_구매", "편차", "일치여부"]

        csv_buffer_tab2 = csv_export_tab2.to_csv(index=False, encoding="utf-8-sig")

        st.download_button(
            label="📥 비교 분석 결과 CSV 다운로드",
            data=csv_buffer_tab2,
            file_name=f"comparison_{perspective2}_vs_{perspective1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )


# ============================================================================
# 페이지2: 상세 분석
# ============================================================================

else:  # page == "🔍 상세 분석"
    df1 = st.session_state.df_file1
    df2 = st.session_state.df_file2
    perspective1 = st.session_state.perspective1
    perspective2 = st.session_state.perspective2

    st.header("🔍 거래별 상세 분석")

    # 필터 설정 영역 (메인 페이지)
    st.subheader("🔍 상세 분석 필터")

    # 거래 날짜 선택, 거래 유형 선택, 일치 여부 필터를 한 행에 배치
    col_date, col_type, col_filter = st.columns([2, 3, 2])

    # 1. 거래 날짜 선택
    available_dates = sorted(df1["date"].unique())
    date_options = [d.strftime("%Y/%m/%d") for d in available_dates]

    # 초기값 설정
    initial_date_idx = 0
    if st.session_state.selected_date is not None:
        try:
            initial_date_str = st.session_state.selected_date.strftime("%Y/%m/%d")
            initial_date_idx = date_options.index(initial_date_str)
        except:
            initial_date_idx = 0

    with col_date:
        selected_date_str = st.selectbox(
            "📅 거래 날짜 선택",
            options=date_options,
            index=initial_date_idx,
            help="비교할 거래 날짜를 선택하세요",
            label_visibility="collapsed",
            key="filter_date",
            on_change=on_filter_change
        )

    selected_date = pd.to_datetime(selected_date_str)

    # 2. 거래 유형 선택
    compare_type_options = [
        f"{perspective1}_판매 vs {perspective2}_구매",
        f"{perspective1}_수금 vs {perspective2}_지급",
        f"{perspective2}_판매 vs {perspective1}_구매",
        f"{perspective2}_수금 vs {perspective1}_지급"
    ]

    initial_type_idx = 0
    if st.session_state.compare_type is not None:
        try:
            initial_type_idx = compare_type_options.index(st.session_state.compare_type)
        except:
            initial_type_idx = 0

    with col_type:
        compare_type = st.selectbox(
            "📋 거래 유형 선택",
            options=compare_type_options,
            index=initial_type_idx,
            help="비교할 거래 유형을 선택하세요",
            label_visibility="collapsed",
            key="filter_type",
            on_change=on_filter_change
        )

    # 3. 일치 여부 필터
    filter_options = ["모두", "일치", "불일치"]

    initial_filter_idx = 0
    if st.session_state.match_filter is not None:
        try:
            initial_filter_idx = filter_options.index(st.session_state.match_filter)
        except:
            initial_filter_idx = 0

    with col_filter:
        match_filter = st.selectbox(
            "🔍 일치 여부 필터",
            options=filter_options,
            index=initial_filter_idx,
            help="일치 여부로 거래를 필터링하세요",
            label_visibility="collapsed",
            key="filter_match",
            on_change=on_filter_change
        )

    # 필터값이 변경되면 자동으로 세션 상태 업데이트
    if st.session_state.get("filter_changed", False):
        st.session_state.selected_date = selected_date
        st.session_state.compare_type = compare_type
        st.session_state.match_filter = match_filter
        st.session_state.filter_changed = False
    else:
        # 초기 로드 시에만 세션 상태 설정
        if st.session_state.selected_date is None:
            st.session_state.selected_date = selected_date
            st.session_state.compare_type = compare_type
            st.session_state.match_filter = match_filter

    st.divider()

    # 상세 분석 탭 추가
    analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs([
        f"📊 {perspective1} ↔ {perspective2} 비교",
        f"👁️ {perspective1} 관점",
        f"👁️ {perspective2} 관점"
    ])

    # ========================================================================
    # 탭1: 두 관점 비교
    # ========================================================================
    with analysis_tab1:
        # 상세 비교 데이터 생성
        if st.session_state.selected_date is not None:
            selected_date = st.session_state.selected_date
            compare_type = st.session_state.compare_type
            match_filter = st.session_state.match_filter

            detail_df = compare_transactions_detail(df1, df2, selected_date, compare_type, match_filter, perspective1, perspective2)

            # 선택 정보 요약
            st.subheader("📊 비교 결과")
            st.info(f"**{selected_date.strftime('%Y/%m/%d')}** 기준 **{len(detail_df)}**개 거래 조회 "
                    f"| 거래 유형: **{compare_type}** | 필터: **{match_filter}**")

            # 상세 비교 테이블 표시
            if len(detail_df) > 0:
                # 표시용 DataFrame 생성
                display_df = detail_df.copy()
                display_df["파일1_금액"] = display_df["파일1_금액"].apply(format_currency)
                display_df["파일2_금액"] = display_df["파일2_금액"].apply(format_currency)

                # 컬럼명을 입력된 관점명으로 변경
                display_df = display_df.rename(columns={
                    "파일1_적요": f"{perspective1}_적요",
                    "파일1_금액": f"{perspective1}_금액",
                    "파일2_적요": f"{perspective2}_적요",
                    "파일2_금액": f"{perspective2}_금액"
                })

                # 색상 강조 적용
                def style_detail_rows(row):
                    status = row["상태"]
                    if status == "일치":
                        return ["background-color: #E8F5E9"] * len(row)
                    elif status == "불일치":
                        return ["background-color: #FFEBEE"] * len(row)
                    else:  # 미매칭
                        return ["background-color: #F5F5F5"] * len(row)

                styled_detail_df = display_df.style.apply(style_detail_rows, axis=1)

                st.dataframe(styled_detail_df, use_container_width=True, hide_index=True)

                # CSV 다운로드
                st.divider()
                st.subheader("💾 다운로드")

                csv_data = detail_df.copy()
                csv_data = csv_data.rename(columns={
                    "파일1_적요": f"{perspective1}_적요",
                    "파일1_금액": f"{perspective1}_금액",
                    "파일2_적요": f"{perspective2}_적요",
                    "파일2_금액": f"{perspective2}_금액"
                })
                csv_data[f"{perspective1}_금액"] = csv_data[f"{perspective1}_금액"].apply(format_currency)
                csv_data[f"{perspective2}_금액"] = csv_data[f"{perspective2}_금액"].apply(format_currency)

                csv_buffer = csv_data.to_csv(index=False, encoding="utf-8-sig")

                st.download_button(
                    label="📥 비교 분석 결과 CSV 다운로드",
                    data=csv_buffer,
                    file_name=f"transaction_detail_{selected_date.strftime('%Y%m%d')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ 선택한 조건에 맞는 거래가 없습니다.")
        else:
            st.info("💡 필터를 설정하면 자동으로 비교 결과가 표시됩니다.")

    # ========================================================================
    # 탭2: 파일1(관점1) 관점 상세 보기
    # ========================================================================
    with analysis_tab2:
        st.subheader(f"{perspective1} 거래 기록")

        if st.session_state.selected_date is not None:
            selected_date = st.session_state.selected_date

            # 해당 날짜의 파일1 데이터만 필터링
            df1_filtered = df1[df1["date"] == selected_date].copy()

            if len(df1_filtered) > 0:
                st.info(f"**{selected_date.strftime('%Y/%m/%d')}** 기준 **{len(df1_filtered)}**개 거래")

                # 표시용 DataFrame 생성
                display_df1 = df1_filtered.copy()
                display_df1["일자"] = display_df1["date"].dt.strftime("%Y/%m/%d")
                display_df1["판매"] = display_df1["sale_amount"].apply(format_currency)
                display_df1["수금"] = display_df1["collection_amount"].apply(format_currency)
                display_df1["구매"] = display_df1["purchase_amount"].apply(format_currency)
                display_df1["지급"] = display_df1["payment_amount"].apply(format_currency)

                # 표시할 컬럼 선택 (잔액 제외)
                show_df1 = display_df1[["일자", "product_info", "판매", "수금", "구매", "지급"]]
                show_df1.columns = ["일자", "적요", "판매", "수금", "구매", "지급"]

                st.dataframe(show_df1, use_container_width=True, hide_index=True)

                # 통계 정보
                st.divider()
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("총 판매액", format_currency(df1_filtered["sale_amount"].sum()))
                with col2:
                    st.metric("총 수금액", format_currency(df1_filtered["collection_amount"].sum()))
                with col3:
                    st.metric("총 구매액", format_currency(df1_filtered["purchase_amount"].sum()))
                with col4:
                    st.metric("총 지급액", format_currency(df1_filtered["payment_amount"].sum()))

                # CSV 다운로드
                st.divider()
                csv_data1 = display_df1[["일자", "product_info", "판매", "수금", "구매", "지급"]].copy()
                csv_data1.columns = ["일자", "적요", "판매", "수금", "구매", "지급"]
                csv_buffer1 = csv_data1.to_csv(index=False, encoding="utf-8-sig")

                st.download_button(
                    label=f"📥 {perspective1} 거래 내역 CSV 다운로드",
                    data=csv_buffer1,
                    file_name=f"{perspective1}_{selected_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning(f"⚠️ {selected_date.strftime('%Y/%m/%d')}에 {perspective1}의 거래가 없습니다.")
        else:
            st.info("💡 필터를 설정하면 자동으로 거래 기록이 표시됩니다.")

    # ========================================================================
    # 탭3: 파일2(관점2) 관점 상세 보기
    # ========================================================================
    with analysis_tab3:
        st.subheader(f"{perspective2} 거래 기록")

        if st.session_state.selected_date is not None:
            selected_date = st.session_state.selected_date

            # 해당 날짜의 파일2 데이터만 필터링
            df2_filtered = df2[df2["date"] == selected_date].copy()

            if len(df2_filtered) > 0:
                st.info(f"**{selected_date.strftime('%Y/%m/%d')}** 기준 **{len(df2_filtered)}**개 거래")

                # 표시용 DataFrame 생성
                display_df2 = df2_filtered.copy()
                display_df2["일자"] = display_df2["date"].dt.strftime("%Y/%m/%d")
                display_df2["판매"] = display_df2["sale_amount"].apply(format_currency)
                display_df2["수금"] = display_df2["collection_amount"].apply(format_currency)
                display_df2["구매"] = display_df2["purchase_amount"].apply(format_currency)
                display_df2["지급"] = display_df2["payment_amount"].apply(format_currency)

                # 표시할 컬럼 선택 (잔액 제외)
                show_df2 = display_df2[["일자", "product_info", "판매", "수금", "구매", "지급"]]
                show_df2.columns = ["일자", "적요", "판매", "수금", "구매", "지급"]

                st.dataframe(show_df2, use_container_width=True, hide_index=True)

                # 통계 정보
                st.divider()
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("총 판매액", format_currency(df2_filtered["sale_amount"].sum()))
                with col2:
                    st.metric("총 수금액", format_currency(df2_filtered["collection_amount"].sum()))
                with col3:
                    st.metric("총 구매액", format_currency(df2_filtered["purchase_amount"].sum()))
                with col4:
                    st.metric("총 지급액", format_currency(df2_filtered["payment_amount"].sum()))

                # CSV 다운로드
                st.divider()
                csv_data2 = display_df2[["일자", "product_info", "판매", "수금", "구매", "지급"]].copy()
                csv_data2.columns = ["일자", "적요", "판매", "수금", "구매", "지급"]
                csv_buffer2 = csv_data2.to_csv(index=False, encoding="utf-8-sig")

                st.download_button(
                    label=f"📥 {perspective2} 거래 내역 CSV 다운로드",
                    data=csv_buffer2,
                    file_name=f"{perspective2}_{selected_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning(f"⚠️ {selected_date.strftime('%Y/%m/%d')}에 {perspective2}의 거래가 없습니다.")
        else:
            st.info("💡 필터를 설정하면 자동으로 거래 기록이 표시됩니다.")
