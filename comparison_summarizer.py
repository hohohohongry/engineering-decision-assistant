from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel


load_dotenv()

client = OpenAI()


# =========================================================
# Structured Output Schema
# =========================================================

class ComparisonSummaryItem(BaseModel):
    """
    후보 비교표의 한 셀에 표시할
    짧은 핵심 포인트
    """

    candidate: str

    criterion: str

    points: list[str]


class ComparisonSummaryResponse(BaseModel):
    """
    여러 후보 / 판단항목의
    비교표용 요약 결과
    """

    summaries: list[
        ComparisonSummaryItem
    ]


# =========================================================
# 비교표용 문장 요약
# =========================================================

def summarize_comparison_values(
    comparison_items,
    model="gpt-5.6-luna"
):
    """
    확정된 문장형 정보를
    후보 비교표에서 읽기 쉬운 짧은 포인트로 변환한다.

    원본 value / evidence는 수정하지 않는다.

    Parameters
    ----------
    comparison_items : list[dict]

    예상 형태:
    [
        {
            "candidate": "A안",
            "criterion": "품질",
            "value": "흑한 전개 불량 및 품질 클레임 위험이 크다."
        },
        ...
    ]

    Returns
    -------
    list[dict]

    예:
    [
        {
            "candidate": "A안",
            "criterion": "품질",
            "points": [
                "흑한 전개 불량",
                "품질 클레임 위험"
            ]
        }
    ]
    """

    if not comparison_items:

        return []


    # =====================================================
    # AI에게 전달할 데이터 구성
    # =====================================================

    item_blocks = []


    for index, item in enumerate(
        comparison_items,
        start=1
    ):

        candidate = str(
            item.get(
                "candidate",
                ""
            )
        ).strip()


        criterion = str(
            item.get(
                "criterion",
                ""
            )
        ).strip()


        value = str(
            item.get(
                "value",
                ""
            )
        ).strip()


        item_blocks.append(
            f"""
[ITEM {index}]
Candidate: {candidate}
Criterion: {criterion}
Original text:
{value}
"""
        )


    comparison_text = "\n".join(
        item_blocks
    )


    # =====================================================
    # AI Instruction
    # =====================================================

    instructions = """
You convert engineering comparison text into compact table shorthand.

The output will be displayed directly inside cells of an engineering
candidate comparison table.

The goal is NOT to summarize the text as another sentence.

The goal is to transform the original meaning into short,
scan-friendly comparison points.

You do NOT:
- make the final engineering decision
- rank candidates
- invent engineering facts
- add information not supported by the original text
- explain why something is good or bad unless the original text says so

For every input item:
- preserve the exact candidate name
- preserve the exact criterion name


=========================================================
CORE OUTPUT STYLE
=========================================================

Each point must look like a compact comparison-table expression.

Prefer:

"중량 +1.2 kg"
"최대 응력 -18%"
"원가 증가"
"검증 범위 확대"
"정비성 우수"
"소음 증가"
"미래감·고급감 ↑"

Avoid:

"중량이 1.2 kg 증가한다."
"최대 응력이 18% 감소한다."
"디자인 상품성이 유지될 수 있다."
"정비성이 좋은 편이다."

Do NOT simply rewrite the original sentence with a bullet in front.


=========================================================
RULES
=========================================================

1. Return 1 to 3 points for each input item.

2. Each point must contain only ONE main comparison fact.

3. Use short phrases or noun phrases whenever possible.

4. Avoid complete explanatory sentences.

5. Remove sentence endings and unnecessary wording such as:
   "~한다"
   "~이다"
   "~할 수 있다"
   "~것으로 판단된다"
   "~영향을 미친다"
   when the same meaning can be expressed more compactly.

6. Preserve all important:
   - numbers
   - units
   - percentages
   - limits
   - increases
   - decreases
   - directional changes

7. When the original text explicitly states a direction,
   compact symbols may be used.

   Examples:
   증가 → ↑ or +
   감소 → ↓ or -
   향상 → ↑
   저하 → ↓

8. Do NOT add a direction symbol if the original text
   does not clearly support that direction.

9. Split different facts into separate points.

10. Remove duplicated or nearly duplicated meaning.

11. Keep technically important qualifiers when removing them
    would change the engineering meaning.

12. Do not preserve unnecessary subjects when they are obvious
    from the criterion or context.

13. Do not repeat the criterion name unless necessary
    to understand the point.

14. Do not force every item to have 3 points.
    Use the minimum number of points needed.

15. Interpret the meaning semantically.
    Do not depend on document-specific keywords,
    engineering domains, or fixed terminology.

16. The same rules must work for mechanical, thermal,
    electrical, manufacturing, quality, cost, validation,
    design, and other engineering documents.


=========================================================
GOOD / BAD EXAMPLES
=========================================================

Original:
"부품 원가와 검증 항목이 증가하고,
디자인센터와 세부 형상 협의가 필요하다."

BAD:
- 부품 원가와 검증 항목이 증가한다.
- 디자인센터와 세부 형상 협의가 필요하다.

GOOD:
- 부품 원가 증가
- 검증 항목 증가
- 세부 형상 협의 필요


Original:
"브래킷 변경으로 중량은 1.2 kg 증가하지만
최대 응력은 18% 감소한다."

BAD:
- 브래킷 변경으로 중량이 1.2 kg 증가한다.
- 최대 응력이 18% 감소한다.

GOOD:
- 중량 +1.2 kg
- 최대 응력 -18%


Original:
"배관 길이가 증가하면서 압력손실이 약 12% 증가하였다."

GOOD:
- 배관 길이 증가
- 압력손실 +12%


Original:
"플러시 이미지는 미래감, 고급감 및
전기차다운 인상에 긍정적이다."

BAD:
- 플러시 이미지는 미래감, 고급감 및 전기차다운 인상에 긍정적이다.

GOOD:
- 미래감·고급감 ↑
- 전기차다운 인상 ↑


Original:
"흑한 신뢰성, 정비성, 사용 직관성이 좋다."

BAD:
- 흑한 신뢰성, 정비성, 사용 직관성이 좋다.

GOOD:
- 흑한 신뢰성 우수
- 정비성 우수
- 사용 직관성 우수


Original:
"미래지향 이미지와 디자인 차별성이 약해진다."

GOOD:
- 미래지향 이미지 ↓
- 디자인 차별성 ↓


=========================================================
FINAL CHECK
=========================================================

Before returning each point, ask:

"Would this be faster to compare inside a table than the original sentence?"

If the point still reads like a normal sentence,
shorten it further without changing its meaning.
"""


    # =====================================================
    # AI 호출
    # =====================================================

    response = client.responses.parse(
        model=model,
        instructions=instructions,
        input=comparison_text,
        text_format=ComparisonSummaryResponse
    )


    parsed_response = (
        response.output_parsed
    )


    if parsed_response is None:

        raise RuntimeError(
            "비교표용 요약 결과를 구조화 데이터로 변환하지 못했습니다."
        )


    # =====================================================
    # dict 형태로 변환
    # =====================================================

    summary_results = []


    for summary in (
        parsed_response.summaries
    ):

        cleaned_points = []


        for point in summary.points:

            cleaned_point = (
                str(point)
                .strip()
                .lstrip("•")
                .strip()
            )


            if (
                cleaned_point
                and cleaned_point
                not in cleaned_points
            ):

                cleaned_points.append(
                    cleaned_point
                )


        # 혹시 AI가 3개 이상 반환해도
        # 비교표에서는 최대 3개만 사용
        cleaned_points = (
            cleaned_points[:3]
        )


        summary_results.append(
            {
                "candidate": (
                    summary.candidate
                ),

                "criterion": (
                    summary.criterion
                ),

                "points": (
                    cleaned_points
                )
            }
        )


    return summary_results