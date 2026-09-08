import streamlit as st
import pandas as pd

from file_reader import read_pdf, read_excel
from mock_extractor import build_mock_results
from ai_extractor import extract_evidence
from qualitative_comparator import compare_qualitative_evidence
from comparison_summarizer import summarize_comparison_values
from candidate_analyzer import analyze_candidate_characteristics
from criterion_recommender import recommend_extraction_fields
from condition_impact_analyzer import (
    analyze_scenario_impact,
    analyze_priority_change,
    analyze_threshold_change
)

st.set_page_config(
    page_title="Engineering Decision Assistant",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown(
    """
    <style>
        .block-container {
            max-width: 96vw;
            padding-left: 2rem;
            padding-right: 2rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 보조 함수
# =========================================================

def format_value(value, unit):
    """
    내부적으로 분리된 값과 단위를
    사용자 화면에서는 하나로 합쳐서 표시
    """

    if unit:
        return f"{value}{unit}"

    return str(value)


def parse_input_value(value_text, data_type):
    """
    사용자가 수정한 값을 원래 데이터 타입에 맞게 변환
    """

    value_text = value_text.strip()

    if data_type in ["numeric", "ranking"]:

        cleaned_value = value_text.replace(",", "")

        number = float(cleaned_value)

        if number.is_integer():
            return int(number)

        return number

    return value_text

# =========================================================
# 후보 비교표 표시용 함수
# =========================================================

def format_comparison_value(
    value,
    unit,
    data_type
):
    """
    후보 비교표에서 정성형 문장을
    읽기 쉬운 bullet 형태로 표시한다.

    원본 데이터는 수정하지 않고
    화면에 표시할 문자열만 변환한다.
    """

    # ---------------------------------------------------------
    # 정량형 / 순위형은 기존 방식 유지
    # ---------------------------------------------------------

    if data_type in [
        "numeric",
        "ranking"
    ]:

        return format_value(
            value,
            unit
        )


    text = str(
        value
    ).strip()


    if not text:

        return "-"


    # ---------------------------------------------------------
    # 이미 상 / 중 / 하처럼 짧은 값이면 그대로 표시
    # ---------------------------------------------------------

    if text in [
        "상",
        "중",
        "하"
    ]:

        return text


    # ---------------------------------------------------------
    # 문장 분리
    #
    # 원문의 의미를 새로 요약하지 않고
    # 기존 문장 구조만 읽기 좋게 나눈다.
    # ---------------------------------------------------------

    normalized_text = (
        text
        .replace(" / ", "\n")
        .replace("/", "\n")
        .replace("; ", "\n")
        .replace(";", "\n")
        .replace(". ", ".\n")
    )


    raw_parts = [
        part.strip()

        for part
        in normalized_text.split(
            "\n"
        )

        if part.strip()
    ]


    display_parts = []


    for part in raw_parts:

        cleaned_part = (
            part.strip()
        )


        if (
            cleaned_part
            and cleaned_part
            not in display_parts
        ):

            display_parts.append(
                cleaned_part
            )


    # 너무 많은 문장이 있더라도
    # 비교표에서는 최대 3개까지만 표시
    display_parts = (
        display_parts[:3]
    )


    if len(display_parts) == 1:

        return (
            f"• {display_parts[0]}"
        )


    return "\n".join(
        f"• {part}"
        for part in display_parts
    )


def has_explicit_risk(
    value
):
    """
    평가항목의 내용에 명시적인
    위험 / 부담 / 문제 신호가 있는지 확인한다.

    단순히 상대적으로 약하다는 이유로는
    리스크로 판정하지 않는다.
    """

    text = str(
        value
    ).strip()


    if not text or text == "-":

        return False


    # ---------------------------------------------------------
    # 개선 / 감소 표현은 위험 신호로 보지 않음
    #
    # 예:
    # "품질·안전 리스크를 줄일 수 있다."
    # ---------------------------------------------------------

    positive_patterns = [
        "리스크를 줄",
        "위험을 줄",
        "위험이 낮",
        "리스크가 낮",
        "부담을 줄",
        "부담이 감소",
        "문제를 줄",
        "개선할 수",
        "개선된다"
    ]


    if any(
        pattern in text
        for pattern in positive_patterns
    ):

        return False


    # ---------------------------------------------------------
    # 명시적 문제 / 위험 표현
    # ---------------------------------------------------------

    direct_risk_patterns = [
        "위험이 크",
        "위험이 높",
        "위험 증가",
        "위험이 증가",
        "리스크가 크",
        "리스크가 높",
        "리스크 증가",
        "리스크가 증가",
        "클레임 위험",
        "불량",
        "작동 실패",
        "고장",
        "파손",
        "간섭 발생",
        "오작동",
        "불신",
        "문제가 발생",
        "문제 발생",
        "우려가 있",
        "우려된다",
        "부족하다",
        "부족하",
        "저하된다",
        "저하될",
        "약화된다",
        "약화될"
    ]


    if any(
        pattern in text
        for pattern in direct_risk_patterns
    ):

        return True


    # ---------------------------------------------------------
    # 부담 / 복잡도 / 비용 등이 증가하는 표현
    # ---------------------------------------------------------

    burden_terms = [
        "부담",
        "복잡",
        "원가",
        "비용",
        "검증 항목",
        "검토 항목",
        "소음",
        "소비전력"
    ]


    increase_terms = [
        "증가",
        "늘어",
        "높아",
        "커진",
        "크다",
        "복잡해",
        "필요하다",
        "필요하"
    ]


    if (
        any(
            term in text
            for term in burden_terms
        )

        and

        any(
            term in text
            for term in increase_terms
        )
    ):

        return True


    return False


# =========================================================
# 후보 간 우위 관계 분석
# =========================================================

def compare_candidate_pair(
    candidate_a,
    candidate_b,
    confirmed_results,
    criterion_settings,
    ai_comparison_results=None
):
    """
    두 후보를 판단항목별로 비교해
    전반적 우위 / Trade-off / 정보 부족 여부를 판정한다.

    종합점수나 가중치는 사용하지 않는다.
    """

    if ai_comparison_results is None:
        ai_comparison_results = []


    # ---------------------------------------------------------
    # 문장형 AI 비교 결과 조회용
    # ---------------------------------------------------------

    ai_position_lookup = {}


    for comparison in ai_comparison_results:

        key = (
            comparison.get("criterion"),
            comparison.get("candidate")
        )

        ai_position_lookup[key] = (
            comparison.get("position")
        )


    # AI 결과의 상대적 위치
    qualitative_position_score = {
        "weakness": 1,
        "neutral": 2,
        "strength": 3
    }


    a_better = []
    b_better = []
    equivalent = []
    unavailable = []


    # =========================================================
    # 판단항목별 비교
    # =========================================================

    for criterion, setting in criterion_settings.items():

        role = setting.get("role")
        direction = setting.get("direction")
        data_type = setting.get("data_type")


        # 참고항목은 우위 판정에 사용하지 않음
        if role not in [
            "필수 기준",
            "평가항목"
        ]:

            continue


        # 선호 방향이 없는 항목도 제외
        if (
            direction is None
            or direction == "방향 없음"
        ):

            continue


        # -----------------------------------------------------
        # 각 후보의 해당 항목 데이터 찾기
        # -----------------------------------------------------

        result_a = next(
            (
                result
                for result in confirmed_results
                if (
                    result["candidate"] == candidate_a
                    and result["field"] == criterion
                )
            ),
            None
        )


        result_b = next(
            (
                result
                for result in confirmed_results
                if (
                    result["candidate"] == candidate_b
                    and result["field"] == criterion
                )
            ),
            None
        )


        if (
            result_a is None
            or result_b is None
        ):

            unavailable.append(
                criterion
            )

            continue


        # =====================================================
        # 정량형 비교
        # =====================================================

        if data_type in [
            "numeric",
            "ranking"
        ]:

            try:

                value_a = float(
                    result_a["value"]
                )

                value_b = float(
                    result_b["value"]
                )


            except (
                ValueError,
                TypeError
            ):

                unavailable.append(
                    criterion
                )

                continue


            if value_a == value_b:

                equivalent.append(
                    criterion
                )

                continue


            if direction == "높을수록 좋음":

                if value_a > value_b:

                    a_better.append(
                        criterion
                    )

                else:

                    b_better.append(
                        criterion
                    )


            elif direction == "낮을수록 좋음":

                if value_a < value_b:

                    a_better.append(
                        criterion
                    )

                else:

                    b_better.append(
                        criterion
                    )


            else:

                unavailable.append(
                    criterion
                )


        # =====================================================
        # 정성형 비교
        # =====================================================

        elif data_type == "qualitative":

            value_a = str(
                result_a["value"]
            ).strip()

            value_b = str(
                result_b["value"]
            ).strip()


            structured_labels = {
                "상",
                "중",
                "하"
            }


            # -------------------------------------------------
            # 상 / 중 / 하 구조화 데이터
            # -------------------------------------------------

            if (
                value_a in structured_labels
                and value_b in structured_labels
            ):

                if direction == "상 > 중 > 하":

                    qualitative_score = {
                        "상": 3,
                        "중": 2,
                        "하": 1
                    }


                elif direction == "하 > 중 > 상":

                    qualitative_score = {
                        "하": 3,
                        "중": 2,
                        "상": 1
                    }


                else:

                    unavailable.append(
                        criterion
                    )

                    continue


                score_a = (
                    qualitative_score[
                        value_a
                    ]
                )

                score_b = (
                    qualitative_score[
                        value_b
                    ]
                )


                if score_a > score_b:

                    a_better.append(
                        criterion
                    )


                elif score_b > score_a:

                    b_better.append(
                        criterion
                    )


                else:

                    equivalent.append(
                        criterion
                    )


            # -------------------------------------------------
            # 문장형 정보
            # -------------------------------------------------

            else:

                position_a = (
                    ai_position_lookup.get(
                        (
                            criterion,
                            candidate_a
                        )
                    )
                )

                position_b = (
                    ai_position_lookup.get(
                        (
                            criterion,
                            candidate_b
                        )
                    )
                )


                # AI 비교 미실행 / 정보 부족
                if (
                    position_a not in qualitative_position_score
                    or position_b not in qualitative_position_score
                ):

                    unavailable.append(
                        criterion
                    )

                    continue


                score_a = (
                    qualitative_position_score[
                        position_a
                    ]
                )

                score_b = (
                    qualitative_position_score[
                        position_b
                    ]
                )


                if score_a > score_b:

                    a_better.append(
                        criterion
                    )


                elif score_b > score_a:

                    b_better.append(
                        criterion
                    )


                else:

                    equivalent.append(
                        criterion
                    )


        else:

            unavailable.append(
                criterion
            )


    # =========================================================
    # 두 후보의 최종 관계 판정
    # =========================================================

    # 서로 하나 이상 우세한 항목이 존재
    if (
        a_better
        and b_better
    ):

        relation = "tradeoff"


    # A만 우세 + 빠진 정보 없음
    elif (
        a_better
        and not b_better
        and not unavailable
    ):

        relation = "a_dominates"


    # B만 우세 + 빠진 정보 없음
    elif (
        b_better
        and not a_better
        and not unavailable
    ):

        relation = "b_dominates"


    # 비교한 모든 항목이 사실상 동일
    elif (
        equivalent
        and not a_better
        and not b_better
        and not unavailable
    ):

        relation = "equivalent"


    # 나머지는 정보 부족
    else:

        relation = "insufficient"


    return {
        "candidate_a": candidate_a,
        "candidate_b": candidate_b,
        "relation": relation,
        "a_better": a_better,
        "b_better": b_better,
        "equivalent": equivalent,
        "unavailable": unavailable
    }


def build_pairwise_relations(
    candidate_names,
    confirmed_results,
    criterion_settings,
    ai_comparison_results=None
):
    """
    모든 후보 조합을 한 번씩 비교한다.
    예: A-B, A-C, A-D, B-C, B-D, C-D
    """

    relations = []


    for i in range(
        len(candidate_names)
    ):

        for j in range(
            i + 1,
            len(candidate_names)
        ):

            relation = (
                compare_candidate_pair(
                    candidate_a=(
                        candidate_names[i]
                    ),
                    candidate_b=(
                        candidate_names[j]
                    ),
                    confirmed_results=(
                        confirmed_results
                    ),
                    criterion_settings=(
                        criterion_settings
                    ),
                    ai_comparison_results=(
                        ai_comparison_results
                    )
                )
            )


            relations.append(
                relation
            )


    return relations

st.title("Engineering Decision Assistant")

tab_analysis, tab_review, tab_criteria, tab_compare = st.tabs(
    [
        "① 자료 분석",
        "② 추출 결과 검토",
        "③ 판단 기준",
        "④ 후보 비교·분석"
    ]
)

with tab_analysis:

    st.markdown(
        "## &lt; 자료 분석 &gt;",
        unsafe_allow_html=True
    )

    st.caption(
        "개발자료를 업로드하고 후보 비교에 필요한 정보를 추출합니다."
    )

    st.divider()


    # =========================================================
    # 1. 개발자료 업로드
    # =========================================================

    st.markdown("### 개발자료 업로드")

    st.write(
        "분석에 사용할 PDF 또는 Excel 파일을 업로드하세요."
    )


    uploaded_files = st.file_uploader(
        "PDF / Excel 파일 선택",
        type=["pdf", "xlsx"],
        accept_multiple_files=True
    )


    if uploaded_files:

        st.write(
            "업로드된 자료:",
            len(uploaded_files),
            "개"
        )

        for file in uploaded_files:

            file_type = (
                file.name
                .split(".")[-1]
                .upper()
            )

            file_size_mb = (
                file.size / (1024 * 1024)
            )

            st.write(
                "✓",
                file.name,
                "|",
                file_type,
                "|",
                f"{file_size_mb:.2f} MB"
            )

            try:

                # -------------------------------------------------
                # PDF
                # -------------------------------------------------

                if file_type == "PDF":

                    pages = read_pdf(file)

                    total_characters = sum(
                        len(page["text"].strip())
                        for page in pages
                    )

                    st.write(
                        "→ PDF /",
                        len(pages),
                        "페이지 /",
                        total_characters,
                        "자 추출"
                    )

                    average_characters = (
                        total_characters / len(pages)
                        if len(pages) > 0
                        else 0
                    )

                    if average_characters < 50:

                        st.warning(
                            "텍스트 추출량이 매우 적습니다. "
                            "스캔본 또는 이미지 중심 PDF일 수 있습니다."
                        )

                    else:

                        st.success(
                            "PDF 텍스트가 정상적으로 추출되었습니다."
                        )

                    with st.expander(
                        "추출 텍스트 미리보기"
                    ):

                        preview_text = ""

                        for page in pages:

                            preview_text += (
                                f"\n--- Page {page['page']} ---\n"
                            )

                            preview_text += (
                                page["text"]
                            )

                        st.text(
                            preview_text[:1000]
                        )


                # -------------------------------------------------
                # Excel
                # -------------------------------------------------

                elif file_type == "XLSX":

                    sheets = read_excel(file)

                    st.write(
                        "→ Excel /",
                        len(sheets),
                        "개 시트 정상 추출"
                    )


            except Exception as e:

                st.error(
                    f"파일 읽기 실패: {file.name}"
                )

                st.write(e)


    else:

        st.info(
            "분석할 자료를 업로드해주세요."
        )


    # =========================================================
    # 2. 추출 항목 설정
    # =========================================================

    st.markdown("### 추출 항목 설정")

    st.write(
        "먼저 AI가 문서에서 중요하게 다뤄지는 판단항목을 추천합니다. "
        "추천 결과를 확인한 뒤 필요한 항목을 선택하거나 직접 추가하세요."
    )


    # =====================================================
    # 기본 항목
    # =====================================================

    default_fields = [
        "개발기간",
        "원가",
        "품질",
        "호환성",
        "고객체감"
    ]


    # =====================================================
    # 현재 PDF 확인
    # =====================================================

    pdf_files_for_recommendation = []


    if uploaded_files:

        pdf_files_for_recommendation = [
            file

            for file
            in uploaded_files

            if file.name.lower().endswith(
                ".pdf"
            )
        ]


    # =====================================================
    # 추천 결과 Session State
    # =====================================================

    if (
        "field_recommendations"
        not in st.session_state
    ):

        st.session_state.field_recommendations = []


    if (
        "field_recommendation_signature"
        not in st.session_state
    ):

        st.session_state.field_recommendation_signature = None


    # =====================================================
    # 현재 PDF 상태 확인
    # =====================================================

    current_recommendation_signature = None


    if pdf_files_for_recommendation:

        recommendation_pdf = (
            pdf_files_for_recommendation[0]
        )


        current_recommendation_signature = (
            recommendation_pdf.name,
            recommendation_pdf.size
        )


        # -------------------------------------------------
        # 다른 PDF를 올렸다면 이전 추천 제거
        # -------------------------------------------------

        if (
            st.session_state.field_recommendation_signature
            is not None

            and

            st.session_state.field_recommendation_signature
            != current_recommendation_signature
        ):

            st.session_state.field_recommendations = []

            st.session_state.field_recommendation_signature = (
                None
            )


    # =====================================================
    # AI 추천 실행
    # =====================================================

    if pdf_files_for_recommendation:

        if st.button(
            "AI 추출항목 추천",
            type="primary",
            key="recommend_extraction_fields"
        ):

            try:

                with st.spinner(
                    "AI가 문서의 핵심 판단항목을 찾고 있습니다..."
                ):

                    recommendation_pages = (
                        read_pdf(
                            recommendation_pdf
                        )
                    )


                    field_recommendations = (
                        recommend_extraction_fields(
                            pages=(
                                recommendation_pages
                            ),

                            source_file=(
                                recommendation_pdf.name
                            )
                        )
                    )


                st.session_state.field_recommendations = (
                    field_recommendations
                )


                st.session_state.field_recommendation_signature = (
                    current_recommendation_signature
                )


                st.success(
                    f"추천 완료 · "
                    f"{len(field_recommendations)}개의 "
                    "판단항목을 찾았습니다."
                )


            except Exception as e:

                st.error(
                    "추출항목 추천 중 오류가 발생했습니다."
                )

                st.write(
                    e
                )


    else:

        st.info(
            "PDF를 업로드하면 AI가 추출항목을 추천할 수 있습니다."
        )


    # =====================================================
    # 추천 결과
    # =====================================================

    field_recommendations = (
        st.session_state.get(
            "field_recommendations",
            []
        )
    )


    recommended_field_names = [
        recommendation[
            "field"
        ]

        for recommendation
        in field_recommendations
    ]


    selected_recommended_fields = []


    if field_recommendations:

        st.markdown(
            "#### AI 추천 항목"
        )

        st.caption(
            "문서에서 후보를 비교할 때 중요하게 다뤄지는 "
            "판단축입니다. 필요 없는 항목은 선택 해제할 수 있습니다."
        )


        selected_recommended_fields = (
            st.multiselect(
                "추천 추출 항목",
                recommended_field_names,
                default=(
                    recommended_field_names
                ),
                key="selected_recommended_fields"
            )
        )


        # -------------------------------------------------
        # 추천 이유
        # -------------------------------------------------

        with st.expander(
            "추천 이유 보기",
            expanded=False
        ):

            for recommendation in (
                field_recommendations
            ):

                st.markdown(
                    f'**{recommendation["field"]}**'
                )


                st.write(
                    recommendation[
                        "reason"
                    ]
                )


                pages = (
                    recommendation.get(
                        "pages",
                        []
                    )
                )


                if pages:

                    st.caption(
                        "관련 페이지 · "
                        + ", ".join(
                            f"p.{page}"
                            for page
                            in pages
                        )
                    )


                st.divider()


    # =====================================================
    # 기본 항목 추가 선택
    # =====================================================

    remaining_default_fields = [
        field

        for field
        in default_fields

        if field
        not in recommended_field_names
    ]


    st.markdown(
        "#### 추가 항목 선택"
    )

    st.caption(
        "AI가 추천하지 않았더라도 필요하다고 판단되는 "
        "기본 항목을 추가할 수 있습니다."
    )


    selected_default_fields = (
        st.multiselect(
            "기본 항목에서 추가",
            remaining_default_fields,
            default=[],
            key="selected_extra_default_fields"
        )
    )


    # ---------------------------------------------------------
    # 자유추가 항목
    # ---------------------------------------------------------

    if "custom_fields" not in st.session_state:
        st.session_state.custom_fields = []


    # ---------------------------------------------------------
    # 입력창 + 추가 버튼
    # ---------------------------------------------------------

    input_col, button_col, spacer_col = st.columns(
        [4, 1, 3],
        vertical_alignment="bottom"
    )


    custom_field = input_col.text_input(
        "추가할 항목",
        placeholder="예: 디자인, 금형비, 검증 부담",
        key="custom_field_input"
    )


    if button_col.button(
        "항목 추가",
        use_container_width=True
    ):

        new_field = custom_field.strip()


        if not new_field:

            st.warning(
                "추가할 항목 이름을 입력해주세요."
            )


        elif (
            new_field in default_fields

            or

            new_field in recommended_field_names

            or

            new_field
            in st.session_state.custom_fields
        ):

            st.info(
                "이미 존재하는 항목입니다."
            )


        else:

            st.session_state.custom_fields.append(
                new_field
            )

            st.rerun()


    # ---------------------------------------------------------
    # 직접 추가한 항목 표시 + 삭제
    # ---------------------------------------------------------

    if st.session_state.custom_fields:

        st.caption(
            "직접 추가한 항목"
        )


        fields_per_row = 5


        for start in range(
            0,
            len(st.session_state.custom_fields),
            fields_per_row
        ):

            row_fields = (
                st.session_state.custom_fields[
                    start:start + fields_per_row
                ]
            )


            # 항상 5칸 고정
            # 항목이 1개여도 전체 폭을 먹지 않음
            field_columns = st.columns(
                fields_per_row
            )


            for index, field in enumerate(
                row_fields
            ):

                if field_columns[index].button(
                    f"{field}  ×",
                    key=f"remove_custom_{field}",
                    use_container_width=True
                ):

                    st.session_state.custom_fields.remove(
                        field
                    )

                    st.rerun()


    # ---------------------------------------------------------
    # 최종 추출항목 생성
    # ---------------------------------------------------------

    selected_fields = (
        selected_recommended_fields
        + selected_default_fields
        + st.session_state.custom_fields
    )


    selected_fields = list(
        dict.fromkeys(
            selected_fields
        )
    )


    st.write(
        "현재 추출 대상"
    )


    if selected_fields:

        st.write(
            " / ".join(
                selected_fields
            )
        )

    else:

        st.warning(
            "최소 한 개 이상의 추출 항목을 선택해주세요."
        )


    # =========================================================
    # 3. 추출 실행
    # =========================================================

    st.markdown(
        "### AI 정보 추출"
    )

    st.caption(
        "선택한 항목을 기준으로 문서에서 판단 근거를 추출합니다."
    )


    # ---------------------------------------------------------
    # 현재는 PDF를 AI 분석 대상으로 사용
    # ---------------------------------------------------------

    pdf_files = []


    if uploaded_files:

        pdf_files = [
            file
            for file in uploaded_files
            if file.name.lower().endswith(".pdf")
        ]


    if not pdf_files:

        st.info(
            "현재 AI 추출은 PDF 파일을 기준으로 진행합니다."
        )


    can_run_extraction = bool(
        pdf_files
        and selected_fields
    )


    # =========================================================
    # 실제 AI 추출
    # =========================================================

    if st.button(
        "AI 추출 실행",
        type="primary",
        disabled=not can_run_extraction
    ):

        source_pdf = pdf_files[0]

        source_file = source_pdf.name

        try:

            with st.spinner(
                "AI가 문서에서 판단 근거를 추출하고 있습니다..."
            ):

                pages = read_pdf(
                    source_pdf
                )

                (
                    requested_results,
                    suggested_results,
                    decision_candidates
                ) = extract_evidence(
                    pages=pages,
                    selected_fields=selected_fields,
                    source_file=source_file
                )


            st.session_state.extracted_results = (
                requested_results
            )

            st.session_state.suggested_results = (
                suggested_results
            )
            
            st.session_state.decision_candidates = (
                decision_candidates
            )
            
            st.session_state.confirmed_results = []


            if requested_results:

                st.success(
                    f"추출 완료 · "
                    f"{len(requested_results)}건의 근거를 찾았습니다."
                )

            else:

                st.warning(
                    "선택한 항목에 해당하는 명시적 근거를 찾지 못했습니다."
                )


        except Exception as e:

            st.error(
                "AI 추출 중 오류가 발생했습니다."
            )

            st.write(e)


    # =========================================================
    # 개발용 Mock
    # =========================================================

    with st.expander(
        "개발용 기능",
        expanded=False
    ):

        if st.button(
            "Mock 데이터로 테스트",
            disabled=not can_run_extraction
        ):

            source_file = pdf_files[0].name

            (
                requested_results,
                suggested_results
            ) = build_mock_results(
                selected_fields,
                source_file
            )

            st.session_state.extracted_results = (
                requested_results
            )

            st.session_state.suggested_results = (
                suggested_results
            )

            mock_decision_candidates = list(
                dict.fromkeys(
                    result.get(
                        "candidate"
                    )

                    for result
                    in requested_results

                    if result.get(
                        "candidate"
                    )
                    and result.get(
                        "candidate"
                    )
                    != "공통 정보"
                )
            )


            st.session_state.decision_candidates = (
                mock_decision_candidates
            )

            st.session_state.confirmed_results = []

            st.success(
                "Mock 추출이 완료되었습니다."
            )

with tab_review:

    st.markdown(
        "## &lt; 추출 결과 검토 &gt;",
        unsafe_allow_html=True
    )

    st.caption(
        "AI가 찾은 정보를 확인하고 필요한 경우 수정한 뒤 최종 확정합니다."
    )

    st.divider()


    # ---------------------------------------------------------
    # 검토 현황 요약
    # ---------------------------------------------------------

    extracted_results = (
        st.session_state.get(
            "extracted_results",
            []
        )
    )

    suggested_results = (
        st.session_state.get(
            "suggested_results",
            []
        )
    )


    total_count = len(
        extracted_results
    )

    approved_count = sum(
        1
        for result in extracted_results
        if result.get("status") == "승인 완료"
    )

    review_count = (
        total_count - approved_count
    )

    suggested_count = len(
        suggested_results
    )


    metric_total, metric_approved, metric_review, metric_suggested = (
        st.columns(4)
    )

    metric_total.metric(
        "전체 추출 결과",
        total_count
    )

    metric_approved.metric(
        "확정 완료",
        approved_count
    )

    metric_review.metric(
        "확인 필요",
        review_count
    )

    metric_suggested.metric(
        "추가로 찾은 정보",
        suggested_count
    )


    st.divider()

    with st.container():
    
            # =========================================================
            # 추가로 찾은 정보
            # =========================================================
    
            suggested_results = (
                st.session_state.get(
                    "suggested_results",
                    []
                )
            )
    
    
            st.markdown(
                f"### 추가로 확인할 정보 · {suggested_count}건"
            )

            if suggested_count > 0:

                st.info(
                    f"AI가 후보 비교에 도움이 될 수 있는 정보를 "
                    f"{suggested_count}건 추가로 찾았습니다. "
                    "필요한 정보만 확인해 반영하세요."
                )

            else:

                st.success(
                    "추가 정보 확인이 완료되었습니다."
                )

            st.caption(
                "비슷한 내용은 하나로 묶어두었습니다. "
                "기존 항목에 연결하거나 새로운 비교 항목으로 추가할 수 있습니다."
            )            
    
    
            # =========================================================
            # 참고정보 저장공간
            # =========================================================
    
            if "reference_results" not in st.session_state:
    
                st.session_state.reference_results = []
    
    
            if suggested_results:
    
                # =====================================================
                # 후보 표시 순서
                # =====================================================
    
                candidate_names_for_sort = list(
                    dict.fromkeys(
                        result["candidate"]
    
                        for result
                        in st.session_state.get(
                            "extracted_results",
                            []
                        )
    
                        if result.get(
                            "candidate"
                        )
                        != "공통 정보"
                    )
                )
    
    
                candidate_order = {
                    candidate: index
    
                    for index, candidate
                    in enumerate(
                        candidate_names_for_sort
                    )
                }
    
    
                # =====================================================
                # 이전 형식 데이터도 깨지지 않도록 정규화
                # =====================================================
    
                normalized_suggestions = []
    
    
                for original_index, suggestion in enumerate(
                    suggested_results
                ):
    
                    suggestion_type = (
                        suggestion.get(
                            "suggestion_type"
                        )
                    )
    
    
                    # 이전 Mock / 이전 세션 데이터 방어
                    if suggestion_type not in [
                        "existing_field",
                        "new_field",
                        "reference"
                    ]:
    
                        if not suggestion.get(
                            "addable_to_candidate",
                            True
                        ):
    
                            suggestion_type = (
                                "reference"
                            )
    
                        else:
    
                            suggestion_type = (
                                "new_field"
                            )
    
    
                    target_field = (
                        suggestion.get(
                            "target_field"
                        )
                    )
    
    
                    group_name = (
                        suggestion.get(
                            "group_name"
                        )
                        or target_field
                        or suggestion.get(
                            "suggested_field"
                        )
                        or "기타"
                    )
    
    
                    normalized_suggestions.append(
                        {
                            "original_index": (
                                original_index
                            ),
    
                            "suggestion_type": (
                                suggestion_type
                            ),
    
                            "target_field": (
                                target_field
                            ),
    
                            "group_name": (
                                group_name
                            ),
    
                            "suggestion": (
                                suggestion
                            )
                        }
                    )
    
    
                # =====================================================
                # 사용자에게 보여줄 순서
                #
                # 1. 기존 항목 연결
                # 2. 새로운 비교 항목
                # 3. 참고정보
                # =====================================================
    
                suggestion_type_order = {
                    "existing_field": 0,
                    "new_field": 1,
                    "reference": 2
                }
    
    
                normalized_suggestions = sorted(
                    normalized_suggestions,
    
                    key=lambda item: (
                        suggestion_type_order.get(
                            item[
                                "suggestion_type"
                            ],
                            99
                        ),
    
                        str(
                            item[
                                "target_field"
                            ]
                            or item[
                                "group_name"
                            ]
                        ),
    
                        candidate_order.get(
                            item[
                                "suggestion"
                            ].get(
                                "candidate"
                            ),
                            999
                        ),
    
                        item[
                            "suggestion"
                        ].get(
                            "page",
                            999
                        )
                    )
                )
    
    
                # =====================================================
                # 비슷한 정보끼리 그룹 생성
                # =====================================================
    
                grouped_suggestions = {}
    
    
                for item in normalized_suggestions:
    
                    suggestion_type = (
                        item[
                            "suggestion_type"
                        ]
                    )
    
    
                    if suggestion_type == "existing_field":
    
                        group_label = (
                            item[
                                "target_field"
                            ]
                            or item[
                                "group_name"
                            ]
                        )
    
                    else:
    
                        group_label = (
                            item[
                                "group_name"
                            ]
                        )
    
    
                    group_key = (
                        suggestion_type,
                        group_label
                    )
    
    
                    if (
                        group_key
                        not in grouped_suggestions
                    ):
    
                        grouped_suggestions[
                            group_key
                        ] = []
    
    
                    grouped_suggestions[
                        group_key
                    ].append(
                        item
                    )
    
    
                # =====================================================
                # 그룹 삭제용 함수
                # =====================================================
    
                def remove_suggestion_group(
                    group_items
                ):
    
                    indices = sorted(
                        [
                            item[
                                "original_index"
                            ]
    
                            for item
                            in group_items
                        ],
                        reverse=True
                    )
    
    
                    for index in indices:
    
                        st.session_state.suggested_results.pop(
                            index
                        )
    
    
                # =====================================================
                # 그룹 하나의 세부 정보 표시
                # =====================================================
    
                def display_group_items(
                    group_items
                ):
    
                    for item_number, item in enumerate(
                        group_items,
                        start=1
                    ):
    
                        suggestion = (
                            item[
                                "suggestion"
                            ]
                        )
    
    
                        candidate = (
                            suggestion.get(
                                "candidate"
                            )
                            or "공통 정보"
                        )
    
    
                        suggestion_value = (
                            format_value(
                                suggestion.get(
                                    "value",
                                    ""
                                ),
                                suggestion.get(
                                    "unit"
                                )
                            )
                        )
    
    
                        st.markdown(
                            f"**{candidate}**"
                        )
    
    
                        st.write(
                            suggestion_value
                        )
    
    
                        st.caption(
                            f'출처 · '
                            f'{suggestion.get("source_file", "-")} '
                            f'/ p.{suggestion.get("page", "-")}'
                        )
    
    
                        if suggestion.get(
                            "reason"
                        ):
    
                            st.write(
                                "왜 중요한가:",
                                suggestion[
                                    "reason"
                                ]
                            )
    
    
                        if suggestion.get(
                            "evidence"
                        ):
    
                            st.write(
                                "원문 근거:",
                                suggestion[
                                    "evidence"
                                ]
                            )
    
    
                        if (
                            item_number
                            < len(
                                group_items
                            )
                        ):
    
                            st.divider()
    
    
                # =====================================================
                # ① 기존 항목에 연결할 정보
                # =====================================================
    
                existing_groups = [
                    (
                        group_key,
                        group_items
                    )
    
                    for group_key, group_items
                    in grouped_suggestions.items()
    
                    if group_key[0]
                    == "existing_field"
                ]
    
    
                if existing_groups:
    
                    st.markdown(
                        "#### 기존 항목에 연결할 정보"
                    )
    
                    st.caption(
                        "이미 사용 중인 항목과 의미가 비슷한 정보입니다. "
                        "새 항목을 만들지 않고 기존 항목의 근거로 연결할 수 있습니다."
                    )
    
    
                    for group_index, (
                        group_key,
                        group_items
                    ) in enumerate(
                        existing_groups
                    ):
    
                        target_field = (
                            group_key[1]
                        )
    
    
                        with st.expander(
                            f"{target_field} · "
                            f"{len(group_items)}건",
                            expanded=False
                        ):
    
                            display_group_items(
                                group_items
                            )
    
    
                            action_col, ignore_col, spacer_col = (
                                st.columns(
                                    [1.5, 1, 3]
                                )
                            )
    
    
                            # =========================================
                            # 기존 판단항목에 연결
                            # =========================================
    
                            if action_col.button(
                                f"'{target_field}'에 연결",
                                key=(
                                    f"connect_existing_"
                                    f"{group_index}_"
                                    f"{target_field}"
                                ),
                                use_container_width=True,
                                type="primary"
                            ):
    
                                for item in group_items:
    
                                    suggestion = (
                                        item[
                                            "suggestion"
                                        ]
                                    )
    
    
                                    candidate = (
                                        suggestion.get(
                                            "candidate"
                                        )
                                    )
    
    
                                    # 공통정보는 후보 데이터로 만들지 않음
                                    if (
                                        candidate
                                        == "공통 정보"
                                        or not suggestion.get(
                                            "addable_to_candidate",
                                            True
                                        )
                                    ):
    
                                        continue
    
    
                                    # ---------------------------------
                                    # 기존 candidate + field가 있는지
                                    # ---------------------------------
    
                                    existing_result = next(
                                        (
                                            result
    
                                            for result
                                            in st.session_state.extracted_results
    
                                            if (
                                                result[
                                                    "candidate"
                                                ]
                                                == candidate
    
                                                and
    
                                                result[
                                                    "field"
                                                ]
                                                == target_field
                                            )
                                        ),
                                        None
                                    )
    
    
                                    # ---------------------------------
                                    # 이미 있으면 새 행을 만들지 않고
                                    # 근거를 기존 결과에 합침
                                    # ---------------------------------
    
                                    if existing_result:
    
                                        extra_evidence = str(
                                            suggestion.get(
                                                "evidence",
                                                ""
                                            )
                                        ).strip()
    
    
                                        if (
                                            extra_evidence
    
                                            and
    
                                            extra_evidence
                                            not in str(
                                                existing_result.get(
                                                    "evidence",
                                                    ""
                                                )
                                            )
                                        ):
    
                                            existing_result[
                                                "evidence"
                                            ] = (
                                                str(
                                                    existing_result.get(
                                                        "evidence",
                                                        ""
                                                    )
                                                ).rstrip()
    
                                                + "\n\n[추가 근거] "
    
                                                + extra_evidence
                                            )
    
    
                                        # 정성정보라면
                                        # 추가 내용도 비교에 활용 가능하도록
                                        # 값에 함께 보존
                                        if (
                                            existing_result.get(
                                                "data_type"
                                            )
                                            == "qualitative"
                                        ):
    
                                            extra_value = str(
                                                suggestion.get(
                                                    "value",
                                                    ""
                                                )
                                            ).strip()
    
    
                                            current_value = str(
                                                existing_result.get(
                                                    "value",
                                                    ""
                                                )
                                            ).strip()
    
    
                                            if (
                                                extra_value
    
                                                and
    
                                                extra_value
                                                not in current_value
                                            ):
    
                                                existing_result[
                                                    "value"
                                                ] = (
                                                    current_value
                                                    + " / "
                                                    + extra_value
                                                )
    
    
                                        # 이미 확정했던 항목이라도
                                        # 근거가 추가되었으므로 재확인
                                        existing_result[
                                            "status"
                                        ] = "검토 필요"
    
    
                                    # ---------------------------------
                                    # 해당 후보에 기존 항목 결과가 없으면
                                    # 새 결과로 추가
                                    # ---------------------------------
    
                                    else:
    
                                        new_result = {
                                            "candidate": (
                                                candidate
                                            ),
    
                                            "field": (
                                                target_field
                                            ),
    
                                            "value": (
                                                suggestion[
                                                    "value"
                                                ]
                                            ),
    
                                            "unit": (
                                                suggestion[
                                                    "unit"
                                                ]
                                            ),
    
                                            "original_candidate": (
                                                candidate
                                            ),
    
                                            "original_field": (
                                                target_field
                                            ),
    
                                            "original_value": (
                                                suggestion[
                                                    "value"
                                                ]
                                            ),
    
                                            "original_unit": (
                                                suggestion[
                                                    "unit"
                                                ]
                                            ),
    
                                            "data_type": (
                                                suggestion[
                                                    "data_type"
                                                ]
                                            ),
    
                                            "source_file": (
                                                suggestion[
                                                    "source_file"
                                                ]
                                            ),
    
                                            "page": (
                                                suggestion[
                                                    "page"
                                                ]
                                            ),
    
                                            "evidence": (
                                                suggestion[
                                                    "evidence"
                                                ]
                                            ),
    
                                            "status": (
                                                "검토 필요"
                                            ),
    
                                            "modified_by_user": (
                                                False
                                            )
                                        }
    
    
                                        st.session_state.extracted_results.append(
                                            new_result
                                        )
    
    
                                remove_suggestion_group(
                                    group_items
                                )
    
                                st.rerun()
    
    
                            if ignore_col.button(
                                "무시",
                                key=(
                                    f"ignore_existing_"
                                    f"{group_index}_"
                                    f"{target_field}"
                                ),
                                use_container_width=True
                            ):
    
                                remove_suggestion_group(
                                    group_items
                                )
    
                                st.rerun()
    
    
                    st.markdown(
                        "<div style='height: 16px;'></div>",
                        unsafe_allow_html=True
                    )
    
    
                # =====================================================
                # ② 새로운 비교 항목 후보
                # =====================================================
    
                new_field_groups = [
                    (
                        group_key,
                        group_items
                    )
    
                    for group_key, group_items
                    in grouped_suggestions.items()
    
                    if group_key[0]
                    == "new_field"
                ]
    
    
                if new_field_groups:
    
                    st.markdown(
                        "#### 새로운 비교 항목 후보"
                    )
    
                    st.caption(
                        "기존 항목과는 다른 판단 기준으로 볼 수 있는 정보입니다. "
                        "비슷한 내용은 하나의 항목으로 묶었습니다."
                    )
    
    
                    for group_index, (
                        group_key,
                        group_items
                    ) in enumerate(
                        new_field_groups
                    ):
    
                        group_name = (
                            group_key[1]
                        )
    
    
                        with st.expander(
                            f"{group_name} · "
                            f"{len(group_items)}건",
                            expanded=False
                        ):
    
                            display_group_items(
                                group_items
                            )
    
    
                            action_col, ignore_col, spacer_col = (
                                st.columns(
                                    [1.7, 1, 3]
                                )
                            )
    
    
                            # =========================================
                            # 새 비교항목으로 추가
                            # =========================================
    
                            if action_col.button(
                                f"'{group_name}'으로 추가",
                                key=(
                                    f"add_new_group_"
                                    f"{group_index}_"
                                    f"{group_name}"
                                ),
                                use_container_width=True,
                                type="primary"
                            ):
    
                                for item in group_items:
    
                                    suggestion = (
                                        item[
                                            "suggestion"
                                        ]
                                    )
    
    
                                    candidate = (
                                        suggestion.get(
                                            "candidate"
                                        )
                                    )
    
    
                                    # 공통정보를 후보로 만들지 않음
                                    if (
                                        candidate
                                        == "공통 정보"
                                        or not suggestion.get(
                                            "addable_to_candidate",
                                            True
                                        )
                                    ):
    
                                        continue
    
    
                                    existing_result = next(
                                        (
                                            result
    
                                            for result
                                            in st.session_state.extracted_results
    
                                            if (
                                                result[
                                                    "candidate"
                                                ]
                                                == candidate
    
                                                and
    
                                                result[
                                                    "field"
                                                ]
                                                == group_name
                                            )
                                        ),
                                        None
                                    )
    
    
                                    # 같은 후보 + 같은 그룹 정보가
                                    # 여러 건이면 한 항목 안에 합침
                                    if existing_result:
    
                                        extra_evidence = str(
                                            suggestion.get(
                                                "evidence",
                                                ""
                                            )
                                        ).strip()
    
    
                                        if (
                                            extra_evidence
    
                                            and
    
                                            extra_evidence
                                            not in str(
                                                existing_result.get(
                                                    "evidence",
                                                    ""
                                                )
                                            )
                                        ):
    
                                            existing_result[
                                                "evidence"
                                            ] = (
                                                str(
                                                    existing_result.get(
                                                        "evidence",
                                                        ""
                                                    )
                                                ).rstrip()
    
                                                + "\n\n[추가 근거] "
    
                                                + extra_evidence
                                            )
    
    
                                        if (
                                            existing_result.get(
                                                "data_type"
                                            )
                                            == "qualitative"
                                        ):
    
                                            extra_value = str(
                                                suggestion.get(
                                                    "value",
                                                    ""
                                                )
                                            ).strip()
    
    
                                            current_value = str(
                                                existing_result.get(
                                                    "value",
                                                    ""
                                                )
                                            ).strip()
    
    
                                            if (
                                                extra_value
    
                                                and
    
                                                extra_value
                                                not in current_value
                                            ):
    
                                                existing_result[
                                                    "value"
                                                ] = (
                                                    current_value
                                                    + " / "
                                                    + extra_value
                                                )
    
    
                                    else:
    
                                        new_result = {
                                            "candidate": (
                                                candidate
                                            ),
    
                                            "field": (
                                                group_name
                                            ),
    
                                            "value": (
                                                suggestion[
                                                    "value"
                                                ]
                                            ),
    
                                            "unit": (
                                                suggestion[
                                                    "unit"
                                                ]
                                            ),
    
                                            "original_candidate": (
                                                candidate
                                            ),
    
                                            "original_field": (
                                                group_name
                                            ),
    
                                            "original_value": (
                                                suggestion[
                                                    "value"
                                                ]
                                            ),
    
                                            "original_unit": (
                                                suggestion[
                                                    "unit"
                                                ]
                                            ),
    
                                            "data_type": (
                                                suggestion[
                                                    "data_type"
                                                ]
                                            ),
    
                                            "source_file": (
                                                suggestion[
                                                    "source_file"
                                                ]
                                            ),
    
                                            "page": (
                                                suggestion[
                                                    "page"
                                                ]
                                            ),
    
                                            "evidence": (
                                                suggestion[
                                                    "evidence"
                                                ]
                                            ),
    
                                            "status": (
                                                "검토 필요"
                                            ),
    
                                            "modified_by_user": (
                                                False
                                            )
                                        }
    
    
                                        st.session_state.extracted_results.append(
                                            new_result
                                        )
    
    
                                # custom_fields에도 대표 그룹명만 추가
                                if (
                                    group_name
                                    not in default_fields
    
                                    and
    
                                    group_name
                                    not in st.session_state.custom_fields
                                ):
    
                                    st.session_state.custom_fields.append(
                                        group_name
                                    )
    
    
                                remove_suggestion_group(
                                    group_items
                                )
    
                                st.rerun()
    
    
                            if ignore_col.button(
                                "무시",
                                key=(
                                    f"ignore_new_"
                                    f"{group_index}_"
                                    f"{group_name}"
                                ),
                                use_container_width=True
                            ):
    
                                remove_suggestion_group(
                                    group_items
                                )
    
                                st.rerun()
    
    
                    st.markdown(
                        "<div style='height: 16px;'></div>",
                        unsafe_allow_html=True
                    )
    
    
                # =====================================================
                # ③ 참고할 공통 정보
                # =====================================================
    
                reference_groups = [
                    (
                        group_key,
                        group_items
                    )
    
                    for group_key, group_items
                    in grouped_suggestions.items()
    
                    if group_key[0]
                    == "reference"
                ]
    
    
                if reference_groups:
    
                    st.markdown(
                        "#### 참고할 공통 정보"
                    )
    
                    st.caption(
                        "특정 후보의 비교값으로 넣기보다는 "
                        "전체 판단 과정에서 참고할 조건이나 배경정보입니다."
                    )
    
    
                    for group_index, (
                        group_key,
                        group_items
                    ) in enumerate(
                        reference_groups
                    ):
    
                        group_name = (
                            group_key[1]
                        )
    
    
                        with st.expander(
                            f"{group_name} · "
                            f"{len(group_items)}건",
                            expanded=False
                        ):
    
                            display_group_items(
                                group_items
                            )
    
    
                            keep_col, ignore_col, spacer_col = (
                                st.columns(
                                    [1.5, 1, 3]
                                )
                            )
    
    
                            # =========================================
                            # 참고정보로 보관
                            # =========================================
    
                            if keep_col.button(
                                "참고 정보로 보관",
                                key=(
                                    f"keep_reference_"
                                    f"{group_index}_"
                                    f"{group_name}"
                                ),
                                use_container_width=True,
                                type="primary"
                            ):
    
                                for item in group_items:
    
                                    suggestion = (
                                        item[
                                            "suggestion"
                                        ]
                                    )
    
    
                                    reference_result = {
                                        "group_name": (
                                            group_name
                                        ),
    
                                        "value": (
                                            suggestion.get(
                                                "value"
                                            )
                                        ),
    
                                        "unit": (
                                            suggestion.get(
                                                "unit"
                                            )
                                        ),
    
                                        "source_file": (
                                            suggestion.get(
                                                "source_file"
                                            )
                                        ),
    
                                        "page": (
                                            suggestion.get(
                                                "page"
                                            )
                                        ),
    
                                        "evidence": (
                                            suggestion.get(
                                                "evidence"
                                            )
                                        ),
    
                                        "reason": (
                                            suggestion.get(
                                                "reason"
                                            )
                                        )
                                    }
    
    
                                    reference_key = (
                                        reference_result[
                                            "group_name"
                                        ],
    
                                        reference_result[
                                            "source_file"
                                        ],
    
                                        reference_result[
                                            "page"
                                        ],
    
                                        reference_result[
                                            "evidence"
                                        ]
                                    )
    
    
                                    already_saved = any(
                                        (
                                            saved.get(
                                                "group_name"
                                            ),
    
                                            saved.get(
                                                "source_file"
                                            ),
    
                                            saved.get(
                                                "page"
                                            ),
    
                                            saved.get(
                                                "evidence"
                                            )
                                        )
                                        == reference_key
    
                                        for saved
                                        in st.session_state.reference_results
                                    )
    
    
                                    if not already_saved:
    
                                        st.session_state.reference_results.append(
                                            reference_result
                                        )
    
    
                                remove_suggestion_group(
                                    group_items
                                )
    
                                st.rerun()
    
    
                            if ignore_col.button(
                                "무시",
                                key=(
                                    f"ignore_reference_"
                                    f"{group_index}_"
                                    f"{group_name}"
                                ),
                                use_container_width=True
                            ):
    
                                remove_suggestion_group(
                                    group_items
                                )
    
                                st.rerun()
    
    
                # =====================================================
                # 아무 그룹도 없는 예외
                # =====================================================
    
                if not grouped_suggestions:
    
                    st.info(
                        "검토할 추가 정보가 없습니다."
                    )
    
    
            else:
    
                st.info(
                    "검토할 추가 정보가 없습니다."
                )
    
    
            # =========================================================
            # 보관한 참고 정보
            # =========================================================
    
            saved_references = (
                st.session_state.get(
                    "reference_results",
                    []
                )
            )
    
    
            if saved_references:
    
                st.markdown(
                    "<div style='height: 20px;'></div>",
                    unsafe_allow_html=True
                )
    
    
                with st.expander(
                    f"보관한 참고 정보 · "
                    f"{len(saved_references)}건",
                    expanded=False
                ):
    
                    for index, reference in enumerate(
                        saved_references
                    ):
    
                        st.markdown(
                            f'**{reference.get("group_name", "참고 정보")}**'
                        )
    
                        st.write(
                            format_value(
                                reference.get(
                                    "value",
                                    ""
                                ),
                                reference.get(
                                    "unit"
                                )
                            )
                        )
    
                        st.caption(
                            f'출처 · '
                            f'{reference.get("source_file", "-")} '
                            f'/ p.{reference.get("page", "-")}'
                        )
    
    
                        if reference.get(
                            "reason"
                        ):
    
                            st.write(
                                "왜 중요한가:",
                                reference[
                                    "reason"
                                ]
                            )
    
    
                        if (
                            index
                            < len(
                                saved_references
                            ) - 1
                        ):
    
                            st.divider()

    st.markdown(
        "<div style='height: 28px;'></div>",
        unsafe_allow_html=True
    )

    st.divider()

    st.markdown(
        "<div style='height: 12px;'></div>",
        unsafe_allow_html=True
    )

    with st.container():
    
        # =========================================================
        # 요청 항목 추출 결과 표시
        # =========================================================

        if (
            "extracted_results"
            in st.session_state
        ):

            requested_results = (
                st.session_state.extracted_results
            )

            st.markdown(
                "### 추출 결과"
            )

            st.caption(
                "처음 요청한 항목과 추가로 반영한 정보를 한눈에 확인합니다."
            )


            display_rows = []


            for result in requested_results:

                display_rows.append(
                    {
                        "후보": (
                            result["candidate"]
                        ),

                        "항목": (
                            result["field"]
                        ),

                        "결과": format_value(
                            result["value"],
                            result["unit"]
                        ),

                        "출처": (
                            f'{result["source_file"]} '
                            f'/ p.{result["page"]}'
                        ),

                        "상태": (
                            result["status"]
                        )
                    }
                )


            result_df = pd.DataFrame(
                display_rows
            )


            st.dataframe(
                result_df,
                use_container_width=True,
                hide_index=True
            )


            # -----------------------------------------------------
            # 근거 확인
            # -----------------------------------------------------

            with st.expander(
                "원문 근거 보기"
            ):

                for result in requested_results:

                    st.markdown(
                        f'**{result["candidate"]} / '
                        f'{result["field"]}**'
                    )

                    st.write(
                        "근거:",
                        result["evidence"]
                    )

                    st.write(
                        "출처:",
                        result["source_file"],
                        "/",
                        f'p.{result["page"]}'
                    )

                    st.divider()

    

    with st.container():

        # =========================================================
        # Evidence 개별 검토
        # =========================================================

        if (
            "extracted_results" in st.session_state
            and st.session_state.extracted_results
        ):

            review_results = (
                st.session_state.extracted_results
            )


            # -----------------------------------------------------
            # 위 결과표와 검토영역 사이 구분
            # -----------------------------------------------------

            st.markdown(
                "<div style='height: 24px;'></div>",
                unsafe_allow_html=True
            )

            st.divider()

            st.markdown(
                "### 추출 결과 확인"
            )

            st.caption(
                "확인할 항목을 선택해 원문 근거와 추출값을 확인하고 "
                "필요하면 수정한 뒤 확정하세요."
            )


            # -----------------------------------------------------
            # 검토할 Evidence 선택
            # -----------------------------------------------------

            review_options = []


            for index, result in enumerate(
                review_results
            ):

                label = (
                    f'{index + 1}. '
                    f'{result["candidate"]} / '
                    f'{result["field"]} / '
                    f'{format_value(result["value"], result["unit"])} '
                    f'[{result["status"]}]'
                )

                review_options.append(
                    label
                )


            selected_review_label = (
                st.selectbox(
                    "확인할 항목",
                    review_options,
                    key="review_evidence_selector"
                )
            )


            selected_index = (
                review_options.index(
                    selected_review_label
                )
            )


            selected_result = (
                review_results[
                    selected_index
                ]
            )


            st.markdown(
                "<div style='height: 14px;'></div>",
                unsafe_allow_html=True
            )


            # =====================================================
            # 선택 Evidence 카드
            # =====================================================

            with st.container(
                border=True
            ):

                # -------------------------------------------------
                # Evidence Header
                # -------------------------------------------------

                header_left, header_right = (
                    st.columns(
                        [5, 1]
                    )
                )


                header_left.markdown(
                    f'#### '
                    f'{selected_result["candidate"]} · '
                    f'{selected_result["field"]}'
                )


                header_right.markdown(
                    f'**{selected_result["status"]}**'
                )


                st.caption(
                    f'출처 · '
                    f'{selected_result["source_file"]} '
                    f'/ p.{selected_result["page"]}'
                )


                # -------------------------------------------------
                # 근거
                # -------------------------------------------------

                st.markdown(
                    "**근거**"
                )

                st.write(
                    selected_result[
                        "evidence"
                    ]
                )


                if selected_result.get(
                    "modified_by_user",
                    False
                ):

                    st.info(
                        "사용자가 수정한 Evidence입니다."
                    )

                    st.caption(
                        "최초 추출값 · "
                        + format_value(
                            selected_result.get(
                                "original_value"
                            ),
                            selected_result.get(
                                "original_unit"
                            )
                        )
                    )


                st.markdown(
                    "<div style='height: 10px;'></div>",
                    unsafe_allow_html=True
                )

                st.divider()


                # -------------------------------------------------
                # 값 수정
                # -------------------------------------------------

                st.markdown(
                    "**추출값 수정**"
                )


                with st.form(
                    key=f"edit_form_{selected_index}"
                ):

                    candidate_col, field_col = (
                        st.columns(2)
                    )


                    edited_candidate = (
                        candidate_col.text_input(
                            "후보",
                            value=str(
                                selected_result[
                                    "candidate"
                                ]
                            )
                        )
                    )


                    edited_field = (
                        field_col.text_input(
                            "항목",
                            value=str(
                                selected_result[
                                    "field"
                                ]
                            )
                        )
                    )


                    value_col, unit_col = (
                        st.columns(
                            [4, 1]
                        )
                    )


                    edited_value_text = (
                        value_col.text_input(
                            "값",
                            value=str(
                                selected_result[
                                    "value"
                                ]
                            )
                        )
                    )


                    edited_unit = (
                        unit_col.text_input(
                            "단위",
                            value=(
                                selected_result[
                                    "unit"
                                ]
                                if selected_result[
                                    "unit"
                                ]
                                else ""
                            )
                        )
                    )


                    save_edit = (
                        st.form_submit_button(
                            "수정 저장"
                        )
                    )


                # -------------------------------------------------
                # 수정 저장 처리
                # -------------------------------------------------

                if save_edit:

                    try:

                        parsed_value = (
                            parse_input_value(
                                edited_value_text,
                                selected_result[
                                    "data_type"
                                ]
                            )
                        )


                        selected_result[
                            "candidate"
                        ] = (
                            edited_candidate.strip()
                        )


                        selected_result[
                            "field"
                        ] = (
                            edited_field.strip()
                        )


                        selected_result[
                            "value"
                        ] = parsed_value


                        selected_result[
                            "unit"
                        ] = (
                            edited_unit.strip()
                            if edited_unit.strip()
                            else None
                        )


                        selected_result[
                            "modified_by_user"
                        ] = True


                        selected_result[
                            "status"
                        ] = "수정됨"


                        st.rerun()


                    except ValueError:

                        st.error(
                            "정량 데이터는 숫자로 입력해주세요."
                        )


                # -------------------------------------------------
                # 승인
                # -------------------------------------------------

                st.markdown(
                    "<div style='height: 12px;'></div>",
                    unsafe_allow_html=True
                )


                approve_col, approve_all_col, spacer_col = (
                    st.columns(
                        [1.4, 1.2, 3]
                    )
                )


                if approve_col.button(
                    "선택 항목 확정",
                    type="primary",
                    use_container_width=True,
                    key="approve_selected_evidence"
                ):

                    selected_result[
                        "status"
                    ] = "승인 완료"

                    st.rerun()


                if approve_all_col.button(
                    "전체 확정",
                    use_container_width=True,
                    key="approve_all_evidence"
                ):

                    for result in (
                        st.session_state.extracted_results
                    ):

                        result[
                            "status"
                        ] = "승인 완료"


                    st.rerun()


            # =====================================================
            # 승인 현황
            # =====================================================

            confirmed_results = [
                result.copy()

                for result
                in st.session_state.extracted_results

                if result.get(
                    "status"
                )
                == "승인 완료"
            ]


            st.session_state.confirmed_results = (
                confirmed_results
            )


            approved_count = (
                len(
                    confirmed_results
                )
            )


            total_count = (
                len(
                    st.session_state.extracted_results
                )
            )


            # 선택 카드와 승인 결과 사이 간격
            st.markdown(
                "<div style='height: 28px;'></div>",
                unsafe_allow_html=True
            )

            st.divider()


            status_col, detail_col = (
                st.columns(
                    [2, 5]
                )
            )


            status_col.markdown(
                f"**확정 현황 · "
                f"{approved_count} / "
                f"{total_count}건**"
            )


            # -----------------------------------------------------
            # 승인된 Evidence 상세
            # -----------------------------------------------------

            if confirmed_results:

                with st.expander(
                    f"확정된 정보 보기 · "
                    f"{len(confirmed_results)}건",
                    expanded=False
                ):

                    confirmed_display_rows = []


                    for result in (
                        confirmed_results
                    ):

                        confirmed_display_rows.append(
                            {
                                "후보": (
                                    result[
                                        "candidate"
                                    ]
                                ),

                                "항목": (
                                    result[
                                        "field"
                                    ]
                                ),

                                "결과": (
                                    format_value(
                                        result[
                                            "value"
                                        ],
                                        result[
                                            "unit"
                                        ]
                                    )
                                ),

                                "출처": (
                                    f'{result["source_file"]} '
                                    f'/ p.{result["page"]}'
                                ),

                                "사용자 수정": (
                                    "Yes"
                                    if result.get(
                                        "modified_by_user",
                                        False
                                    )
                                    else "No"
                                )
                            }
                        )


                    confirmed_df = (
                        pd.DataFrame(
                            confirmed_display_rows
                        )
                    )


                    st.dataframe(
                        confirmed_df,
                        use_container_width=True,
                        hide_index=True
                    )


            else:

                st.info(
                    "아직 확정된 정보가 없습니다."
                )
    
with tab_criteria:

    st.markdown(
        "## &lt; 판단 기준 &gt;",
        unsafe_allow_html=True
    )

    st.caption(
        "후보 비교에 사용할 항목의 역할, 우선순위와 기준값을 설정합니다."
    )

    st.divider()


    # =========================================================
    # 판단기준 설정
    # =========================================================

    if (
        "confirmed_results" in st.session_state
        and st.session_state.confirmed_results
    ):

        st.markdown(
            "### 항목별 설정"
        )

        st.caption(
            "필수 기준은 후보를 자동 탈락시키지 않고 "
            "비교 화면에서 충족 여부를 표시합니다."
        )


        # -----------------------------------------------------
        # 판단기준 설정 저장공간
        # -----------------------------------------------------

        if "criterion_settings" not in st.session_state:

            st.session_state.criterion_settings = {}


        confirmed_results = (
            st.session_state.confirmed_results
        )


        criterion_names = list(
            dict.fromkeys(
                result["field"]
                for result in confirmed_results
            )
        )


        temporary_settings = {}


        # -----------------------------------------------------
        # 표 형태 Header
        # -----------------------------------------------------

        st.markdown(
            "<div style='height: 12px;'></div>",
            unsafe_allow_html=True
        )


        header_criterion, header_role, header_priority, header_direction = (
            st.columns(
                [2.4, 2, 1.3, 2.5]
            )
        )


        header_criterion.caption(
            "판단항목"
        )

        header_role.caption(
            "역할"
        )

        header_priority.caption(
            "우선순위"
        )

        header_direction.caption(
            "선호 방향"
        )


        # =====================================================
        # 판단항목별 설정
        # =====================================================

        for index, criterion in enumerate(
            criterion_names
        ):

            example_result = next(
                result
                for result in confirmed_results
                if result["field"] == criterion
            )


            data_type = (
                example_result["data_type"]
            )

            unit = (
                example_result["unit"]
            )


            existing_setting = (
                st.session_state.criterion_settings.get(
                    criterion,
                    {}
                )
            )


            # =================================================
            # 판단항목 Row
            # =================================================

            with st.container(
                border=True
            ):

                criterion_col, role_col, priority_col, direction_col = (
                    st.columns(
                        [2.4, 2, 1.3, 2.5],
                        vertical_alignment="center"
                    )
                )


                # ---------------------------------------------
                # 판단항목 이름
                # ---------------------------------------------

                criterion_col.markdown(
                    f"**{criterion}**"
                )


                if unit:

                    criterion_col.caption(
                        f"{data_type} · {unit}"
                    )

                else:

                    criterion_col.caption(
                        data_type
                    )


                # ---------------------------------------------
                # 역할
                # ---------------------------------------------

                role_options = [
                    "필수 기준",
                    "평가항목",
                    "참고항목"
                ]


                current_role = (
                    existing_setting.get(
                        "role"
                    )
                    or "평가항목"
                )


                if current_role not in role_options:

                    current_role = (
                        "평가항목"
                    )


                role = (
                    role_col.selectbox(
                        "역할",
                        role_options,
                        index=role_options.index(
                            current_role
                        ),
                        key=f"criterion_role_{index}",
                        label_visibility="collapsed"
                    )
                )


                # ---------------------------------------------
                # 우선순위
                # ---------------------------------------------

                current_priority = (
                    existing_setting.get(
                        "priority"
                    )
                )


                if current_priority is None:

                    current_priority = (
                        index + 1
                    )


                priority = (
                    priority_col.number_input(
                        "우선순위",
                        min_value=1,
                        value=int(
                            current_priority
                        ),
                        step=1,
                        key=f"criterion_priority_{index}",
                        label_visibility="collapsed"
                    )
                )


                # 기본값
                direction = None
                constraint_operator = None
                constraint_value = None


                # =================================================
                # 정량 / 순위형
                # =================================================

                if data_type in [
                    "numeric",
                    "ranking"
                ]:

                    if role in [
                        "필수 기준",
                        "평가항목"
                    ]:

                        direction_options = [
                            "높을수록 좋음",
                            "낮을수록 좋음",
                            "방향 없음"
                        ]


                        current_direction = (
                            existing_setting.get(
                                "direction"
                            )
                            or "방향 없음"
                        )


                        if (
                            current_direction
                            not in direction_options
                        ):

                            current_direction = (
                                "방향 없음"
                            )


                        direction = (
                            direction_col.selectbox(
                                "선호 방향",
                                direction_options,
                                index=direction_options.index(
                                    current_direction
                                ),
                                key=f"criterion_direction_{index}",
                                label_visibility="collapsed"
                            )
                        )


                    else:

                        direction_col.caption(
                            "비교 방향 미적용"
                        )


                    # -----------------------------------------
                    # 필수 기준 Threshold
                    # -----------------------------------------

                    if role == "필수 기준":

                        st.markdown(
                            "<div style='height: 4px;'></div>",
                            unsafe_allow_html=True
                        )


                        constraint_label_col, operator_col, value_col, unit_col, constraint_spacer = (
                            st.columns(
                                [2.4, 1, 1.6, 0.8, 2.4],
                                vertical_alignment="center"
                            )
                        )


                        constraint_label_col.caption(
                            "허용 기준"
                        )


                        operator_options = [
                            "≤",
                            "≥",
                            "="
                        ]


                        current_operator = (
                            existing_setting.get(
                                "constraint_operator"
                            )
                            or "≤"
                        )


                        if (
                            current_operator
                            not in operator_options
                        ):

                            current_operator = "≤"


                        constraint_operator = (
                            operator_col.selectbox(
                                "조건",
                                operator_options,
                                index=operator_options.index(
                                    current_operator
                                ),
                                key=f"criterion_operator_{index}",
                                label_visibility="collapsed"
                            )
                        )


                        current_constraint_value = (
                            existing_setting.get(
                                "constraint_value"
                            )
                        )


                        if (
                            current_constraint_value
                            is None
                        ):

                            current_constraint_value = 0.0


                        constraint_value = (
                            value_col.number_input(
                                "기준값",
                                value=float(
                                    current_constraint_value
                                ),
                                key=f"criterion_value_{index}",
                                label_visibility="collapsed"
                            )
                        )


                        unit_col.write(
                            unit or ""
                        )


                # =================================================
                # 정성형
                # =================================================

                else:

                    if role in [
                        "필수 기준",
                        "평가항목"
                    ]:

                        direction_options = [
                            "상 > 중 > 하",
                            "하 > 중 > 상",
                            "방향 없음"
                        ]


                        current_direction = (
                            existing_setting.get(
                                "direction"
                            )
                            or "방향 없음"
                        )


                        if (
                            current_direction
                            not in direction_options
                        ):

                            current_direction = (
                                "방향 없음"
                            )


                        direction = (
                            direction_col.selectbox(
                                "선호 방향",
                                direction_options,
                                index=direction_options.index(
                                    current_direction
                                ),
                                key=f"criterion_direction_{index}",
                                label_visibility="collapsed"
                            )
                        )


                    else:

                        direction_col.caption(
                            "비교 방향 미적용"
                        )


                    if role == "필수 기준":

                        st.caption(
                            "정성형 필수 기준의 허용조건 설정은 아직 지원하지 않습니다."
                        )


                # ---------------------------------------------
                # 임시 설정 저장
                # ---------------------------------------------

                temporary_settings[
                    criterion
                ] = {

                    "criterion": criterion,

                    "data_type": data_type,

                    "unit": unit,

                    "role": role,

                    "priority": priority,

                    "direction": direction,

                    "constraint_operator": (
                        constraint_operator
                    ),

                    "constraint_value": (
                        constraint_value
                    )
                }


        # =====================================================
        # 저장 버튼
        # =====================================================

        st.markdown(
            "<div style='height: 16px;'></div>",
            unsafe_allow_html=True
        )


        save_col, save_spacer = (
            st.columns(
                [1.4, 5]
            )
        )


        if save_col.button(
            "판단 기준 저장",
            type="primary",
            use_container_width=True
        ):

            st.session_state.criterion_settings = (
                temporary_settings
            )

            st.success(
                "판단 기준 설정이 저장되었습니다."
            )


        # =====================================================
        # 저장 결과
        # =====================================================

        if (
            st.session_state.criterion_settings
        ):

            st.markdown(
                "<div style='height: 28px;'></div>",
                unsafe_allow_html=True
            )

            st.divider()

            st.markdown(
                "### 현재 판단 기준"
            )


            criterion_display_rows = []


            sorted_settings = sorted(
                st.session_state.criterion_settings.values(),
                key=lambda setting: (
                    setting.get(
                        "priority"
                    )
                    or 9999
                )
            )


            for setting in sorted_settings:

                if (
                    setting["role"]
                    == "필수 기준"

                    and

                    setting[
                        "constraint_operator"
                    ]
                    is not None
                ):

                    constraint_value = (
                        setting[
                            "constraint_value"
                        ]
                    )


                    if (
                        isinstance(
                            constraint_value,
                            float
                        )
                        and
                        constraint_value.is_integer()
                    ):

                        constraint_value = int(
                            constraint_value
                        )


                    constraint_text = (
                        f'{setting["constraint_operator"]} '
                        f'{constraint_value}'
                    )


                    if setting["unit"]:

                        constraint_text += (
                            str(
                                setting["unit"]
                            )
                        )


                elif (
                    setting["role"]
                    == "필수 기준"
                ):

                    constraint_text = (
                        "조건 설정 예정"
                    )


                else:

                    constraint_text = "-"


                direction_text = (
                    setting["direction"]
                    if setting["direction"]
                    else "-"
                )


                criterion_display_rows.append(
                    {
                        "판단기준": (
                            setting["criterion"]
                        ),

                        "역할": (
                            setting["role"]
                        ),

                        "우선순위": (
                            setting["priority"]
                        ),

                        "평가방향": (
                            direction_text
                        ),

                        "기준조건": (
                            constraint_text
                        )
                    }
                )


            criterion_settings_df = (
                pd.DataFrame(
                    criterion_display_rows
                )
            )


            st.dataframe(
                criterion_settings_df,
                use_container_width=True,
                hide_index=True
            )


    else:

        st.info(
            "승인된 Evidence가 없습니다. "
            "② Evidence 검토에서 먼저 데이터를 승인해주세요."
        )
        
with tab_compare:

    st.markdown(
        "## &lt; 후보 비교·분석 &gt;",
        unsafe_allow_html=True
    )

    st.caption(
        "후보별 정보를 비교하고 상대적 강점·약점과 "
        "AI 분석 결과를 확인합니다."
    )

    st.divider()

    

    # =========================================================
    # 6. 후보 비교
    # =========================================================

    if (
        "confirmed_results" in st.session_state
        and st.session_state.confirmed_results
        and "criterion_settings" in st.session_state
        and st.session_state.criterion_settings
    ):

        st.markdown(
            "### 후보 비교"
        )

        st.caption(
            "확정된 Evidence를 기준으로 후보별 값을 직접 비교합니다."
        )

        confirmed_results = (
            st.session_state.confirmed_results
        )

        criterion_settings = (
            st.session_state.criterion_settings
        )


        # -----------------------------------------------------
        # 필수 기준 빠른 수정
        # -----------------------------------------------------

        required_criteria = [
            criterion
            for criterion, setting
            in criterion_settings.items()
            if setting.get("role") == "필수 기준"
            and setting.get("data_type")
            in ["numeric", "ranking"]
        ]


        if required_criteria:

            st.markdown(
                "#### 필수 기준 빠른 수정"
            )


            for index, criterion in enumerate(
                required_criteria
            ):

                setting = (
                    criterion_settings[criterion]
                )

                unit = (
                    setting.get("unit")
                    or ""
                )


                criterion_column, operator_column, value_column, unit_column = (
                    st.columns(
                        [2.5, 1, 2, 1]
                    )
                )


                # 판단항목 이름
                criterion_column.write(
                    criterion
                )


                # 현재 기준 조건
                current_operator = (
                    setting.get(
                        "constraint_operator"
                    )
                    or "≤"
                )


                operator_options = [
                    "≤",
                    "≥",
                    "="
                ]


                new_operator = (
                    operator_column.selectbox(
                        "조건",
                        operator_options,
                        index=operator_options.index(
                            current_operator
                        ),
                        key=f"quick_operator_{criterion}",
                        label_visibility="collapsed"
                    )
                )


                # 현재 기준값
                current_value = (
                    setting.get(
                        "constraint_value"
                    )
                )


                if current_value is None:

                    current_value = 0.0


                new_value = (
                    value_column.number_input(
                        "기준값",
                        value=float(
                            current_value
                        ),
                        key=f"quick_value_{criterion}",
                        label_visibility="collapsed"
                    )
                )


                # 단위 표시
                unit_column.write(
                    unit
                )


                # 변경된 값을 실제 판단기준 설정에 반영
                st.session_state.criterion_settings[
                    criterion
                ][
                    "constraint_operator"
                ] = new_operator


                st.session_state.criterion_settings[
                    criterion
                ][
                    "constraint_value"
                ] = new_value


            st.divider()


        # -----------------------------------------------------
        # 후보 목록
        #
        # Evidence 유무와 관계없이
        # 문서에서 처음 식별한 전체 후보를 유지한다.
        # -----------------------------------------------------

        candidate_names = list(
            st.session_state.get(
                "decision_candidates",
                []
            )
        )


        # 이전 세션 데이터 등에서 후보목록이 없는 경우만
        # confirmed_results를 fallback으로 사용
        if not candidate_names:

            candidate_names = list(
                dict.fromkeys(
                    result["candidate"]

                    for result
                    in confirmed_results

                    if result.get(
                        "candidate"
                    )
                    and result.get(
                        "candidate"
                    )
                    != "공통 정보"
                )
            )


        candidate_names = [
            candidate

            for candidate
            in candidate_names

            if candidate
            and candidate
            != "공통 정보"
        ]


        # -----------------------------------------------------
        # 판단항목 목록
        # -----------------------------------------------------

        criterion_names = list(
            dict.fromkeys(
                result["field"]
                for result
                in confirmed_results
            )
        )


        # 기존 순서 저장
        original_order = {
            criterion: index
            for index, criterion
            in enumerate(
                criterion_names
            )
        }


        # -----------------------------------------------------
        # 사용자 우선순위에 따라 정렬
        # -----------------------------------------------------

        def criterion_sort_key(
            criterion
        ):

            setting = (
                criterion_settings.get(
                    criterion,
                    {}
                )
            )

            priority = (
                setting.get(
                    "priority"
                )
                or 9999
            )

            return (
                priority,
                original_order[
                    criterion
                ]
            )


        criterion_names = sorted(
            criterion_names,
            key=criterion_sort_key
        )

        # =====================================================
        # 비교표용 문장 요약
        # =====================================================
        #
        # 정량값은 그대로 사용하고,
        # 문장형 정성정보만 AI가 짧게 정리한다.
        #
        # 같은 내용은 한 번 요약한 뒤 session_state에 저장하고,
        # 원본 문장이 바뀌었을 때만 다시 AI를 호출한다.
        # =====================================================

        # =====================================================
        # 같은 후보 + 같은 항목의 문장형 정보를 먼저 묶음
        # =====================================================

        grouped_comparison_values = {}


        for result in confirmed_results:

            value_text = str(
                result.get(
                    "value",
                    ""
                )
            ).strip()


            # 숫자형은 AI 요약하지 않음
            if (
                result.get(
                    "data_type"
                )
                != "qualitative"
            ):

                continue


            # 상 / 중 / 하는 이미 충분히 짧으므로 제외
            if value_text in {
                "상",
                "중",
                "하"
            }:

                continue


            if not value_text:

                continue


            group_key = (
                result[
                    "candidate"
                ],
                result[
                    "field"
                ]
            )


            if (
                group_key
                not in grouped_comparison_values
            ):

                grouped_comparison_values[
                    group_key
                ] = []


            # 완전히 같은 내용은 중복 저장하지 않음
            if (
                value_text
                not in grouped_comparison_values[
                    group_key
                ]
            ):

                grouped_comparison_values[
                    group_key
                ].append(
                    value_text
                )


        # =====================================================
        # AI에게는 후보 + 항목당 하나의 입력만 전달
        # =====================================================

        comparison_summary_items = []


        for (
            candidate,
            criterion
        ), values in (
            grouped_comparison_values.items()
        ):

            combined_value = "\n".join(
                f"- {value}"
                for value in values
            )


            comparison_summary_items.append(
                {
                    "candidate": (
                        candidate
                    ),

                    "criterion": (
                        criterion
                    ),

                    "value": (
                        combined_value
                    )
                }
            )


        # -----------------------------------------------------
        # 현재 요약 대상 문장들의 상태
        #
        # candidate / criterion / value 중 하나라도 바뀌면
        # 이전 요약을 다시 사용하지 않음
        # -----------------------------------------------------

        comparison_summary_signature = tuple(
            sorted(
                (
                    str(
                        item[
                            "candidate"
                        ]
                    ),

                    str(
                        item[
                            "criterion"
                        ]
                    ),

                    str(
                        item[
                            "value"
                        ]
                    )
                )

                for item
                in comparison_summary_items
            )
        )


        stored_summary_signature = (
            st.session_state.get(
                "comparison_summary_signature"
            )
        )


        # -----------------------------------------------------
        # 처음 실행하거나 원본 문장이 변경된 경우에만
        # AI 요약 새로 실행
        # -----------------------------------------------------

        if (
            comparison_summary_items

            and

            stored_summary_signature
            != comparison_summary_signature
        ):

            try:

                with st.spinner(
                    "비교표의 문장형 정보를 간단히 정리하고 있습니다..."
                ):

                    comparison_summary_results = (
                        summarize_comparison_values(
                            comparison_summary_items
                        )
                    )


                st.session_state[
                    "comparison_summary_results"
                ] = (
                    comparison_summary_results
                )


                st.session_state[
                    "comparison_summary_signature"
                ] = (
                    comparison_summary_signature
                )


            except Exception as e:

                # 요약에 실패해도
                # 비교표 자체는 기존 원문으로 표시
                st.warning(
                    "비교표용 문장 요약에 실패해 "
                    "기존 내용을 표시합니다."
                )


        # 문장형 정보가 하나도 없으면
        # 이전에 저장된 결과 제거
        elif not comparison_summary_items:

            st.session_state[
                "comparison_summary_results"
            ] = []


            st.session_state[
                "comparison_summary_signature"
            ] = (
                comparison_summary_signature
            )


        # -----------------------------------------------------
        # 저장된 요약을 빠르게 찾기 위한 lookup
        #
        # 예:
        # ("A안", "품질")
        # → ["흑한 전개 불량 위험 큼", "품질 클레임 위험 큼"]
        # -----------------------------------------------------

        comparison_summary_lookup = {}


        if (
            st.session_state.get(
                "comparison_summary_signature"
            )
            == comparison_summary_signature
        ):

            for summary in (
                st.session_state.get(
                    "comparison_summary_results",
                    []
                )
            ):

                key = (
                    summary[
                        "candidate"
                    ],
                    summary[
                        "criterion"
                    ]
                )


                comparison_summary_lookup[
                    key
                ] = (
                    summary[
                        "points"
                    ]
                )

        # -----------------------------------------------------
        # 후보 비교표 생성
        # -----------------------------------------------------

        comparison_rows = []


        for criterion in criterion_names:

            setting = (
                criterion_settings.get(
                    criterion,
                    {}
                )
            )


            row_label = criterion


            # 필수 기준이면
            # 판단항목 이름 옆에 기준 표시
            if (
                setting.get("role")
                == "필수 기준"
            ):

                operator = (
                    setting.get(
                        "constraint_operator"
                    )
                )

                constraint_value = (
                    setting.get(
                        "constraint_value"
                    )
                )

                unit = (
                    setting.get(
                        "unit"
                    )
                )


                if (
                    operator is not None
                    and constraint_value
                    is not None
                ):

                    numeric_constraint = float(
                        constraint_value
                    )


                    # 3.0 → 3
                    if (
                        numeric_constraint
                        .is_integer()
                    ):

                        displayed_constraint = int(
                            numeric_constraint
                        )

                    else:

                        displayed_constraint = (
                            numeric_constraint
                        )


                    row_label = (
                        f"{criterion} "
                        f"{operator} "
                        f"{displayed_constraint}"
                    )


                    if unit:

                        row_label += (
                            str(unit)
                        )


            row_data = {
                "판단항목 (우선순위 높은 순)": (
                    row_label
                )
            }


            # 후보별 값 삽입
            for candidate in candidate_names:

                matching_result = next(
                    (
                        result
                        for result
                        in confirmed_results
                        if (
                            result[
                                "candidate"
                            ]
                            == candidate
                            and
                            result[
                                "field"
                            ]
                            == criterion
                        )
                    ),
                    None
                )


                if matching_result:

                    # -----------------------------------------
                    # AI가 만든 비교표용 짧은 요약 확인
                    # -----------------------------------------

                    summary_points = (
                        comparison_summary_lookup.get(
                            (
                                candidate,
                                criterion
                            )
                        )
                    )


                    # 문장형 정보에 AI 요약이 있으면
                    # 비교표에서는 짧은 포인트만 표시
                    if summary_points:

                        row_data[
                            candidate
                        ] = "\n".join(
                            f"• {point}"

                            for point
                            in summary_points
                        )


                    # 숫자형 / 상중하 / 요약 실패 등의 경우
                    # 기존 표시 방식 사용
                    else:

                        row_data[
                            candidate
                        ] = format_comparison_value(
                            value=(
                                matching_result[
                                    "value"
                                ]
                            ),
                            unit=(
                                matching_result[
                                    "unit"
                                ]
                            ),
                            data_type=(
                                matching_result[
                                    "data_type"
                                ]
                            )
                        )


                else:

                    row_data[
                        candidate
                    ] = "-"              


            comparison_rows.append(
                row_data
            )


        comparison_df = pd.DataFrame(
            comparison_rows
        )


        # -----------------------------------------------------
        # 필수 기준 충족 여부 색상
        # -----------------------------------------------------

        def color_comparison_cell(
            row
        ):

            styles = [
                ""
                for _ in row
            ]


            row_label = (
                row[
                    "판단항목 (우선순위 높은 순)"
                ]
            )


            current_criterion = None


            for criterion in criterion_names:

                if (
                    row_label == criterion
                    or row_label.startswith(
                        criterion + " "
                    )
                ):

                    current_criterion = (
                        criterion
                    )

                    break


            if current_criterion is None:

                return styles


            setting = (
                criterion_settings.get(
                    current_criterion,
                    {}
                )
            )


            role = (
                setting.get(
                    "role"
                )
            )


            # =====================================================
            # 1. 필수 기준
            #
            # 정량형 threshold가 존재하는 경우
            # 충족 / 미충족을 파랑 / 빨강으로 표시
            # =====================================================

            if role == "필수 기준":

                operator = (
                    setting.get(
                        "constraint_operator"
                    )
                )

                constraint_value = (
                    setting.get(
                        "constraint_value"
                    )
                )


                if (
                    operator is None
                    or constraint_value is None
                ):

                    return styles


                for column_index, candidate in enumerate(
                    candidate_names,
                    start=1
                ):

                    matching_result = next(
                        (
                            result

                            for result
                            in confirmed_results

                            if (
                                result[
                                    "candidate"
                                ]
                                == candidate

                                and

                                result[
                                    "field"
                                ]
                                == current_criterion
                            )
                        ),
                        None
                    )


                    if matching_result is None:

                        continue


                    try:

                        actual_value = float(
                            matching_result[
                                "value"
                            ]
                        )

                        standard_value = float(
                            constraint_value
                        )


                        if operator == "≤":

                            satisfied = (
                                actual_value
                                <= standard_value
                            )


                        elif operator == "≥":

                            satisfied = (
                                actual_value
                                >= standard_value
                            )


                        elif operator == "=":

                            satisfied = (
                                actual_value
                                == standard_value
                            )


                        else:

                            continue


                        # 충족 → 연한 하늘색
                        if satisfied:

                            styles[
                                column_index
                            ] = (
                                "background-color: #D9EEF7"
                            )


                        # 미충족 → 연한 빨간색
                        else:

                            styles[
                                column_index
                            ] = (
                                "background-color: #F8D7DA"
                            )


                    except (
                        ValueError,
                        TypeError
                    ):

                        pass


                return styles


            # =====================================================
            # 2. 평가항목
            #
            # 명시적인 위험 / 부담 / 문제 표현이 있는 경우만
            # 연한 주황색으로 표시
            # =====================================================

            if role == "평가항목":

                for column_index, candidate in enumerate(
                    candidate_names,
                    start=1
                ):

                    matching_result = next(
                        (
                            result

                            for result
                            in confirmed_results

                            if (
                                result[
                                    "candidate"
                                ]
                                == candidate

                                and

                                result[
                                    "field"
                                ]
                                == current_criterion
                            )
                        ),
                        None
                    )


                    if matching_result is None:

                        continue


                    if has_explicit_risk(
                        matching_result[
                            "value"
                        ]
                    ):

                        styles[
                            column_index
                        ] = (
                            "background-color: #FCE8D5"
                        )


                return styles


            # 참고항목은 색상 없음
            return styles


        # -----------------------------------------------------
        # 스타일 적용
        # -----------------------------------------------------

        styled_comparison_df = (
            comparison_df.style
            .apply(
                color_comparison_cell,
                axis=1
            )
            .hide(
                axis="index"
            )
            .set_properties(
                **{
                    "white-space": "pre-line",
                    "overflow-wrap": "anywhere",
                    "word-break": "break-word",
                    "vertical-align": "top",
                    "text-align": "left",
                    "padding": "10px 12px",
                    "line-height": "1.45"
                }
            )
            .set_table_styles(
                [
                    {
                        "selector": "table",
                        "props": [
                            ("width", "100%"),
                            ("table-layout", "fixed"),
                            ("border-collapse", "collapse")
                        ]
                    },
                    {
                        "selector": "th",
                        "props": [
                            ("white-space", "normal"),
                            ("overflow-wrap", "anywhere"),
                            ("word-break", "break-word"),
                            ("text-align", "left"),
                            ("vertical-align", "middle"),
                            ("padding", "10px 12px")
                        ]
                    },
                    {
                        "selector": "th:nth-child(1)",
                        "props": [
                            ("width", "18%")
                        ]
                    },
                    {
                        "selector": "td:nth-child(1)",
                        "props": [
                            ("width", "18%"),
                            ("font-weight", "600")
                        ]
                    }
                ]
            )
        )


        # =====================================================
        # 후보 비교표
        # =====================================================

        st.caption(
            "색상 표시 · "
            "연한 파랑: 필수 기준 충족 / "
            "연한 빨강: 필수 기준 미충족 / "
            "연한 주황: 평가항목에서 확인된 리스크·부담"
        )

        st.markdown(
            styled_comparison_df.to_html(),
            unsafe_allow_html=True
        )

        st.divider()

        st.markdown(
            "<div style='height: 12px;'></div>",
            unsafe_allow_html=True
        )
        
        # =========================================================
        # 7. 후보 특성 분석
        # =========================================================

        if (
            "confirmed_results" in st.session_state
            and st.session_state.confirmed_results
            and "criterion_settings" in st.session_state
            and st.session_state.criterion_settings
        ):

            st.markdown(
                "### 문장형 정보 비교"
            )

            st.caption(
                "품질이나 고객체감처럼 숫자로 직접 비교하기 어려운 내용을 "
                "AI가 후보별로 비교합니다. 비교 결과는 아래 후보별 특성에 반영됩니다."
            )

        


            confirmed_results = (
                st.session_state.confirmed_results
            )

            criterion_settings = (
                st.session_state.criterion_settings
            )


            # -----------------------------------------------------
            # 후보 목록
            #
            # 최초 식별 후보 전체를 유지한다.
            # -----------------------------------------------------

            candidate_names = list(
                st.session_state.get(
                    "decision_candidates",
                    []
                )
            )


            if not candidate_names:

                candidate_names = list(
                    dict.fromkeys(
                        result["candidate"]

                        for result
                        in confirmed_results

                        if result.get(
                            "candidate"
                        )
                        and result.get(
                            "candidate"
                        )
                        != "공통 정보"
                    )
                )


            candidate_names = [
                candidate

                for candidate
                in candidate_names

                if candidate
                and candidate
                != "공통 정보"
            ]


            # =====================================================
            # 현재 데이터 상태 Signature 생성
            # =====================================================
            #
            # AI 분석 이후 Evidence나 판단방향이 변경되었는데도
            # 예전 AI 결과가 그대로 남는 문제를 방지하기 위함
            # =====================================================

            comparison_signature = (

                tuple(
                    candidate_names
                ),
                
                tuple(
                    sorted(
                        (
                            str(
                                result.get(
                                    "candidate",
                                    ""
                                )
                            ),

                            str(
                                result.get(
                                    "field",
                                    ""
                                )
                            ),

                            str(
                                result.get(
                                    "value",
                                    ""
                                )
                            ),

                            str(
                                result.get(
                                    "unit",
                                    ""
                                )
                            ),

                            str(
                                result.get(
                                    "page",
                                    ""
                                )
                            ),

                            str(
                                result.get(
                                    "evidence",
                                    ""
                                )
                            )
                        )

                        for result
                        in confirmed_results
                    )
                ),

                tuple(
                    sorted(
                        (
                            str(criterion),

                            str(
                                setting.get(
                                    "data_type",
                                    ""
                                )
                            ),

                            str(
                                setting.get(
                                    "direction",
                                    ""
                                )
                            )
                        )

                        for criterion, setting
                        in criterion_settings.items()
                    )
                )
            )


            # =====================================================
            # 문장형 정성정보가 존재하는 판단항목 탐색
            # =====================================================

            structured_qualitative_labels = {
                "상",
                "중",
                "하"
            }


            free_text_criteria = []


            for criterion, setting in (
                criterion_settings.items()
            ):

                data_type = (
                    setting.get(
                        "data_type"
                    )
                )

                direction = (
                    setting.get(
                        "direction"
                    )
                )


                if data_type != "qualitative":

                    continue


                if (
                    direction is None
                    or direction == "방향 없음"
                ):

                    continue


                criterion_results = [
                    result
                    for result in confirmed_results
                    if result["field"] == criterion
                ]


                # 실제 비교 가능한 후보 수 확인
                criterion_candidates = {
                    result["candidate"]
                    for result in criterion_results
                }


                if len(
                    criterion_candidates
                ) < 2:

                    continue


                values = [
                    str(
                        result["value"]
                    ).strip()

                    for result
                    in criterion_results
                ]


                # 하나라도 상/중/하가 아닌 값이 존재하면
                # 문장형 정성 비교 대상으로 처리
                if any(
                    value
                    not in structured_qualitative_labels

                    for value in values
                ):

                    free_text_criteria.append(
                        criterion
                    )


            # =====================================================
            # 문장형 정성정보 AI 비교
            # =====================================================



            if free_text_criteria:

                st.write(
                    "비교할 항목:",
                    " / ".join(
                        free_text_criteria
                    )
                )

            


                if st.button(
                    "AI 비교 실행",
                    type="primary",
                    key="run_qualitative_comparison"
                ):

                    try:

                        with st.spinner(
                            "AI가 후보별 정성 근거를 "
                            "상대 비교하고 있습니다..."
                        ):

                            ai_comparison_results = (
                                compare_qualitative_evidence(
                                    confirmed_results=(
                                        confirmed_results
                                    ),
                                    criterion_settings=(
                                        criterion_settings
                                    )
                                )
                            )


                        st.session_state[
                            "qualitative_comparison_results"
                        ] = ai_comparison_results


                        st.session_state[
                            "qualitative_comparison_signature"
                        ] = comparison_signature


                        st.success(
                            f"문장형 정성 비교 완료: "
                            f"{len(ai_comparison_results)}건 분석"
                        )


                    except Exception as e:

                        st.error(
                            "문장형 정성 비교 중 "
                            "오류가 발생했습니다."
                        )

                        st.write(e)


            else:

                st.info(
                    "현재 AI 의미 비교가 필요한 "
                    "문장형 정성정보가 없습니다."
                )


            # =====================================================
            # 저장된 AI 결과가 현재 데이터와 일치하는지 확인
            # =====================================================

            ai_comparison_results = []


            stored_signature = (
                st.session_state.get(
                    "qualitative_comparison_signature"
                )
            )


            has_stored_ai_results = (
                "qualitative_comparison_results"
                in st.session_state
            )


            current_ai_result_available = (
                has_stored_ai_results
                and stored_signature
                == comparison_signature
            )


            if current_ai_result_available:

                ai_comparison_results = (
                    st.session_state[
                        "qualitative_comparison_results"
                    ]
                )


            elif (
                has_stored_ai_results
                and free_text_criteria
            ):

                st.warning(
                    "Evidence 또는 판단기준이 변경되어 "
                    "기존 AI 정성 비교 결과를 사용하지 않습니다. "
                    "문장형 정성 비교를 다시 실행해주세요."
                )


            # =====================================================
            # 후보별 장단점 / Trade-off 분석
            # =====================================================
            #
            # Python과 기존 정성 비교 결과를 바탕으로
            # 후보별 강점·약점·Trade-off를 AI가 설명한다.
            #
            # Evidence / 판단기준 / 정성 비교결과 중 하나라도
            # 바뀌면 기존 분석 결과를 다시 사용하지 않는다.
            # =====================================================

            candidate_analysis_signature = (

                "analysis_basis_v2",
                
                comparison_signature,

                tuple(
                    sorted(
                        (
                            str(
                                criterion
                            ),

                            str(
                                setting.get(
                                    "role",
                                    ""
                                )
                            ),

                            str(
                                setting.get(
                                    "priority",
                                    ""
                                )
                            ),

                            str(
                                setting.get(
                                    "direction",
                                    ""
                                )
                            ),

                            str(
                                setting.get(
                                    "constraint_operator",
                                    ""
                                )
                            ),

                            str(
                                setting.get(
                                    "constraint_value",
                                    ""
                                )
                            )
                        )

                        for criterion, setting
                        in criterion_settings.items()
                    )
                ),

                tuple(
                    sorted(
                        (
                            str(
                                comparison.get(
                                    "candidate",
                                    ""
                                )
                            ),

                            str(
                                comparison.get(
                                    "criterion",
                                    ""
                                )
                            ),

                            str(
                                comparison.get(
                                    "position",
                                    ""
                                )
                            ),

                            str(
                                comparison.get(
                                    "reason",
                                    ""
                                )
                            )
                        )

                        for comparison
                        in ai_comparison_results
                    )
                )
            )


            stored_candidate_analysis_signature = (
                st.session_state.get(
                    "candidate_analysis_signature"
                )
            )


            has_candidate_analysis = (
                "candidate_analysis_results"
                in st.session_state
            )


            current_candidate_analysis_available = (
                has_candidate_analysis

                and

                stored_candidate_analysis_signature
                == candidate_analysis_signature
            )


            # =====================================================
            # 분석 실행 가능 여부
            # =====================================================
            #
            # 문장형 정성정보가 존재한다면
            # 먼저 앞 단계의 AI 상대비교를 완료해야 한다.
            #
            # 정성정보가 없다면 바로 실행 가능하다.
            # =====================================================

            can_run_candidate_analysis = (

                not free_text_criteria

                or

                current_ai_result_available
            )


            st.markdown(
                "<div style='height: 28px;'></div>",
                unsafe_allow_html=True
            )

            st.divider()

            st.markdown(
                "<div style='height: 12px;'></div>",
                unsafe_allow_html=True
            )


            st.markdown(
                "### 후보별 장단점·Trade-off"
            )

            st.caption(
                "확정된 정보와 후보 간 비교를 바탕으로 "
                "확인된 장점·부담과 상대적 강점·약점을 정리하고, "
                "설계구조에서 예상되는 영향은 별도로 구분해 보여줍니다. "
                "AI가 최종 후보를 선택하지는 않습니다."
            )


            # =====================================================
            # 문장형 비교 선행 필요 안내
            # =====================================================

            if (
                free_text_criteria

                and

                not current_ai_result_available
            ):

                st.info(
                    "문장형 정성정보가 포함되어 있습니다. "
                    "위의 'AI 비교 실행'을 먼저 실행하면 "
                    "정성정보의 상대적 강점·약점까지 반영할 수 있습니다."
                )


            # =====================================================
            # 후보 특성 분석 실행
            # =====================================================

            if st.button(
                "후보 특성 분석 실행",
                type="primary",
                key="run_candidate_characteristic_analysis",
                disabled=(
                    not can_run_candidate_analysis
                )
            ):

                try:

                    with st.spinner(
                        "후보별 강점·약점과 "
                        "Trade-off를 정리하고 있습니다..."
                    ):

                        candidate_analysis_results = (
                            analyze_candidate_characteristics(
                                confirmed_results=(
                                    confirmed_results
                                ),
                                criterion_settings=(
                                    criterion_settings
                                ),
                                qualitative_comparison_results=(
                                    ai_comparison_results
                                )
                            )
                        )


                    st.session_state[
                        "candidate_analysis_results"
                    ] = (
                        candidate_analysis_results
                    )


                    st.session_state[
                        "candidate_analysis_signature"
                    ] = (
                        candidate_analysis_signature
                    )


                    current_candidate_analysis_available = (
                        True
                    )


                    st.success(
                        "후보별 특성 분석이 완료되었습니다."
                    )


                except Exception as e:

                    st.error(
                        "후보별 특성 분석 중 "
                        "오류가 발생했습니다."
                    )

                    st.write(
                        e
                    )


            # =====================================================
            # 기존 결과가 오래된 경우
            # =====================================================

            elif (
                has_candidate_analysis

                and

                stored_candidate_analysis_signature
                != candidate_analysis_signature
            ):

                st.warning(
                    "확정된 정보 또는 판단기준이 변경되어 "
                    "기존 후보 특성 분석 결과를 사용하지 않습니다. "
                    "다시 분석해주세요."
                )


            # =====================================================
            # 분석 결과 표시
            # =====================================================

            if (
                current_candidate_analysis_available
            ):

                candidate_analysis_results = (
                    st.session_state.get(
                        "candidate_analysis_results",
                        []
                    )
                )


                analysis_lookup = {
                    analysis.get(
                        "candidate"
                    ): analysis

                    for analysis
                    in candidate_analysis_results

                    if analysis.get(
                        "candidate"
                    )
                }


                st.markdown(
                    "<div style='height: 20px;'></div>",
                    unsafe_allow_html=True
                )


                for candidate in (
                    candidate_names
                ):

                    analysis = (
                        analysis_lookup.get(
                            candidate,
                            {}
                        )
                    )


                    strengths = (
                        analysis.get(
                            "strengths",
                            []
                        )
                    )


                    weaknesses = (
                        analysis.get(
                            "weaknesses",
                            []
                        )
                    )


                    tradeoffs = (
                        analysis.get(
                            "tradeoffs",
                            []
                        )
                    )


                    with st.container(
                        border=True
                    ):

                        st.markdown(
                            f"#### {candidate}"
                        )


                        strength_col, weakness_col, tradeoff_col = (
                            st.columns(
                                [1, 1, 1.2]
                            )
                        )


                        # =========================================
                        # 강점
                        # =========================================

                        strength_col.markdown(
                            "**강점**"
                        )


                        if strengths:

                            for point in (
                                strengths
                            ):

                                criterion = (
                                    point.get(
                                        "criterion",
                                        "-"
                                    )
                                )


                                basis = (
                                    point.get(
                                        "basis",
                                        "confirmed"
                                    )
                                )


                                text = (
                                    point.get(
                                        "text",
                                        ""
                                    )
                                )


                                strength_basis_label = {
                                    "relative": (
                                        "상대 강점"
                                    ),

                                    "confirmed": (
                                        "확인된 장점"
                                    ),

                                    "inferred": (
                                        "예상 장점"
                                    )
                                }.get(
                                    basis,
                                    "장점"
                                )


                                inference_note = (
                                    " *(추가 검증 필요)*"
                                    if basis
                                    == "inferred"
                                    else ""
                                )


                                strength_col.markdown(
                                    f"- **{criterion}** · "
                                    f"**{strength_basis_label}** · "
                                    f"{text}"
                                    f"{inference_note}"
                                )


                        else:

                            strength_col.caption(
                                "확인된 장점 없음"
                            )


                        # =========================================
                        # 약점
                        # =========================================

                        weakness_col.markdown(
                            "**약점**"
                        )


                        if weaknesses:

                            for point in (
                                weaknesses
                            ):

                                criterion = (
                                    point.get(
                                        "criterion",
                                        "-"
                                    )
                                )


                                basis = (
                                    point.get(
                                        "basis",
                                        "confirmed"
                                    )
                                )


                                text = (
                                    point.get(
                                        "text",
                                        ""
                                    )
                                )


                                weakness_basis_label = {
                                    "relative": (
                                        "상대 약점"
                                    ),

                                    "confirmed": (
                                        "확인된 부담"
                                    ),

                                    "inferred": (
                                        "예상 부담"
                                    )
                                }.get(
                                    basis,
                                    "약점"
                                )


                                inference_note = (
                                    " *(추가 검증 필요)*"
                                    if basis
                                    == "inferred"
                                    else ""
                                )


                                weakness_col.markdown(
                                    f"- **{criterion}** · "
                                    f"**{weakness_basis_label}** · "
                                    f"{text}"
                                    f"{inference_note}"
                                )


                        else:

                            weakness_col.caption(
                                "확인된 부담 없음"
                            )


                        # =========================================
                        # Trade-off
                        # =========================================

                        tradeoff_col.markdown(
                            "**Trade-off**"
                        )


                        if tradeoffs:

                            for point in (
                                tradeoffs
                            ):

                                criteria = (
                                    point.get(
                                        "criteria",
                                        []
                                    )
                                )


                                criteria_text = (
                                    " ↔ ".join(
                                        criteria
                                    )
                                )


                                text = (
                                    point.get(
                                        "text",
                                        ""
                                    )
                                )


                                if criteria_text:

                                    tradeoff_col.markdown(
                                        f"- **{criteria_text}** · "
                                        f"{text}"
                                    )


                                else:

                                    tradeoff_col.markdown(
                                        f"- {text}"
                                    )


                        else:

                            tradeoff_col.caption(
                                "명확한 Trade-off 없음"
                            )

            # =====================================================
            # 판단조건 변화 시나리오 분석
            # =====================================================

            st.markdown(
                "<div style='height: 28px;'></div>",
                unsafe_allow_html=True
            )

            st.divider()

            st.markdown(
                "<div style='height: 12px;'></div>",
                unsafe_allow_html=True
            )

            st.markdown(
                "### 판단조건 변화 분석"
            )

            st.caption(
                "판단항목의 중요도, 필수 기준값, 사용환경 등이 "
                "달라졌을 때 후보별 판단근거가 어떻게 달라지는지 확인합니다."
            )

            # =====================================================
            # 1. 판단항목 중요도 변화
            # =====================================================

            st.markdown(
                "#### 1. 판단항목 중요도 변화"
            )

            st.caption(
                "특정 판단항목을 더 중요하게 또는 덜 중요하게 볼 때 "
                "후보별 기존 강점·약점이 어떻게 달라 보이는지 확인합니다."
            )


            # -----------------------------------------------------
            # 중요도 변화 분석 가능한 항목
            # -----------------------------------------------------

            priority_change_criteria = [
                criterion

                for criterion, setting
                in criterion_settings.items()

                if (
                    setting.get("role")
                    in [
                        "필수 기준",
                        "평가항목"
                    ]

                    and

                    setting.get("direction")
                    not in [
                        None,
                        "방향 없음"
                    ]
                )
            ]


            if priority_change_criteria:

                (
                    priority_criterion_col,
                    priority_value_col,
                    priority_button_col
                ) = st.columns(
                    [2.5, 1.5, 1.2],
                    vertical_alignment="bottom"
                )


                selected_priority_criterion = (
                    priority_criterion_col.selectbox(
                        "판단항목",
                        priority_change_criteria,
                        key="priority_change_criterion"
                    )
                )


                selected_priority_setting = (
                    criterion_settings[
                        selected_priority_criterion
                    ]
                )


                current_priority = int(
                    selected_priority_setting.get(
                        "priority"
                    )
                    or 1
                )


                new_priority = (
                    priority_value_col.number_input(
                        "가상 우선순위",
                        min_value=1,
                        value=current_priority,
                        step=1,
                        key=(
                            f"priority_change_value_"
                            f"{selected_priority_criterion}"
                        )
                    )
                )


                # -------------------------------------------------
                # 현재 분석 조건 Signature
                # -------------------------------------------------

                priority_change_signature = (
                    selected_priority_criterion,

                    current_priority,

                    int(
                        new_priority
                    ),

                    comparison_signature,

                    tuple(
                        sorted(
                            (
                                str(
                                    comparison.get(
                                        "candidate",
                                        ""
                                    )
                                ),

                                str(
                                    comparison.get(
                                        "criterion",
                                        ""
                                    )
                                ),

                                str(
                                    comparison.get(
                                        "position",
                                        ""
                                    )
                                )
                            )

                            for comparison
                            in ai_comparison_results
                        )
                    )
                )


                # -------------------------------------------------
                # 중요도 변화 분석 실행
                # -------------------------------------------------

                if priority_button_col.button(
                    "영향 확인",
                    key="run_priority_change_analysis",
                    use_container_width=True
                ):

                    priority_change_result = (
                        analyze_priority_change(
                            criterion=(
                                selected_priority_criterion
                            ),

                            new_priority=(
                                new_priority
                            ),

                            confirmed_results=(
                                confirmed_results
                            ),

                            criterion_settings=(
                                criterion_settings
                            ),

                            qualitative_comparison_results=(
                                ai_comparison_results
                            )
                        )
                    )


                    st.session_state[
                        "priority_change_result"
                    ] = (
                        priority_change_result
                    )


                    st.session_state[
                        "priority_change_signature"
                    ] = (
                        priority_change_signature
                    )


                # -------------------------------------------------
                # 현재 조건에 해당하는 결과만 표시
                # -------------------------------------------------

                current_priority_result_available = (
                    st.session_state.get(
                        "priority_change_signature"
                    )
                    == priority_change_signature

                    and

                    "priority_change_result"
                    in st.session_state
                )


                if current_priority_result_available:

                    priority_result = (
                        st.session_state[
                            "priority_change_result"
                        ]
                    )


                    if not priority_result.get(
                        "available",
                        False
                    ):

                        st.info(
                            priority_result.get(
                                "reason",
                                "현재 조건에서는 분석하기 어렵습니다."
                            )
                        )


                    else:

                        priority_change = (
                            priority_result.get(
                                "priority_change"
                            )
                        )


                        strength_candidates = (
                            priority_result.get(
                                "strength_candidates",
                                []
                            )
                        )


                        weakness_candidates = (
                            priority_result.get(
                                "weakness_candidates",
                                []
                            )
                        )


                        insufficient_candidates = (
                            priority_result.get(
                                "insufficient_candidates",
                                []
                            )
                        )


                        # =========================================
                        # 중요도 높임
                        # =========================================

                        if (
                            priority_change
                            == "importance_increases"
                        ):

                            st.markdown(
                                f"**{selected_priority_criterion} "
                                f"중요도 높임 · "
                                f"{current_priority} → "
                                f"{int(new_priority)}순위**"
                            )


                            if weakness_candidates:

                                st.markdown(
                                    f"- **{', '.join(weakness_candidates)}** · "
                                    f"{selected_priority_criterion} 약점 반영 ↑"
                                )


                            if strength_candidates:

                                st.markdown(
                                    f"- **{', '.join(strength_candidates)}** · "
                                    f"{selected_priority_criterion} 강점 반영 ↑"
                                )


                        # =========================================
                        # 중요도 낮춤
                        # =========================================

                        elif (
                            priority_change
                            == "importance_decreases"
                        ):

                            st.markdown(
                                f"**{selected_priority_criterion} "
                                f"중요도 낮춤 · "
                                f"{current_priority} → "
                                f"{int(new_priority)}순위**"
                            )


                            if weakness_candidates:

                                st.markdown(
                                    f"- **{', '.join(weakness_candidates)}** · "
                                    f"{selected_priority_criterion} "
                                    "약점 반영 ↓"
                                )


                            if strength_candidates:

                                st.markdown(
                                    f"- **{', '.join(strength_candidates)}** · "
                                    f"{selected_priority_criterion} "
                                    "강점 반영 ↓"
                                )


                        # =========================================
                        # 변화 없음
                        # =========================================

                        else:

                            st.info(
                                "현재 우선순위와 동일합니다."
                            )


                        if insufficient_candidates:

                            st.caption(
                                "비교 근거 부족 · "
                                + ", ".join(
                                    insufficient_candidates
                                )
                            )


            else:

                st.info(
                    "중요도 변화 분석이 가능한 판단항목이 없습니다."
                )


            st.markdown(
                "<div style='height: 20px;'></div>",
                unsafe_allow_html=True
            )


            # =====================================================
            # 2. 필수 기준값 변화
            # =====================================================

            st.markdown(
                "#### 2. 필수 기준값 변화"
            )

            st.caption(
                "현재 저장된 기준은 바꾸지 않고, "
                "가상의 기준값에서 후보별 충족 여부가 "
                "어떻게 달라지는지 확인합니다."
            )


            # -----------------------------------------------------
            # 분석 가능한 숫자형 필수 기준
            # -----------------------------------------------------

            threshold_change_criteria = [
                criterion

                for criterion, setting
                in criterion_settings.items()

                if (
                    setting.get("role")
                    == "필수 기준"

                    and

                    setting.get("data_type")
                    in [
                        "numeric",
                        "ranking"
                    ]

                    and

                    setting.get(
                        "constraint_operator"
                    )
                    is not None

                    and

                    setting.get(
                        "constraint_value"
                    )
                    is not None
                )
            ]


            if threshold_change_criteria:

                (
                    threshold_criterion_col,
                    threshold_operator_col,
                    threshold_value_col,
                    threshold_button_col
                ) = st.columns(
                    [2.3, 1, 1.5, 1.2],
                    vertical_alignment="bottom"
                )


                selected_threshold_criterion = (
                    threshold_criterion_col.selectbox(
                        "필수 기준",
                        threshold_change_criteria,
                        key="threshold_change_criterion"
                    )
                )


                threshold_setting = (
                    criterion_settings[
                        selected_threshold_criterion
                    ]
                )


                current_threshold_operator = (
                    threshold_setting.get(
                        "constraint_operator"
                    )
                    or "≤"
                )


                current_threshold_value = float(
                    threshold_setting.get(
                        "constraint_value"
                    )
                )


                threshold_operator_options = [
                    "≤",
                    "≥",
                    "="
                ]


                new_threshold_operator = (
                    threshold_operator_col.selectbox(
                        "가상 조건",
                        threshold_operator_options,
                        index=(
                            threshold_operator_options.index(
                                current_threshold_operator
                            )
                        ),
                        key=(
                            f"threshold_change_operator_"
                            f"{selected_threshold_criterion}"
                        )
                    )
                )


                new_threshold_value = (
                    threshold_value_col.number_input(
                        "가상 기준값",
                        value=current_threshold_value,
                        key=(
                            f"threshold_change_value_"
                            f"{selected_threshold_criterion}"
                        )
                    )
                )


                # -------------------------------------------------
                # 현재 분석 조건 Signature
                # -------------------------------------------------

                threshold_change_signature = (
                    selected_threshold_criterion,

                    current_threshold_operator,

                    current_threshold_value,

                    new_threshold_operator,

                    float(
                        new_threshold_value
                    ),

                    comparison_signature
                )


                # -------------------------------------------------
                # 기준값 변화 분석 실행
                # -------------------------------------------------

                if threshold_button_col.button(
                    "변화 확인",
                    key="run_threshold_change_analysis",
                    use_container_width=True
                ):

                    threshold_change_result = (
                        analyze_threshold_change(
                            criterion=(
                                selected_threshold_criterion
                            ),

                            new_operator=(
                                new_threshold_operator
                            ),

                            new_standard=(
                                new_threshold_value
                            ),

                            confirmed_results=(
                                confirmed_results
                            ),

                            criterion_settings=(
                                criterion_settings
                            )
                        )
                    )


                    st.session_state[
                        "threshold_change_result"
                    ] = (
                        threshold_change_result
                    )


                    st.session_state[
                        "threshold_change_signature"
                    ] = (
                        threshold_change_signature
                    )


                # -------------------------------------------------
                # 현재 가정과 일치하는 결과만 표시
                # -------------------------------------------------

                current_threshold_result_available = (
                    st.session_state.get(
                        "threshold_change_signature"
                    )
                    == threshold_change_signature

                    and

                    "threshold_change_result"
                    in st.session_state
                )


                if current_threshold_result_available:

                    threshold_result = (
                        st.session_state[
                            "threshold_change_result"
                        ]
                    )


                    if not threshold_result.get(
                        "available",
                        False
                    ):

                        st.info(
                            threshold_result.get(
                                "reason",
                                "현재 조건에서는 분석하기 어렵습니다."
                            )
                        )


                    else:

                        unit = (
                            threshold_result.get(
                                "unit"
                            )
                            or ""
                        )


                        current_standard = (
                            threshold_result.get(
                                "current_standard"
                            )
                        )


                        if (
                            isinstance(
                                current_standard,
                                float
                            )
                            and
                            current_standard.is_integer()
                        ):

                            current_standard = int(
                                current_standard
                            )


                        displayed_new_standard = float(
                            new_threshold_value
                        )


                        if (
                            displayed_new_standard.is_integer()
                        ):

                            displayed_new_standard = int(
                                displayed_new_standard
                            )


                        st.markdown(
                            f"**{selected_threshold_criterion} 기준 변경 · "
                            f"{current_threshold_operator} "
                            f"{current_standard}{unit} "
                            f"→ "
                            f"{new_threshold_operator} "
                            f"{displayed_new_standard}{unit}**"
                        )


                        transition_labels = {
                            "stays_satisfied": (
                                "충족 유지"
                            ),

                            "stays_unmet": (
                                "미충족 유지"
                            ),

                            "becomes_satisfied": (
                                "미충족 → 충족"
                            ),

                            "becomes_unmet": (
                                "충족 → 미충족"
                            )
                        }


                        candidate_changes = (
                            threshold_result.get(
                                "candidate_changes",
                                []
                            )
                        )


                        if candidate_changes:

                            for change in (
                                candidate_changes
                            ):

                                candidate = (
                                    change.get(
                                        "candidate",
                                        "-"
                                    )
                                )


                                actual_value = (
                                    change.get(
                                        "actual_value"
                                    )
                                )


                                if (
                                    isinstance(
                                        actual_value,
                                        float
                                    )
                                    and
                                    actual_value.is_integer()
                                ):

                                    actual_value = int(
                                        actual_value
                                    )


                                transition = (
                                    transition_labels.get(
                                        change.get(
                                            "transition"
                                        ),
                                        "-"
                                    )
                                )


                                st.markdown(
                                    f"- **{candidate}** · "
                                    f"{actual_value}{unit} · "
                                    f"{transition}"
                                )


                        else:

                            st.info(
                                "비교 가능한 후보의 정량 정보가 없습니다."
                            )


                        ambiguous_candidates = (
                            threshold_result.get(
                                "ambiguous_candidates",
                                []
                            )
                        )


                        if ambiguous_candidates:

                            st.caption(
                                "판단 보류 · 동일 후보에 여러 값이 있거나 "
                                "숫자로 해석할 수 없는 정보: "
                                + ", ".join(
                                    ambiguous_candidates
                                )
                            )


            else:

                st.info(
                    "수치 기준 변화 분석이 가능한 필수 기준이 없습니다."
                )


            st.markdown(
                "<div style='height: 24px;'></div>",
                unsafe_allow_html=True
            )

            st.divider()


            # =====================================================
            # 3. 상황 변화 시나리오
            # =====================================================

            st.markdown(
                "#### 3. 상황 변화 시나리오"
            )

            st.caption(
                "사용환경, 고객, 개발상황처럼 숫자로 직접 계산하기 어려운 "
                "조건 변화는 LLM이 확정된 근거와 연결해 해석합니다."
            )

            # =====================================================
            # 사용자 시나리오 입력
            # =====================================================

            scenario_text = (
                st.text_area(
                    "상황 변화",
                    placeholder=(
                        "예: 혹한 지역 판매 비중이 낮아진다면?\n"
                        "예: 젊은 고객보다 법인 고객 비중이 높아진다면?\n"
                        "예: 개발 일정이 더 촉박해진다면?"
                    ),
                    key="scenario_impact_input",
                    height=110
                )
            )


            # =====================================================
            # 현재 분석 대상 상태 Signature
            # =====================================================
            #
            # 시나리오 / Evidence / 판단기준 /
            # 정성 비교 결과가 바뀌면
            # 이전 분석을 다시 사용하지 않는다.
            # =====================================================

            scenario_impact_signature = (

                str(
                    scenario_text
                ).strip(),

                comparison_signature,

                tuple(
                    sorted(
                        (
                            str(
                                criterion
                            ),

                            str(
                                setting.get(
                                    "role",
                                    ""
                                )
                            ),

                            str(
                                setting.get(
                                    "priority",
                                    ""
                                )
                            ),

                            str(
                                setting.get(
                                    "direction",
                                    ""
                                )
                            )
                        )

                        for criterion, setting
                        in criterion_settings.items()
                    )
                ),

                tuple(
                    sorted(
                        (
                            str(
                                comparison.get(
                                    "candidate",
                                    ""
                                )
                            ),

                            str(
                                comparison.get(
                                    "criterion",
                                    ""
                                )
                            ),

                            str(
                                comparison.get(
                                    "position",
                                    ""
                                )
                            ),

                            str(
                                comparison.get(
                                    "reason",
                                    ""
                                )
                            )
                        )

                        for comparison
                        in ai_comparison_results
                    )
                )
            )


            stored_scenario_signature = (
                st.session_state.get(
                    "scenario_impact_signature"
                )
            )


            has_scenario_result = (
                "scenario_impact_result"
                in st.session_state
            )


            current_scenario_result_available = (
                has_scenario_result

                and

                stored_scenario_signature
                == scenario_impact_signature
            )


            # =====================================================
            # 분석 실행 버튼
            # =====================================================

            if st.button(
                "변화 영향 분석",
                type="primary",
                key="run_scenario_impact_analysis",
                disabled=(
                    not scenario_text.strip()
                )
            ):

                try:

                    with st.spinner(
                        "변화된 조건이 기존 판단근거에 "
                        "어떤 영향을 주는지 분석하고 있습니다..."
                    ):

                        scenario_impact_result = (
                            analyze_scenario_impact(
                                scenario=(
                                    scenario_text
                                ),
                                confirmed_results=(
                                    confirmed_results
                                ),
                                criterion_settings=(
                                    criterion_settings
                                ),
                                qualitative_comparison_results=(
                                    ai_comparison_results
                                )
                            )
                        )


                    st.session_state[
                        "scenario_impact_result"
                    ] = (
                        scenario_impact_result
                    )


                    st.session_state[
                        "scenario_impact_signature"
                    ] = (
                        scenario_impact_signature
                    )


                    current_scenario_result_available = (
                        True
                    )


                    st.success(
                        "판단조건 변화 분석이 완료되었습니다."
                    )


                except Exception as e:

                    st.error(
                        "판단조건 변화 분석 중 "
                        "오류가 발생했습니다."
                    )

                    st.write(
                        e
                    )


            # =====================================================
            # 이전 결과가 현재 조건과 다른 경우
            # =====================================================

            elif (
                has_scenario_result

                and

                stored_scenario_signature
                != scenario_impact_signature
            ):

                st.caption(
                    "상황 조건이나 판단근거가 변경되었습니다. "
                    "다시 분석하면 변경된 조건을 반영합니다."
                )


            # =====================================================
            # 결과 표시
            # =====================================================

            if (
                current_scenario_result_available
            ):

                scenario_impact_result = (
                    st.session_state.get(
                        "scenario_impact_result",
                        {}
                    )
                )


                affected_criteria = (
                    scenario_impact_result.get(
                        "affected_criteria",
                        []
                    )
                )


                impacts = (
                    scenario_impact_result.get(
                        "impacts",
                        []
                    )
                )


                st.markdown(
                    "<div style='height: 18px;'></div>",
                    unsafe_allow_html=True
                )


                # =============================================
                # 영향받는 판단항목
                # =============================================

                if affected_criteria:

                    st.markdown(
                        "**영향받는 판단항목**"
                    )

                    st.write(
                        " / ".join(
                            affected_criteria
                        )
                    )


                else:

                    st.info(
                        "현재 확정된 정보만으로는 "
                        "이 조건 변화의 영향을 명확히 판단하기 어렵습니다."
                    )


                # =============================================
                # 후보별 영향
                # =============================================

                if impacts:

                    impact_label_map = {
                        "importance_increases": (
                            "판단 영향 증가"
                        ),

                        "importance_decreases": (
                            "판단 영향 감소"
                        ),

                        "mixed": (
                            "복합 영향"
                        ),

                        "uncertain": (
                            "영향 불확실"
                        )
                    }


                    st.markdown(
                        "<div style='height: 12px;'></div>",
                        unsafe_allow_html=True
                    )


                    for candidate in (
                        candidate_names
                    ):

                        candidate_impacts = [
                            impact

                            for impact
                            in impacts

                            if (
                                impact.get(
                                    "candidate"
                                )
                                == candidate
                            )
                        ]


                        if not candidate_impacts:

                            continue


                        with st.container(
                            border=True
                        ):

                            st.markdown(
                                f"#### {candidate}"
                            )


                            for impact in (
                                candidate_impacts
                            ):

                                criterion = (
                                    impact.get(
                                        "criterion",
                                        "-"
                                    )
                                )


                                impact_type = (
                                    impact.get(
                                        "impact",
                                        "uncertain"
                                    )
                                )


                                impact_label = (
                                    impact_label_map.get(
                                        impact_type,
                                        impact_type
                                    )
                                )


                                text = (
                                    impact.get(
                                        "text",
                                        ""
                                    )
                                )


                                st.markdown(
                                    f"**{criterion} · "
                                    f"{impact_label}**"
                                )

                                st.write(
                                    text
                                )

            # =====================================================
            # 5. AI 문장형 정성 비교 근거
            # =====================================================

            if (
                current_ai_result_available
                and ai_comparison_results
            ):

                with st.expander(
                    "AI가 이렇게 비교한 이유 보기"
                ):

                    position_labels = {
                        "strength": "상대적 강점",
                        "neutral": "중립",
                        "weakness": "상대적 약점",
                        "insufficient": "판단 불가"
                    }


                    for criterion in (
                        free_text_criteria
                    ):

                        criterion_comparisons = [
                            comparison

                            for comparison
                            in ai_comparison_results

                            if (
                                comparison.get(
                                    "criterion"
                                )
                                == criterion
                            )
                        ]


                        if not criterion_comparisons:

                            continue


                        st.markdown(
                            f"### {criterion}"
                        )


                        for comparison in (
                            criterion_comparisons
                        ):

                            candidate = (
                                comparison.get(
                                    "candidate",
                                    "-"
                                )
                            )

                            position = (
                                comparison.get(
                                    "position",
                                    "insufficient"
                                )
                            )

                            reason = (
                                comparison.get(
                                    "reason",
                                    ""
                                )
                            )


                            position_text = (
                                position_labels.get(
                                    position,
                                    position
                                )
                            )


                            st.markdown(
                                f"**{candidate} — "
                                f"{position_text}**"
                            )

                            st.write(
                                reason
                            )


                        st.divider()


            elif free_text_criteria:

                st.caption(
                    "문장형 정성정보의 강점·약점은 "
                    "'문장형 정성 비교 실행' 후 반영됩니다."
                )