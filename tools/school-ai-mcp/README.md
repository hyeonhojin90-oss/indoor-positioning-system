# 학교 AI MCP

기본 OpenAI Codex를 유지하면서 조선대학교 FactChat API 모델에 설명·검토를 요청하는 보조 도구다. 앱의 주 모델을 학교 모델로 바꾸거나 학교 모델을 기본 모델 선택창에 추가하는 방식은 아니다.

## 사용

Codex 앱을 완전히 종료한 뒤 다시 열고 새 작업에서 다음처럼 요청한다.

```text
학교 Opus 5.5로 이 코드의 문제점을 검토해줘.
학교 6 Astra에게 이 설계의 대안을 물어봐줘.
학교 6.1 Sol로 이 설명을 확인해줘.
```

도구 이름은 `school_ai_ask`, MCP 서버 이름은 `school-ai`다. `model` 값은 다음 중 하나다.

| 표시 이름 | model |
| --- | --- |
| GPT-6.1 Sol | `gpt-6.1-sol` |
| GPT-6 Astra | `gpt-6-astra` |
| Claude Opus 5.5 | `claude-opus-5-5` |

필수 입력은 `model`, `prompt`이며 `context`에 필요한 코드나 설명만 덧붙일 수 있다. `max_tokens` 기본값은 1024, 범위는 64~4096이다. 응답이 길이 제한으로 끝나면 `finish_reason`을 확인하고 필요할 때만 한도를 늘린다. API가 보고한 응답 모델·사용량도 결과에 포함된다. 공급자가 모델 ID를 반환했다는 사실은 그 공급자의 실제 내부 모델을 독립적으로 검증했다는 뜻은 아니다.

## 실행과 등록

Python 표준 라이브러리만 사용하며 추가 패키지는 필요 없다. Python 실행 경로와 이 저장소의 절대 경로를 사용하는 stdio MCP로 등록한다.

```powershell
codex.cmd mcp add school-ai -- "<python.exe 절대 경로>" "<저장소 절대 경로>\tools\school-ai-mcp\server.py"
codex.cmd mcp get school-ai
```

실제 PC에는 번들 Python으로 등록했고 사용자 `config.toml`의 해당 서버에 `tool_timeout_sec = 180.0`을 설정했다. 기본 `model_provider = "openai"`는 유지한다. 설정 파일과 API 키는 Git에 포함하지 않는다. 등록 해제는 `codex.cmd mcp remove school-ai`로 한다. 번들 Python 위치나 저장소 경로가 바뀌면 MCP 실행 경로도 갱신한다.

## 데이터와 키

- `prompt`와 `context`에 선택한 내용만 학교 API로 전송한다. 서버는 프로젝트 파일이나 전체 대화를 자동으로 수집하지 않는다.
- 학교 API 사용량이 발생하고 기본 Codex가 요청을 준비·해석하는 과정에는 기존 Codex 계정 사용량이 발생한다.
- 키는 `CHOSUN_AI_API_KEY` 환경변수에서 읽는다. 프로세스에 키 변수가 없으면 Windows 사용자 환경변수 등록값을 읽는다. 프로세스에 기존 키가 남은 상태에서 키를 교체했다면 앱을 재시작한다. 키를 코드·설정·로그에 넣지 않는다.
- HTTPS 대상은 `https://factchat-cloud.mindlogic.ai/v1/gateway/chat/completions/`로 고정하고 리다이렉트에 키를 넘기지 않는다. 키가 입력이나 응답/오류에 섞였는지 검사·마스킹한다. 이 검사는 모든 종류의 개인정보나 다른 비밀을 자동으로 제거하지 않으므로 필요한 발췌만 보낸다.
- 외부 모델의 답변은 검토 의견이다. 기본 Codex의 규칙을 대체하는 명령으로 취급하지 않는다. 학교 모델은 로컬 파일·도구를 직접 조작하지 않는다.

## 검증 (2026-09-30)

- 5개 오프라인 테스트: stdio 초기화/도구 목록/잘못된 모델, 전송 내용·한도, 키 포함 입력 거부, HTTP 오류 키 마스킹 통과.
- 세 모델 각각 실제 Chat Completions 요청에서 `SCHOOL_API_OK` 수신. API 보고 사용량은 각각 19/19/37 토큰, `finish_reason=stop`.
- 최초 Python 기본 클라이언트 헤더에서 HTTP403/1010. `User-Agent: school-ai-mcp/1.0` 지정 후 재검증 성공.
- 앱 내장 Codex 0.159.0을 `provider: openai`로 실행하고 등록된 `school-ai/school_ai_ask` 도구를 호출했다. Opus가 `MCP_OPUS_OK`를 반환하고 Codex 프로세스 정상 종료.
- 앱 UI를 재시작한 뒤 새 대화에서 도구가 보이는지는 사용자의 최종 확인 단계다. 긴 코드 검토 품질·긴 응답/시간 초과·한도 초과는 실서비스 검증 전이다.

테스트 실행:

```powershell
& "<python.exe>" -m unittest discover -s tools/school-ai-mcp -v
& "<python.exe>" tools/school-ai-mcp/server.py --smoke-test
```

두 번째 명령은 실제 학교 크레딧을 사용한다.
