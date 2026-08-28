# GLB 검사 도구

이 페이지는 `indoor/web`의 3층 GLB와 도구 폴더의 4층 GLB를 함께 불러오므로 프로젝트 루트를 기준으로 서버를 실행한다.

```powershell
cd "C:\Users\20222967\Documents\ChatGPT\자율설계 2"
python -m http.server 4175 --bind 127.0.0.1
```

브라우저에서 다음 주소를 연다.

```text
http://127.0.0.1:4175/indoor/tools/glb-viewer/index.html
```

각 스캔을 선택하고 모델 요청이 404 없이 완료되는지 확인한다.
