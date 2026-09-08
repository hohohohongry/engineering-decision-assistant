from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel


load_dotenv()

client = OpenAI()


# =========================================================
# Structured Output Schema
# =========================================================

class RecommendedCriterion(BaseModel):

    field: str

    reason: str

    pages: list[int]


class CriterionRecommendationResponse(BaseModel):

    recommended_fields: list[
        RecommendedCriterion
    ]


# =========================================================
# PDF 기반 추출항목 추천
# =========================================================

def recommend_extraction_fields(
    pages,
    source_file,
    model="gpt-5.6-luna"
):

    if not pages:

        raise ValueError(
            "분석할 PDF 페이지가 없습니다."
        )


    # =====================================================
    # 문서 텍스트 구성
    # =====================================================

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


    # =====================================================
    # AI 지시
    # =====================================================

    instructions = """
You are an engineering decision-criterion discovery engine.

The document contains an engineering decision problem with
multiple alternatives, design concepts, suppliers, plans, or
development options.

Your task is NOT to select the best alternative.

Your task is to recommend which engineering criteria the user
should extract in order to compare the alternatives properly.


=========================================================
CORE QUESTION
=========================================================

Ask:

"What separate questions would an engineer need to evaluate
to compare the alternatives described in this document?"


Examples of valid decision axes may include:

- 조립성
- 검출성
- 품질
- 신뢰성
- 원가
- 개발기간
- 정비성
- 고객체감
- 디자인 영향
- 패키지 / 간섭
- 제조 복잡도
- 검증 부담

These are examples only.

Do NOT force any example into the result unless the document
actually supports it.


=========================================================
WHAT SHOULD BECOME A RECOMMENDED FIELD
=========================================================

Recommend a criterion when at least one of the following is true:

1. The document explicitly compares alternatives on that aspect.

2. Different alternatives create meaningfully different
   advantages, disadvantages, risks, or burdens on that aspect.

3. The document repeatedly treats that aspect as important to
   the engineering decision.

4. Ignoring that aspect would remove a meaningful dimension
   of the decision.


A useful test is:

"Could the engineer reasonably ask:
'How do the alternatives compare on this criterion?'"

If YES, it may be a recommended field.


=========================================================
WHAT SHOULD NOT BECOME A FIELD
=========================================================

Do NOT recommend:

- candidate names
- component names
- technologies by themselves
- individual symptoms
- one-off facts
- exact solutions
- generic background information
- common environmental conditions
- broad statements that do not distinguish or evaluate options

For example:

"커넥터 불완전 체결"

is usually a specific failure mode, not necessarily a criterion.

A broader engineering question such as:

"검출성"
"조립성"
"품질"

may be the proper criterion depending on the document.


=========================================================
AVOID DUPLICATED CRITERIA
=========================================================

Use a SMALL number of meaningful criteria.

Do not create several fields that represent nearly the same
engineering question.

For example, do not separately recommend:

- 생산 작업성
- 조립 작업성
- 작업 편의성

if they represent the same decision axis.

Normalize them to a short canonical name such as:

"조립성"


Likewise, avoid unnecessary compound fields such as:

"원가·개발 부담"

when the two concepts should be evaluated separately.


=========================================================
FIELD NAMING
=========================================================

field must be:

- short
- clear
- reusable across candidates
- preferably a Korean engineering noun or noun phrase

Good:

조립성
검출성
품질
원가
디자인 영향
패키지 간섭

Bad:

B안 하네스 70mm 증가
커넥터 문제
서비스 홀을 키워야 함


=========================================================
REASON
=========================================================

For each recommended field, explain briefly why the document
shows that this is an important comparison axis.

Ground the reason only in the supplied document.

Do not invent candidate effects.


=========================================================
PAGES
=========================================================

Return the page numbers that most clearly support why the
criterion matters.

Only use page numbers that exist in the document.


=========================================================
NUMBER OF CRITERIA
=========================================================

Prefer approximately 4 to 8 strong criteria.

Fewer is acceptable if the document supports fewer.

Do not add weak criteria merely to reach a target count.


=========================================================
FINAL RULE
=========================================================

These are RECOMMENDATIONS only.

The user will decide which criteria to actually use.
"""


    user_input = f"""
SOURCE FILE:
{source_file}

DOCUMENT:
{document_text}
"""


    # =====================================================
    # AI 호출
    # =====================================================

    response = client.responses.parse(
        model=model,
        instructions=instructions,
        input=user_input,
        text_format=(
            CriterionRecommendationResponse
        )
    )


    parsed = (
        response.output_parsed
    )


    if parsed is None:

        raise RuntimeError(
            "추출항목 추천 결과를 구조화하지 못했습니다."
        )


    # =====================================================
    # 후처리
    # =====================================================

    valid_pages = {
        page["page"]
        for page in pages
    }


    recommendations = []

    seen_fields = set()


    for item in (
        parsed.recommended_fields
    ):

        field = (
            item.field.strip()
        )


        if not field:

            continue


        normalized_field = (
            field.casefold()
        )


        if (
            normalized_field
            in seen_fields
        ):

            continue


        seen_fields.add(
            normalized_field
        )


        supported_pages = [
            page

            for page
            in item.pages

            if page
            in valid_pages
        ]


        recommendations.append(
            {
                "field": field,

                "reason": (
                    item.reason.strip()
                ),

                "pages": (
                    supported_pages
                )
            }
        )


    return recommendations