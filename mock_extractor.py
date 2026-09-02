def build_mock_results(selected_fields, source_file):

    # =====================================================
    # 후보별 Mock 데이터
    # =====================================================

    sample_library = {

        "후보 A": {
            "개발기간": {
                "value": 2,
                "unit": "개월",
                "data_type": "numeric"
            },
            "원가": {
                "value": 5,
                "unit": "%",
                "data_type": "numeric"
            },
            "품질": {
                "value": "중",
                "unit": None,
                "data_type": "qualitative"
            },
            "호환성": {
                "value": 85,
                "unit": "%",
                "data_type": "numeric"
            },
            "고객체감": {
                "value": "상",
                "unit": None,
                "data_type": "qualitative"
            }
        },

        "후보 B": {
            "개발기간": {
                "value": 4,
                "unit": "개월",
                "data_type": "numeric"
            },
            "원가": {
                "value": 8,
                "unit": "%",
                "data_type": "numeric"
            },
            "품질": {
                "value": "상",
                "unit": None,
                "data_type": "qualitative"
            },
            "호환성": {
                "value": 70,
                "unit": "%",
                "data_type": "numeric"
            },
            "고객체감": {
                "value": "중",
                "unit": None,
                "data_type": "qualitative"
            }
        },

        "후보 C": {
            "개발기간": {
                "value": 3,
                "unit": "개월",
                "data_type": "numeric"
            },
            "원가": {
                "value": 6,
                "unit": "%",
                "data_type": "numeric"
            },
            "품질": {
                "value": "중",
                "unit": None,
                "data_type": "qualitative"
            },
            "호환성": {
                "value": 90,
                "unit": "%",
                "data_type": "numeric"
            },
            "고객체감": {
                "value": "하",
                "unit": None,
                "data_type": "qualitative"
            }
        }
    }


    requested_results = []


    # =====================================================
    # 후보 × 선택 항목 조합 생성
    # =====================================================

    for candidate, candidate_data in sample_library.items():

        for field in selected_fields:

            # 기본 Mock 데이터에 있는 항목
            if field in candidate_data:

                sample = candidate_data[field]

            # 사용자가 자유추가한 항목
            else:

                sample = {
                    "value": "샘플값",
                    "unit": None,
                    "data_type": "qualitative"
                }


            requested_results.append(
                {
                    # 현재 데이터
                    "candidate": candidate,
                    "field": field,
                    "value": sample["value"],
                    "unit": sample["unit"],

                    # 최초 추출값 보존
                    "original_candidate": candidate,
                    "original_field": field,
                    "original_value": sample["value"],
                    "original_unit": sample["unit"],

                    "data_type": sample["data_type"],
                    "source_file": source_file,

                    # Mock이므로 일단 모두 1페이지
                    "page": 1,

                    "evidence": (
                        f"[Mock] {candidate}의 "
                        f"'{field}' 관련 정보가 문서에 "
                        "명시되어 있다고 가정한 테스트 근거입니다."
                    ),

                    "status": "검토 필요",
                    "modified_by_user": False
                }
            )


    # =====================================================
    # 사용자가 지정하지 않은 중요정보 Mock
    # =====================================================

    suggested_results = [
        {
            "candidate": "후보 B",
            "suggested_field": "미래 플랫폼 적용성",
            "value": "적용 제한",
            "unit": None,
            "data_type": "qualitative",
            "source_file": source_file,
            "page": 1,

            "evidence": (
                "[Mock] 향후 플랫폼에서는 후보 B의 "
                "적용범위가 제한될 수 있다는 내용입니다."
            ),

            "reason": (
                "향후 공용화 적용범위를 제한할 수 있어 "
                "의사결정에 영향을 줄 가능성이 있습니다."
            )
        }
    ]


    return requested_results, suggested_results