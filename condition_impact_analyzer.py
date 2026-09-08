from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from candidate_analyzer import (
    build_relative_position_lookup
)

load_dotenv()

client = OpenAI()


# =========================================================
# Structured Output Schema
# =========================================================

class ScenarioImpactItem(BaseModel):

    candidate: str

    criterion: str

    impact: Literal[
        "importance_increases",
        "importance_decreases",
        "mixed",
        "uncertain"
    ]

    text: str


class ScenarioImpactResponse(BaseModel):

    affected_criteria: list[str]

    impacts: list[
        ScenarioImpactItem
    ]

# =========================================================
# 숫자형 필수 기준 충족 여부
# =========================================================

def check_constraint(
    actual_value,
    operator,
    standard_value
):

    try:

        actual_value = float(
            actual_value
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
# 판단항목 중요도 변화 분석
# =========================================================

def analyze_priority_change(
    criterion,
    new_priority,
    confirmed_results,
    criterion_settings,
    qualitative_comparison_results=None
):

    if (
        qualitative_comparison_results
        is None
    ):

        qualitative_comparison_results = []


    setting = (
        criterion_settings.get(
            criterion
        )
    )


    if not setting:

        return {
            "available": False,
            "reason": (
                "해당 판단항목 설정을 찾을 수 없습니다."
            )
        }


    if (
        setting.get(
            "role"
        )
        not in [
            "필수 기준",
            "평가항목"
        ]
    ):

        return {
            "available": False,
            "reason": (
                "참고항목은 중요도 변화 분석에 사용하지 않습니다."
            )
        }


    current_priority = (
        setting.get(
            "priority"
        )
    )


    try:

        current_priority = int(
            current_priority
        )

        new_priority = int(
            new_priority
        )


    except (
        ValueError,
        TypeError
    ):

        return {
            "available": False,
            "reason": (
                "우선순위 값을 확인할 수 없습니다."
            )
        }


    # =====================================================
    # 중요도 변화 방향
    #
    # 숫자가 작을수록 높은 우선순위
    # =====================================================

    if (
        new_priority
        < current_priority
    ):

        priority_change = (
            "importance_increases"
        )


    elif (
        new_priority
        > current_priority
    ):

        priority_change = (
            "importance_decreases"
        )


    else:

        priority_change = (
            "unchanged"
        )


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
    # Python 기반 상대 위치
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
    # 문장형 정성정보의 기존 AI 비교 결과 병합
    # =====================================================

    for comparison in (
        qualitative_comparison_results
    ):

        comparison_criterion = (
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
            comparison_criterion
            == criterion

            and

            candidate
            in candidate_names

            and

            position
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
    # 후보별 상대 위치 정리
    # =====================================================

    strength_candidates = []

    weakness_candidates = []

    neutral_candidates = []

    insufficient_candidates = []


    for candidate in (
        candidate_names
    ):

        position = (
            position_lookup.get(
                (
                    criterion,
                    candidate
                )
            )
        )


        if position == "strength":

            strength_candidates.append(
                candidate
            )


        elif position == "weakness":

            weakness_candidates.append(
                candidate
            )


        elif position == "neutral":

            neutral_candidates.append(
                candidate
            )


        else:

            insufficient_candidates.append(
                candidate
            )


    return {
        "available": True,

        "criterion": (
            criterion
        ),

        "current_priority": (
            current_priority
        ),

        "new_priority": (
            new_priority
        ),

        "priority_change": (
            priority_change
        ),

        "strength_candidates": (
            strength_candidates
        ),

        "weakness_candidates": (
            weakness_candidates
        ),

        "neutral_candidates": (
            neutral_candidates
        ),

        "insufficient_candidates": (
            insufficient_candidates
        )
    }


# =========================================================
# 필수 기준값 변화 분석
# =========================================================

def analyze_threshold_change(
    criterion,
    new_operator,
    new_standard,
    confirmed_results,
    criterion_settings
):

    setting = (
        criterion_settings.get(
            criterion
        )
    )


    if not setting:

        return {
            "available": False,
            "reason": (
                "해당 판단항목 설정을 찾을 수 없습니다."
            )
        }


    # 필수 기준 + 숫자형만 계산
    if (
        setting.get(
            "role"
        )
        != "필수 기준"

        or

        setting.get(
            "data_type"
        )
        not in [
            "numeric",
            "ranking"
        ]
    ):

        return {
            "available": False,
            "reason": (
                "숫자형 필수 기준만 기준값 변화 분석이 가능합니다."
            )
        }


    current_operator = (
        setting.get(
            "constraint_operator"
        )
    )

    current_standard = (
        setting.get(
            "constraint_value"
        )
    )

    unit = (
        setting.get(
            "unit"
        )
        or ""
    )


    if (
        current_operator is None
        or current_standard is None
    ):

        return {
            "available": False,
            "reason": (
                "현재 필수 기준값이 설정되지 않았습니다."
            )
        }


    try:

        current_standard = float(
            current_standard
        )

        new_standard = float(
            new_standard
        )


    except (
        ValueError,
        TypeError
    ):

        return {
            "available": False,
            "reason": (
                "기준값을 숫자로 변환할 수 없습니다."
            )
        }


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


    candidate_changes = []

    ambiguous_candidates = []


    # =====================================================
    # 후보별 현재 / 변경 기준 비교
    # =====================================================

    for candidate in (
        candidate_names
    ):

        candidate_results = [
            result

            for result
            in confirmed_results

            if (
                result.get(
                    "candidate"
                )
                == candidate

                and

                result.get(
                    "field"
                )
                == criterion
            )
        ]


        # 값이 없으면 분석하지 않음
        if not candidate_results:

            continue


        # 동일 후보 + 동일 항목의 숫자가 여러 개라면
        # 임의로 하나를 선택하지 않는다.
        if (
            len(
                candidate_results
            )
            != 1
        ):

            ambiguous_candidates.append(
                candidate
            )

            continue


        result = (
            candidate_results[0]
        )


        try:

            actual_value = float(
                result.get(
                    "value"
                )
            )


        except (
            ValueError,
            TypeError
        ):

            ambiguous_candidates.append(
                candidate
            )

            continue


        current_satisfied = (
            check_constraint(
                actual_value=(
                    actual_value
                ),
                operator=(
                    current_operator
                ),
                standard_value=(
                    current_standard
                )
            )
        )


        new_satisfied = (
            check_constraint(
                actual_value=(
                    actual_value
                ),
                operator=(
                    new_operator
                ),
                standard_value=(
                    new_standard
                )
            )
        )


        if (
            current_satisfied is None
            or new_satisfied is None
        ):

            ambiguous_candidates.append(
                candidate
            )

            continue


        # =================================================
        # 상태 변화 분류
        # =================================================

        if (
            current_satisfied
            and new_satisfied
        ):

            transition = (
                "stays_satisfied"
            )


        elif (
            not current_satisfied
            and not new_satisfied
        ):

            transition = (
                "stays_unmet"
            )


        elif (
            not current_satisfied
            and new_satisfied
        ):

            transition = (
                "becomes_satisfied"
            )


        else:

            transition = (
                "becomes_unmet"
            )


        candidate_changes.append(
            {
                "candidate": (
                    candidate
                ),

                "actual_value": (
                    actual_value
                ),

                "unit": (
                    unit
                ),

                "current_satisfied": (
                    current_satisfied
                ),

                "new_satisfied": (
                    new_satisfied
                ),

                "transition": (
                    transition
                )
            }
        )


    return {
        "available": True,

        "criterion": (
            criterion
        ),

        "unit": (
            unit
        ),

        "current_operator": (
            current_operator
        ),

        "current_standard": (
            current_standard
        ),

        "new_operator": (
            new_operator
        ),

        "new_standard": (
            new_standard
        ),

        "candidate_changes": (
            candidate_changes
        ),

        "ambiguous_candidates": (
            ambiguous_candidates
        )
    }

# =========================================================
# 상황 변화 시나리오 분석
# =========================================================

def analyze_scenario_impact(
    scenario,
    confirmed_results,
    criterion_settings,
    qualitative_comparison_results=None,
    model="gpt-5.6-luna"
):

    if not scenario.strip():

        return {
            "affected_criteria": [],
            "impacts": []
        }


    if not confirmed_results:

        return {
            "affected_criteria": [],
            "impacts": []
        }


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


    candidate_set = set(
        candidate_names
    )


    criterion_set = set(
        criterion_settings.keys()
    )


    # =====================================================
    # 기존 정성 비교 결과 조회용
    # =====================================================

    qualitative_lookup = {}


    for comparison in (
        qualitative_comparison_results
    ):

        key = (
            comparison.get(
                "candidate"
            ),
            comparison.get(
                "criterion"
            )
        )


        qualitative_lookup[
            key
        ] = {
            "position": (
                comparison.get(
                    "position"
                )
            ),

            "reason": (
                comparison.get(
                    "reason"
                )
            )
        }


    # =====================================================
    # AI에게 전달할 Evidence 구성
    # =====================================================

    evidence_blocks = []


    for candidate in (
        candidate_names
    ):

        candidate_lines = []


        candidate_results = [
            result

            for result
            in confirmed_results

            if (
                result.get(
                    "candidate"
                )
                == candidate
            )
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


            # 참고항목도 상황변화 판단에
            # 의미가 있을 수 있으므로 Evidence는 제공
            role = (
                setting.get(
                    "role"
                )
                or "설정 없음"
            )


            priority = (
                setting.get(
                    "priority"
                )
            )


            value = str(
                result.get(
                    "value",
                    ""
                )
            ).strip()


            unit = (
                result.get(
                    "unit"
                )
            )


            if unit:

                value = (
                    f"{value}{unit}"
                )


            evidence = str(
                result.get(
                    "evidence",
                    ""
                )
            ).strip()


            comparison = (
                qualitative_lookup.get(
                    (
                        candidate,
                        criterion
                    ),
                    {}
                )
            )


            relative_position = (
                comparison.get(
                    "position"
                )
                or "unknown"
            )


            comparison_reason = (
                comparison.get(
                    "reason"
                )
                or "-"
            )


            candidate_lines.append(
                (
                    f"- criterion: {criterion}\n"
                    f"  role: {role}\n"
                    f"  priority: {priority}\n"
                    f"  value: {value}\n"
                    f"  relative_position: {relative_position}\n"
                    f"  comparison_reason: {comparison_reason}\n"
                    f"  evidence: {evidence}"
                )
            )


        evidence_blocks.append(
            f"""
[CANDIDATE: {candidate}]

{chr(10).join(candidate_lines)}
"""
        )


    evidence_context = "\n".join(
        evidence_blocks
    )


    # =====================================================
    # AI Instruction
    # =====================================================

    instructions = """
You are an engineering decision-support scenario analysis engine.

The user will provide a hypothetical change in decision context.

Examples:

- cold-region sales decrease
- target customers change
- premium positioning becomes more important
- maintenance convenience becomes more important
- development schedule becomes tighter
- validation resources become limited


Your task is NOT to predict new engineering performance.

The physical design alternatives themselves have NOT changed.

Your task is only to analyze whether the IMPORTANCE or DECISION
IMPACT of already-confirmed strengths, weaknesses, risks, and
characteristics changes under the new scenario.


=========================================================
CORE DISTINCTION
=========================================================

Never say:

"The candidate becomes better."
"The quality improves."
"The cost decreases."
"The reliability improves."

unless the supplied evidence explicitly says the physical
property itself changes under the scenario.

Normally the correct interpretation is:

"The importance of this existing advantage increases."
"The decision impact of this existing weakness decreases."
"This risk becomes more important in the decision."


=========================================================
USE ONLY SUPPLIED EVIDENCE
=========================================================

Do not invent:

- new candidate properties
- new performance values
- new costs
- new risks
- new customer reactions
- causal engineering relationships

Every impact must be traceable to the supplied confirmed evidence.


=========================================================
AFFECTED CRITERIA
=========================================================

First identify which existing criteria are meaningfully affected
by the user's scenario.

Do NOT force every criterion to be affected.

If the relationship between the scenario and a criterion is weak
or speculative, exclude that criterion.


=========================================================
IMPACT LABELS
=========================================================

importance_increases

Use when an already-confirmed characteristic, strength, weakness,
or risk becomes MORE important to the decision under the scenario.


importance_decreases

Use when its importance to the decision becomes LESS important.


mixed

Use when the scenario makes different aspects of the same
candidate/criterion pull in different directions.


uncertain

Use only when the supplied evidence suggests relevance but does
not support a reliable direction.


=========================================================
RELATIVE POSITION
=========================================================

If relative_position is supplied:

strength
→ the candidate was previously assessed as relatively strong
   on this criterion.

weakness
→ the candidate was previously assessed as relatively weak.

neutral
→ there was no clear relative advantage/disadvantage.

unknown
→ do not infer relative superiority.


The scenario may change how IMPORTANT that position is.

It does NOT automatically change strength into weakness or
weakness into strength.


=========================================================
EXAMPLE
=========================================================

Scenario:

"Cold-region sales become much less important."


Evidence:

A안 / 품질
"혹한 전개 불량 위험이 크다."

C안 / 품질
"혹한 신뢰성이 좋다."


Good interpretation:

A안 / 품질
importance_decreases

"The decision impact of A안's cold-weather operating risk may
decrease because cold-region use becomes less important."


C안 / 품질
importance_decreases

"The relative importance of C안's cold-weather reliability
advantage may also decrease."


Bad interpretation:

"A안의 품질이 좋아진다."

"C안의 신뢰성이 낮아진다."


=========================================================
WRITING STYLE
=========================================================

Write concise Korean engineering explanations.

Each text should normally be one short sentence.

Use exact candidate and criterion names supplied in the input.

Do not recommend a final candidate.

Do not rank candidates overall.

The user makes the final engineering decision.
"""


    user_input = f"""
SCENARIO CHANGE:

{scenario}


CURRENT CONFIRMED ENGINEERING INFORMATION:

{evidence_context}
"""


    # =====================================================
    # AI 호출
    # =====================================================

    response = client.responses.parse(
        model=model,
        instructions=instructions,
        input=user_input,
        text_format=(
            ScenarioImpactResponse
        )
    )


    parsed = (
        response.output_parsed
    )


    if parsed is None:

        raise RuntimeError(
            "상황 변화 분석 결과를 구조화하지 못했습니다."
        )


    # =====================================================
    # 결과 검증
    # =====================================================

    affected_criteria = []


    for criterion in (
        parsed.affected_criteria
    ):

        if (
            criterion
            in criterion_set
            and criterion
            not in affected_criteria
        ):

            affected_criteria.append(
                criterion
            )


    valid_impacts = []


    for impact in (
        parsed.impacts
    ):

        if (
            impact.candidate
            not in candidate_set
        ):

            continue


        if (
            impact.criterion
            not in criterion_set
        ):

            continue


        if (
            impact.criterion
            not in affected_criteria
        ):

            continue


        valid_impacts.append(
            impact.model_dump()
        )


    return {
        "affected_criteria": (
            affected_criteria
        ),

        "impacts": (
            valid_impacts
        )
    }