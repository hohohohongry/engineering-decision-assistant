from comparison_summarizer import summarize_comparison_values


test_items = [
    {
        "candidate": "A안",
        "criterion": "품질",
        "value": "흑한 전개 불량 및 품질 클레임 위험이 크다."
    },
    {
        "candidate": "B안",
        "criterion": "주요 리스크",
        "value": "부품 원가와 검증 항목이 증가하고, 디자인센터와 세부 형상 협의가 필요하다."
    },
    {
        "candidate": "C안",
        "criterion": "구조 성능",
        "value": "브래킷 변경으로 중량은 1.2 kg 증가하지만 최대 응력은 18% 감소한다."
    }
]


results = summarize_comparison_values(
    test_items
)


for result in results:

    print(
        f'\n[{result["candidate"]} / {result["criterion"]}]'
    )

    for point in result["points"]:

        print(
            f"- {point}"
        )