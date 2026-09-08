from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel


load_dotenv()

client = OpenAI()


# =========================================================
# Structured Output Schema
# =========================================================

class AnalysisPoint(BaseModel):

    criterion: str

    # -----------------------------------------------------
    # 이 장점/약점이 어떤 근거 수준에서 나온 것인지
    #
    # relative:
    # 후보 간 상대비교에서 확인
    #
    # confirmed:
    # 문서에 효과가 직접 명시되었거나
    # 숫자 기준으로 직접 확인
    #
    # inferred:
    # 설계 구조/방식에서 합리적으로 예상한 영향
    # -----------------------------------------------------

    basis: Literal[
        "relative",
        "confirmed",
        "inferred"
    ]

    text: str


class TradeoffPoint(BaseModel):

    criteria: list[str]

    text: str


class CandidateAnalysis(BaseModel):

    candidate: str

    strengths: list[
        AnalysisPoint
    ]

    weaknesses: list[
        AnalysisPoint
    ]

    tradeoffs: list[
        TradeoffPoint
    ]


class CandidateAnalysisResponse(BaseModel):

    analyses: list[
        CandidateAnalysis
    ]


# =========================================================
# 값 표시
# =========================================================

def format_analysis_value(
    value,
    unit
):

    if unit:

        return (
            f"{value}{unit}"
        )

    return str(
        value
    )


# =========================================================
# 필수조건 충족 여부
# =========================================================

def evaluate_constraint(
    value,
    operator,
    standard_value
):

    try:

        actual_value = float(
            value
        )

        standard_value = float(
            standard_value
        )


        if operator == "≤":

            return (
                actual_value
                <= standard_value
            )


        if operator == "≥":

            return (
                actual_value
                >= standard_value
            )


        if operator == "=":

            return (
                actual_value
                == standard_value
            )


    except (
        ValueError,
        TypeError
    ):

        return None


    return None


# =========================================================
# 정량 / 상중하 상대 위치 계산
# =========================================================

def build_relative_position_lookup(
    candidate_names,
    confirmed_results,
    criterion_settings
):

    position_lookup = {}


    # =====================================================
    # 판단항목별 처리
    # =====================================================

    for criterion, setting in (
        criterion_settings.items()
    ):

        role = (
            setting.get(
                "role"
            )
        )

        direction = (
            setting.get(
                "direction"
            )
        )

        data_type = (
            setting.get(
                "data_type"
            )
        )


        # 참고항목은 상대 우위 판정에서 제외
        if role not in [
            "필수 기준",
            "평가항목"
        ]:

            continue


        if (
            direction is None
            or direction == "방향 없음"
        ):

            continue


        criterion_results = [
            result

            for result
            in confirmed_results

            if result.get(
                "field"
            )
            == criterion

            and

            result.get(
                "candidate"
            )
            in candidate_names
        ]


        # 후보가 2개 미만이면
        # 상대비교 불가능
        candidate_set = {
            result.get(
                "candidate"
            )

            for result
            in criterion_results
        }


        if len(
            candidate_set
        ) < 2:

            continue


        # =================================================
        # 정량 / ranking
        # =================================================

        if data_type in [
            "numeric",
            "ranking"
        ]:

            candidate_values = {}


            for result in (
                criterion_results
            ):

                candidate = (
                    result.get(
                        "candidate"
                    )
                )


                # 동일 후보에 같은 판단항목이
                # 여러 값이면 임의로 하나를 고르지 않음
                if (
                    candidate
                    in candidate_values
                ):

                    candidate_values[
                        candidate
                    ] = None

                    continue


                try:

                    candidate_values[
                        candidate
                    ] = float(
                        result.get(
                            "value"
                        )
                    )


                except (
                    ValueError,
                    TypeError
                ):

                    candidate_values[
                        candidate
                    ] = None


            valid_values = {
                candidate: value

                for candidate, value
                in candidate_values.items()

                if value is not None
            }


            if len(
                valid_values
            ) < 2:

                continue


            all_values = list(
                valid_values.values()
            )


            if (
                max(all_values)
                == min(all_values)
            ):

                for candidate in (
                    valid_values
                ):

                    position_lookup[
                        (
                            criterion,
                            candidate
                        )
                    ] = "neutral"


                continue


            if (
                direction
                == "높을수록 좋음"
            ):

                best_value = max(
                    all_values
                )

                worst_value = min(
                    all_values
                )


            elif (
                direction
                == "낮을수록 좋음"
            ):

                best_value = min(
                    all_values
                )

                worst_value = max(
                    all_values
                )


            else:

                continue


            for candidate, value in (
                valid_values.items()
            ):

                if value == best_value:

                    position = (
                        "strength"
                    )


                elif value == worst_value:

                    position = (
                        "weakness"
                    )


                else:

                    position = (
                        "neutral"
                    )


                position_lookup[
                    (
                        criterion,
                        candidate
                    )
                ] = position


        # =================================================
        # 상 / 중 / 하
        # =================================================

        elif (
            data_type
            == "qualitative"
        ):

            structured_labels = {
                "상",
                "중",
                "하"
            }


            candidate_values = {}


            for result in (
                criterion_results
            ):

                candidate = (
                    result.get(
                        "candidate"
                    )
                )

                value = str(
                    result.get(
                        "value",
                        ""
                    )
                ).strip()


                if (
                    value
                    not in structured_labels
                ):

                    continue


                # 동일 후보에 여러 값이 있으면
                # 임의 판단하지 않음
                if (
                    candidate
                    in candidate_values
                ):

                    candidate_values[
                        candidate
                    ] = None

                    continue


                candidate_values[
                    candidate
                ] = value


            candidate_values = {
                candidate: value

                for candidate, value
                in candidate_values.items()

                if value is not None
            }


            if len(
                candidate_values
            ) < 2:

                continue


            if (
                direction
                == "상 > 중 > 하"
            ):

                score_map = {
                    "상": 3,
                    "중": 2,
                    "하": 1
                }


            elif (
                direction
                == "하 > 중 > 상"
            ):

                score_map = {
                    "하": 3,
                    "중": 2,
                    "상": 1
                }


            else:

                continue


            scored_values = {
                candidate: (
                    score_map[
                        value
                    ]
                )

                for candidate, value
                in candidate_values.items()
            }


            scores = list(
                scored_values.values()
            )


            if (
                max(scores)
                == min(scores)
            ):

                for candidate in (
                    scored_values
                ):

                    position_lookup[
                        (
                            criterion,
                            candidate
                        )
                    ] = "neutral"


                continue


            best_score = max(
                scores
            )

            worst_score = min(
                scores
            )


            for candidate, score in (
                scored_values.items()
            ):

                if (
                    score
                    == best_score
                ):

                    position = (
                        "strength"
                    )


                elif (
                    score
                    == worst_score
                ):

                    position = (
                        "weakness"
                    )


                else:

                    position = (
                        "neutral"
                    )


                position_lookup[
                    (
                        criterion,
                        candidate
                    )
                ] = position


    return position_lookup


# =========================================================
# 후보 특성 분석
# =========================================================

def analyze_candidate_characteristics(
    confirmed_results,
    criterion_settings,
    qualitative_comparison_results=None,
    model="gpt-5.6-luna"
):

    if not confirmed_results:

        return []


    if not criterion_settings:

        return []


    if (
        qualitative_comparison_results
        is None
    ):

        qualitative_comparison_results = []


    # =====================================================
    # 후보 목록
    # =====================================================

    candidate_names = list(
        dict.fromkeys(
            result.get(
                "candidate"
            )

            for result
            in confirmed_results

            if result.get(
                "candidate"
            )
        )
    )


    # =====================================================
    # Python 상대 위치 계산
    # =====================================================

    position_lookup = (
        build_relative_position_lookup(
            candidate_names=(
                candidate_names
            ),
            confirmed_results=(
                confirmed_results
            ),
            criterion_settings=(
                criterion_settings
            )
        )
    )


    # =====================================================
    # 기존 문장형 AI 비교 결과 병합
    # =====================================================

    for comparison in (
        qualitative_comparison_results
    ):

        criterion = (
            comparison.get(
                "criterion"
            )
        )

        candidate = (
            comparison.get(
                "candidate"
            )
        )

        position = (
            comparison.get(
                "position"
            )
        )


        if (
            criterion
            and candidate
            and position
            in [
                "strength",
                "neutral",
                "weakness"
            ]
        ):

            position_lookup[
                (
                    criterion,
                    candidate
                )
            ] = position


    # =====================================================
    # AI에게 전달할 후보별 정보 구성
    # =====================================================

    candidate_blocks = []


    for candidate in (
        candidate_names
    ):

        fact_lines = []


        candidate_results = [
            result

            for result
            in confirmed_results

            if result.get(
                "candidate"
            )
            == candidate
        ]


        for result in (
            candidate_results
        ):

            criterion = (
                result.get(
                    "field"
                )
            )


            setting = (
                criterion_settings.get(
                    criterion,
                    {}
                )
            )


            role = (
                setting.get(
                    "role"
                )
                or "설정 없음"
            )


            # 참고항목은 장단점 판단에서 제외
            if (
                role
                == "참고항목"
            ):

                continue


            priority = (
                setting.get(
                    "priority"
                )
            )

            direction = (
                setting.get(
                    "direction"
                )
                or "방향 없음"
            )


            value_text = (
                format_analysis_value(
                    result.get(
                        "value"
                    ),
                    result.get(
                        "unit"
                    )
                )
            )


            relative_position = (
                position_lookup.get(
                    (
                        criterion,
                        candidate
                    ),
                    "unknown"
                )
            )


            # =============================================
            # 필수 기준 충족 여부
            # =============================================

            constraint_status = (
                "not_applicable"
            )


            if (
                role
                == "필수 기준"
            ):

                operator = (
                    setting.get(
                        "constraint_operator"
                    )
                )

                standard_value = (
                    setting.get(
                        "constraint_value"
                    )
                )


                if (
                    operator is not None
                    and
                    standard_value is not None
                ):

                    constraint_result = (
                        evaluate_constraint(
                            value=(
                                result.get(
                                    "value"
                                )
                            ),
                            operator=(
                                operator
                            ),
                            standard_value=(
                                standard_value
                            )
                        )
                    )


                    if (
                        constraint_result
                        is True
                    ):

                        constraint_status = (
                            "satisfied"
                        )


                    elif (
                        constraint_result
                        is False
                    ):

                        constraint_status = (
                            "unmet"
                        )


                    else:

                        constraint_status = (
                            "unknown"
                        )


            evidence_text = str(
                result.get(
                    "evidence",
                    ""
                )
            ).strip()


            fact_lines.append(
                (
                    f"- criterion: {criterion}\n"
                    f"  role: {role}\n"
                    f"  priority: {priority}\n"
                    f"  direction: {direction}\n"
                    f"  value: {value_text}\n"
                    f"  relative_position: {relative_position}\n"
                    f"  required_constraint: {constraint_status}\n"
                    f"  evidence: {evidence_text}"
                )
            )


        candidate_blocks.append(
            (
                f"""
[CANDIDATE: {candidate}]

{chr(10).join(fact_lines)}
"""
            )
        )


    analysis_context = "\n".join(
        candidate_blocks
    )


    # =====================================================
    # AI 지시
    # =====================================================

    instructions = """
You are an engineering decision-support explanation engine.

The engineering evidence has already been extracted and reviewed.

You do NOT choose the final candidate.
You do NOT rank the candidates overall.
You do NOT recommend a winner.

Your task is only to explain each candidate's:

1. strengths
2. weaknesses
3. trade-offs

using ONLY the supplied confirmed information and comparison status.


=========================================================
GROUNDING RULES
=========================================================

Never invent unsupported specific facts.

However, this is a decision-support tool.

You MAY provide a limited engineering inference when a likely
effect follows directly and reasonably from the confirmed
design configuration or operating method.

The important requirement is to clearly distinguish:

1. relative
2. confirmed
3. inferred


---------------------------------------------------------
1. relative
---------------------------------------------------------

Use basis = "relative" only when a relative advantage or
disadvantage has actually been established between candidates.

Examples:

- direct numeric comparison
- structured high / medium / low comparison
- qualitative comparison supported by candidate evidence

relative_position = strength or weakness is an important
comparison signal.

However, do NOT blindly call every relative_position result
a confirmed relative advantage.

If explaining the advantage requires an additional engineering
inference from a design configuration, use basis = "inferred"
instead.


---------------------------------------------------------
2. confirmed
---------------------------------------------------------

Use basis = "confirmed" when the supplied document directly
states the beneficial or negative effect.

Examples:

"공장 작업량이 감소한다."
"체결 확인성이 개선된다."
"원가 증가가 우려된다."
"내부 간섭 재검토가 필요하다."

A deterministic numeric requirement result may also be treated
as confirmed.


---------------------------------------------------------
3. inferred
---------------------------------------------------------

Use basis = "inferred" when:

- the document confirms the candidate's structure, configuration,
  or operating method

AND

- a useful engineering effect can reasonably be inferred from
  that confirmed fact

BUT

- the effect itself is not directly stated or verified
  in the document.


Example:

Confirmed fact:
"완전 사전조립 모듈로 전환"

Reasonable first-order inference:
"현장 개별 조립 작업이 줄어들 가능성"

This may be returned as:

basis = "inferred"


IMPORTANT:

An inferred point must use cautious wording such as:

- 가능
- 예상
- 가능성
- 줄어들 수 있음
- 증가할 수 있음

Do NOT express an inferred effect as a confirmed fact.


=========================================================
INFERENCE LIMITS
=========================================================

Inference must remain close to the confirmed design fact.

Allow only a direct, first-order engineering implication.

Do NOT make long chains such as:

사전조립
→ 작업시간 감소
→ 인건비 감소
→ 총원가 절감
→ 수익성 향상

unless those later effects are explicitly supported.

Do NOT invent:

- numeric magnitudes
- exact cost changes
- exact performance improvements
- safety conclusions
- reliability conclusions
- regulatory conclusions

unless supported by the supplied information.

If several outcomes are similarly plausible or the relationship
is too uncertain, omit the point rather than guessing.


Use required_constraint exactly as supplied:

satisfied
→ the required numeric condition is satisfied.

unmet
→ the required numeric condition is not satisfied.

unknown
→ do not claim whether the requirement is satisfied.


=========================================================
STRENGTHS
=========================================================

A strength may have one of three basis types.


---------------------------------------------------------
A. RELATIVE STRENGTH
---------------------------------------------------------

Use:

basis = "relative"

when the supplied comparison establishes that the candidate
is relatively favorable on that criterion.

The text should briefly explain the established relative advantage.


---------------------------------------------------------
B. CONFIRMED ADVANTAGE
---------------------------------------------------------

Use:

basis = "confirmed"

when the supplied evidence directly states a beneficial effect
for the candidate.

Examples:

- 작업량 감소
- 검출성 개선
- 원가 절감
- 정비 접근성 향상

A satisfied required numeric condition may also support
a confirmed positive point.


---------------------------------------------------------
C. INFERRED ADVANTAGE
---------------------------------------------------------

Use:

basis = "inferred"

when a useful beneficial effect is a reasonable first-order
engineering implication of the confirmed candidate configuration,
but the document does not directly state that effect.

Example:

Confirmed configuration:
"완전 사전조립 모듈로 전환"

Possible inferred advantage:
"현장 개별 조립 작업이 줄어들 가능성"


Do not suppress a useful engineering inference merely because
the document does not explicitly state the consequence.

Instead, classify it honestly as inferred.


Maximum 3 strength points per candidate.

Prefer higher-priority decision criteria when several points exist.


=========================================================
WEAKNESSES
=========================================================

A weakness may also have one of three basis types.


---------------------------------------------------------
A. RELATIVE WEAKNESS
---------------------------------------------------------

Use:

basis = "relative"

when the supplied comparison establishes that the candidate
is relatively unfavorable on that criterion.


---------------------------------------------------------
B. CONFIRMED BURDEN
---------------------------------------------------------

Use:

basis = "confirmed"

when the supplied evidence directly states a burden, risk,
disadvantage, additional work, or constraint.

Examples:

- 원가 증가 우려
- 내부 간섭 재검토 필요
- 검사 기준 추가 필요
- 수분 유입 위험

An unmet required numeric condition may also support
a confirmed negative point.


---------------------------------------------------------
C. INFERRED BURDEN
---------------------------------------------------------

Use:

basis = "inferred"

when a likely negative effect follows directly from a confirmed
candidate configuration but is not explicitly verified
in the document.

Use cautious wording.

Do not infer second-order burdens or speculative risks.


Maximum 3 weakness points per candidate.

Prefer higher-priority decision criteria when several points exist.


=========================================================
TRADE-OFFS
=========================================================

A trade-off requires at least two distinct supported aspects.

A trade-off MAY include an inferred advantage or inferred burden.

However, if any part of the trade-off depends on engineering
inference, the wording must clearly preserve uncertainty.

Example:

"한 측면의 개선이 예상되지만 다른 측면의 부담은 추가 검토 필요"

Do not present an inferred trade-off as a verified causal fact.

For example:

- one criterion is a strength while another is a burden
- performance improves while cost increases
- customer value is maintained while validation burden increases

Do NOT invent a causal relationship.

Unless the supplied evidence explicitly establishes causality,
write the trade-off as coexistence:

"품질 측 강점이 있으나 원가 부담이 함께 존재"

rather than:

"품질을 높이기 위해 원가가 증가함"

Maximum 2 trade-off points per candidate.


=========================================================
WRITING STYLE
=========================================================

Write concise Korean engineering phrases.

The UI will separately display whether the point is:

- 상대 강점 / 상대 약점
- 확인된 장점 / 확인된 부담
- 예상 장점 / 예상 부담

Therefore, do NOT repeat these labels inside text.


Good text examples:

relative:
"체결 검출성이 다른 후보 대비 우수"

confirmed:
"서비스 홀 확대를 통해 작업성 개선"

inferred:
"사전조립 전환으로 현장 개별 조립 작업이 줄어들 가능성"


For inferred points:

- keep the wording cautious
- describe only the likely direct effect
- do not state it as certainty


Avoid long explanatory paragraphs.

Each point should normally be one short sentence.

criterion must use the exact criterion name supplied in the input.

For a trade-off, criteria must contain the exact names of the
criteria involved.

If neither confirmed evidence nor reasonable engineering inference
supports a useful point, return an empty list.


=========================================================
FINAL RULE
=========================================================

Never write:

- 최적안
- 추천안
- 가장 적합한 후보
- 선택해야 한다
- 종합적으로 우수하다

The final engineering decision belongs to the user.
"""


    # =====================================================
    # AI 호출
    # =====================================================

    response = client.responses.parse(
        model=model,
        instructions=instructions,
        input=analysis_context,
        text_format=(
            CandidateAnalysisResponse
        )
    )


    parsed = (
        response.output_parsed
    )


    if parsed is None:

        raise RuntimeError(
            "후보 특성 분석 결과를 구조화하지 못했습니다."
        )


    # =====================================================
    # 후보명 검증
    # =====================================================

    valid_analyses = []


    for analysis in (
        parsed.analyses
    ):

        if (
            analysis.candidate
            not in candidate_names
        ):

            continue


        valid_analyses.append(
            analysis.model_dump()
        )


    return valid_analyses