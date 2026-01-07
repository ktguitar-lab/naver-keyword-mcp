"""
네이버 키워드 MCP 서버
Claude에서 연관 키워드를 조회할 수 있는 MCP 서버
"""

import os
import time
import hmac
import hashlib
import base64
import json
import requests
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

app = FastAPI(title="Naver Keyword MCP Server")

# 환경변수에서 API 키 로드
CUSTOMER_ID = os.getenv("NAVER_CUSTOMER_ID", "")
API_KEY = os.getenv("NAVER_API_KEY", "")
SECRET_KEY = os.getenv("NAVER_SECRET_KEY", "")

BASE_URL = "https://api.naver.com"

def generate_signature(timestamp, method, path):
    """HMAC-SHA256 서명 생성"""
    message = f"{timestamp}.{method}.{path}"
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode('utf-8')

def get_related_keywords(keyword: str):
    """네이버 API에서 연관 키워드 조회"""
    timestamp = str(int(time.time() * 1000))
    path = "/keywordstool"
    method = "GET"
    
    signature = generate_signature(timestamp, method, path)
    
    headers = {
        "X-API-KEY": API_KEY,
        "X-CUSTOMER": CUSTOMER_ID,
        "X-Timestamp": timestamp,
        "X-Signature": signature
    }
    
    params = {
        "hintKeywords": keyword,
        "showDetail": "1"
    }
    
    response = requests.get(
        BASE_URL + path,
        headers=headers,
        params=params
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"API 오류: {response.status_code}", "detail": response.text}

def format_keywords(data: dict, keyword: str, top_n: int = 15):
    """키워드 결과를 읽기 좋게 포맷"""
    if "error" in data:
        return data
    
    if "keywordList" not in data:
        return {"error": "키워드 데이터 없음"}
    
    keywords = data["keywordList"]
    
    # 검색량 기준 정렬
    keywords_sorted = sorted(
        keywords,
        key=lambda x: (int(x.get("monthlyPcQcCnt", 0)) if str(x.get("monthlyPcQcCnt", 0)).isdigit() else 0) +
                      (int(x.get("monthlyMobileQcCnt", 0)) if str(x.get("monthlyMobileQcCnt", 0)).isdigit() else 0),
        reverse=True
    )
    
    result = []
    for kw in keywords_sorted[:top_n]:
        pc = kw.get("monthlyPcQcCnt", 0)
        mobile = kw.get("monthlyMobileQcCnt", 0)
        pc_val = 0 if str(pc) == "< 10" else int(pc) if str(pc).isdigit() else 0
        mobile_val = 0 if str(mobile) == "< 10" else int(mobile) if str(mobile).isdigit() else 0
        
        result.append({
            "keyword": kw.get("relKeyword", ""),
            "monthlySearches": pc_val + mobile_val,
            "pcSearches": pc_val,
            "mobileSearches": mobile_val,
            "competition": kw.get("compIdx", "")
        })
    
    return {
        "searchKeyword": keyword,
        "totalResults": len(keywords),
        "topKeywords": result
    }

# MCP 프로토콜 구현
TOOLS = [
    {
        "name": "get_naver_keywords",
        "description": "네이버 검색광고 API를 사용하여 키워드의 연관 키워드와 월간 검색량을 조회합니다. 블로그 제목 최적화, SEO 키워드 분석에 활용할 수 있습니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "검색할 키워드 (예: 소상공인 대환대출, 청년창업지원금)"
                },
                "top_n": {
                    "type": "integer",
                    "description": "반환할 상위 키워드 개수 (기본값: 15)",
                    "default": 15
                }
            },
            "required": ["keyword"]
        }
    }
]

@app.get("/")
async def root():
    return {"status": "ok", "service": "Naver Keyword MCP Server"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/mcp")
async def mcp_sse(request: Request):
    """MCP SSE 엔드포인트"""
    async def event_generator():
        # 초기 연결 메시지
        yield f"data: {json.dumps({'jsonrpc': '2.0', 'method': 'initialized'})}\n\n"
        
        # 연결 유지
        while True:
            if await request.is_disconnected():
                break
            yield ": keepalive\n\n"
            await asyncio.sleep(30)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.post("/mcp")
async def mcp_post(request: Request):
    """MCP JSON-RPC 엔드포인트"""
    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    request_id = body.get("id")
    
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "naver-keyword-mcp",
                    "version": "1.0.0"
                }
            }
        })
    
    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": TOOLS
            }
        })
    
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if tool_name == "get_naver_keywords":
            keyword = arguments.get("keyword", "")
            top_n = arguments.get("top_n", 15)
            
            if not keyword:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": "키워드를 입력해주세요."}]
                    }
                })
            
            # API 호출
            raw_data = get_related_keywords(keyword)
            formatted = format_keywords(raw_data, keyword, top_n)
            
            if "error" in formatted:
                result_text = f"오류: {formatted['error']}"
            else:
                lines = [
                    f"🔍 '{formatted['searchKeyword']}' 연관 키워드 분석 결과",
                    f"총 {formatted['totalResults']}개 키워드 중 상위 {len(formatted['topKeywords'])}개",
                    "",
                    "순위 | 키워드 | 월간검색량 | 경쟁강도",
                    "---|---|---|---"
                ]
                for i, kw in enumerate(formatted['topKeywords'], 1):
                    lines.append(f"{i} | {kw['keyword']} | {kw['monthlySearches']:,} | {kw['competition']}")
                
                result_text = "\n".join(lines)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}]
                }
            })
    
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"}
    })

# 간단한 REST API도 제공 (테스트용)
@app.get("/api/keywords/{keyword}")
async def api_keywords(keyword: str, top_n: int = 15):
    """REST API 엔드포인트 (테스트용)"""
    raw_data = get_related_keywords(keyword)
    return format_keywords(raw_data, keyword, top_n)

if __name__ == "__main__":
    import asyncio
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
