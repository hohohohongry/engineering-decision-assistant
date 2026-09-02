import streamlit as st
import pandas as pd

st.title("Engineering Decision Assistant")
st.write("첫 화면 테스트")

deadline = st.slider("개발 완료 기한(개월)", 0, 12, 3)
criterion = st.selectbox(
    "최우선 판단기준",
    ["고객체감", "원가절감", "호환성", "품질안정성"]
)
st.write("현재 개발 완료 기한:", deadline, "개월")

# 부품별 품질 개선 개발기간(개월)
parts = {
    "페달브래킷": 6,
    "시트프레임": 3,
    "와이퍼": 1,
    "도어힌지": 0
}
st.write(parts)

# 고객체감 수준을 비교하기 위해 숫자로 변환 (임시 숫자화)
customer_impact = {
    "페달브래킷": 3,
    "시트프레임": 3,
    "와이퍼": 2,
    "도어힌지": 1
}

# 원가절감 효과 순위: 숫자가 작을수록 원가절감 효과가 큼
cost_rank = {
    "페달브래킷": 1,
    "시트프레임": 2,
    "와이퍼": 3,
    "도어힌지": 4
}

# 호환성 순위: 숫자가 작을수록 호환성이 높음
compatibility_rank = {
    "페달브래킷": 1,
    "시트프레임": 2,
    "와이퍼": 3,
    "도어힌지": 4
}

# 공용화 후 품질 문제 재발률(%)
recurrence_rate = {
    "페달브래킷": 1.0,
    "시트프레임": 0.8,
    "와이퍼": 0.5,
    "도어힌지": 0.2
}


# 개발기한 조건을 만족한 부품을 저장할 리스트
eligible_parts = []

# 각 부품의 개발기간이 사용자가 설정한 기한 이내인지 확인
for part, months in parts.items():
        st.write(part, months)
        
        if months <= deadline:
            st.write("조건 충족")
            eligible_parts.append(part)
        else:
            st.write("조건 미충족")
            
st.write("조건 충족 부품:", eligible_parts)



for part in eligible_parts:
    st.write(part, "고객체감 점수:", customer_impact[part])

if criterion == "고객체감":
    best_score = max(customer_impact[part] for part in eligible_parts)
elif criterion == "원가절감":
    best_score = min(cost_rank[part] for part in eligible_parts)
elif criterion == "호환성":
    best_score = min(compatibility_rank[part] for part in eligible_parts)
elif criterion == "품질안정성":
    best_score = min(recurrence_rate[part] for part in eligible_parts)
   
            
st.write("선택 기준 최적값:", best_score)

if criterion == "고객체감":
    best_parts = [part for part in eligible_parts if customer_impact[part] == best_score]
elif criterion == "원가절감":
    best_parts = [part for part in eligible_parts if cost_rank[part] == best_score]
elif criterion == "호환성":
    best_parts = [part for part in eligible_parts if compatibility_rank[part] == best_score]
elif criterion == "품질안정성":
    best_parts = [part for part in eligible_parts if recurrence_rate[part] == best_score]
selected_part = best_parts[0]
alternative_parts = [part for part in eligible_parts if part != selected_part]
st.write("대안 후보:", alternative_parts)
compare_part = st.selectbox(
    "비교할 대안 후보",
    alternative_parts
)
st.write("원가절감 순위 비교:", selected_part, cost_rank[selected_part], "위 /", compare_part, cost_rank[compare_part], "위")
st.write("호환성 순위 비교:", selected_part, compatibility_rank[selected_part], "위 /", compare_part, compatibility_rank[compare_part], "위")
st.write("고객체감 비교:", selected_part, customer_impact[selected_part], "/",
         compare_part, customer_impact[compare_part])
st.write("품질 재발률 비교:", selected_part, recurrence_rate[selected_part], "% /",
         compare_part, recurrence_rate[compare_part], "%")
st.write("개발기간 비교:", selected_part, parts[selected_part], "개월 /",
         compare_part, parts[compare_part], "개월")

# 선정안과 대안의 장단점 자동 비교
strengths = []
weaknesses = []

if cost_rank[selected_part] < cost_rank[compare_part]:
    strengths.append("원가절감")
elif cost_rank[selected_part] > cost_rank[compare_part]:
    weaknesses.append("원가절감")

if compatibility_rank[selected_part] < compatibility_rank[compare_part]:
    strengths.append("호환성")
elif compatibility_rank[selected_part] > compatibility_rank[compare_part]:
    weaknesses.append("호환성")

if customer_impact[selected_part] > customer_impact[compare_part]:
    strengths.append("고객체감")
elif customer_impact[selected_part] < customer_impact[compare_part]:
    weaknesses.append("고객체감")

if recurrence_rate[selected_part] < recurrence_rate[compare_part]:
    strengths.append("품질안정성")
elif recurrence_rate[selected_part] > recurrence_rate[compare_part]:
    weaknesses.append("품질안정성")

if parts[selected_part] < parts[compare_part]:
    strengths.append("개발기간")
elif parts[selected_part] > parts[compare_part]:
    weaknesses.append("개발기간")

st.write("선정안 우위:", strengths)
st.write("선정안 열위:", weaknesses)
    

if criterion == "고객체감":
    for part in alternative_parts:
        st.write(part, "고객체감 점수:", customer_impact[part])
elif criterion == "원가절감":
    for part in alternative_parts:
        st.write(part, "원가절감 순위:", cost_rank[part])
elif criterion == "호환성":
    for part in alternative_parts:
        st.write(part, "호환성 순위:", compatibility_rank[part])
elif criterion == "품질안정성":
    for part in alternative_parts:
        st.write(part, "품질 재발률:", recurrence_rate[part], "%")

risk_messages = []

# 개발기간 마진 계산 식
schedule_margin = deadline - parts[selected_part]

# 아래는, 재발률이 0.8% 이상이면 품질 리스크가 있다고 보는 임시기준.
quality_risk_threshold = 0.8
# 호환성 순위가 3위 이하(3위 4위)면 호환성 리스크로 봄
compatibility_risk_threshold = 3
if compatibility_rank[selected_part] >= compatibility_risk_threshold:
    risk_messages.append("호환성 우선순위 낮음")
    
if recurrence_rate[selected_part] >= quality_risk_threshold:
    st.warning("품질 리스크 주의: 재발률이 기준 이상임")
    risk_messages.append("품질 재발률 기준 이상")

st.write("선정 후보 호환성 순위:", compatibility_rank[selected_part], "위")
st.write("선정 후보 원가절감 순위:", cost_rank[selected_part], "위")
st.write("선정 후보 고객체감 점수:", customer_impact[selected_part])
st.write(criterion, "기준 최우선 후보:", best_parts)

st.write("일정 여유:", schedule_margin, "개월")
if schedule_margin == 0:
    st.warning("일정 여유 없음: 개발기한과 예상 개발기간이 동일함")
    risk_messages.append("일정 여유 없음")

if risk_messages:
    st.write("주요 리스크:", risk_messages)
else:
    st.write("주요 리스크 없음")

st.write("선정 후보 품질 재발률:", recurrence_rate[selected_part], "%")

for part in eligible_parts:
    st.write(part, "원가절감 순위:", cost_rank[part])
for part in eligible_parts:
    st.write(part, "호환성 순위:", compatibility_rank[part])
for part in eligible_parts:
    st.write(part, "품질 재발률:", recurrence_rate[part], "%")

summary_data = []

for part in eligible_parts:
    st.write(part, "| 고객체감:", customer_impact[part], "| 원가순위:", cost_rank[part], "| 호환성순위:", compatibility_rank[part], "| 재발률:", recurrence_rate[part], "%")
    
    summary_data.append({
        "부품": part,
        "개발기간(개월)": parts[part],
        "고객체감": customer_impact[part],
        "원가순위": cost_rank[part],
        "호환성순위": compatibility_rank[part],
        "재발률(%)": recurrence_rate[part]
    })

summary_df = pd.DataFrame(summary_data)
st.subheader("공용화 후보 비교")
st.dataframe(summary_df)

st.success("추천 후보: " + ", ".join(best_parts))
st.write("선정 근거: 개발기한을 충족한 후보 중", criterion, "기준이 가장 우수함")
