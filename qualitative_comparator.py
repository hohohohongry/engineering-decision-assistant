from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel


# =========================================================
# 환경변수 / OpenAI Client
# =========================================================

load_dotenv()

client = OpenAI()


# =========================================================
# Structured Output Schema
# =========================================================

class CandidateAssessment(BaseModel):

    candidate: str

    position: Literal[
        "strength",
        "neutral",
        "weakness",
        "insufficient"
    ]

    reason: str


class CriterionAssessment(BaseModel):

    criterion: str

    assessments: list[CandidateAssessment]


class QualitativeComparisonResponse(BaseModel):

    comparisons: list[CriterionAssessment]


# =========================================================
# 문장형 정성 데이터 비교
# =========================================================

def compare_qualitative_evidence(
    confirmed_results,
    criterion_settings,
    model="gpt-5.6-luna"
):

    # -----------------------------------------------------
    # 후보 목록
    # -----------------------------------------------------

    candidate_names = list(
        dict.fromkeys(
            result["candidate"]
            for result in confirmed_results
        )
    )


    # -----------------------------------------------------
    # AI 비교가 필요한 판단항목 구성
    # -----------------------------------------------------

    comparison_targets = []


    for criterion, setting in criterion_settings.items():

        data_type = setting.get(
            "data_type"
        )

        direction = setting.get(
            "direction"
        )


        # 정성형이 아니면 AI 비교 대상이 아님
        if data_type != "qualitative":

            continue


        # 비교 방향이 없으면 분석하지 않음
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


        if not criterion_results:

            continue


        # ---------------------------------------------
        # 상/중/하처럼 이미 정형화된 값인지 확인
        # ---------------------------------------------

        normalized_values = [
            str(result["value"]).strip()
            for result in criterion_results
        ]


        structured_labels = {
            "상",
            "중",
            "하"
        }


        # 전부 상/중/하라면 기존 Python 비교로 처리
        if all(
            value in structured_labels
            for value in normalized_values
        ):

            continue


        # ---------------------------------------------
        # 후보별 Evidence 묶기
        # ---------------------------------------------

        candidate_evidence = []


        for candidate in candidate_names:

            candidate_results = [
                result
                for result in criterion_results
                if result["candidate"] == candidate
            ]


            if not candidate_results:

                candidate_evidence.append(
                    {
                        "candidate": candidate,
                        "evidence": []
                    }
                )

                continue


            evidence_items = []


            for result in candidate_results:

                evidence_items.append(
                    {
                        "value": result["value"],
                        "page": result["page"],
                        "evidence": result["evidence"]
                    }
                )


            candidate_evidence.append(
                {
                    "candidate": candidate,
                    "evidence": evidence_items
                }
            )


        comparison_targets.append(
            {
                "criterion": criterion,
                "direction": direction,
                "candidates": candidate_evidence
            }
        )


    # 비교할 문장형 정성 데이터가 없는 경우
    if not comparison_targets:

        return []


    # -----------------------------------------------------
    # AI 지시문
    # -----------------------------------------------------

    instructions = """
You are an engineering decision-support comparison engine.

You are NOT selecting the final candidate.
You are comparing qualitative engineering evidence across candidates.

For each criterion:

1. Compare ALL supplied candidates together.
2. Judge only relative favorability for that specific criterion.
3. Follow the user's preferred direction.
4. Use only the supplied evidence.
5. Do not invent missing performance, cost, quality, risk, or feasibility information.
6. Do not convert qualitative evidence into arbitrary numerical scores.
7. Multiple candidates may simultaneously be strengths or weaknesses.
8. Do not force a single winner.
9. If a candidate has insufficient evidence for that criterion, classify it as "insufficient".
10. If candidates are broadly similar or the evidence does not establish meaningful superiority/inferiority, classify them as "neutral".
11. "strength" means the supplied evidence places that candidate relatively favorably for the criterion.
12. "weakness" means the supplied evidence places that candidate relatively unfavorably for the criterion.
13. Preserve trade-offs. A candidate may be a strength for one criterion and a weakness for another.
14. The reason must briefly explain why the classification follows from the supplied evidence.
15. Candidate names and criterion names must exactly match the supplied input.

The goal is to support an engineer's judgment, not replace it.
"""


    # -----------------------------------------------------
    # AI 입력
    # -----------------------------------------------------

    user_input = f"""
Compare the following qualitative engineering evidence.

DATA:
{comparison_targets}
"""


    # -----------------------------------------------------
    # Structured Output 호출
    # -----------------------------------------------------

    response = client.responses.parse(
        model=model,
        instructions=instructions,
        input=user_input,
        text_format=QualitativeComparisonResponse
    )


    parsed = response.output_parsed


    if parsed is None:

        raise RuntimeError(
            "문장형 정성 비교 결과를 구조화하지 못했습니다."
        )


    # -----------------------------------------------------
    # app.py에서 사용하기 쉬운 형태로 변환
    # -----------------------------------------------------

    comparison_results = []


    valid_candidates = set(
        candidate_names
    )

    valid_criteria = {
        target["criterion"]
        for target in comparison_targets
    }


    for comparison in parsed.comparisons:

        # AI가 입력에 없던 항목명을 생성하는 것 방지
        if comparison.criterion not in valid_criteria:

            continue


        for assessment in comparison.assessments:

            # AI가 입력에 없던 후보를 생성하는 것 방지
            if assessment.candidate not in valid_candidates:

                continue


            comparison_results.append(
                {
                    "criterion": comparison.criterion,
                    "candidate": assessment.candidate,
                    "position": assessment.position,
                    "reason": assessment.reason
                }
            )


    return comparison_results