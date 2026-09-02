# Engineering Decision Assistant

다양한 개발자료에 분산된 근거를 구조화하고, 여러 후보를 동일한 판단기준으로 비교할 수 있도록 지원하는 엔지니어링 의사결정 보조 도구입니다.

본 프로젝트는 AI가 최종 대안을 대신 결정하는 것이 아니라,  
**어떤 근거와 판단기준 때문에 결과가 달라지는지 엔지니어가 확인할 수 있도록 지원하는 것**을 목표로 합니다.

---

## 1. Project Background

부품 공용화, 설계안 선정과 같은 엔지니어링 의사결정에서는 다음과 같은 여러 조건을 동시에 검토해야 합니다.

- 개발기간
- 원가
- 품질
- 호환성
- 고객체감
- 향후 플랫폼 적용성
- 기타 프로젝트별 요구조건

하지만 자료가 PDF, Excel 등 여러 문서에 분산되어 있으면 필요한 정보를 다시 정리하고 후보별 Trade-off를 비교하는 과정에 시간이 소요됩니다.

이를 개선하기 위해,

> **개발자료 → 판단근거 구조화 → 사용자 검토 → 판단기준 설정 → 후보 비교**

과정을 하나의 Workflow로 연결하는 Engineering Decision Assistant를 개발하고 있습니다.

---

## 2. Core Concept

### Evidence-based Decision Support

단순 점수 계산이 아니라 각 판단값에 다음 정보를 함께 관리합니다.

- Candidate
- Criterion
- Value
- Unit
- Source File
- Page
- Evidence
- Review Status

이를 통해 결과뿐 아니라 **판단 근거까지 추적할 수 있는 구조**를 목표로 합니다.

### Human-in-the-loop

추출된 정보는 바로 의사결정에 사용하지 않습니다.

사용자가 직접

1. 추출 결과 확인
2. 값 수정
3. 근거 확인
4. 승인

과정을 거친 데이터만 최종 판단 데이터로 사용합니다.

---

## 3. Current Features

현재 구현된 기능입니다.

### Document Input
- PDF / Excel 파일 업로드
- PDF 페이지별 텍스트 추출
- PDF 텍스트 추출 상태 검증
- 추출 텍스트 미리보기

### Extraction Criteria
- 기본 추출항목 선택
- 사용자 정의 항목 추가
- 프로젝트별 추출항목 동적 구성

### Evidence Review
- Mock 기반 구조화 추출 결과 생성
- 값 / 단위 분리 저장
- 사용자 화면에서는 값과 단위를 통합 표시
- 출처 파일 / 페이지 / 근거문장 관리
- 사용자 수정
- 최초 추출값 보존
- 개별 승인 / 전체 승인
- Confirmed Evidence Data 생성

### Decision Criteria
- 판단항목별 역할 설정
  - 필수 기준
  - 평가항목
  - 참고항목
- 정량 데이터 평가 방향 설정
- 필수 기준 조건 및 기준값 설정
- 모든 판단항목의 우선순위 설정

### Candidate Comparison
- 판단항목 × 후보 비교표
- 사용자 우선순위에 따른 자동 정렬
- 필수 기준 충족 여부 시각화
  - 충족: 하늘색
  - 미충족: 빨간색
- 필수 기준을 충족하지 못해도 후보를 자동 제거하지 않고 비교 가능

---

## 4. Planned Features

향후 다음 기능을 구현할 예정입니다.

### Interactive Criteria Update
후보 비교 화면에서 기준값을 직접 변경하고 결과 변화를 즉시 확인할 수 있도록 개선합니다.

### Weighted Evaluation
평가항목별 가중치를 설정하고 후보별 종합 평가를 수행합니다.

### Sensitivity Analysis
가중치와 판단조건 변화에 따라 우선 후보가 변경되는 임계점을 분석합니다.

예:

> 현재 조건에서는 후보 A가 우선이지만,  
> 품질 가중치가 5%p 이상 증가하면 후보 B가 우선 후보로 변경됨.

이를 통해 단순 추천이 아니라,

> **어떤 판단기준 때문에 현재 결과가 만들어졌으며, 어떤 조건에서 판단이 바뀌는가**

를 보여주는 Decision Support 기능을 구현하는 것이 목표입니다.

### AI-based Information Extraction
현재는 전체 Workflow 검증을 위해 Mock 데이터를 사용하고 있습니다.

향후 LLM을 연결하여 사용자 지정 판단항목과 문서 내용을 기반으로

- 요청 정보 추출
- 값 / 단위 구조화
- 페이지 / 근거문장 연결
- 사용자가 놓친 중요정보 제안
- 누락 / 충돌 정보 탐지

기능을 구현할 예정입니다.

---

## 5. Technology Stack

- Python
- Streamlit
- Pandas
- PyMuPDF
- OpenPyXL
- Git / GitHub

---

## 6. Development Status

**Status: In Progress**

현재 문서 입력부터 Evidence 검토, 판단기준 설정, 후보 비교까지의 기본 Workflow를 구현했습니다.

다음 개발 단계는 다음과 같습니다.

1. 후보 비교 화면 내 판단기준 실시간 수정
2. 평가항목 가중치 적용
3. 종합 평가
4. 민감도 분석 및 Decision Boundary 탐색
5. 실제 AI 기반 문서 정보 추출
6. Excel 구조화 데이터 연동 및 결과 Export