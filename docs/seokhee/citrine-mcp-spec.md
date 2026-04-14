# CitrineOS PostgreSQL MCP 서버 구현 지침서
> CitrineOS OCPP DB (PostgreSQL) 를 Claude Desktop / Claude Code 에서 MCP 도구로 사용
> 작성일: 2026-04-14
> Claude Code에게 전달하는 구현 명세서

---

## 개발 현황 범례

| 기호 | 의미 |
|---|---|
| ✅ | 개발 완료 |
| 🔧 | 개발 중 |
| ⬜ | 미개발 |

---

## 1. 접속 정보

```
Host:     localhost
Port:     5432
User:     citrine
Password: citrine
Database: citrine
DSN:      postgres://citrine:citrine@localhost:5432/citrine

Docker 내부 접속 시:
DSN:      postgres://citrine:citrine@ocpp-db:5432/citrine
```

---

## 2. 프로젝트 구조

```
citrine-mcp/
├── citrine_mcp.py      # MCP 서버 메인
├── .env                # 접속 정보 (chmod 600)
├── .env.example        # 예시 (git 포함)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 3. 구현 명세

### ⬜ CORE-001: 기본 구조 및 DB 연결

```python
# citrine_mcp.py
from fastmcp import FastMCP
import psycopg2
import psycopg2.extras
import os
import json
import re
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

mcp = FastMCP("citrine-ocpp-db")

# 접속 정보
DB_CONFIG = {
    "host":     os.getenv("PG_HOST",     "localhost"),
    "port":     int(os.getenv("PG_PORT", "5432")),
    "user":     os.getenv("PG_USER",     "citrine"),
    "password": os.getenv("PG_PASS",     "citrine"),
    "dbname":   os.getenv("PG_DB",       "citrine"),
    "connect_timeout": 10,
    "options":  "-c search_path=public",
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

if __name__ == "__main__":
    mcp.run()
```

### ⬜ CORE-002: 쿼리 안전성 검사

```python
ALLOWED = {"select", "show", "explain", "with", "table"}
BLOCKED = {
    "insert", "update", "delete", "drop", "create",
    "alter", "truncate", "replace", "rename",
    "grant", "revoke", "copy", "call", "do",
}

def is_safe(sql: str) -> tuple[bool, str]:
    clean = sql.strip().lower()
    if not clean:
        return False, "빈 쿼리입니다."
    first = clean.split()[0]
    if first not in ALLOWED:
        return False, f"'{first}' 는 허용되지 않습니다. SELECT / EXPLAIN 만 가능합니다."
    for kw in BLOCKED:
        if re.search(rf'\b{kw}\b', clean):
            return False, f"'{kw}' 키워드는 허용되지 않습니다."
    if clean.count(";") > 1:
        return False, "다중 쿼리(;)는 허용되지 않습니다."
    return True, "ok"
```

### ⬜ TOOL-001: 연결 상태 확인

```python
@mcp.tool()
def check_connection() -> str:
    """CitrineOS DB 연결 상태 및 서버 정보 확인"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        cur.execute("SELECT current_database(), current_user")
        db, user = cur.fetchone()
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        table_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return (
            f"✅ CitrineOS DB 연결 정상\n"
            f"버전: {version[:40]}\n"
            f"DB: {db}  사용자: {user}\n"
            f"테이블 수: {table_count}개"
        )
    except Exception as e:
        return f"❌ 연결 실패: {e}"
```

### ⬜ TOOL-002: 테이블 목록 조회

```python
@mcp.tool()
def list_tables() -> str:
    """citrine DB의 전체 테이블 목록과 행 수 조회"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                t.table_name,
                obj_description(
                    (quote_ident(t.table_schema)||'.'||
                     quote_ident(t.table_name))::regclass, 'pg_class'
                ) AS comment
            FROM information_schema.tables t
            WHERE t.table_schema = 'public'
              AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
        """)
        tables = cur.fetchall()
        cur.close()
        conn.close()

        if not tables:
            return "테이블이 없습니다."

        result = f"총 {len(tables)}개 테이블 (citrine DB):\n\n"
        for name, comment in tables:
            note = f"  ← {comment}" if comment else ""
            result += f"  • {name}{note}\n"
        return result
    except Exception as e:
        return f"❌ 오류: {e}"
```

### ⬜ TOOL-003: 테이블 구조 조회

```python
@mcp.tool()
def describe_table(table_name: str) -> str:
    """
    테이블 컬럼 구조, 타입, 제약조건, 인덱스 조회

    Args:
        table_name: 테이블 이름 (예: Transaction, ChargingStation)
    """
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 컬럼 정보
        cur.execute("""
            SELECT
                c.column_name,
                c.data_type,
                c.character_maximum_length,
                c.is_nullable,
                c.column_default,
                col_description(
                    (quote_ident(c.table_schema)||'.'||
                     quote_ident(c.table_name))::regclass,
                    c.ordinal_position
                ) AS comment
            FROM information_schema.columns c
            WHERE c.table_schema = 'public'
              AND c.table_name = %s
            ORDER BY c.ordinal_position
        """, (table_name,))
        columns = cur.fetchall()

        if not columns:
            return f"테이블 '{table_name}' 을 찾을 수 없습니다."

        # 행 수
        cur.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        )
        row_count = cur.fetchone()[0]

        # 인덱스
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = %s
        """, (table_name,))
        indexes = cur.fetchall()

        # 외래키
        cur.execute("""
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = %s
        """, (table_name,))
        fkeys = cur.fetchall()

        cur.close()
        conn.close()

        # 포맷팅
        result = f"테이블: {table_name} ({row_count:,}행)\n\n"
        result += "컬럼:\n"
        for col in columns:
            dtype = col["data_type"]
            if col["character_maximum_length"]:
                dtype += f"({col['character_maximum_length']})"
            nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
            default = f" DEFAULT {col['column_default']}" \
                      if col["column_default"] else ""
            comment = f"  -- {col['comment']}" if col["comment"] else ""
            result += (f"  {col['column_name']:<30} "
                      f"{dtype:<20} {nullable}{default}{comment}\n")

        if indexes:
            result += "\n인덱스:\n"
            for idx_name, idx_def in indexes:
                result += f"  {idx_name}\n"

        if fkeys:
            result += "\n외래키:\n"
            for col, ftable, fcol in fkeys:
                result += f"  {col} → {ftable}.{fcol}\n"

        return result
    except Exception as e:
        return f"❌ 오류: {e}"
```

### ⬜ TOOL-004: 쿼리 실행

```python
@mcp.tool()
def execute_query(sql: str, limit: int = 100) -> str:
    """
    SELECT 쿼리 실행 (읽기 전용)

    Args:
        sql:   실행할 SELECT 쿼리
        limit: 최대 행 수 (기본 100, 최대 500)
    """
    safe, reason = is_safe(sql)
    if not safe:
        return f"⛔ 차단됨: {reason}"

    limit = min(limit, 500)
    # LIMIT 자동 추가
    if sql.strip().lower().startswith("select") \
            and "limit" not in sql.lower():
        sql = sql.rstrip(";") + f" LIMIT {limit}"

    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return "결과 없음 (0행)"

        result = json.dumps(
            [dict(r) for r in rows],
            ensure_ascii=False,
            default=str,
            indent=2
        )
        return f"{len(rows)}행 반환:\n{result}"
    except psycopg2.Error as e:
        return f"❌ DB 오류: {e.pgerror or str(e)}"
    except Exception as e:
        return f"❌ 오류: {str(e)}"
```

### ⬜ TOOL-005: OCPP 특화 — 충전기 목록

```python
@mcp.tool()
def list_charging_stations() -> str:
    """
    등록된 충전기 목록 조회 (CitrineOS OCPP 특화)
    """
    sql = """
        SELECT
            id,
            "isOnline",
            "lastSeen",
            "createdAt"
        FROM "ChargingStation"
        ORDER BY "lastSeen" DESC NULLS LAST
        LIMIT 100
    """
    return execute_query(sql)
```

### ⬜ TOOL-006: OCPP 특화 — 최근 트랜잭션

```python
@mcp.tool()
def list_recent_transactions(limit: int = 20) -> str:
    """
    최근 OCPP 충전 트랜잭션 목록 조회

    Args:
        limit: 조회할 건수 (기본 20)
    """
    limit = min(limit, 100)
    sql = f"""
        SELECT
            id,
            "stationId",
            "evseid",
            "chargingState",
            "timeSpentCharging",
            "totalKwh",
            "stoppedReason",
            "createdAt",
            "updatedAt"
        FROM "Transaction"
        ORDER BY "createdAt" DESC
        LIMIT {limit}
    """
    return execute_query(sql)
```

### ⬜ TOOL-007: OCPP 특화 — 충전기 상태 요약

```python
@mcp.tool()
def station_status_summary() -> str:
    """충전기 온라인/오프라인 현황 요약"""
    sql = """
        SELECT
            "isOnline",
            COUNT(*) as count
        FROM "ChargingStation"
        GROUP BY "isOnline"
    """
    return execute_query(sql)
```

### ⬜ TOOL-008: 샘플 데이터 조회

```python
@mcp.tool()
def sample_data(table_name: str, rows: int = 5) -> str:
    """
    테이블 샘플 데이터 조회

    Args:
        table_name: 테이블 이름
        rows:       조회 행 수 (기본 5, 최대 20)
    """
    rows = min(rows, 20)
    return execute_query(
        f'SELECT * FROM "{table_name}" LIMIT {rows}'
    )
```

### ⬜ TOOL-009: 쿼리 실행 계획

```python
@mcp.tool()
def explain_query(sql: str) -> str:
    """
    쿼리 실행 계획 분석 (성능 확인용)

    Args:
        sql: 분석할 SELECT 쿼리
    """
    safe, reason = is_safe(sql)
    if not safe:
        return f"⛔ 차단됨: {reason}"
    return execute_query(f"EXPLAIN ANALYZE {sql}")
```

---

## 4. 설정 파일

### ⬜ CONFIG-001: .env 파일

```bash
# .env — chmod 600 필수
PG_HOST=localhost
PG_PORT=5432
PG_USER=citrine
PG_PASS=citrine
PG_DB=citrine
```

### ⬜ CONFIG-002: requirements.txt

```
fastmcp>=0.1.0
psycopg2-binary>=2.9.0
python-dotenv>=1.0.0
```

### ⬜ CONFIG-003: Claude Desktop 설정

```json
// ~/.config/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "citrine-ocpp-db": {
      "command": "python3",
      "args": ["/home/caram88/citrine-mcp/citrine_mcp.py"],
      "env": {}
    }
  }
}
```

---

## 5. 도구 목록 전체 요약

| 도구명 | 기능 | 상태 |
|---|---|---|
| `check_connection` | DB 연결 확인 | ⬜ |
| `list_tables` | 테이블 목록 | ⬜ |
| `describe_table` | 컬럼/인덱스/FK 구조 | ⬜ |
| `execute_query` | SELECT 쿼리 실행 | ⬜ |
| `sample_data` | 샘플 데이터 조회 | ⬜ |
| `explain_query` | 실행 계획 분석 | ⬜ |
| `list_charging_stations` | 충전기 목록 | ⬜ |
| `list_recent_transactions` | 최근 트랜잭션 | ⬜ |
| `station_status_summary` | 충전기 상태 요약 | ⬜ |

---

## 6. Claude Code 실행 명령

```bash
mkdir -p ~/citrine-mcp
cd ~/citrine-mcp
claude

# Claude Code에게 입력:
"citrine-mcp-spec.md 파일을 읽고 전체 구현해줘.

 접속 정보:
 - DSN: postgres://citrine:citrine@localhost:5432/citrine
 - docker 내부: postgres://citrine:citrine@ocpp-db:5432/citrine

 구현 순서:
 1. requirements.txt, .gitignore, .env, .env.example 생성
    → .env 는 chmod 600 자동 적용
 2. citrine_mcp.py 전체 구현
    → CORE-001: 기본 구조
    → CORE-002: 쿼리 안전성 검사
    → TOOL-001~009: 전체 도구 구현
 3. psycopg2-binary 설치 확인:
    pip install psycopg2-binary fastmcp python-dotenv
 4. Docker OCPP DB 실행 여부 확인:
    docker ps | grep ocpp-db
 5. 연결 테스트:
    python3 citrine_mcp.py
 6. Claude Desktop config 업데이트:
    ~/.config/Claude/claude_desktop_config.json

 보안:
 - SELECT / EXPLAIN 만 허용
 - INSERT/UPDATE/DELETE/DROP 차단
 - .env chmod 600

 구현 완료 항목은 ⬜ → ✅ 로 spec 파일 업데이트해줘."
```

---

## 7. 테스트 시나리오

```
# Claude Desktop 재시작 후

# 테스트 1: 연결
"CitrineOS DB 연결 확인해줘"
→ ✅ citrine DB 연결 정상 출력

# 테스트 2: 테이블 목록
"어떤 테이블들이 있어?"
→ ChargingStation, Transaction 등 목록 출력

# 테스트 3: OCPP 구조 파악
"Transaction 테이블 구조 보여줘"
→ 컬럼, 타입, 외래키 출력

# 테스트 4: 충전기 현황
"현재 등록된 충전기 목록 보여줘"
→ list_charging_stations 호출

# 테스트 5: 트랜잭션 조회
"최근 충전 세션 10건 보여줘"
→ list_recent_transactions(10) 호출

# 테스트 6: 자연어 쿼리
"오늘 충전된 총 kWh 합계를 구해줘"
→ Claude가 쿼리 생성 후 execute_query 호출

# 테스트 7: 보안 차단
"DELETE FROM Transaction"
→ ⛔ 차단됨 출력 (정상)
```

---

*이 사양서는 Claude Code가 CitrineOS PostgreSQL MCP 서버를 구현하기 위한 명세입니다.*
*구현 완료 시 각 항목을 ⬜ → ✅ 로 업데이트하세요.*
