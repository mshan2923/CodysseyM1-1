# 세피리아 패치 전후 플레이어 수 분석

Steam 게임 **Sephiria**(앱 ID 2436940)의 일별 평균 플레이어 수와 패치 날짜를 이용해 패치 전후 변화를 분석한다.
분석 내용과 결론은 [REPORT.md](REPORT.md)에 있다.

### 배포주소[https://mshan2923.github.io/CodysseyM1-1/]

## 폴더 구조

```
sephiria_analysis/
|-- data/
|   |-- steamdb_chart_Sephira_Max.csv   # 원본 (SteamDB 차트 내보내기, 수정하지 않음)
|   |-- sephiria_patchnotes.csv         # 패치 날짜/제목/메이저 여부 (SteamDB 패치노트 목록 정리)
|   |-- cleaned_data.csv                # 일별 평균 플레이어 수 (정제 결과)
|   |-- patch_analysis.csv              # 패치별 전후 비교 결과
|   `-- outliers.csv                    # 이상치 후보 (제거하지 않고 기록만)
|-- images/                             # 시각화 4개
|-- sephiria_analysis.py                # 분석 코드 (함수 단위로 분리)
|-- REPORT.md
|-- requirements.txt
`-- README.md
```

## 실행 방법

- Python 3.10 이상 (개발 환경: 3.12)

```bash
pip install -r requirements.txt
python sephiria_analysis.py
```

실행하면 `data/`의 `cleaned_data.csv`, `patch_analysis.csv`, `outliers.csv`와 `images/`의 그래프 4개가 다시 만들어진다.
한글 폰트는 Noto Sans CJK(리눅스), 맑은 고딕(Windows), AppleSDGothicNeo(macOS) 순으로 찾으며, 없으면 한글이 깨질 수 있다.

## 코드 구조 (재사용용)

| 함수 | 역할 |
|---|---|
| `load_daily`, `check_data` | 일별 평균 로드, 데이터 점검 |
| `load_patches` | 패치 목록 로드 (같은 날짜 패치는 하루로 묶음) |
| `overall_stats`, `moving_average` | 전체 통계, 이동평균 |
| `analyze_patches` | 패치별 전후 7/14일 비교, 구간별 평균, 지속일, clean/overlap 판정 |
| `weekday_weekend`, `find_outliers` | 요일 비교, 이상치 후보 탐색 |
| `plot_*` | 그래프 4종 |

## 데이터 출처와 주의

- 플레이어 수: [SteamDB](https://steamdb.info/app/2436940/charts/) 차트 CSV
- 패치 목록: [SteamDB 패치노트](https://steamdb.info/app/2436940/patchnotes/)
- SteamDB 데이터의 사용 조건은 SteamDB 이용약관/FAQ를 따른다. 이 저장소의 데이터는 학습·분석 목적의 사본이며 재배포 시 출처 표기와 약관 확인이 필요하다.
