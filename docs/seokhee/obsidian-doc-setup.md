---
title: Obsidian 문서 관리 지침
version: 1.0.0
created: 2026-04-14
---

# Obsidian 문서 관리 지침

이 파일을 읽고 아래 커맨드와 구조를 설정해줘.

---

## 사전 설정

처음 실행 시 아래 두 가지를 물어보고
~/.claude/config.md 에 저장해줘:

```
OBSIDIAN_VAULT: (Obsidian Vault 경로)
DEV_ROOT: (코드 저장 경로)
```

---

## /doc-init 커맨드 생성

~/.claude/commands/doc-init.md 로 저장.

동작:
1. 프로젝트명 물어보기 (영문, 하이픈 허용)
2. 프로젝트 한 줄 설명 물어보기
3. 아래 구조 생성

### 생성할 구조

#### Obsidian 문서 저장소
$OBSIDIAN_VAULT/Projects/$PROJECT_NAME/
├── INDEX.md
├── daily/
├── weekly/
└── monthly/

#### 프로젝트 코드 문서 폴더
$DEV_ROOT/$PROJECT_NAME/
├── .claudeignore
├── CLAUDE.md
└── docs/
    ├── requirements/
    │   ├── README.md
    │   ├── functional.md
    │   └── user-stories.md
    ├── planning/
    │   ├── business-analysis.md
    │   ├── user-journey.md
    │   └── glossary.md
    ├── ux/
    │   ├── userflow.md
    │   └── wireframes/
    │       └── ai-prompts/
    │           └── README.md
    ├── architecture/
    │   ├── c4-context.md
    │   └── data-flow.md
    ├── api/
    │   └── swagger.yaml
    └── test/
        ├── test-scenarios.md
        └── checklist.md

---

## 각 파일 초기 내용

### INDEX.md (Obsidian)

```markdown
---
created: YYYY-MM-DD
status: active
tags: [PROJECT_NAME, index]
---

# PROJECT_NAME

## 개요
- 설명: 한 줄 설명
- 시작일: YYYY-MM-DD
- 코드 위치: ~/dev/PROJECT_NAME/

## 진행상황
- [ ] 요구사항 확정
- [ ] 기획/UX 설계
- [ ] 아키텍처 설계
- [ ] 개발 시작
- [ ] 테스트
- [ ] 배포

## 문서
- [[requirements/README]]
- [[planning/business-analysis]]
- [[architecture/c4-context]]

## 작업일지
- [[monthly/YYYY-MM]]
- [[weekly/YYYY-WXX]]
- [[daily/YYYY-MM-DD]]

## 관련 프로젝트
(링크)
```

### CLAUDE.md (코드 폴더)

```markdown
---
project: PROJECT_NAME
created: YYYY-MM-DD
status: active
---

# PROJECT_NAME

## 개요
- 설명: 한 줄 설명
- 시작일: YYYY-MM-DD

## 문서 위치
- 작업일지: $OBSIDIAN_VAULT/Projects/PROJECT_NAME/
- 요구사항: docs/requirements/README.md
- 기획: docs/planning/business-analysis.md
- 아키텍처: docs/architecture/c4-context.md

## 최근 현황
- YYYY-MM-DD: (자동 업데이트)

## 다음 할 일
- [ ] (자동 업데이트)
```

### .claudeignore (코드 폴더)

```
daily/
weekly/
monthly/
*.log
node_modules/
build/
dist/
```

### docs/requirements/README.md

```markdown
---
created: YYYY-MM-DD
status: draft
tags: [PROJECT_NAME, requirements]
---

# 요구사항 정의서

## 기능 요구사항
[[functional]]

## 사용자 스토리
[[user-stories]]
```

### docs/planning/glossary.md

```markdown
---
created: YYYY-MM-DD
tags: [PROJECT_NAME, glossary]
---

# 용어 사전

프로젝트에서 사용하는 핵심 용어 정의.
Claude가 일관된 이해를 위해 이 파일을 참고함.

| 용어 | 정의 |
|------|------|
| (용어) | (정의) |
```

### docs/ux/wireframes/ai-prompts/README.md

```markdown
---
created: YYYY-MM-DD
tags: [PROJECT_NAME, wireframe]
---

# AI 와이어프레임 생성 가이드

## Midjourney
/imagine [화면설명], wireframe style,
mobile app UI, clean design, --ar 9:16

## DALL-E
"모바일 앱 와이어프레임: [화면설명]
스타일: 선 드로잉, 흑백"

## Claude (직접 HTML 생성)
"아래 요구사항으로 HTML 와이어프레임 만들어줘:
[화면설명]"

## 화면 목록
(각 화면별 .md 파일 추가)
```

---

## /today 커맨드 생성

~/.claude/commands/today.md 로 저장.

동작:
1. 현재 프로젝트 CLAUDE.md 읽기
2. $OBSIDIAN_VAULT/Projects/현재프로젝트/daily/YYYY-MM-DD.md 없으면 생성
3. 어제 일지에서 미완료 태스크 이월
4. 오늘 우선순위 3가지 제안
5. 추가할 것 물어보기

생성되는 일지 형식:
```markdown
---
date: YYYY-MM-DD
tags: [PROJECT_NAME, daily]
---

# YYYY-MM-DD

## 오늘 집중 (Top 3)
1.
2.
3.

## 완료 ✅
-

## 진행중 🔄
-

## 블로킹 🚫
-

## 내일 할 일
- [ ]

## 한 줄 회고
```

---

## /wrap 커맨드 생성

~/.claude/commands/wrap.md 로 저장.

동작:
1. 오늘 일지 마무리 섹션 채우기
2. 완료 태스크 ✅ 표시
3. INDEX.md 진행상황 체크박스 업데이트
4. CLAUDE.md 최근 현황 업데이트
5. 내일 할 일 정리

---

## 규칙

1. 모든 md 파일 상단에 frontmatter 포함
   (created, status, tags)
2. Obsidian [[링크]] 문법 사용
3. daily/, weekly/, monthly/ 는
   .claudeignore 에 포함
   (Claude가 읽지 않음 — 토큰 절약)
4. CLAUDE.md 는 500자 이내 핵심만 유지
5. INDEX.md 가 Obsidian Graph 허브 역할

---

## 완료 후 안내

생성 완료 시 아래 출력:
1. 생성된 폴더 트리
2. 첫 번째 할 일:
   - docs/requirements/README.md 작성
   - docs/planning/glossary.md 용어 정의
   - /today 로 오늘 일지 시작
3. 커맨드 목록:
   /doc-init, /today, /wrap
