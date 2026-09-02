from typing import Literal, Union

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel


load_dotenv()

client = OpenAI()


# =========================================================
# Structured Output Schema
# =========================================================

class RequestedEvidence(BaseModel):

    # candidate:
    # 특정 후보 하나에 직접 연결되는 정보
    #
    # multi_candidate:
    # 여러 후보에 동시에 적용되는 정보
    #
    # global:
    # 전체 의사결정에 공통으로 적용되는 정보
    #
    # context:
    # 중요한 배경정보이지만 특정 후보 속성으로
    # 직접 연결하기 어려운 정보

    scope: Literal[
        "candidate",
        "multi_candidate",
        "global",
        "context"
    ]

    applies_to: list[str]

    field: str

    value: Union[
        float,
        str
    ]

    unit: str | None

    data_type: Literal[
        "numeric",
        "qualitative",
        "ranking"
    ]

    page: int

    evidence: str

    reason: str

    extraction_status: Literal[
        "found",
        "conflict"
    ]


class SuggestedEvidence(BaseModel):

    scope: Literal[
        "candidate",
        "multi_candidate",
        "global",
        "context"
    ]

    applies_to: list[str]

    suggested_field: str

    value: Union[
        float,
        str
    ]

    unit: str | None

    data_type: Literal[
        "numeric",
        "qualitative",
        "ranking"
    ]

    page: int

    evidence: str

    reason: str


    # -----------------------------------------------------
    # 추가정보 정리용 분류
    # -----------------------------------------------------

    suggestion_type: Literal[
        "existing_field",
        "new_field",
        "reference"
    ]

    # existing_field일 경우
    # 반드시 사용자가 선택한 기존 항목명 중 하나
    target_field: str | None

    # UI에서 비슷한 정보를 묶어 보여주기 위한 대표 이름
    group_name: str


class ExtractionResponse(BaseModel):

    # 문서에서 실제 의사결정 대상으로 제시된 후보
    decision_candidates: list[str]

    requested_results: list[
        RequestedEvidence
    ]

    suggested_results: list[
        SuggestedEvidence
    ]


# =========================================================
# AI Evidence 추출
# =========================================================

def extract_evidence(
    pages,
    selected_fields,
    source_file,
    model="gpt-5.6-luna"
):

    if not pages:

        raise ValueError(
            "분석할 PDF 페이지가 없습니다."
        )


    if not selected_fields:

        raise ValueError(
            "추출할 항목이 선택되지 않았습니다."
        )


    # -----------------------------------------------------
    # PDF 전체 텍스트 구성
    # -----------------------------------------------------

    document_parts = []


    for page in pages:

        document_parts.append(
            f"""
[PAGE {page["page"]}]
{page["text"]}
"""
        )


    document_text = "\n".join(
        document_parts
    )


    fields_text = ", ".join(
        selected_fields
    )


    # =====================================================
    # AI Instruction
    # =====================================================

    instructions = """
You are an engineering evidence extraction engine.

Your role is to extract traceable engineering evidence.
You do NOT make the final engineering decision.


=========================================================
STEP 1. IDENTIFY THE ACTUAL DECISION CANDIDATES
=========================================================

Before extracting evidence, identify the actual alternatives,
candidates, design options, suppliers, parts, concepts, or plans
that the document explicitly presents as choices in the decision.

Examples:

A안 / B안 / C안 / D안
Alternative 1 / Alternative 2
Supplier A / Supplier B
Design Concept A / Design Concept B

decision_candidates must contain ONLY these actual decision alternatives.

Do NOT treat the following as new candidates unless the document
explicitly defines them as independent decision alternatives:

- technologies
- features
- components
- customer groups
- performance attributes
- design characteristics
- generic product types
- risks
- requirements

For example, if the alternatives are A안, B안, C안, D안,
do NOT create a new candidate named "플러시 도어핸들"
just because the document discusses flush door handles.


=========================================================
STEP 2. DETERMINE THE SCOPE OF EACH PIECE OF EVIDENCE
=========================================================

Every evidence item must have one of four scopes.


1. candidate

The evidence is directly attributable to exactly one
decision candidate.

Example:

B안:
"부품 원가와 검증 항목이 증가한다."

scope = "candidate"
applies_to = ["B안"]


2. multi_candidate

The same evidence clearly applies to multiple identified
decision candidates.

Example:

If A안 and B안 both use a flush-handle architecture and the
document explicitly supports that the same customer perception
applies to both:

scope = "multi_candidate"
applies_to = ["A안", "B안"]


3. global

The evidence represents an overall requirement, constraint,
risk, or condition relevant to the whole decision rather than
a particular candidate.

Example:

"In cold regions, a door failing to open can become a safety concern."

scope = "global"
applies_to = []


4. context

The information is relevant background or decision context,
but the document does not provide enough evidence to assign
it directly to one or more candidates.

scope = "context"
applies_to = []


IMPORTANT:

Never invent candidate applicability.

If the document does not explicitly support which candidate
an item applies to, use global or context instead of guessing.


=========================================================
STEP 3. EXTRACT USER-REQUESTED INFORMATION
=========================================================

requested_results must contain only fields requested by the user.

The field value must exactly match one of the user's requested
field names.

Use only explicitly supported document information.

Never estimate or fabricate missing values.


For numeric information:

value = number only
unit = unit only

Example:

3개월
→ value = 3
→ unit = "개월"


For qualitative information:

Preserve the actual meaning stated in the document.

Do not arbitrarily convert free-text qualitative information
into high / medium / low or numerical scores.


For ranking information:

Use data_type = "ranking".


Every item must include:

- scope
- applies_to
- page
- evidence
- reason

For reason:

Explain briefly why this evidence could matter to the engineering decision.

The reason must be grounded only in the supplied document.

Explain the decision relevance, such as its possible effect on:
- feasibility
- performance
- quality
- customer value
- safety
- reliability
- cost
- schedule
- manufacturing
- validation
- maintainability
- compatibility
- operational complexity
- engineering risk

Do not invent an effect that the document does not support.

Do not merely repeat the evidence.
Explain why the evidence matters for comparing or evaluating the alternatives.

=========================================================
REQUESTED FIELD COVERAGE
=========================================================

Treat every user-requested field as an independent search task.

Before finishing, mentally build a matrix:

requested field × decision candidate

and inspect the ENTIRE document for explicit evidence for each cell.

Do not stop searching a requested field after finding evidence
for another semantically similar field.

For example, if the user requested both:
- 디자인
- 고객체감

do not automatically classify all design-related evidence only
as 고객체감.

Check independently whether the document explicitly supports
each requested field.

The same source evidence MAY support more than one requested field
when its content explicitly supports both concepts.

In that case, it is valid to emit separate requested_results
using the same evidence text under different field names.

For every candidate-field combination:

- if explicit evidence exists, extract it.
- if explicit evidence does not exist, do not fabricate a result.

Do not collapse or rename the user's requested fields.

=========================================================
STEP 4. CONFLICTS
=========================================================

If two explicit pieces of evidence conflict for the same
candidate and field:

- preserve both pieces separately
- extraction_status = "conflict"

Otherwise:

extraction_status = "found"


=========================================================
STEP 5. SUGGEST IMPORTANT UNREQUESTED INFORMATION
=========================================================

suggested_results contains information that could materially
help the engineering decision but was not already sufficiently
represented in requested_results.

The purpose of suggested_results is NOT to create as many new
criteria as possible.

The purpose is to help the user discover useful information
while keeping the decision criteria concise and non-duplicative.


---------------------------------------------------------
A. FIRST CHECK FOR OVERLAP WITH USER-REQUESTED FIELDS
---------------------------------------------------------

Before creating a new suggested field, compare its meaning with
ALL USER REQUESTED FIELDS.

If the information substantially belongs to an existing
user-requested field:

suggestion_type = "existing_field"

target_field must exactly match ONE of the USER REQUESTED FIELDS.

group_name must also use that existing field name whenever possible.


Example:

USER REQUESTED FIELDS:
품질, 원가, 고객체감

Document evidence:
"혹한에서 전개 실패 및 품질 클레임 위험"

Do NOT create:
"품질·안전 리스크"

Prefer:

suggestion_type = "existing_field"
target_field = "품질"
group_name = "품질"


Another example:

Document evidence:
"디자인 상품성을 유지할 수 있다."

If the user already requested "고객체감" and the evidence is
explicitly about customer-perceived product appeal,
it may be linked to:

suggestion_type = "existing_field"
target_field = "고객체감"

Only do this when the semantic connection is genuinely supported.
Do not force unrelated concepts into an existing field.


---------------------------------------------------------
B. CREATE A NEW FIELD ONLY FOR A DISTINCT DECISION AXIS
---------------------------------------------------------

Use:

suggestion_type = "new_field"

only when the information represents a meaningfully distinct
decision criterion that is not already covered by the requested fields.

Examples may include:

- 검증 부담
- 제조 복잡도
- 정비성
- 운영 복잡도

For new fields:

target_field = null

group_name must be a SHORT, CONSISTENT canonical field name.

Semantically equivalent suggested information MUST use the same
group_name.

For example, these should NOT become three separate groups:

- 제조 복잡도
- 생산 복잡성
- 공장 투입 관리 복잡도

If they describe the same decision axis in context,
use one shared group_name such as:

"제조 복잡도"


---------------------------------------------------------
C. SPLIT COMPOUND CONCEPTS WHEN APPROPRIATE
---------------------------------------------------------

Avoid unnecessarily creating combined criterion names such as:

- 원가·검증 부담
- 품질·안전 리스크
- 제조·운영 복잡성

If the evidence contains two genuinely separable concepts,
represent them separately when doing so preserves the meaning.

Example:

"부품 원가와 검증 항목이 증가한다."

If "원가" is already a requested field:

1)
suggestion_type = "existing_field"
target_field = "원가"
group_name = "원가"

and if validation burden is independently decision-relevant:

2)
suggestion_type = "new_field"
target_field = null
group_name = "검증 부담"

The same source evidence MAY support both items when appropriate.


---------------------------------------------------------
D. COMMON OR REFERENCE INFORMATION
---------------------------------------------------------

Use:

suggestion_type = "reference"

for information that is relevant to the decision but should not
become a candidate comparison criterion.

Typical examples:

- common validation conditions
- overall environmental conditions
- general requirements
- decision context
- test conditions applying to the whole decision

For reference information:

target_field = null

Use a short descriptive group_name such as:

"검증 조건"
"공통 요구사항"
"환경 조건"


---------------------------------------------------------
E. SCOPE STILL MATTERS
---------------------------------------------------------

All suggested information must still use the existing scope rules:

candidate
multi_candidate
global
context

Do not turn a technology, feature, general concept, risk,
or customer group into a new decision candidate.

Do not fill suggested_results with generic background information.


---------------------------------------------------------
F. GROUPING CONSISTENCY CHECK
---------------------------------------------------------

Before finishing suggested_results, review ALL suggested items together.

Ask:

1. Are multiple suggested_field names describing essentially
   the same decision axis?

2. Could an item reasonably belong to one of the user's
   requested fields instead of creating a new criterion?

3. Are compound criterion names unnecessarily mixing multiple
   concepts?

4. Are global/context items being incorrectly treated as
   candidate comparison criteria?

Normalize group_name consistently before returning the response.

The goal is a SMALL number of meaningful decision criteria,
not a large list of slightly different labels.


For every suggested item, explain briefly why it matters to the
engineering decision.


=========================================================
CORE RULE
=========================================================

Decision candidates are fixed by decision_candidates.

Evidence may refer to technologies, features, or common conditions,
but these MUST NOT create additional candidate names.

If evidence cannot be reliably mapped to an existing decision
candidate, preserve it as global or context instead of guessing.
"""


    user_input = f"""
SOURCE FILE:
{source_file}

USER REQUESTED FIELDS:
{fields_text}

DOCUMENT:
{document_text}
"""


    # =====================================================
    # AI 호출 함수
    # =====================================================

    def run_extraction_call(
        requested_fields,
        fixed_candidates=None,
        recovery_mode=False
    ):

        fields_for_call = ", ".join(
            requested_fields
        )


        # -------------------------------------------------
        # 후보가 이미 식별된 재검색이라면 후보를 고정
        # -------------------------------------------------

        candidate_lock_text = ""


        if fixed_candidates:

            candidate_lock_text = f"""
    FIXED DECISION CANDIDATES:

    {", ".join(fixed_candidates)}

    These candidates were already identified in the first pass.

    Do NOT create, rename, merge, or add any other decision candidate.
    All candidate or multi_candidate evidence must use only these names.
    """


        # -------------------------------------------------
        # 누락항목 재검색용 추가 지시
        # -------------------------------------------------

        recovery_text = ""


        if recovery_mode:

            recovery_text = """
    RECOVERY PASS:

    A previous extraction pass found no candidate-linked evidence
    for the requested fields listed below.

    Re-scan the ENTIRE document specifically for those fields.

    Pay particular attention to:
    - tables
    - alternative descriptions
    - advantages
    - disadvantages
    - risks
    - meeting comments
    - customer feedback
    - design notes
    - validation notes

    Do not assume that evidence exists.

    If explicit candidate-linked evidence truly does not exist,
    return no fabricated result.

    This recovery pass is intended to improve recall,
    not to force every field to have a value.
    """


        call_input = f"""
    SOURCE FILE:
    {source_file}

    USER REQUESTED FIELDS:
    {fields_for_call}

    {candidate_lock_text}

    {recovery_text}

    DOCUMENT:
    {document_text}
    """


        response = client.responses.parse(
            model=model,
            instructions=instructions,
            input=call_input,
            text_format=ExtractionResponse
        )


        parsed_response = (
            response.output_parsed
        )


        if parsed_response is None:

            raise RuntimeError(
                "AI 응답을 구조화 데이터로 변환하지 못했습니다."
            )


        return parsed_response


    # =====================================================
    # 1차 전체 추출
    # =====================================================

    parsed = run_extraction_call(
        requested_fields=selected_fields
    )


    # =====================================================
    # 최초 후보 목록 확정
    # =====================================================

    candidate_names = list(
        dict.fromkeys(
            candidate.strip()

            for candidate
            in parsed.decision_candidates

            if candidate.strip()
        )
    )


    candidate_set = set(
        candidate_names
    )


    # =====================================================
    # 요청항목 Coverage 검사
    # =====================================================

    candidate_linked_fields = set()


    for item in parsed.requested_results:

        if item.scope not in [
            "candidate",
            "multi_candidate"
        ]:

            continue


        valid_targets = [
            candidate

            for candidate
            in item.applies_to

            if candidate in candidate_set
        ]


        if valid_targets:

            candidate_linked_fields.add(
                item.field
            )


    missing_fields = [
        field

        for field
        in selected_fields

        if field
        not in candidate_linked_fields
    ]


    # =====================================================
    # 누락항목이 있으면 1회 집중 재검색
    # =====================================================

    all_requested_items = list(
        parsed.requested_results
    )

    all_suggested_items = list(
        parsed.suggested_results
    )


    if (
        missing_fields
        and candidate_names
    ):

        recovery_parsed = (
            run_extraction_call(
                requested_fields=missing_fields,
                fixed_candidates=candidate_names,
                recovery_mode=True
            )
        )


        all_requested_items.extend(
            recovery_parsed.requested_results
        )


        all_suggested_items.extend(
            recovery_parsed.suggested_results
        )


    # =====================================================
    # 중복 Evidence 제거
    # =====================================================

    unique_requested_items = []

    seen_requested = set()


    for item in all_requested_items:

        item_key = (
            item.scope,
            tuple(
                sorted(
                    item.applies_to
                )
            ),
            item.field,
            str(item.value),
            str(item.unit),
            item.page,
            item.evidence.strip()
        )


        if item_key in seen_requested:

            continue


        seen_requested.add(
            item_key
        )

        unique_requested_items.append(
            item
        )


    unique_suggested_items = []

    seen_suggested = set()


    for item in all_suggested_items:

        item_key = (
            item.scope,

            tuple(
                sorted(
                    item.applies_to
                )
            ),

            item.suggestion_type,

            str(
                item.target_field
            ),

            item.group_name,

            item.suggested_field,

            str(
                item.value
            ),

            str(
                item.unit
            ),

            item.page,

            item.evidence.strip()
        )


        if item_key in seen_suggested:

            continue


        seen_suggested.add(
            item_key
        )

        unique_suggested_items.append(
            item
        )

    # =====================================================
    # 후처리
    # =====================================================

    valid_pages = {
        page["page"]
        for page in pages
    }



    requested_results = []

    suggested_results = []


    # =====================================================
    # 요청 항목 처리
    # =====================================================

    for item in (
        unique_requested_items
    ):

        # 사용자가 요청하지 않은 field가 섞이면 제외
        if (
            item.field
            not in selected_fields
        ):

            continue


        # 페이지 상태 확인
        if (
            item.page
            not in valid_pages
        ):

            status = (
                "페이지 검토 필요"
            )


        elif (
            item.extraction_status
            == "conflict"
        ):

            status = (
                "충돌 검토"
            )


        else:

            status = (
                "검토 필요"
            )


        # ---------------------------------------------
        # 특정 후보 / 여러 후보에 연결되는 정보
        # ---------------------------------------------

        if item.scope in [
            "candidate",
            "multi_candidate"
        ]:

            valid_targets = [
                candidate

                for candidate
                in item.applies_to

                if candidate
                in candidate_set
            ]


            # AI가 후보 연결을 주장했지만
            # 실제 후보목록에 존재하지 않는 경우
            # 억지로 후보를 만들지 않고 공통정보로 보존
            if not valid_targets:

                suggested_results.append(
                    {
                        "candidate": "공통 정보",

                        "scope": "context",

                        "applies_to": [],

                        "suggested_field": (
                            item.field
                        ),

                        "value": (
                            item.value
                        ),

                        "unit": (
                            item.unit
                        ),

                        "data_type": (
                            item.data_type
                        ),

                        "source_file": (
                            source_file
                        ),

                        "page": (
                            item.page
                        ),

                        "evidence": (
                            item.evidence
                        ),

                        "reason": (
                            item.reason
                        ),

                        "suggestion_type": "reference",

                        "target_field": (
                            item.field
                        ),

                        "group_name": (
                            item.field
                        ),

                        "addable_to_candidate": False
                    }
                )

                continue


            # multi_candidate라면
            # 같은 근거를 해당 후보 각각에 연결
            for candidate in valid_targets:

                requested_results.append(
                    {
                        "candidate": (
                            candidate
                        ),

                        "field": (
                            item.field
                        ),

                        "value": (
                            item.value
                        ),

                        "unit": (
                            item.unit
                        ),

                        "original_candidate": (
                            candidate
                        ),

                        "original_field": (
                            item.field
                        ),

                        "original_value": (
                            item.value
                        ),

                        "original_unit": (
                            item.unit
                        ),

                        "data_type": (
                            item.data_type
                        ),

                        "source_file": (
                            source_file
                        ),

                        "page": (
                            item.page
                        ),

                        "evidence": (
                            item.evidence
                        ),
                        
                        "reason": (
                            item.reason
                        ),
                        
                        "scope": (
                            item.scope
                        ),

                        "applies_to": (
                            valid_targets
                        ),

                        "status": (
                            status
                        ),

                        "modified_by_user": (
                            False
                        )
                    }
                )


        # ---------------------------------------------
        # Global / Context 정보
        # ---------------------------------------------

        else:

            # 요청 항목이지만 후보별 비교값으로
            # 직접 넣을 수 없으므로
            # 공통 참고정보 영역으로 이동
            suggested_results.append(
                {
                    "candidate": "공통 정보",

                    "scope": (
                        item.scope
                    ),

                    "applies_to": [],

                    "suggested_field": (
                        item.field
                    ),

                    "value": (
                        item.value
                    ),

                    "unit": (
                        item.unit
                    ),

                    "data_type": (
                        item.data_type
                    ),

                    "source_file": (
                        source_file
                    ),

                    "page": (
                        item.page
                    ),

                    "evidence": (
                        item.evidence
                    ),

                    "reason": (
                        item.reason
                    ),

                    "suggestion_type": "reference",

                    "target_field": (
                        item.field
                    ),

                    "group_name": (
                        item.field
                    ),

                    "addable_to_candidate": False
                }
            )


    # =====================================================
    # 추가 발견 정보 처리
    # =====================================================

    for item in (
        unique_suggested_items
    ):

        # 페이지 검증
        if (
            item.page
            in valid_pages
        ):

            suggestion_page = (
                item.page
            )


        else:

            suggestion_page = (
                item.page
            )


        # ---------------------------------------------
        # 후보에 연결 가능한 추가정보
        # ---------------------------------------------

        if item.scope in [
            "candidate",
            "multi_candidate"
        ]:

            valid_targets = [
                candidate

                for candidate
                in item.applies_to

                if candidate
                in candidate_set
            ]


            if valid_targets:

                # 후보별로 분리해서 저장
                for candidate in (
                    valid_targets
                ):

                    suggested_results.append(
                        {
                            "candidate": (
                                candidate
                            ),

                            "scope": (
                                item.scope
                            ),

                            "applies_to": (
                                valid_targets
                            ),

                            "suggested_field": (
                                item.suggested_field
                            ),

                            "value": (
                                item.value
                            ),

                            "unit": (
                                item.unit
                            ),

                            "data_type": (
                                item.data_type
                            ),

                            "source_file": (
                                source_file
                            ),

                            "page": (
                                suggestion_page
                            ),

                            "evidence": (
                                item.evidence
                            ),

                            "reason": (
                                item.reason
                            ),

                            "suggestion_type": (
                                item.suggestion_type
                            ),

                            "target_field": (
                                item.target_field
                            ),

                            "group_name": (
                                item.group_name
                            ),

                            "addable_to_candidate": (
                                True
                            )
                        }
                    )


                continue


        # ---------------------------------------------
        # 후보에 직접 연결할 수 없는 추가정보
        # ---------------------------------------------

        suggested_results.append(
            {
                "candidate": (
                    "공통 정보"
                ),

                "scope": (
                    item.scope
                ),

                "applies_to": [],

                "suggested_field": (
                    item.suggested_field
                ),

                "value": (
                    item.value
                ),

                "unit": (
                    item.unit
                ),

                "data_type": (
                    item.data_type
                ),

                "source_file": (
                    source_file
                ),

                "page": (
                    suggestion_page
                ),

                "evidence": (
                    item.evidence
                ),

                "reason": (
                    item.reason
                ),

                "suggestion_type": (
                    item.suggestion_type
                ),

                "target_field": (
                    item.target_field
                ),

                "group_name": (
                    item.group_name
                ),

                "addable_to_candidate": (
                    False
                )
            }
        )

    # =====================================================
    # 추가 발견 정보 표시 순서 정리
    # =====================================================

    suggestion_type_order = {
        "existing_field": 0,
        "new_field": 1,
        "reference": 2
    }


    candidate_order = {
        candidate: index

        for index, candidate
        in enumerate(
            candidate_names
        )
    }


    suggested_results = sorted(
        suggested_results,

        key=lambda result: (
            suggestion_type_order.get(
                result.get(
                    "suggestion_type"
                ),
                99
            ),

            str(
                result.get(
                    "target_field"
                )
                or result.get(
                    "group_name"
                )
                or ""
            ),

            candidate_order.get(
                result.get(
                    "candidate"
                ),
                999
            ),

            result.get(
                "page",
                999
            )
        )
    )

    return (
        requested_results,
        suggested_results
    )