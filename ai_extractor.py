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

# =========================================================
# Suggested Evidence 2차 검수 Schema
# =========================================================

class SuggestedEvidenceReviewItem(BaseModel):

    # 어떤 원본 suggested item을 검수한 결과인지
    item_id: int

    suggestion_type: Literal[
        "existing_field",
        "new_field",
        "reference"
    ]

    # existing_field일 때만 기존 사용자 항목명
    target_field: str | None

    # 최종적으로 UI에서 묶어 보여줄 이름
    group_name: str


class SuggestedEvidenceReviewResponse(BaseModel):

    reviewed_items: list[
        SuggestedEvidenceReviewItem
    ]

# =========================================================
# Requested Evidence 2차 검수 Schema
# =========================================================

class RequestedEvidenceReviewItem(BaseModel):

    item_id: int

    action: Literal[
        "keep",
        "rewrite",
        "remove"
    ]

    corrected_value: Union[
        float,
        str,
        None
    ]

    corrected_unit: str | None

    corrected_data_type: Literal[
        "numeric",
        "qualitative",
        "ranking"
    ] | None

    reason: str


class RequestedEvidenceReviewResponse(BaseModel):

    reviewed_items: list[
        RequestedEvidenceReviewItem
    ]

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
# Suggested Evidence 2차 의미 검수
# =========================================================

def refine_suggested_evidence(
    suggested_items,
    selected_fields,
    model="gpt-5.6-luna"
):
    """
    1차 AI가 찾은 추가정보를 다시 검토해

    - 기존 항목에 연결할 정보
    - 진짜 새로운 비교항목
    - 참고정보

    로 한 번 더 정리한다.

    원본 value / evidence / scope는 변경하지 않는다.
    """

    if not suggested_items:

        return suggested_items


    # =====================================================
    # 사용자 기존 판단항목
    # =====================================================

    requested_fields_text = ", ".join(
        selected_fields
    )


    # =====================================================
    # 검수할 추가정보 목록 생성
    # =====================================================

    review_blocks = []


    for item_id, item in enumerate(
        suggested_items
    ):

        applies_to_text = (
            ", ".join(
                item.applies_to
            )
            if item.applies_to
            else "-"
        )


        review_blocks.append(
            f"""
[ITEM {item_id}]

Current suggested field:
{item.suggested_field}

Current classification:
{item.suggestion_type}

Current target field:
{item.target_field}

Current group name:
{item.group_name}

Scope:
{item.scope}

Applies to:
{applies_to_text}

Value:
{item.value}

Reason:
{item.reason}

Source evidence:
{item.evidence}
"""
        )


    review_text = "\n".join(
        review_blocks
    )


    # =====================================================
    # 2차 검수 지시
    # =====================================================

    review_instructions = """
You are reviewing engineering information that was already
extracted from a document.

Do NOT extract new information.

Do NOT modify:
- the source evidence
- the engineering value
- candidate applicability
- scope

Your only task is to review how each suggested item should be
classified for an engineering decision-support interface.


=========================================================
AVAILABLE CLASSIFICATIONS
=========================================================

1. existing_field

Use this when the information can reasonably be evaluated
under one of the USER REQUESTED FIELDS.

Different wording does NOT mean a different criterion.

Examples of information that may belong to an existing field:

- a more specific aspect of that field
- a benefit within that field
- a disadvantage within that field
- a risk within that field
- a supporting fact for that field

If existing_field:

target_field MUST exactly match one USER REQUESTED FIELD.

group_name MUST equal target_field.


=========================================================

2. new_field

Use this ONLY when the information represents a genuinely
separate engineering evaluation axis that is not reasonably
covered by any USER REQUESTED FIELD.

Ask:

"Would an engineer need to evaluate this as a separate question
even after considering all existing requested fields?"

If the answer is NO, use existing_field instead.

If new_field:

target_field = null

group_name must be a short, clear canonical criterion name.


=========================================================

3. reference

Use this when the information is useful decision context but
should not become a candidate comparison criterion.

Examples:

- common test conditions
- environmental conditions
- general requirements
- shared constraints
- background information

If reference:

target_field = null


=========================================================
IMPORTANT REVIEW RULES
=========================================================

Review ALL items together.

Prefer a small number of meaningful criteria.

Do NOT create a new criterion merely because the wording differs
from an existing requested field.

If several suggested items describe the same new decision axis,
use the SAME group_name.

If an item's current classification is already appropriate,
keep it.

Do not force unrelated information into an existing field.

Return exactly ONE review result for each input ITEM.

Preserve the original item_id exactly.
"""


    review_input = f"""
USER REQUESTED FIELDS:

{requested_fields_text}


SUGGESTED ITEMS TO REVIEW:

{review_text}
"""


    # =====================================================
    # AI 호출
    # =====================================================

    try:

        response = client.responses.parse(
            model=model,
            instructions=review_instructions,
            input=review_input,
            text_format=SuggestedEvidenceReviewResponse
        )


        parsed_review = (
            response.output_parsed
        )


        if parsed_review is None:

            return suggested_items


    except Exception:

        # 2차 검수에 실패하더라도
        # 기존 추출 결과는 그대로 사용할 수 있게 함
        return suggested_items


    # =====================================================
    # AI 검수결과 조회
    # =====================================================

    review_lookup = {
        review.item_id: review

        for review
        in parsed_review.reviewed_items
    }


    # 사용자 항목 실제 표기 보존
    selected_field_lookup = {
        str(field).strip().casefold(): field

        for field
        in selected_fields
    }


    # =====================================================
    # 기존 SuggestedEvidence에 검수 결과 반영
    # =====================================================

    for item_id, item in enumerate(
        suggested_items
    ):

        review = (
            review_lookup.get(
                item_id
            )
        )


        # AI가 특정 item을 누락했다면
        # 기존 분류 그대로 유지
        if review is None:

            continue


        # -------------------------------------------------
        # global / context는 비교항목으로 만들지 않음
        # -------------------------------------------------

        if item.scope in [
            "global",
            "context"
        ]:

            item.suggestion_type = (
                "reference"
            )

            item.target_field = None

            if review.group_name.strip():

                item.group_name = (
                    review.group_name.strip()
                )

            continue


        # -------------------------------------------------
        # 기존 항목으로 연결
        # -------------------------------------------------

        if (
            review.suggestion_type
            == "existing_field"
        ):

            if not review.target_field:

                continue


            canonical_field = (
                selected_field_lookup.get(
                    str(
                        review.target_field
                    )
                    .strip()
                    .casefold()
                )
            )


            # 사용자가 실제로 선택한 항목만 허용
            if canonical_field is None:

                continue


            item.suggestion_type = (
                "existing_field"
            )

            item.target_field = (
                canonical_field
            )

            item.group_name = (
                canonical_field
            )


        # -------------------------------------------------
        # 새로운 비교 항목
        # -------------------------------------------------

        elif (
            review.suggestion_type
            == "new_field"
        ):

            item.suggestion_type = (
                "new_field"
            )

            item.target_field = None


            if review.group_name.strip():

                item.group_name = (
                    review.group_name.strip()
                )


        # -------------------------------------------------
        # 참고정보
        # -------------------------------------------------

        elif (
            review.suggestion_type
            == "reference"
        ):

            item.suggestion_type = (
                "reference"
            )

            item.target_field = None


            if review.group_name.strip():

                item.group_name = (
                    review.group_name.strip()
                )


    return suggested_items

# =========================================================
# Requested Evidence 2차 의미 검수
# =========================================================

def refine_requested_evidence(
    requested_items,
    selected_fields,
    model="gpt-5.6-luna"
):
    """
    1차 추출 결과의 field와 value가
    실제로 의미상 직접 연결되는지 다시 확인한다.

    특히 주변에 존재하는 숫자를
    잘못된 판단항목의 값으로 사용하는 오류를 방지한다.

    원본 evidence / page / candidate / scope는 변경하지 않는다.
    """

    if not requested_items:

        return requested_items


    # =====================================================
    # 검수 대상 구성
    # =====================================================

    review_blocks = []


    for item_id, item in enumerate(
        requested_items
    ):

        applies_to_text = (
            ", ".join(
                item.applies_to
            )
            if item.applies_to
            else "-"
        )


        review_blocks.append(
            f"""
[ITEM {item_id}]

Requested field:
{item.field}

Current value:
{item.value}

Current unit:
{item.unit}

Current data type:
{item.data_type}

Scope:
{item.scope}

Applies to:
{applies_to_text}

Source evidence:
{item.evidence}

Current reason:
{item.reason}
"""
        )


    review_text = "\n".join(
        review_blocks
    )


    # =====================================================
    # AI 검수 지시
    # =====================================================

    review_instructions = """
You are validating engineering evidence that has already
been extracted from a document.

Do NOT search for new evidence.

Do NOT change:

- requested field
- candidate applicability
- scope
- page
- source evidence

Your only task is to verify whether the CURRENT VALUE
actually answers the REQUESTED FIELD.


=========================================================
CORE TEST
=========================================================

For every item ask:

"Does this value directly describe or measure the requested field?"

Do NOT accept a value merely because it appears in the same
sentence, paragraph, table, or design option.


=========================================================
NUMERIC SEMANTIC ALIGNMENT
=========================================================

A numeric value may be used as numeric evidence ONLY when the
number itself directly measures the requested field.

Do NOT borrow a nearby number that measures a different
engineering parameter.


Example:

Requested field:
패키지 간섭

Source evidence:
"하네스 길이가 약 70 mm 증가하며,
스포일러 내부 간섭 재검토가 필요하다."

Incorrect:

value = 70
unit = "mm"
data_type = "numeric"

because 70 mm measures harness length increase,
NOT package interference itself.

Correct:

value = "스포일러 내부 간섭 재검토 필요"
unit = null
data_type = "qualitative"


However, if the requested field were:

하네스 길이 증가

then:

value = 70
unit = "mm"
data_type = "numeric"

would be valid.


Another example:

Requested field:
원가

Source evidence:
"부품 수가 3개 증가하며 원가 증가가 우려된다."

Do NOT use:

value = 3

as the cost value.

The number 3 measures part-count increase,
not cost.

Use the explicit cost-related meaning instead:

value = "원가 증가 우려"
unit = null
data_type = "qualitative"


=========================================================
ACTIONS
=========================================================

1. keep

Use when the current value directly and correctly answers
the requested field.

For keep:

corrected_value = null
corrected_unit = null
corrected_data_type = null


=========================================================

2. rewrite

Use when the current value is not the best representation
of the requested field, BUT the SAME supplied source evidence
clearly contains another explicit fact that directly answers it.

The rewritten value must be grounded ONLY in the supplied
source evidence.

Do NOT introduce engineering inference.

Do NOT use outside knowledge.

For rewrite:

- corrected_value must contain the corrected value
- corrected_unit must be the correct unit or null
- corrected_data_type must be specified


=========================================================

3. remove

Use when the supplied source evidence does NOT actually support
the requested field.

Use remove rather than forcing a neighboring fact into
the requested field.


=========================================================
IMPORTANT
=========================================================

Do not change one requested field into another field.

For example:

If an item is requested as "패키지 간섭",
do NOT rename it to "하네스 길이".

The field belongs to the user's extraction request.

You are only validating whether the evidence contains a valid
value for that field.


Do not convert qualitative statements into numeric values
unless the number directly measures the requested concept.

Do not infer causal relationships or performance effects.

Return exactly ONE review result for every input ITEM.

Preserve item_id exactly.
"""


    review_input = f"""
USER REQUESTED FIELDS:

{", ".join(selected_fields)}


EXTRACTED ITEMS TO REVIEW:

{review_text}
"""


    # =====================================================
    # AI 호출
    # =====================================================

    try:

        response = client.responses.parse(
            model=model,
            instructions=review_instructions,
            input=review_input,
            text_format=(
                RequestedEvidenceReviewResponse
            )
        )


        parsed_review = (
            response.output_parsed
        )


        if parsed_review is None:

            return requested_items


    except Exception:

        # 검수 실패 시 기존 추출 결과는 유지
        return requested_items


    # =====================================================
    # 검수 결과 조회
    # =====================================================

    review_lookup = {
        review.item_id: review

        for review
        in parsed_review.reviewed_items
    }


    refined_items = []


    # =====================================================
    # 검수 결과 적용
    # =====================================================

    for item_id, item in enumerate(
        requested_items
    ):

        review = (
            review_lookup.get(
                item_id
            )
        )


        # 검수결과 누락 시 기존 결과 유지
        if review is None:

            refined_items.append(
                item
            )

            continue


        # -------------------------------------------------
        # 삭제
        # -------------------------------------------------

        if review.action == "remove":

            continue


        # -------------------------------------------------
        # 같은 원문 안의 더 정확한 값으로 수정
        # -------------------------------------------------

        if review.action == "rewrite":

            if (
                review.corrected_value
                is None

                or

                review.corrected_data_type
                is None
            ):

                # 수정값이 불완전하면
                # 기존 결과를 함부로 버리지 않음
                refined_items.append(
                    item
                )

                continue


            item.value = (
                review.corrected_value
            )


            item.unit = (
                review.corrected_unit
            )


            item.data_type = (
                review.corrected_data_type
            )


        # keep이면 아무것도 수정하지 않음
        refined_items.append(
            item
        )


    return refined_items

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

If explicit evidence for a candidate-field combination does not exist,
OMIT that combination entirely from requested_results.

Do NOT create placeholder results such as:

- "정보가 명시되지 않음"
- "관련 정보 없음"
- "확인할 수 없음"
- "자료에 제시되지 않음"
- "not specified"
- "not provided"
- "no information available"

Absence of evidence is NOT an evidence result.

For numeric information:

value = number only
unit = unit only

Example:

3개월
→ value = 3
→ unit = "개월"

IMPORTANT NUMERIC SEMANTIC RULE:

A numeric value may be assigned to a requested field ONLY when
that number directly measures the meaning of that requested field.

Do NOT use a nearby number simply because it appears in the same
sentence or paragraph.

Example:

Requested field:
패키지 간섭

Evidence:
"하네스 길이가 약 70 mm 증가하며
스포일러 내부 간섭 재검토가 필요하다."

Incorrect:

value = 70
unit = "mm"

because 70 mm describes harness length,
not package interference.

Correct:

value = "스포일러 내부 간섭 재검토 필요"
unit = null
data_type = "qualitative"


If the requested field were instead:

하네스 길이 증가

then:

value = 70
unit = "mm"
data_type = "numeric"

would be correct.


When a passage contains both:

- a numeric engineering parameter
- and a qualitative effect on another requested criterion

keep their meanings separate.

Never transfer the number from one concept to another.

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
A. FIRST CHECK WHETHER THE INFORMATION IS ALREADY COVERED
---------------------------------------------------------

Before creating ANY new field, compare the semantic meaning of the
information with ALL USER REQUESTED FIELDS.

Different wording does NOT mean a different decision criterion.

A suggested item must be classified as:

suggestion_type = "existing_field"

when the information is reasonably part of, evidence for, or a
more specific aspect of an existing user-requested field.


This includes information that describes:

- a specific aspect of the existing field
- an advantage or disadvantage within the existing field
- a risk related to the existing field
- a consequence related to the existing field
- a cause that explains the existing field
- a concrete example or supporting fact for the existing field


Use this test:

"If an engineer were evaluating the existing requested field,
could this information reasonably be used as evidence for that
evaluation without creating a separate evaluation question?"

If YES:

suggestion_type = "existing_field"

target_field must exactly match the BEST matching
USER REQUESTED FIELD.

group_name must use that same existing field name.

Do NOT create a new criterion only because the document uses
a different label.


Example:

USER REQUESTED FIELD:
고객체감

Document evidence:
"미래감과 고급감이 높고 전기차다운 인상을 줄 수 있다."

This information describes how the customer may perceive
the product.

Prefer:

suggestion_type = "existing_field"
target_field = "고객체감"
group_name = "고객체감"

Do NOT create a separate field such as:
"고객가치"
"디자인 이미지"
"상품성"

when those labels are only describing a specific aspect
of the already-requested 고객체감 criterion.


Another example:

USER REQUESTED FIELD:
품질

Document evidence:
"혹한에서 전개 불량이 발생하고 품질 클레임 위험이 있다."

Prefer:

suggestion_type = "existing_field"
target_field = "품질"
group_name = "품질"

Do NOT create:
"품질 리스크"
"품질·안전 리스크"
"클레임 위험"

as separate criteria if they are simply describing
the quality-related evidence.


IMPORTANT:

If one evidence passage contains multiple DISTINCT and SEPARABLE
facts that belong to different USER REQUESTED FIELDS,
split those facts into separate suggested_results.

The same source evidence MAY therefore appear more than once,
but each output item must contain only the part of the meaning
that belongs to its target_field.

Example:

USER REQUESTED FIELDS:
품질, 고객체감

Document evidence:
"디자인 상품성을 유지하면서 품질·안전 리스크를 줄일 수 있다."

Do NOT create:
"디자인 상품성"

Do NOT force the entire sentence into only one existing field.

Instead, separate the meanings:

1)
suggestion_type = "existing_field"
target_field = "고객체감"
group_name = "고객체감"
value = "디자인 상품성 유지"

2)
suggestion_type = "existing_field"
target_field = "품질"
group_name = "품질"
value = "품질·안전 리스크 감소"

Both items may use the same page and source evidence.

However, do NOT duplicate the same meaning across several fields.
Split only when the source clearly contains genuinely different
decision-relevant facts.


---------------------------------------------------------
B. CREATE A NEW FIELD ONLY FOR A TRULY DISTINCT DECISION AXIS
---------------------------------------------------------

Use:

suggestion_type = "new_field"

ONLY when the information cannot reasonably be evaluated
under any existing user-requested field.

A new field should represent a genuinely separate question
the engineer would need to evaluate.


Use this test:

"Would the engineer need to ask a separate evaluation question
for this information, even after considering all existing
requested fields?"

If NO:
connect it to an existing field.

If YES:
a new field may be created.


Example:

USER REQUESTED FIELDS:
품질, 원가, 고객체감

Document evidence:
"공정 단계와 부품번호 관리가 증가해 생산 운영이 복잡해진다."

This is not simply another expression of 품질, 원가,
or 고객체감.

It represents a separate evaluation question:

"How complex is this option to manufacture or operate?"

Therefore:

suggestion_type = "new_field"
target_field = null
group_name = "제조 복잡도"


Other genuinely distinct axes may include, depending on
the actual document context:

- 검증 부담
- 제조 복잡도
- 정비성
- 운영 복잡도

These are examples only.

Do NOT force these fields to exist when the document
does not support them.


For every new_field, verify all three conditions:

1. Its meaning is not already covered by a user-requested field.

2. It would require a genuinely separate engineering evaluation.

3. Removing this new criterion would cause a meaningful
   decision dimension to be lost.

If any of these conditions is not satisfied,
prefer existing_field instead.


For new fields:

target_field = null

group_name must be a SHORT, CONSISTENT canonical field name.

Semantically equivalent suggested information MUST use
the same group_name.

For example, these should NOT become separate groups:

- 제조 복잡도
- 생산 복잡성
- 공장 투입 관리 복잡도

If they represent the same decision axis in context,
normalize them to one shared group_name such as:

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
    # 요청항목 2차 의미 검수
    # =====================================================
    #
    # 추출된 값이 해당 판단항목을
    # 실제로 직접 설명하는지 다시 확인한다.
    #
    # 예:
    # 패키지 간섭 = 70 mm
    # → 70 mm가 실제로 하네스 길이 증가량이라면
    #   패키지 간섭의 숫자값으로 사용하지 않는다.
    # =====================================================

    all_requested_items = (
        refine_requested_evidence(
            requested_items=(
                all_requested_items
            ),
            selected_fields=(
                selected_fields
            ),
            model=model
        )
    )

    # =====================================================
    # 추가 발견 정보 2차 의미 검수
    # =====================================================
    #
    # 1차 AI가 찾은 추가정보를 다시 한 번 모아서 보고,
    # 기존 항목 / 신규 항목 / 참고정보 분류를 정리한다.
    # =====================================================

    all_suggested_items = (
        refine_suggested_evidence(
            suggested_items=(
                all_suggested_items
            ),
            selected_fields=(
                selected_fields
            ),
            model=model
        )
    )

    # =====================================================
    # 중복 Evidence 제거
    # =====================================================

    unique_requested_items = []

    seen_requested = set()


    for item in all_requested_items:

        # -------------------------------------------------
        # 실제 데이터가 아니라
        # "정보가 없다"는 설명만 반환된 경우 제외
        # -------------------------------------------------

        value_text = (
            str(item.value)
            .strip()
            .casefold()
        )


        missing_value_patterns = [
            "정보가 명시되지 않",
            "정보가 제공되지 않",
            "관련 정보가 없",
            "관련 정보 없음",
            "명시적 정보가 없",
            "명시적 정보 없음",
            "확인되지 않음",
            "확인할 수 없음",
            "자료에 제시되지 않",
            "정보를 찾을 수 없",
            "not specified",
            "not provided",
            "no information",
            "information not found",
            "not available"
        ]


        if any(
            pattern in value_text

            for pattern
            in missing_value_patterns
        ):

            continue

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

    # =====================================================
    # 기존 요청항목 이름 조회용
    # =====================================================
    #
    # AI가 실수로 기존 항목과 똑같은 이름을
    # new_field로 반환하는 경우를 Python에서 보정한다.
    #
    # 예:
    # USER REQUESTED FIELD = "품질"
    # AI new_field = "품질"
    # → existing_field / target_field="품질"
    # =====================================================

    selected_field_lookup = {
        str(field).strip().casefold(): field

        for field
        in selected_fields
    }

    for item in all_suggested_items:

        # -------------------------------------------------
        # AI가 기존 요청항목과 정확히 같은 이름을
        # 신규 항목으로 잘못 분류한 경우 자동 보정
        # -------------------------------------------------

        if item.suggestion_type == "new_field":

            matched_existing_field = None


            # 대표 그룹명과 AI가 만든 원래 항목명을
            # 둘 다 기존 요청항목과 비교
            for possible_name in [
                item.group_name,
                item.suggested_field
            ]:

                if not possible_name:

                    continue


                canonical_field = (
                    selected_field_lookup.get(
                        str(
                            possible_name
                        ).strip().casefold()
                    )
                )


                if canonical_field:

                    matched_existing_field = (
                        canonical_field
                    )

                    break


            if matched_existing_field:

                item.suggestion_type = (
                    "existing_field"
                )

                item.target_field = (
                    matched_existing_field
                )

                item.group_name = (
                    matched_existing_field
                )


        # -------------------------------------------------
        # existing_field인데 기존 항목명의 대소문자나
        # 공백이 달라진 경우도 실제 사용자 항목명으로 통일
        # -------------------------------------------------

        elif (
            item.suggestion_type
            == "existing_field"

            and

            item.target_field
        ):

            canonical_field = (
                selected_field_lookup.get(
                    str(
                        item.target_field
                    ).strip().casefold()
                )
            )


            if canonical_field:

                item.target_field = (
                    canonical_field
                )

                item.group_name = (
                    canonical_field
                )

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
        suggested_results,
        candidate_names
    )