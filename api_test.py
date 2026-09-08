from dotenv import load_dotenv
from openai import OpenAI


# .env 파일의 환경변수 불러오기
load_dotenv()

# OPENAI_API_KEY를 자동으로 읽어 Client 생성
client = OpenAI()


# 최소 API 호출 테스트
response = client.responses.create(
    model="gpt-5.6-luna",
    input="Reply only with: API connection successful"
)


print(response.output_text)
