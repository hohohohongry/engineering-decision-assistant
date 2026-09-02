import streamlit as st
import pandas as pd

from file_reader import read_pdf, read_excel
from mock_extractor import build_mock_results


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


st.title("Engineering Decision Assistant")


# =========================================================
# 1. 개발자료 업로드
# =========================================================

st.subheader("1. 개발자료 업로드")

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

st.subheader("2. 추출 항목 설정")

st.write(
    "업로드한 자료에서 추출할 정보를 선택하거나 직접 추가하세요."
)


default_fields = [
    "개발기간",
    "원가",
    "품질",
    "호환성",
    "고객체감"
]


selected_default_fields = st.multiselect(
    "기본 추출 항목",
    default_fields,
    default=default_fields
)


# ---------------------------------------------------------
# 자유추가 항목 저장
# ---------------------------------------------------------

if "custom_fields" not in st.session_state:

    st.session_state.custom_fields = []


custom_field = st.text_input(
    "추가할 항목",
    placeholder="예: 금형비, 중량, 시험기간"
)


if st.button(
    "항목 추가"
):

    new_field = (
        custom_field.strip()
    )

    if not new_field:

        st.warning(
            "추가할 항목 이름을 입력해주세요."
        )

    elif (
        new_field in default_fields
        or new_field
        in st.session_state.custom_fields
    ):

        st.info(
            "이미 존재하는 항목입니다."
        )

    else:

        st.session_state.custom_fields.append(
            new_field
        )

        st.success(
            f"'{new_field}' 항목이 추가되었습니다."
        )


if st.session_state.custom_fields:

    st.write(
        "직접 추가한 항목:",
        st.session_state.custom_fields
    )


# ---------------------------------------------------------
# 최종 추출항목 생성
# ---------------------------------------------------------

selected_fields = (
    selected_default_fields
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
# 3. 추출 결과 테스트
# =========================================================

st.subheader(
    "3. 추출 결과"
)

st.caption(
    "현재 단계에서는 실제 AI 분석이 아닌 "
    "Mock 테스트 데이터를 사용합니다."
)


# ---------------------------------------------------------
# PDF 파일만 테스트 대상으로 사용
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
        "현재 추출 테스트는 PDF 파일을 기준으로 진행합니다."
    )


can_run_mock = bool(
    pdf_files
    and selected_fields
)


# ---------------------------------------------------------
# Mock 데이터 생성
# ---------------------------------------------------------

if st.button(
    "Mock 추출 테스트 실행",
    disabled=not can_run_mock
):

    source_file = (
        pdf_files[0].name
    )

    (
        requested_results,
        suggested_results
    ) = build_mock_results(
        selected_fields,
        source_file
    )

    st.session_state.mock_requested_results = (
        requested_results
    )

    st.session_state.mock_suggested_results = (
        suggested_results
    )

    # 새로운 추출을 실행하면
    # 기존 확정 데이터도 초기화
    st.session_state.confirmed_results = []


# =========================================================
# 요청 항목 추출 결과 표시
# =========================================================

if (
    "mock_requested_results"
    in st.session_state
):

    requested_results = (
        st.session_state.mock_requested_results
    )

    st.markdown(
        "#### 요청 항목 추출 결과"
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
        "추출 근거 확인"
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


# =========================================================
# 추가 발견 정보
# =========================================================

if (
    "mock_suggested_results"
    in st.session_state
):

    suggested_results = (
        st.session_state.mock_suggested_results
    )


    st.markdown(
        "#### 추가 발견 정보"
    )


    if suggested_results:

        st.write(
            "사용자가 지정하지 않았지만 "
            "의사결정에 영향을 줄 가능성이 있는 정보입니다."
        )


        for index, suggestion in enumerate(
            suggested_results
        ):

            st.markdown("---")


            suggestion_value = (
                format_value(
                    suggestion["value"],
                    suggestion["unit"]
                )
            )


            st.markdown(
                f'**{suggestion["suggested_field"]}**'
            )

            st.write(
                "대상:",
                suggestion["candidate"]
            )

            st.write(
                "내용:",
                suggestion_value
            )

            st.write(
                "중요한 이유:",
                suggestion["reason"]
            )

            st.write(
                "근거:",
                suggestion["evidence"]
            )

            st.write(
                "출처:",
                suggestion["source_file"],
                "/",
                f'p.{suggestion["page"]}'
            )


            add_column, ignore_column = (
                st.columns(2)
            )


            # ---------------------------------------------
            # 판단항목에 추가
            # ---------------------------------------------

            if add_column.button(
                "판단항목에 추가",
                key=f"add_suggestion_{index}"
            ):

                new_result = {
                    "candidate": (
                        suggestion["candidate"]
                    ),

                    "field": (
                        suggestion["suggested_field"]
                    ),

                    "value": (
                        suggestion["value"]
                    ),

                    "unit": (
                        suggestion["unit"]
                    ),

                    # 최초값 보존
                    "original_candidate": (
                        suggestion["candidate"]
                    ),

                    "original_field": (
                        suggestion["suggested_field"]
                    ),

                    "original_value": (
                        suggestion["value"]
                    ),

                    "original_unit": (
                        suggestion["unit"]
                    ),

                    "data_type": (
                        suggestion["data_type"]
                    ),

                    "source_file": (
                        suggestion["source_file"]
                    ),

                    "page": (
                        suggestion["page"]
                    ),

                    "evidence": (
                        suggestion["evidence"]
                    ),

                    "status": "검토 필요",

                    "modified_by_user": False
                }


                already_exists = any(

                    result["candidate"]
                    == new_result["candidate"]

                    and

                    result["field"]
                    == new_result["field"]

                    for result
                    in st.session_state.mock_requested_results
                )


                if not already_exists:

                    st.session_state.mock_requested_results.append(
                        new_result
                    )


                suggested_field = (
                    suggestion["suggested_field"]
                )


                if (
                    suggested_field
                    not in default_fields

                    and

                    suggested_field
                    not in st.session_state.custom_fields
                ):

                    st.session_state.custom_fields.append(
                        suggested_field
                    )


                st.session_state.mock_suggested_results.pop(
                    index
                )

                st.rerun()


            # ---------------------------------------------
            # 무시
            # ---------------------------------------------

            if ignore_column.button(
                "무시",
                key=f"ignore_suggestion_{index}"
            ):

                st.session_state.mock_suggested_results.pop(
                    index
                )

                st.rerun()


    else:

        st.info(
            "검토할 추가 발견 정보가 없습니다."
        )


# =========================================================
# 4. 추출 결과 검토 및 확정
# =========================================================

if (
    "mock_requested_results"
    in st.session_state
    and st.session_state.mock_requested_results
):

    st.subheader(
        "4. 추출 결과 검토 및 확정"
    )

    st.write(
        "추출된 값과 근거를 확인한 뒤 "
        "필요하면 수정하고 승인하세요."
    )


    review_results = (
        st.session_state.mock_requested_results
    )


    # -----------------------------------------------------
    # 검토할 행 선택
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
            "검토할 항목 선택",
            review_options
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


    # -----------------------------------------------------
    # 선택한 항목의 원문 정보 표시
    # -----------------------------------------------------

    st.markdown(
        "##### 근거 정보"
    )

    st.write(
        "출처:",
        selected_result["source_file"],
        "/",
        f'p.{selected_result["page"]}'
    )

    st.write(
        "근거:",
        selected_result["evidence"]
    )


    if selected_result[
        "modified_by_user"
    ]:

        st.info(
            "이 항목은 사용자가 수정했습니다. "
            "최초 추출값은 아래에 보존되어 있습니다."
        )

        st.write(
            "최초 추출값:",
            format_value(
                selected_result["original_value"],
                selected_result["original_unit"]
            )
        )


    # -----------------------------------------------------
    # 값 수정
    # -----------------------------------------------------

    st.markdown(
        "##### 추출값 수정"
    )


    with st.form(
        key=f"edit_form_{selected_index}"
    ):

        edited_candidate = (
            st.text_input(
                "후보",
                value=str(
                    selected_result["candidate"]
                )
            )
        )


        edited_field = (
            st.text_input(
                "항목",
                value=str(
                    selected_result["field"]
                )
            )
        )


        edited_value_text = (
            st.text_input(
                "값",
                value=str(
                    selected_result["value"]
                )
            )
        )


        edited_unit = (
            st.text_input(
                "단위",
                value=(
                    selected_result["unit"]
                    if selected_result["unit"]
                    else ""
                )
            )
        )


        save_edit = (
            st.form_submit_button(
                "수정 저장"
            )
        )


    # -----------------------------------------------------
    # 수정 저장 처리
    # -----------------------------------------------------

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
            ] = edited_candidate.strip()


            selected_result[
                "field"
            ] = edited_field.strip()


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


            st.success(
                "수정사항이 저장되었습니다."
            )

            st.rerun()


        except ValueError:

            st.error(
                "정량 데이터는 숫자로 입력해주세요."
            )


    # -----------------------------------------------------
    # 승인 기능
    # -----------------------------------------------------

    approve_column, approve_all_column = (
        st.columns(2)
    )


    # 개별 승인
    if approve_column.button(
        "선택 항목 승인"
    ):

        selected_result[
            "status"
        ] = "승인 완료"

        st.rerun()


    # 전체 승인
    if approve_all_column.button(
        "전체 승인"
    ):

        for result in (
            st.session_state.mock_requested_results
        ):

            result[
                "status"
            ] = "승인 완료"

        st.rerun()


    # =====================================================
    # 확정 데이터 생성
    # =====================================================

    confirmed_results = [
        result.copy()

        for result
        in st.session_state.mock_requested_results

        if result["status"]
        == "승인 완료"
    ]


    st.session_state.confirmed_results = (
        confirmed_results
    )


    st.markdown(
        "##### 승인 현황"
    )


    approved_count = (
        len(confirmed_results)
    )

    total_count = (
        len(
            st.session_state.mock_requested_results
        )
    )


    st.write(
        f"{approved_count} / "
        f"{total_count}개 승인 완료"
    )


    # -----------------------------------------------------
    # Confirmed Evidence Data
    # -----------------------------------------------------

    if confirmed_results:

        st.markdown(
            "##### Confirmed Evidence Data"
        )


        confirmed_display_rows = []


        for result in confirmed_results:

            confirmed_display_rows.append(
                {
                    "후보": (
                        result["candidate"]
                    ),

                    "항목": (
                        result["field"]
                    ),

                    "결과": (
                        format_value(
                            result["value"],
                            result["unit"]
                        )
                    ),

                    "출처": (
                        f'{result["source_file"]} '
                        f'/ p.{result["page"]}'
                    ),

                    "사용자 수정": (
                        "Yes"
                        if result["modified_by_user"]
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
            "아직 승인된 데이터가 없습니다."
        )
        
# =========================================================
# 5. 판단기준 설정
# =========================================================

if (
    "confirmed_results" in st.session_state
    and st.session_state.confirmed_results
):

    st.subheader("5. 판단기준 설정")

    st.write(
        "확정된 각 항목이 의사결정에서 어떤 역할을 하는지 설정하세요."
    )

    st.caption(
        "필수 기준은 후보를 자동 탈락시키지 않고, "
        "이후 비교 화면에서 충족 여부를 표시하는 데 사용합니다."
    )


    # -----------------------------------------------------
    # 판단기준 설정 저장공간
    # -----------------------------------------------------

    if "criterion_settings" not in st.session_state:
        st.session_state.criterion_settings = {}


    confirmed_results = st.session_state.confirmed_results


    # 확정 데이터에 존재하는 항목명만 추출
    criterion_names = list(
        dict.fromkeys(
            result["field"]
            for result in confirmed_results
        )
    )


    temporary_settings = {}


    # -----------------------------------------------------
    # 판단기준 설정 Form
    # -----------------------------------------------------

    with st.form("criterion_settings_form"):

        for index, criterion in enumerate(criterion_names):

            # 해당 항목의 데이터 형식과 단위 확인
            example_result = next(
                result
                for result in confirmed_results
                if result["field"] == criterion
            )

            data_type = example_result["data_type"]
            unit = example_result["unit"]


            # 이전에 저장한 설정이 있으면 불러오기
            existing_setting = (
                st.session_state.criterion_settings.get(
                    criterion,
                    {}
                )
            )


            st.markdown(f"### {criterion}")


            if unit:
                st.caption(
                    f"데이터 형식: {data_type} / 단위: {unit}"
                )
            else:
                st.caption(
                    f"데이터 형식: {data_type}"
                )


            # -------------------------------------------------
            # 역할 설정
            # -------------------------------------------------

            role_options = [
                "필수 기준",
                "평가항목",
                "참고항목"
            ]

            current_role = existing_setting.get(
                "role",
                "평가항목"
            )

            role = st.selectbox(
                "역할",
                role_options,
                index=role_options.index(current_role),
                key=f"criterion_role_{index}"
            )

            # 모든 판단항목의 우선순위 설정
            current_priority = (
                existing_setting.get("priority")
                or index + 1
            )

            priority = st.number_input(
                "우선순위 (1이 가장 중요)",
                min_value=1,
                value=int(current_priority),
                step=1,
                key=f"criterion_priority_{index}"
            )
    
            direction = None
            constraint_operator = None
            constraint_value = None


            # =================================================
            # 정량형 데이터
            # =================================================

            if data_type in ["numeric", "ranking"]:

                # 평가항목일 경우
                if role == "평가항목":

                    direction_options = [
                        "높을수록 좋음",
                        "낮을수록 좋음",
                        "방향 없음"
                    ]

                    current_direction = (
                        existing_setting.get("direction")
                        or "방향 없음"
                    )

                    direction = st.selectbox(
                        "평가 방향",
                        direction_options,
                        index=direction_options.index(
                            current_direction
                        ),
                        key=f"criterion_direction_{index}"
                    )


                # 필수 기준일 경우
                elif role == "필수 기준":

                    operator_options = [
                        "≤",
                        "≥",
                        "="
                    ]

                    
                    current_operator = (
                        existing_setting.get("constraint_operator")
                        or "≤"
                    )

                    constraint_operator = st.selectbox(
                        "기준 조건",
                        operator_options,
                        index=operator_options.index(
                            current_operator
                        ),
                        key=f"criterion_operator_{index}"
                    )


                    current_constraint_value = (
                        existing_setting.get("constraint_value")
                        or 0.0
                    )

                    constraint_value = st.number_input(
                        "기준값",
                        value=float(
                            current_constraint_value
                        ),
                        key=f"criterion_value_{index}"
                    )


            # =================================================
            # 정성형 데이터
            # =================================================

            else:

                if role == "평가항목":

                    direction_options = [
                        "상 > 중 > 하",
                        "하 > 중 > 상",
                        "방향 없음"
                    ]

                    current_direction = (
                        existing_setting.get("direction")
                        or "방향 없음"
                    )

                    direction = st.selectbox(
                        "평가 방향",
                        direction_options,
                        index=direction_options.index(
                            current_direction
                        ),
                        key=f"criterion_direction_{index}"
                    )


                elif role == "필수 기준":

                    st.info(
                        "정성형 필수 기준의 충족 조건은 "
                        "다음 단계에서 설정합니다."
                    )


            # -------------------------------------------------
            # 현재 입력값 임시 저장
            # -------------------------------------------------

            temporary_settings[criterion] = {
                "criterion": criterion,
                "data_type": data_type,
                "unit": unit,
                "role": role,
                "priority": priority,
                "direction": direction,
                "constraint_operator": constraint_operator,
                "constraint_value": constraint_value
            }


            st.divider()


        save_criteria = st.form_submit_button(
            "판단기준 설정 저장"
        )


    # -----------------------------------------------------
    # 설정 저장
    # -----------------------------------------------------

    if save_criteria:

        st.session_state.criterion_settings = (
            temporary_settings
        )

        st.success(
            "판단기준 설정이 저장되었습니다."
        )


    # -----------------------------------------------------
    # 저장된 설정 확인
    # -----------------------------------------------------

    if st.session_state.criterion_settings:

        st.markdown(
            "#### 현재 판단기준"
        )

        criterion_display_rows = []


        for setting in (
            st.session_state.criterion_settings.values()
        ):

            # 필수 기준 표현
            if (
                setting["role"] == "필수 기준"
                and setting["constraint_operator"] is not None
            ):

                constraint_text = (
                    f'{setting["constraint_operator"]} '
                    f'{setting["constraint_value"]}'
                )

                if setting["unit"]:
                    constraint_text += str(
                        setting["unit"]
                    )

            elif setting["role"] == "필수 기준":

                constraint_text = "조건 설정 예정"

            else:

                constraint_text = "-"


            direction_text = (
                setting["direction"]
                if setting["direction"]
                else "-"
            )


            criterion_display_rows.append(
                {
                    "판단기준": setting["criterion"],
                    "역할": setting["role"],
                    "우선순위": setting["priority"],
                    "평가방향": direction_text,
                    "기준조건": constraint_text
                }
            )


        criterion_settings_df = pd.DataFrame(
            criterion_display_rows
        )


        st.dataframe(
            criterion_settings_df,
            use_container_width=True,
            hide_index=True
        )
        
# =========================================================
# 6. 후보 비교
# =========================================================

if (
    "confirmed_results" in st.session_state
    and st.session_state.confirmed_results
    and "criterion_settings" in st.session_state
    and st.session_state.criterion_settings
):

    st.subheader("6. 후보 비교")

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
    # -----------------------------------------------------

    candidate_names = list(
        dict.fromkeys(
            result["candidate"]
            for result
            in confirmed_results
        )
    )


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

                row_data[
                    candidate
                ] = format_value(
                    matching_result[
                        "value"
                    ],
                    matching_result[
                        "unit"
                    ]
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


        # 필수 기준만 색상 적용
        if (
            setting.get("role")
            != "필수 기준"
        ):

            return styles


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
            or constraint_value
            is None
        ):

            return styles


        # 후보별 충족 여부 판정
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


    # -----------------------------------------------------
    # 스타일 적용
    # -----------------------------------------------------

    styled_comparison_df = (
        comparison_df.style.apply(
            color_comparison_cell,
            axis=1
        )
    )


    st.dataframe(
        styled_comparison_df,
        use_container_width=True,
        hide_index=True
    )