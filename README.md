# Naver Keyword MCP Server

네이버 검색광고 API를 활용한 키워드 조회 MCP 서버

## 기능

- 연관 키워드 조회
- 월간 검색량 (PC/모바일)
- 경쟁 강도 분석

## 환경변수

Railway에서 다음 환경변수 설정 필요:

```
NAVER_CUSTOMER_ID=your_customer_id
NAVER_API_KEY=your_api_key
NAVER_SECRET_KEY=your_secret_key
```

## 엔드포인트

- `GET /` - 서버 상태
- `GET /health` - 헬스체크
- `POST /mcp` - MCP JSON-RPC
- `GET /api/keywords/{keyword}` - REST API (테스트용)
