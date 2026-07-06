"""
🍨 아이스크림 컨셉 설계 어시스턴트 v2
근거자료: H. Douglas Goff & Richard W. Hartel, "Ice Cream" 7th Edition (Springer, 2013)

구조:
  STEP 0. 조성 (옵션, 기본값=아이스크림)
  STEP 1. 형태 (텁 → 스틱바 → 샌드위치 → 익스트루더·몰드 → 케이크)
  STEP 2. 형태별 분기 (형태를 고르면 해당 하위 카테고리만 표시)
  STEP 3. AI 컨셉 브리프 생성 → 대화로 다듬기
"""

import streamlit as st
from anthropic import Anthropic
import json
import re
from datetime import date

st.set_page_config(page_title="아이스크림 컨셉 설계 어시스턴트", page_icon="🍨", layout="wide")

MODEL = "claude-opus-4-6"
SOURCE = 'H. Douglas Goff & Richard W. Hartel, "Ice Cream" 7th Edition (Springer, 2013)'

# ===========================================================================
# 1. 조성 (STEP 0) — 기본값: 아이스크림
# ===========================================================================
COMPOSITIONS = [
    {"id": "ice_cream", "name": "아이스크림 (기본)",
     "detail": "유지방 10~16% 스펙트럼. 이코노미→레귤러→프리미엄→슈퍼프리미엄", "chapter": "Ch.2 Table 2.4"},
    {"id": "frozen_custard", "name": "프로즌커스터드 / 프렌치",
     "detail": "난황고형분 최소 1.4% (벌키플레이버 1.12%)", "chapter": "Ch.2"},
    {"id": "gelato", "name": "젤라또",
     "detail": "지방 4–8%, overrun 25–60%, 당 최대 25%(고맥아당시럽 포함)", "chapter": "Ch.2, 15"},
    {"id": "frozen_yogurt", "name": "프로즌요거트 (발효)",
     "detail": "전형: 지방 2%, MSNF 14%, 당 15%, 안정제 0.35%, 산도 0.30%(젖산 기준)", "chapter": "Ch.2, 15"},
    {"id": "sherbet", "name": "셔벗",
     "detail": "유고형분 5% 이하(지방 1–2%, MSNF 3–4%), 산도 0.35%↑, 총고형분 32–35%, overrun ~50%", "chapter": "Ch.2, 15"},
    {"id": "water_ice_sorbet", "name": "소르베 / 워터아이스 (빙과)",
     "detail": "유제품 미포함. 워터아이스 전형: 당 14%, CSS 3.5%, 안정제 0.4%, 구연산 0.25%. 소르베는 과일 25%↑(Euroglaces)", "chapter": "Ch.2, 15"},
    {"id": "nondairy", "name": "논데어리 / 식물성",
     "detail": "멜로린 기준 지방 6%↑, 단백질 2.7%↑ (식물성 지방 대체)", "chapter": "Ch.2"},
]

# ===========================================================================
# 2. 형태 (STEP 1) — 순서: 텁 → 스틱바 → 샌드위치 → 익스트루더·몰드 → 케이크
# ===========================================================================
FORMATS = [
    {"id": "tub", "name": "🥡 텁 (3갤런/11.35L 벌크)", "default": True,
     "detail": "스쿠핑샵용 벌크 텁 기본 3갤런 = 384 fl oz ≈ 11.35L (배스킨라빈스 스타일). 텁 내부 2~3포션 구성 가능, 하드프리즌",
     "suggest": "지방 10–16% · 총고형분 36.5–41.65% · Overrun 90–100%", "chapter": "Ch.2"},
    {"id": "stick_bar", "name": "🍡 스틱바",
     "detail": "핸드헬드 노벨티. 몰드형(정치동결) 또는 압출형",
     "suggest": "코팅·코어 구조에 따라 배합 조정. 프리미엄 바는 overrun 40–50%", "chapter": "Ch.9"},
    {"id": "sandwich", "name": "🍪 샌드위치",
     "detail": "비스킷/웨이퍼 사이 아이스크림. 수분전이 관리가 핵심",
     "suggest": "지방 10–12% · 총고형분 36–38%", "chapter": "Ch.9, 12"},
    {"id": "extruded_molded", "name": "🧊 익스트루더 / 몰드 제품",
     "detail": "압출 성형(자유 형태) 또는 팬시 몰드(캐릭터·기념일 형태)",
     "suggest": "압출: 성형 자유도↑, 저온 압출 시 조직 치밀. 몰드: 정치동결, 워터아이스류 적합", "chapter": "Ch.9"},
    {"id": "cake", "name": "🎂 아이스크림 케이크",
     "detail": "멀티포션. 레이어 구조 안정성·절단 텍스처·유통 형태유지가 핵심",
     "suggest": "레이어별 조성 상이 가능", "chapter": "Ch.9"},
]

# ===========================================================================
# 3. 형태별 분기 (STEP 2)
#    -- 각 형태 선택 시 해당 하위 카테고리만 렌더링 --
# ===========================================================================
CONFECTION_OPTIONS = [
    {"id": "none", "name": "없음"},
    {"id": "choco_chip", "name": "초콜릿칩 / 청크", "detail": "저장 중 오일 마이그레이션 체크", "chapter": "Ch.4, 12"},
    {"id": "caramel_chip", "name": "카라멜 / 토피 칩", "detail": "수분 전이로 인한 눅눅함 방지 조치 필요", "chapter": "Ch.4, 12"},
    {"id": "nuts", "name": "넛츠 (아몬드·피칸·피스타치오 등)", "detail": "알러지 표기 의무", "chapter": "Ch.4"},
    {"id": "bakery", "name": "쿠키 / 베이커리 조각", "detail": "수분 이행 시 눅눅해짐 리스크", "chapter": "Ch.4, 12"},
    {"id": "candy", "name": "캔디 피스 (버터크런치·페퍼민트 등)", "chapter": "Ch.4"},
    {"id": "fruit", "name": "과일 (생과·냉동·프리저브)", "detail": "과일 내 수분·당이 빙점과 조직에 영향", "chapter": "Ch.4"},
]

RIBBON_OPTIONS = [
    {"id": "none", "name": "없음"},
    {"id": "fudge", "name": "퍼지 / 초콜릿", "chapter": "Ch.2 Variegated"},
    {"id": "caramel", "name": "카라멜 / 버터스카치", "detail": "당류 조성이 빙점강하(FPD)에 영향 — Ch.6 계산 필요", "chapter": "Ch.2, 6"},
    {"id": "fruit_syrup", "name": "과일 시럽 (스트로베리 등)", "chapter": "Ch.2 Variegated"},
    {"id": "marshmallow", "name": "마시멜로", "chapter": "Ch.2"},
]

FORMAT_BRANCHES = {
    "tub": [
        # 텁의 포션 구성(플레이버 개수·배치·색상)은 전용 UI에서 처리 (아래 STEP 2 참조)
        {"id": "confection", "title": "컨펙션 종류", "type": "multi", "options": CONFECTION_OPTIONS},
        {"id": "ribbon", "title": "리본(버라이어게이트) 종류", "type": "single", "options": RIBBON_OPTIONS},
    ],
    "stick_bar": [
        {"id": "coating", "title": "코팅 유무 · 종류", "type": "single", "options": [
            {"id": "none", "name": "코팅 없음"},
            {"id": "chocolate", "name": "초콜릿 엔로빙", "detail": "경화속도·부착성·균열/박리 방지가 핵심", "chapter": "Ch.9"},
            {"id": "compound", "name": "컴파운드 코팅 (화이트/컬러)", "chapter": "Ch.9"},
            {"id": "crunch", "name": "크런치 코팅 (넛츠·크리스피 부착)", "detail": "부착 수율 관리, 알러지 표기", "chapter": "Ch.9"},
            {"id": "double", "name": "더블 코팅 (2중)", "detail": "층간 경화 타이밍 제어", "chapter": "Ch.9"},
        ]},
        {"id": "confection", "title": "컨펙션 종류", "type": "multi", "options": CONFECTION_OPTIONS},
        {"id": "ribbon_core", "title": "리본 · 코어", "type": "single", "options": [
            {"id": "none", "name": "없음"},
            {"id": "core_inject", "name": "코어 주입 (카라멜·초코 등)", "detail": "코어 점도·동결온도가 쉘과 달라야 흐름성 확보. 누출·상분리 리스크", "chapter": "Ch.11"},
            {"id": "swirl", "name": "스월", "detail": "시럽 점도-베이스 매칭", "chapter": "Ch.2, 4"},
        ]},
        {"id": "make_type", "title": "제조 형태", "type": "single", "options": [
            {"id": "molded", "name": "몰드형 (정치동결)", "detail": "몰드 이탈·스틱 삽입이 공정 변수. 워터아이스류 적합", "chapter": "Ch.9"},
            {"id": "extruded", "name": "압출형", "detail": "저온 압출로 치밀한 조직, 성형 자유도 높음, 설비투자 큼", "chapter": "Ch.9"},
        ]},
    ],
    "sandwich": [
        {"id": "biscuit", "title": "비스킷 종류", "type": "single", "options": [
            {"id": "choco_wafer", "name": "초코 웨이퍼 (클래식)"},
            {"id": "cookie", "name": "청크 쿠키", "detail": "수분전이로 인한 눅눅해짐 관리 필수", "chapter": "Ch.12"},
            {"id": "macaron", "name": "마카롱", "detail": "흡습성 높음 — 장벽처리 검토"},
            {"id": "waffle", "name": "와플"},
        ]},
        {"id": "side_coating", "title": "측면 코팅", "type": "single", "options": [
            {"id": "none", "name": "없음"},
            {"id": "choco_dip", "name": "초코 디핑"},
            {"id": "crunch_roll", "name": "크런치 굴리기 (칩 부착)", "detail": "부착 수율 관리"},
        ]},
        {"id": "confection", "title": "내부 컨펙션", "type": "multi", "options": CONFECTION_OPTIONS},
        {"id": "ribbon", "title": "내부 리본", "type": "single", "options": RIBBON_OPTIONS},
        {"id": "shape", "title": "형태", "type": "single", "options": [
            {"id": "round", "name": "원형"},
            {"id": "square", "name": "사각"},
            {"id": "bar", "name": "바형"},
        ]},
    ],
    "extruded_molded": [
        {"id": "shape", "title": "성형 형태", "type": "single", "options": [
            {"id": "bar", "name": "바"},
            {"id": "ball", "name": "볼 / 비셔형"},
            {"id": "fancy", "name": "캐릭터 · 팬시 몰드", "detail": "Ch.2 'Fancy molded' — 과일·기념일 형태", "chapter": "Ch.2, 9"},
            {"id": "cone", "name": "콘형"},
            {"id": "roll", "name": "롤"},
        ]},
        {"id": "coating", "title": "코팅", "type": "single", "options": [
            {"id": "none", "name": "없음"},
            {"id": "chocolate", "name": "초콜릿 엔로빙", "chapter": "Ch.9"},
            {"id": "compound", "name": "컴파운드 코팅"},
        ]},
        {"id": "confection", "title": "컨펙션", "type": "multi", "options": CONFECTION_OPTIONS},
        {"id": "ribbon", "title": "리본", "type": "single", "options": RIBBON_OPTIONS},
        {"id": "stick", "title": "스틱 유무", "type": "single", "options": [
            {"id": "with_stick", "name": "스틱 있음", "detail": "스틱 삽입 타이밍·고정력이 공정 변수", "chapter": "Ch.9"},
            {"id": "no_stick", "name": "스틱 없음"},
        ]},
    ],
    "cake": [
        {"id": "layers", "title": "구성", "type": "single", "options": [
            {"id": "single", "name": "단층"},
            {"id": "layered", "name": "다층 레이어드", "detail": "층간 접착·절단면 유지", "chapter": "Ch.9"},
            {"id": "roll", "name": "롤 케이크", "detail": "Ch.2 'Cake roll' — 케이크 위 아이스크림을 젤리롤처럼 말기", "chapter": "Ch.2"},
            {"id": "dome", "name": "돔형"},
        ]},
        {"id": "crunch_layer", "title": "크런치층 유무", "type": "single", "options": [
            {"id": "yes", "name": "크런치층 있음", "detail": "수분전이 방지 장벽처리 필요", "chapter": "Ch.12"},
            {"id": "no", "name": "없음"},
        ]},
        {"id": "deco", "title": "데코", "type": "multi", "options": [
            {"id": "rosette", "name": "로제트 휘핑"},
            {"id": "ganache", "name": "가나슈"},
            {"id": "fruit", "name": "과일"},
            {"id": "candy", "name": "캔디 · 스프링클"},
            {"id": "none", "name": "없음"},
        ]},
        {"id": "ribbon", "title": "내부 리본 · 컨펙션", "type": "multi", "options": CONFECTION_OPTIONS + [
            {"id": "fudge_ribbon", "name": "퍼지 리본"},
            {"id": "caramel_ribbon", "name": "카라멜 리본"},
        ]},
    ],
}

# ===========================================================================
# 3-1. 기타/보충 전용 근거 데이터 (STEP 3, 6번 섹션 전용)
#    -- 4.제약조건에 담기지 않는 "부가" 정보만 여기 정리 --
#    -- 조성 id / 형태 id를 키로 두고, 아래 항목마다 반드시 책 챕터를 명시할 것 --
#    -- 근거: H. Douglas Goff & Richard W. Hartel, "Ice Cream" 7th Ed. (Springer, 2013) 원문 --
# ===========================================================================
SUPPLEMENTARY_DATA = {
    "by_composition": {
        "ice_cream": [
            {"topic": "품질등급 간 전환 시 참고", "detail": "이코노미↔레귤러↔프리미엄 전환 시 지방%뿐 아니라 overrun·총고형분도 함께 재조정 필요", "chapter": "Ch.2 Table 2.4"},
        ],
        "frozen_custard": [
            {"topic": "국가별 규격 차이", "detail": "미국은 최소 난황고형분 1.4%(벌키플레이버 1.12%)를 요구하나 캐나다는 별도 규격이 없음. 프랑스식 'glace aux oeufs'는 최소 7% 난황고형분, 독일식 'Kremeis'는 우유 1L당 최소 240g 계란 사용 — 현지화·수출 시 국가별 규격 확인 필요", "chapter": "Ch.2"},
            {"topic": "난황 대체재의 한계", "detail": "변성전분·유청단백질농축물·대두단백분리물로 난황의 식감(텍스처)은 일부 재현 가능하나, 어떤 대체재도 진짜 난황 대조군의 풍미 특성과는 일치하지 않음", "chapter": "Ch.8"},
        ],
        "frozen_yogurt": [
            {"topic": "저장 중 생균수 변화", "detail": "-23°C 저장 시 유산균은 60주 이상 경과해도 1로그 미만 감소, 프로바이오틱균(L. acidophilus, Bifidobacterium)도 90일 기준 1로그 미만 감소 — '생균 함유' 표기 시 유통기한 내 생존율 근거로 활용 가능", "chapter": "Ch.15"},
            {"topic": "전형 배합 기준값", "detail": "무가당 요거트 원료(20%)를 살균 믹스(지방 2.5%·MSNF 14.4%·당 18.75%·안정제 0.44%)에 80:20으로 블렌딩 시 최종 지방 2%·MSNF 14%·당 15%·총고형분 31.35% — 이 범위를 벗어나면 '발효 유산균' 표기 요건 재검토 필요", "chapter": "Ch.15"},
        ],
        "gelato": [
            {"topic": "인접 조성 비교", "detail": "젤라또는 낮은 overrun·낮은 지방으로 아이스크림 대비 밀도·풍미 강도 차이가 큼 — 배합 전환 시 단순 지방% 조정만으로는 텍스처 재현 불가", "chapter": "Ch.15"},
        ],
        "sherbet": [
            {"topic": "산도 관련 부가 리스크", "detail": "산도(0.35%↑) 조정 시 단백질 안정성·조직감에 미치는 영향 추가 검토 필요 — 우유고형분이 포함된 셔벗 믹스에 산을 넣으면 단백질 응집/침전 유발 가능, 그래서 냉동 직전에 산을 첨가", "chapter": "Ch.15"},
        ],
        "water_ice_sorbet": [
            {"topic": "소르베·워터아이스 규격 차이", "detail": "소르베는 과일/과즙 30~50%가 특성 성분인 반면 워터아이스는 인공 향료 사용 가능. 미국 기준 워터아이스·셔벗은 법적 정의 식품(21 CFR 135.140/135.160)이나 소르베는 비정의 식품", "chapter": "Ch.15"},
            {"topic": "과당 함량 차이에 따른 배합 조정", "detail": "과일별 과당 함량 편차가 큼(키위·라즈베리·패션프루트·블루베리 7% ~ 잘 익은 바나나 16%) — 사용 과일에 따라 첨가당량을 재조정하지 않으면 냉동점이 달라짐", "chapter": "Ch.15"},
        ],
        "nondairy": [
            {"topic": "지방원 선택 기준", "detail": "팜유·팜핵유·코코넛유 등을 배합해 4°C에서 고체지방 70% 이상을 확보해야 유제품과 유사한 융해 거동 재현 가능 — 액상 불포화유(옥수수유·카놀라유)만 쓰면 형태 유지력이 떨어짐", "chapter": "Ch.15"},
            {"topic": "유당 부재로 인한 당 함량 상향", "detail": "우유 유래 유당이 없어 동일한 냉동 곡선을 맞추려면 첨가당을 최대 20%까지 올려야 할 수 있음(전분당 가수분해물 사용 시 더 높게, 단당류 사용 시 더 낮게)", "chapter": "Ch.15"},
        ],
    },
    "by_format": {
        "tub": [
            {"topic": "포션 경계면 관리", "detail": "멀티포션 텁에서 포션 간 경계(스월/레이어)의 재결정 속도 차이가 저장 중 조직 불균일을 유발할 수 있음", "chapter": "Ch.12"},
        ],
        "stick_bar": [
            {"topic": "코팅-베이스 접착 규격", "detail": "코팅 두께·경화 속도가 유통 중 균열/박리에 미치는 영향, 라벨링 시 코팅 성분 별도 표기 필요 여부", "chapter": "Ch.9, 12"},
        ],
        "sandwich": [
            {"topic": "오버런 상한 규정", "detail": "샌드위치용 아이스크림은 오버런 100% 이하로 유지해야 절단면·형태 유지가 양호 — 압출이 과습하면 유화제 비율을 높여 형태 유지력 보완", "chapter": "Ch.9"},
            {"topic": "비스킷 흡습 대응", "detail": "아이스크림→비스킷으로의 수분전이가 눅눅함의 원인 — 비스킷 자체에 식용 장벽(edible barrier) 코팅을 적용하면 수분전이를 늦출 수 있음", "chapter": "Ch.9"},
        ],
        "extruded_molded": [
            {"topic": "몰드형 vs 압출형 코팅 배합 차이", "detail": "몰드형(디핑)용 코팅은 당 34%·지방 55%, 압출형용 코팅은 당 29%·지방 60%로 배합이 다르며, 디핑용 코팅의 라우르산 지방은 압출용보다 더 단단해야 함", "chapter": "Ch.9"},
            {"topic": "오버런-코팅 온도 상관관계", "detail": "오버런이 높을수록 표면이 빨리 녹으므로 코팅 온도를 오버런 변화에 맞춰 재조정해야 함 — 코팅 온도가 높을수록 부착량은 줄지만 융해 리스크는 커짐", "chapter": "Ch.9"},
        ],
        "cake": [
            {"topic": "레이어 사이 과일층 처리", "detail": "레이어 사이에 과일을 넣는 'au fait' 방식은 설탕+젤라틴을 과일과 섞어야 결빙에 의한 조직 손상(iciness)을 방지할 수 있음", "chapter": "Ch.9"},
            {"topic": "케이크용 코팅은 콘용보다 고점도로 설계", "detail": "케이크·파이용 코팅(코코아 12%·슈가파우더 37%·라우르산지방 50.5%·레시틴 0.5%)은 콘 분사용 코팅(지방 65%)보다 점도가 높게 설계됨 — 과잉분은 강제송풍·진동으로 제거", "chapter": "Ch.9"},
        ],
    },
}


def get_supplementary_context(composition_id, format_id):
    """선택된 조성·형태에 해당하는 보충 근거만 추려서 반환 (전체 kb를 다 훑지 않고 타겟팅)"""
    comp_items = SUPPLEMENTARY_DATA.get("by_composition", {}).get(composition_id, [])
    fmt_items = SUPPLEMENTARY_DATA.get("by_format", {}).get(format_id, [])
    return comp_items + fmt_items


# ===========================================================================
# 3-2. 카테고리별 기술 검토표 (결정론적 생성 — AI 호출 없이 KB에서 직접 조립)
#      선택된 조성/형태/분기 옵션마다 이미 KB에 박혀 있는 detail·chapter를
#      그대로 표로 뽑아낸다. AI가 임의로 요약·누락시키지 않도록 4번 섹션에
#      "그대로 인용"하라고 시스템 프롬프트에서 강제한다.
# ===========================================================================
def _find_option(options, opt_id):
    return next((o for o in options if o["id"] == opt_id), None)


def build_category_review_table(selections, fmt_id):
    """selections(dict)를 순회하며 (카테고리, 선택카드, 기술적 고려사항, 챕터) 행을 만든다.
    detail이 없는 항목(단순 명칭뿐인 옵션)은 '책에 세부 고려사항 없음 — 실험적 검증 필요'로 표기."""
    rows = []

    # 조성
    comp_id = selections.get("composition")
    if comp_id:
        comp = _find_option(COMPOSITIONS, comp_id)
        if comp:
            rows.append(("조성", comp["name"], comp.get("detail", ""), comp.get("chapter", "")))

    # 형태
    fmt = _find_option(FORMATS, fmt_id) if fmt_id else None
    if fmt:
        rows.append(("형태", fmt["name"], fmt.get("detail", ""), fmt.get("chapter", "")))

    # 형태별 분기 (텁 전용 UI 선택은 portions/ribbon/confection 등 별도 처리)
    for br in FORMAT_BRANCHES.get(fmt_id, []):
        sel = selections.get(br["id"])
        if not sel:
            continue
        sel_ids = sel if isinstance(sel, list) else [sel]
        for sid in sel_ids:
            if sid == "none":
                continue
            opt = _find_option(br["options"], sid)
            if opt:
                rows.append((br["title"], opt["name"], opt.get("detail", ""), opt.get("chapter", "")))

    # 텁 전용 12L 세부 분기 (리본 분산 · 인클루전 분산 · 표면 마감)
    if fmt_id == "tub":
        for br in TUB_12L_EXTRA_BRANCHES:
            sid = selections.get(br["id"])
            if not sid or sid == "none":
                continue
            opt = _find_option(br["options"], sid)
            if opt:
                rows.append((br["title"], opt["name"], opt.get("detail", ""), opt.get("chapter", "")))

    # 공통 옵션 (품질등급 · 포션/용량 · 유통채널)
    for cm in COMMON:
        sid = selections.get(cm["id"])
        if not sid or sid == "unset":
            continue
        opt = _find_option(cm["options"], sid)
        if opt:
            rows.append((cm["title"], opt["name"], opt.get("detail", ""), opt.get("chapter", "")))

    return rows


def render_review_table_md(rows):
    """build_category_review_table 결과를 마크다운 표로 렌더링."""
    if not rows:
        return "(선택된 항목 중 표로 낼 카테고리 없음)"
    lines = ["| 카테고리 | 선택 옵션 | 기술적 고려사항 | 참고 |", "|---|---|---|---|"]
    for cat, name, detail, chapter in rows:
        detail_txt = detail if detail else "책에 세부 고려사항 없음 — 실험적 검증 필요"
        chapter_txt = f"Ch.{chapter.replace('Ch.', '')}" if chapter else "-"
        lines.append(f"| {cat} | {name} | {detail_txt} | {chapter_txt} |")
    return "\n".join(lines)


def split_brief_sections(text):
    """최종 브리프를 '## N. 제목' 단위로 분리해 [(번호, 제목, 본문), ...] 리스트로 반환.
    번호가 없는 선행 텍스트가 있으면 0번으로 묶는다."""
    if not text:
        return []
    parts = re.split(r'(?=^##\s*\d+\.)', text, flags=re.MULTILINE)
    sections = []
    for part in parts:
        part = part.strip("\n")
        if not part.strip():
            continue
        m = re.match(r'^##\s*(\d+)\.\s*(.+)', part)
        if m:
            sections.append((int(m.group(1)), m.group(2).strip(), part))
        else:
            sections.append((0, "머리말", part))
    return sections


# ===========================================================================
# 4. 공통 옵션 (품질등급 · 용량 · 채널) — 접이식
# ===========================================================================
COMMON = [
    {"id": "quality_tier", "title": "품질 등급", "type": "single", "options": [
        {"id": "unset", "name": "— 미지정 —"},
        {"id": "economy", "name": "이코노미 (지방 10%)", "chapter": "Ch.2 Table 2.4"},
        {"id": "regular", "name": "레귤러 (지방 11–12%)", "chapter": "Ch.2 Table 2.4"},
        {"id": "premium", "name": "프리미엄 (지방 13%)", "chapter": "Ch.2 Table 2.4"},
        {"id": "superpremium", "name": "수퍼프리미엄 (지방 14–16%, 낮은 overrun)", "chapter": "Ch.2, 3"},
        {"id": "light", "name": "라이트/저지방", "chapter": "Ch.15"},
        {"id": "nosugar", "name": "무설탕/저당", "chapter": "Ch.15"},
    ]},
    {"id": "portion", "title": "포션 / 용량", "type": "single", "options": [
        {"id": "unset", "name": "— 미지정 —"},
        {"id": "single_mini", "name": "미니컵/미니바"},
        {"id": "pint", "name": "파인트/텁 (473ml급)"},
        {"id": "family", "name": "패밀리 사이즈"},
        {"id": "stick_single", "name": "스틱 단품"},
        {"id": "multipack", "name": "멀티팩"},
    ]},
    {"id": "channel", "title": "유통 채널", "type": "single", "options": [
        {"id": "unset", "name": "— 미지정 —"},
        {"id": "own_direct_franchise", "name": "자사 직가맹"},
        {"id": "convenience", "name": "편의점/임펄스"},
        {"id": "retail", "name": "마트/테이크홈"},
        {"id": "foodservice", "name": "카페/디저트전문점"},
        {"id": "vending", "name": "자판기"},
    ]},
]

# ===========================================================================
# 3-3. 배합비 계산기 — [근거 데이터]에 이미 있는 수치(범위)만 사용해
#      100%로 밸런스되는 구체적 배합비를 산출한다 (AI의 자유서술이 아니라
#      결정론적 계산). 책에 명시된 값은 그대로, 책에 없는 분배(MSNF/설탕/
#      안정제-유화제 배분)는 Ch.2 표준 배합 밸런스 관행에 따른 근사치임을
#      "assumption" 필드에 명시해 AI가 "책 원문"인 것처럼 서술하지 않게 한다.
# ===========================================================================
FORMULATION_TARGETS = {
    # 아이스크림: 지방%는 품질등급(COMMON quality_tier)별로 다르고, 총고형분·overrun은
    # FORMATS[tub]의 "지방 10–16% · 총고형분 36.5–41.65% · Overrun 90–100%"에서 가져옴
    "ice_cream": {
        "chapter": "Ch.2 Table 2.4",
        "by_tier": {
            "economy":      {"fat": 10.0, "ts": 36.5, "overrun": 90},
            "regular":      {"fat": 11.5, "ts": 38.5, "overrun": 95},
            "premium":      {"fat": 13.0, "ts": 40.0, "overrun": 95},
            "superpremium": {"fat": 15.0, "ts": 41.65, "overrun": 70},
            "unset":        {"fat": 13.0, "ts": 39.0, "overrun": 95},  # 미지정 시 레귤러~프리미엄 중간값
        },
        "sugar": 15.0,          # Ch.2 표준 배합 밸런스 관행 근사치 (책의 typical range 12~16% 중간값)
        "stab_emul": 0.35,      # 상동 (typical 0.2~0.5% 중간값)
        "assumption": "설탕·안정제/유화제는 책의 전형적 배합 밸런스 관행(typical range)에서 취한 근사치이며, "
                       "지방%·총고형분%·overrun만 [근거 데이터]에 직접 명시된 값임",
    },
    "gelato": {
        "chapter": "Ch.2, 15",
        "fat": 6.0, "ts": None, "overrun": 42.5, "sugar": 20.0, "stab_emul": 0.4,
        "assumption": "지방(4–8% 중간값)·overrun(25–60% 중간값)·설탕(최대25% 이내 근사치)은 [근거 데이터] 범위의 "
                       "중간값이며, 총고형분은 책에 별도 수치 없음",
    },
    "frozen_yogurt": {
        "chapter": "Ch.15",
        "fat": 2.0, "msnf": 14.0, "sugar": 15.0, "stab_emul": 0.35, "ts": 31.35, "overrun": None,
        "assumption": "책의 '전형 배합 기준값'(살균믹스 80:20 블렌딩 결과)을 그대로 사용",
    },
    "sherbet": {
        "chapter": "Ch.2, 15",
        "fat": 1.5, "msnf": 3.5, "ts": 33.5, "overrun": 50,
        "assumption": "지방(1–2%)·MSNF(3–4%)·총고형분(32–35%)은 [근거 데이터] 범위의 중간값",
    },
    "water_ice_sorbet": {
        "chapter": "Ch.2, 15",
        "sugar": 14.0, "css": 3.5, "stab_emul": 0.4, "acid": 0.25, "ts": None, "overrun": None,
        "assumption": "워터아이스 전형값을 그대로 사용 (소르베는 과일 25%↑ 별도 규정 — Euroglaces)",
    },
    "nondairy": {
        "chapter": "Ch.2",
        "fat": 6.0, "protein": 2.7, "ts": None, "overrun": None,
        "assumption": "멜로린(Mellorine) 기준 하한값 그대로 사용 — 상한은 책에 명시 없음",
    },
    "frozen_custard": {
        "chapter": "Ch.2",
        "egg_yolk_solids": 1.4, "ts": None, "overrun": None,
        "assumption": "미국 기준 최소 난황고형분(벌키플레이버 1.12%) — 국가별 상이(Ch.2 국가별 규격 참고)",
    },
}


def calculate_formulation(composition_id, quality_tier_id=None):
    """FORMULATION_TARGETS의 수치만으로 100%(또는 가능한 항목)로 밸런스되는 배합비 표를 계산.
    책에 없는 항목은 절대 채우지 않고 '책에 명시되지 않음'으로 남긴다."""
    spec = FORMULATION_TARGETS.get(composition_id)
    if not spec:
        return None

    rows = []  # (성분, %, 근거)
    chapter = spec["chapter"]

    if composition_id == "ice_cream":
        tier = spec["by_tier"].get(quality_tier_id or "unset", spec["by_tier"]["unset"])
        fat, ts, overrun = tier["fat"], tier["ts"], tier["overrun"]
        sugar, stab = spec["sugar"], spec["stab_emul"]
        msnf = round(ts - fat - sugar - stab, 2)
        water = round(100 - ts, 2)
        rows = [
            ("지방", f"{fat}%", "[근거 데이터] 품질등급 범위"),
            ("MSNF(무지유고형분)", f"{msnf}%", "계산값 = 총고형분 - 지방 - 설탕 - 안정제/유화제"),
            ("설탕", f"{sugar}%", "책 전형 배합 관행 근사치"),
            ("안정제/유화제", f"{stab}%", "책 전형 배합 관행 근사치"),
            ("물", f"{water}%", "계산값 = 100 - 총고형분"),
            ("총고형분(TS)", f"{ts}%", "[근거 데이터] 품질등급/형태 범위"),
            ("Overrun", f"{overrun}%", "[근거 데이터] 형태 범위"),
        ]
        if msnf < 0:
            rows.insert(1, ("⚠ 경고", "MSNF 음수", "설탕·안정제 가정치가 이 총고형분 범위와 맞지 않음 — 수동 재조정 필요"))
    else:
        for key, label in [("fat", "지방"), ("msnf", "MSNF"), ("sugar", "설탕"),
                            ("stab_emul", "안정제/유화제"), ("css", "옥수수시럽고형분(CSS)"),
                            ("acid", "산(구연산 등)"), ("protein", "단백질"),
                            ("egg_yolk_solids", "난황고형분"), ("ts", "총고형분(TS)"),
                            ("overrun", "Overrun")]:
            val = spec.get(key)
            rows.append((label, f"{val}%" if val is not None else "책에 명시되지 않음",
                         "[근거 데이터]" if val is not None else "-"))

    return {"rows": rows, "chapter": chapter, "assumption": spec.get("assumption", "")}


def render_formulation_md(calc):
    if not calc:
        return "(이 조성에 대한 배합비 계산 데이터 없음)"
    lines = ["| 성분 | 값 | 근거 |", "|---|---|---|"]
    for name, val, basis in calc["rows"]:
        lines.append(f"| {name} | {val} | {basis} |")
    lines.append(f"\n*참고: {calc['chapter']}*")
    if calc.get("assumption"):
        lines.append(f"\n*가정: {calc['assumption']}*")
    return "\n".join(lines)


# ===========================================================================
# 4-1. TUB(12L) 전용 세부 분기 — 스쿱 매장용 벌크 카타리 텁
#      (포션 개수·배치는 위 텁 전용 UI에서 별도 처리, 여기서는 분산·마감 방식)
# ===========================================================================
TUB_12L_EXTRA_BRANCHES = [
    {"id": "ribbon_distribution", "title": "리본/버라이어게이트 분산", "type": "single", "options": [
        {"id": "none", "name": "없음"},
        {"id": "inline_zigzag", "name": "인라인 지그재그 (연속 충전 중 실시간 주입)",
         "detail": "버라이어게이트 펌프가 충전 라인에 지그재그로 주입 — 스쿱마다 리본 노출, 카타리 텁의 전형적 방식", "chapter": "Ch.2, 4"},
        {"id": "layer_only", "name": "층간 주입 (레이어 사이에만 도포)",
         "detail": "레이어드 배치와 결합 시 사용 — 국지적 집중(스쿱별 편차) 리스크", "chapter": "Ch.9"},
    ]},
    {"id": "inclusion_distribution", "title": "컨펙션/인클루전 분산", "type": "single", "options": [
        {"id": "none", "name": "없음"},
        {"id": "even_inline", "name": "균일 분산 (인클루전 피더 연속 투입)",
         "detail": "피더가 충전 라인에 연속 투입 — 텁 전체 깊이에 고르게 분포", "chapter": "Ch.9"},
        {"id": "top_heavy", "name": "상단 집중 투입",
         "detail": "충전 마지막 단계에만 투입 — 스쿱 초반에 편중되므로 권장되지 않음", "chapter": "Ch.9"},
    ]},
    {"id": "surface_finish", "title": "표면 마감", "type": "single", "options": [
        {"id": "flat_scrape", "name": "평탄화 (스크레이퍼)",
         "detail": "스쿱 매장 표준 — 충전 후 표면 평탄화, 라벨 부착 전 공정", "chapter": "Ch.9"},
        {"id": "swirl_top", "name": "장식 스월 탑핑",
         "detail": "표면에 별도 토핑/스월 장식 — 프리미엄 포지셔닝", "chapter": "Ch.9"},
        {"id": "none", "name": "없음"},
    ]},
]

SEASONS = {(3, 4, 5): "봄 (3-5월)", (6, 7, 8): "여름 (6-8월)", (9, 10, 11): "가을 (9-11월)", (12, 1, 2): "겨울 (12-2월)"}


def season_of(m):
    return next((v for k, v in SEASONS.items() if m in k), "")


# ===========================================================================
# 4b. SVG 미리보기 렌더러 (텁 단면 + 스쿠핑 싱글콘)
# ===========================================================================
import math

RIBBON_COLORS = {"fudge": "#5A3825", "caramel": "#C87F2A", "fruit_syrup": "#D94F6B",
                 "marshmallow": "#FDFBF5", "none": None}
CONFECTION_COLORS = {"choco_chip": "#4A2C1A", "caramel_chip": "#D89A3D", "nuts": "#C9A36B",
                     "bakery": "#A67B4F", "candy": "#E05C7A", "fruit": "#C23B4E"}
# 고정 좌표(의사 랜덤) — 컨펙션 점 배치용 (0~1 정규화)
_DOT_POS = [(0.18, 0.30), (0.42, 0.62), (0.66, 0.25), (0.82, 0.55), (0.30, 0.80),
            (0.55, 0.42), (0.75, 0.78), (0.12, 0.60), (0.48, 0.15), (0.88, 0.35)]


def _confection_dots(conf_ids, x0, y0, w, h, r=4.5):
    """선택된 컨펙션 종류별 색상 점을 지정 영역 안에 찍는다."""
    colors = [CONFECTION_COLORS[c] for c in conf_ids if c in CONFECTION_COLORS]
    if not colors:
        return ""
    out = []
    for i, (nx, ny) in enumerate(_DOT_POS):
        color = colors[i % len(colors)]
        out.append(f'<circle cx="{x0 + nx * w:.1f}" cy="{y0 + ny * h:.1f}" r="{r}" fill="{color}" opacity="0.9"/>')
    return "".join(out)


def _swirl_pattern(colors, x0, y0, w, h):
    """회오리(소용돌이) 스월 패턴 — 중심에서 바깥으로 퍼지는 나선형 색상 밴드."""
    if not colors:
        return ""
    n = len(colors)
    cx, cy = x0 + w / 2, y0 + h / 2
    max_r = math.hypot(w, h) / 2 + 20
    turns = 3.0
    steps = 220
    out = [f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="{colors[0]}"/>']
    group = max(2, steps // int(turns * n * 2))
    pts = []
    for i in range(steps + 1):
        t = turns * 2 * math.pi * i / steps
        r = max_r * (i / steps)
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    stroke_w = max_r / (turns * 1.05)
    for i in range(len(pts) - 1):
        color = colors[(i // group) % n]
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                    f'stroke="{color}" stroke-width="{stroke_w:.1f}" stroke-linecap="round"/>')
    return "".join(out)


def _ribbon_wave(ribbon_id, x0, y0, w, h):
    color = RIBBON_COLORS.get(ribbon_id)
    if not color:
        return ""
    y_mid = y0 + h * 0.45
    amp = h * 0.12
    path = f"M {x0} {y_mid}"
    seg = w / 4
    for i in range(4):
        cx = x0 + seg * (i + 0.5)
        cy = y_mid + (amp if i % 2 == 0 else -amp)
        ex = x0 + seg * (i + 1)
        path += f" Q {cx:.1f} {cy:.1f} {ex:.1f} {y_mid:.1f}"
    stroke = "#8B7355" if ribbon_id == "marshmallow" else "none"
    return (f'<path d="{path}" fill="none" stroke="{color}" stroke-width="7" '
            f'stroke-linecap="round" opacity="0.95"/>' +
            (f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="8" opacity="0.25"/>' if stroke != "none" else ""))


def tub_svg(portions, layout, ribbon_id, conf_ids, volume_label="12L"):
    """텁 단면(측면) SVG: 포션 배치(세로분할/레이어/스월) + 리본 + 컨펙션."""
    W, H = 340, 250
    tx, ty, tw, th = 50, 60, 240, 150  # 텁 내부 영역
    n = len(portions)
    inner = []

    if layout == "vertical":       # 세로 분할
        cw = tw / n
        for i, p in enumerate(portions):
            inner.append(f'<rect x="{tx + i * cw:.1f}" y="{ty}" width="{cw:.1f}" height="{th}" fill="{p["color"]}"/>')
        for i in range(1, n):
            inner.append(f'<line x1="{tx + i * cw:.1f}" y1="{ty}" x2="{tx + i * cw:.1f}" y2="{ty + th}" stroke="#00000022" stroke-width="2"/>')
    elif layout == "layered":      # 레이어 (수평)
        lh = th / n
        for i, p in enumerate(portions):
            inner.append(f'<rect x="{tx}" y="{ty + i * lh:.1f}" width="{tw}" height="{lh:.1f}" fill="{p["color"]}"/>')
    else:                          # 스월 결합 — 회오리(소용돌이) 나선 밴드
        colors = [p["color"] for p in portions]
        inner.append(_swirl_pattern(colors, tx, ty, tw, th))

    inner.append(_ribbon_wave(ribbon_id, tx, ty, tw, th))
    inner.append(_confection_dots(conf_ids, tx + 10, ty + 10, tw - 20, th - 20))

    labels = "".join(
        f'<text x="{tx + tw / n * (i + 0.5):.0f}" y="{ty + th + 24}" font-size="12" text-anchor="middle" '
        f'fill="#2B2620" font-family="sans-serif">{p["name"] or f"플레이버{i+1}"}</text>'
        for i, p in enumerate(portions)
    ) if layout == "vertical" else "".join(
        f'<text x="{tx - 8}" y="{ty + th / n * (i + 0.55):.0f}" font-size="11" text-anchor="end" '
        f'fill="#2B2620" font-family="sans-serif">{p["name"] or f"플레이버{i+1}"}</text>'
        for i, p in enumerate(portions)
    )

    return f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs><clipPath id="tubclip"><rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="10"/></clipPath></defs>
  <rect x="{tx - 6}" y="{ty - 6}" width="{tw + 12}" height="{th + 12}" rx="14" fill="#E8DCC8" stroke="#B8A888" stroke-width="2"/>
  <g clip-path="url(#tubclip)">{"".join(inner)}</g>
  <rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="10" fill="none" stroke="#8B7355" stroke-width="2"/>
  <ellipse cx="{tx + tw / 2}" cy="{ty - 6}" rx="{tw / 2 + 6}" ry="12" fill="#D9CBAF" stroke="#8B7355" stroke-width="2"/>
  <text x="{tx + tw / 2}" y="{ty - 2}" font-size="13" font-weight="bold" text-anchor="middle" fill="#5A4A32" font-family="sans-serif">{volume_label} 벌크 텁 · 단면</text>
  {labels}
</svg>'''


def cone_svg(portions, ribbon_id, conf_ids):
    """스쿠핑 싱글콘 SVG: 포션 1개면 단색, 2~3개면 마블 스월(회오리)로 섞여 표현 + 리본 아크 + 컨펙션."""
    W, H = 240, 280
    cx, cy, r = 120, 105, 52
    n = len(portions)
    colors = [p["color"] for p in portions]
    if n == 1:
        scoop = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colors[0]}"/>'
    else:
        scoop = (f'<g clip-path="url(#scoopclip)">'
                 f'{_swirl_pattern(colors, cx - r, cy - r, r * 2, r * 2)}'
                 f'</g>')

    ribbon = ""
    rc = RIBBON_COLORS.get(ribbon_id)
    if rc:
        ribbon = (f'<path d="M {cx - r * 0.7:.0f} {cy + 10} Q {cx} {cy - r * 0.6:.0f} {cx + r * 0.7:.0f} {cy + 4}" '
                  f'fill="none" stroke="{rc}" stroke-width="6" stroke-linecap="round" opacity="0.95"/>')

    dots = _confection_dots(conf_ids, cx - r * 0.75, cy - r * 0.75, r * 1.5, r * 1.5, r=4)

    # 와플콘 (크로스해치)
    hatch = []
    for i in range(1, 5):
        y = 160 + i * 18
        halfw = 34 * (1 - (y - 160) / 100)
        hatch.append(f'<line x1="{cx - halfw:.0f}" y1="{y}" x2="{cx + halfw:.0f}" y2="{y}" stroke="#B07B3E" stroke-width="1.5"/>')
    hatch.append(f'<line x1="{cx - 22}" y1="168" x2="{cx + 8}" y2="245" stroke="#B07B3E" stroke-width="1.5"/>')
    hatch.append(f'<line x1="{cx + 22}" y1="168" x2="{cx - 8}" y2="245" stroke="#B07B3E" stroke-width="1.5"/>')

    return f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs><clipPath id="scoopclip"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath></defs>
  <path d="M {cx - 36} 158 L {cx} 252 L {cx + 36} 158 Z" fill="#D9A05B" stroke="#A9743A" stroke-width="2"/>
  {"".join(hatch)}
  <g>
  {scoop}
  {ribbon}{dots}
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#00000022" stroke-width="2"/>
  <ellipse cx="{cx - 18}" cy="{cy - 22}" rx="14" ry="8" fill="#FFFFFF" opacity="0.28"/>
  </g>
  <text x="{cx}" y="26" font-size="13" font-weight="bold" text-anchor="middle" fill="#5A4A32" font-family="sans-serif">스쿠핑 · 싱글콘</text>
</svg>'''


# ===========================================================================
# 5. Claude API
# ===========================================================================
@st.cache_resource
def get_client():
    key = st.secrets.get("ANTHROPIC_API_KEY", None)
    return Anthropic(api_key=key) if key else None


def build_system_prompt():
    kb = {
        "compositions": COMPOSITIONS,
        "formats": FORMATS,
        "format_branches": FORMAT_BRANCHES,
        "common": COMMON,
        "tub_12l_extra_branches": TUB_12L_EXTRA_BRANCHES,
    }
    return f"""당신은 아이스크림/프로즌디저트 제품개발(R&D) 전문 컨설턴트입니다.
아래는 "{SOURCE}"에서 발췌한 근거 데이터입니다. 연구원은 [조성 → 형태 → 형태별 분기]
의사결정 트리를 따라 시장 트렌드/플레이버를 실제 제품 스펙으로 전환합니다.
모든 답변은 이 데이터에 최대한 근거하고, 책에 없는 내용은
"책에 명시되지 않음 — 실험적 검증 필요"라고 표시하세요.

[근거 데이터]
{json.dumps(kb, ensure_ascii=False, indent=1)}

답변 원칙:
- 한국어, 마크다운, 기술문서 톤 (과도한 수식어 지양)
- 배합비는 %(중량 기준)로, 반드시 데이터 근거 범위 내에서 제시
- 선택된 조성×형태×분기 조합에서 발생 가능한 공정·저장수명 리스크를 반드시 짚을 것
  (예: 셔벗 조성 + 초코 코팅이면 저지방 기재-코팅 접착성 이슈, 카라멜 리본이면 FPD 재계산 필요 등)
- 근거로 사용한 챕터를 "참고: Ch.X" 형태로 명시
- 입력에 "한국(국내) 트렌드"와 "글로벌 트렌드"가 함께 주어지면, 한국 트렌드를 항상 1순위 근거로 삼고
  글로벌 트렌드는 교차검증·보완용 2순위 신호로만 참고할 것. 두 신호가 상충하면 한국 트렌드를 우선하고,
  글로벌 신호는 "글로벌에서도 유사 신호 확인됨(보조)" 정도로만 짧게 덧붙일 것

=== 최종 컨셉 브리프 형식 (6개 섹션) ===
최종 컨셉 브리프를 요청받으면 반드시 아래 6개 섹션을 이 순서・제목 그대로 작성하세요.

## 1. 타겟 정의
선택된 메인/보조 재료의 트렌드 신호(한국 신호 우선)와 사용자가 입력한 타겟 메모에 근거해,
이 컨셉이 소구되는 소비자 계층을 구체적으로 정의. 연령대(2030/3040/4050 등)·직업 또는 가정 내 역할
(직장인/주부/맞벌이/은퇴 등)·가족 구성(1인가구/신혼/자녀가구/다세대 등)·라이프스타일·소비 상황을
신호에 근거해 그때그때 판단할 것. "2030 여성 카페 이용객"을 기본값으로 가정하지 말고, 예를 들어
HMR·보양식 신호면 3040 맞벌이 부모/주부, 명절·선물 신호면 4050 가족 단위처럼 재료 성격에 맞게 도출할 것.

## 2. 트렌드 분석
메인/보조 재료가 왜 지금 유효한 신호인지 한국 트렌드를 1순위 근거로 설명하고,
글로벌 트렌드는 교차검증용 2순위 신호로만 짧게 덧붙일 것. 경쟁 환경 정보가 있으면 언급.

## 3. 컨셉 정의
맨 앞에 반드시 "컨셉 스크립트"를 1개 작성하고, 그 아래 "대안 컨셉" 변주 2개를 추가(각 1문단, 동일 밀도).
컨셉 스크립트는 다음 요소를 한 문단에 압축한 것입니다:
[제품명(가칭)] — [핵심 맛/텍스처를 담은 한 줄 설명]. [포맷 정의]. [향 조합 구조(메인 N + 보조 N)],
[구조적 차별점: 단면 reveal·코어·레이어 등 먹는 순간의 경험]. [SKU 전략]. [시즌 한정 여부].
[브랜드/라인업 적합도]. [라인 전략 검토 포인트].

컨셉 스크립트 예시 (이 밀도와 톤을 따를 것):
"아즈키 젤라또 파르페 — 일본식 단팥과 쫀득 모찌, 크리미 젤라또의 층층 파르페. 떠먹는 프리미엄
디저트(파르페/무스/테린) 포맷. 메인 1 + 보조 1 향 조합, 자르거나 떠먹을 때 단면 layered reveal.
single-serve 컵 + 선물형 2 SKU. 가을 (9-11월) → 겨울 (12-2월) 한정 컨셉. 베스킨라빈스 core
라인업 적합도 우선. 31 flavor 시스템과 시즌 한정 라인 hybrid 가능 검토"

컨셉 스크립트에 반드시 반영할 것:
- 연구원이 선택한 조성·형태·분기(코팅/리본/컨펙션/플레이버 개수 등)가 문장에 자연스럽게 녹아 있을 것
- 선택 데이터에 main_flavor/support_flavor/third_flavor(텁 이외 형태) 또는 텁 포션명이 있으면 그 재료명을
  형태와 무관하게 그대로 메인/보조/3번째 향으로 사용할 것. 임의로 다른 맛을 지어내지 말 것
- 텁 이외 형태에서 flavor_count가 2 이상이면 해당 형태의 구조(스틱바=스플릿 코어, 샌드위치·케이크=레이어 스택,
  익스트루더·몰드=분할/디자인 성형)에 맞춰 플레이버가 어떻게 배치·결합되는지 구조적 차별점 문장에 반영할 것.
  flavor_count가 1(단일)이면 다중 플레이버 구조를 지어내지 말 것
- 형태가 텁인 경우: 텁 용량(기본 3갤런 = 384 fl oz ≈ 11.35L 벌크), 포션 수(2~3포션), 포션 배치(세로분할/레이어/스월),
  포션별 플레이버명을 반영하고, "스쿠핑 시 싱글콘에서 어떻게 보이는지"(한 스쿱에 담기는 색·맛 조합의 경험)를
  구조적 차별점 문장에 포함할 것
- 포션별 고유 색상(hex)이 주어지면 그 hex를 실제 색 이름으로 변환해(예: #F5E6C8→아이보리,
  #4B0082→진보라) 단면/스월 reveal을 묘사할 때 반드시 그 색으로 표현할 것 (임의의 다른 색을 지어내지 말 것)
- 워크스페이스의 출시 시즌을 시즌 한정 문구에 사용할 것

## 4. 제약 조건
반드시 아래 순서로 3개 하위 항목을 채울 것:

**4-1. 배합비 방향성**
사용자 메시지의 "[계산된 배합비]" 표를 그대로(숫자 변경·재계산 없이) 인용해 제시하고,
"가정" 항목이 있으면 그 값이 책 원문 수치가 아니라 근사치임을 함께 밝힐 것. 이 조합에서
배합비가 형태/구조(코팅·리본·코어 등) 때문에 추가로 조정되어야 하는 지점이 있으면 덧붙일 것.

**4-2. 카테고리별 기술 검토**
사용자 메시지의 "[카테고리별 기술 검토표]"를 표 형태 그대로 인용할 것(행을 임의로 줄이거나
표현을 바꾸지 말 것). 표에 없는 조합 간 상호작용(예: 셔벗 조성 + 초코 코팅의 접착성 이슈,
카라멜 리본이면 FPD 재계산 필요 등)이 있으면 표 아래에 문장으로 추가.

**4-3. 저장수명/품질 리스크 및 제약**
위 두 표에서 도출되는 저장수명·품질 리스크를 종합하고, 사용자가 입력한 원가/콜드체인/알러지 등
제약 메모를 그대로 반영, 워크스페이스의 R&D 마감(rdDeadline)을 명시.

## 5. 검증 계획
4-2 카테고리별 기술 검토표에서 리스크·주의 문구가 있는 행(예: "리스크", "관리 필요", "재계산 필요"가
포함된 항목)을 우선순위로 뽑아, 그 항목을 실제로 무엇을(관능·기기분석·저장테스트 등) 어떻게 검증할지
구체적으로 설계할 것 — "핵심 지표를 반영해 검증 설계를 구체화" 같은 일반론적 문장만 쓰지 말고,
표의 특정 행을 지목해 검증 방법을 매칭시킬 것. 그 다음 사용자가 지정한 가상 소비자 표본 수·핵심
지표·배합비 테스트 라운드를 반영하고, 출시 시즌 컨텍스트(기온·이벤트)를 검증 조건에 명시. 지정되지
않은 항목은 합리적 기본값을 제안.

## 6. 기타 / 보충
사용자 메시지에 포함된 "[6번 기타/보충 전용 근거]" 항목을 우선 사용하되, 그대로 나열만 하지 말고
4-1/4-2에서 다룬 내용과 비교해 실제 분석을 덧붙일 것 — 예: "인접 품질등급으로 전환 시 4-1 수치가
어떻게 달라지는지", "4-2에서 선택한 코팅/리본 대신 다른 옵션을 썼다면 검토사항이 어떻게 바뀌는지"
같은 대안 비교, 규격·라벨링 관련 챕터, 이 조합에서만 발생하는 부가 리스크. [6번] 근거도 비어 있고
[근거 데이터] 전체에서도 추가로 찾을 내용이 없으면 반드시 "책에 명시되지 않음"으로 표시 —
마케팅성 추측을 지어내지 말 것. 반드시 근거 챕터를 "참고: Ch.X"로 표기. 사용자가 입력한 기타
메모가 있으면 그 내용도 반영할 것."""


def call_claude(user_content, extra_system=""):
    client = get_client()
    if client is None:
        st.error("ANTHROPIC_API_KEY가 설정되지 않았습니다. .streamlit/secrets.toml을 확인하세요.")
        return ""
    resp = client.messages.create(
        model=MODEL, max_tokens=2500,
        system=build_system_prompt() + extra_system,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def build_trend_extract_prompt(kr_text, global_text):
    return f"""아래는 한국(국내) 트렌드 분석과 글로벌 트렌드 분석 원문이다. 한국 트렌드가 1순위,
글로벌 트렌드는 2순위(보조) 근거다.

[한국(국내) 트렌드 — 1순위]
{kr_text or "(입력 없음)"}

[글로벌 트렌드 — 2순위(보조)]
{global_text or "(입력 없음)"}

위 두 텍스트에서 재료/소재 후보를 모두 추출하고, 아래 JSON 스키마로만 응답하라.
마크다운 코드펜스나 설명 문장 없이 순수 JSON 객체 하나만 출력할 것.

스키마:
{{
  "ingredients": [
    {{"name": "재료명", "region": "KR 또는 Global", "signal": "근거 신호 요약(1문장)", "idea": "응용 아이디어(1문장)",
     "color": "#RRGGBB 형식의 그 재료 고유 색상"}}
  ],
  "target_definition": "타겟 소비자 계층 정의 초안 (2~3문장)",
  "trend_definition": "한국 신호 1순위 + 글로벌 신호 2순위(보조)로 구성한 트렌드 정의 초안 (3~4문장)"
}}

target_definition 작성 규칙:
- 재료의 실제 신호에 근거해 연령대·직업/가정역할·가족구성을 그때그때 스스로 판단할 것
  (예: HMR·보양식 신호→3040 맞벌이 부모 또는 주부, 웰니스 스낵 신호→2030 1인가구 직장인,
  명절·선물 신호→4050 가족 단위 등). "2030 여성 카페 이용객"을 기본값으로 가정하지 말 것
- 연령대(2030/3040/4050 등), 직업 또는 가정 내 역할(직장인/주부/맞벌이/은퇴 등), 가족 구성
  (1인가구/신혼/자녀가구/다세대 등) 중 신호로 뒷받침되는 항목만 구체적으로 명시할 것

규칙:
- ingredients는 한국(KR) 항목을 먼저, 글로벌(Global) 항목을 그 뒤에 배치할 것
- color는 그 재료의 실제/특징적인 색에 최대한 가깝게 지정할 것
  (예: 레몬탱→노란색 계열, 블루베리→진보라/남색 계열, 콩국물→아이보리/베이지 계열, 수박→핑크/레드 계열,
  두카→올리브/브라운 계열, 흑임자→짙은 회색·검정 계열)
- 텍스트에 없는 내용을 지어내지 말 것"""


def call_claude_json(user_content):
    client = get_client()
    if client is None:
        st.error("ANTHROPIC_API_KEY가 설정되지 않았습니다. .streamlit/secrets.toml을 확인하세요.")
        return None
    resp = client.messages.create(
        model=MODEL, max_tokens=2000,
        system="You output only a single valid JSON object. No markdown fences, no prose.",
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        st.error("AI 응답을 JSON으로 해석하지 못했습니다. 다시 시도해주세요.")
        return None


# ===========================================================================
# 6. 세션 상태
# ===========================================================================
for k, v in [("brief_result", ""), ("chat_history", []),
             ("ingredient_candidates", []), ("target_draft", ""), ("trend_draft", "")]:
    if k not in st.session_state:
        st.session_state[k] = v


# ===========================================================================
# 7. UI
# ===========================================================================
st.title("🍨 아이스크림 컨셉 설계 어시스턴트")
st.caption(f"근거자료: {SOURCE}")

today = date.today()
c1, c2, c3, c4 = st.columns(4)
c1.metric("오늘", today.strftime("%Y-%m-%d"))
c2.metric("현재 계절", season_of(today.month))
with c3:
    launch_ym = st.text_input("출시 타겟월 (YYYY-MM)", value=f"{today.year + (1 if today.month + 5 > 12 else 0)}-{(today.month + 4) % 12 + 1:02d}")
launch_season, rd_deadline = "", "-"
try:
    ly, lm = map(int, launch_ym.split("-"))
    launch_season = season_of(lm)
    dm, dy = lm - 2, ly
    if dm <= 0:
        dm, dy = dm + 12, dy - 1
    rd_deadline = f"{dy}년 {dm}월까지"
except ValueError:
    pass
c4.metric("R&D 마감 (역산: 셋업1M+시범1M)", rd_deadline)

workspace = {"today": today.strftime("%Y-%m-%d"), "currentSeason": season_of(today.month),
             "launchTarget": launch_ym, "launchSeason": launch_season, "rdDeadline": rd_deadline}

st.divider()

tab_paste, tab_design = st.tabs(["📥 트렌드 붙여넣기 (한국·글로벌)", "📝 컨셉 설계 (1→6)"])

# ===========================================================================
# 탭 A: 트렌드 붙여넣기
# ===========================================================================
with tab_paste:
    st.caption("한국(국내) 트렌드는 1순위 근거, 글로벌 트렌드는 2순위(보조) 근거로만 사용됩니다.")
    kr_trend_text = st.text_area("🇰🇷 한국(국내) AI 트렌드 분석 — 최우선", height=220, key="kr_trend_input",
        placeholder="예: 레몬탱 — 관련 신호: '벤슨', '셀럽 콜라보 프리미엄 아이스크림' → 복고 분말음료 맛을 프리미엄 아이스크림으로 재해석...")
    global_trend_text = st.text_area("🌍 글로벌 AI 트렌드 분석 — 보조 신호", height=220, key="global_trend_input",
        placeholder="예: 호주: 두카(dukkah) 검색 상승 — '터키식 달걀' 연관으로 브렉퍼스트·토핑 응용...")
    if st.button("🔎 트렌드 분석 → 컨셉 설계 탭에 반영", type="primary"):
        if not (kr_trend_text.strip() or global_trend_text.strip()):
            st.warning("한국 또는 글로벌 트렌드 중 최소 1개는 입력해주세요.")
        else:
            with st.spinner("트렌드 분석 중..."):
                parsed = call_claude_json(build_trend_extract_prompt(kr_trend_text, global_trend_text))
            if parsed:
                st.session_state.ingredient_candidates = parsed.get("ingredients", [])
                st.session_state.target_draft = parsed.get("target_definition", "")
                st.session_state.trend_draft = parsed.get("trend_definition", "")
                st.success("분석 완료 — '📝 컨셉 설계' 탭의 1️⃣·2️⃣에 초안이 반영되었습니다.")

# ===========================================================================
# 탭 B: 컨셉 설계 (1 타겟정의 → 2 트렌드정의 → 3 컨셉정의 → 4 제약조건 → 5 검증계획 → 6 기타)
# ===========================================================================
with tab_design:
    selections = {}

    # --- 1. 타겟 정의 ---
    st.header("1️⃣ 타겟 정의")
    if "target_def_input" not in st.session_state:
        st.session_state.target_def_input = ""
    if st.session_state.target_draft and not st.session_state.target_def_input:
        st.session_state.target_def_input = st.session_state.target_draft
    target_definition = st.text_area(
        "이 컨셉이 소구되는 소비자 계층 (트렌드 분석 시 자동 초안 생성 · 자유 수정 가능)",
        key="target_def_input", height=90,
        placeholder="예: 3040 맞벌이 주부 / 2030 1인가구 직장인 / 4050 가족 단위 등 — 재료 신호에 맞게 자동 판단됩니다.")

    st.divider()

    # --- 2. 트렌드 정의 ---
    st.header("2️⃣ 트렌드 정의")
    candidates = st.session_state.ingredient_candidates
    cand_by_label = {}
    main_ingredient, support_ingredients = None, []
    if candidates:
        labels = [f"[{c.get('region', '?')}] {c.get('name', '')} — {c.get('idea', '')}" for c in candidates]
        cand_by_label = dict(zip(labels, candidates))
        if st.session_state.get("main_ingredient_radio") not in labels:
            st.session_state.main_ingredient_radio = labels[0]
        main_pick = st.radio("메인 재료 선택 (한국 신호 우선 정렬)", labels, key="main_ingredient_radio")
        support_pool = [l for l in labels if l != main_pick]
        if "support_ingredient_multiselect" in st.session_state:
            st.session_state.support_ingredient_multiselect = [
                l for l in st.session_state.support_ingredient_multiselect if l in support_pool]
        support_picks = st.multiselect("보조 재료 선택 (0~2개)", support_pool, key="support_ingredient_multiselect")
        main_ingredient = cand_by_label.get(main_pick)
        support_ingredients = [cand_by_label[l] for l in support_picks]
        for c in [main_ingredient] + support_ingredients:
            st.caption(f"[{c.get('region')}] **{c.get('name')}** — {c.get('signal', '')} → {c.get('idea', '')}")
    else:
        st.caption("먼저 '📥 트렌드 붙여넣기' 탭에서 분석을 실행하면 재료 후보가 여기 나타납니다 (선택 없이 진행도 가능).")

    if "trend_def_input" not in st.session_state:
        st.session_state.trend_def_input = ""
    if st.session_state.trend_draft and not st.session_state.trend_def_input:
        st.session_state.trend_def_input = st.session_state.trend_draft
    trend_definition = st.text_area(
        "트렌드 정의 (한국 1순위 + 글로벌 2순위 · 자동 초안 생성 · 자유 수정 가능)",
        key="trend_def_input", height=100)

    st.divider()

    # --- 3. 컨셉 정의 (조성 → 형태 → 형태별 분기) ---
    st.header("3️⃣ 컨셉 정의")

    st.subheader("3-1. 조성 (기본: 아이스크림)")
    comp_names = [c["name"] for c in COMPOSITIONS]
    comp_choice = st.selectbox("조성 선택", comp_names, index=0)
    comp = next(c for c in COMPOSITIONS if c["name"] == comp_choice)
    selections["composition"] = comp["id"]
    st.caption(f"`{comp['detail']}` · *{comp['chapter']}*")

    st.subheader("3-2. 제품 형태")
    fmt_names = [f["name"] for f in FORMATS]
    fmt_choice = st.radio("형태 선택", fmt_names, index=0, horizontal=True, label_visibility="collapsed")
    fmt = next(f for f in FORMATS if f["name"] == fmt_choice)
    selections["format"] = fmt["id"]
    st.caption(f"{fmt['detail']} — `{fmt['suggest']}` · *{fmt['chapter']}*")

    st.subheader(f"3-3. {fmt['name']} 상세 구성")

    # --- 텁 이외 형태: 플레이버 개수 선택 + 메인/보조/3번째 플레이버명 ---
    FLAVOR_COUNT_OPTIONS = {
        "stick_bar": [("단일", None), ("2가지 (스플릿 구조)", "Ch.9")],
        "sandwich": [("단일", None), ("2가지 (레이어 스택)", "Ch.9"), ("3가지 (레이어 스택)", "Ch.9")],
        "extruded_molded": [("단일", None), ("2가지 (분할 성형)", "Ch.9"), ("3가지 이상 (디자인 성형)", "Ch.9")],
        "cake": [("단일", None), ("2가지 (체커보드/컬러 대비)", "Ch.9"), ("3가지 이상 (멀티레이어)", "Ch.9")],
    }
    if fmt["id"] != "tub":
        fc_options = FLAVOR_COUNT_OPTIONS.get(fmt["id"], [("단일", None)])
        fc_labels = [o[0] for o in fc_options]
        flavor_count_choice = st.radio("플레이버 개수", fc_labels, horizontal=True, key=f"flavor_count_{fmt['id']}")
        fc_chapter = next((o[1] for o in fc_options if o[0] == flavor_count_choice), None)
        n_flavors = 3 if flavor_count_choice.startswith("3") else (2 if flavor_count_choice.startswith("2") else 1)
        selections["flavor_count"] = n_flavors
        if fc_chapter:
            st.caption(f"근거: *{fc_chapter}*")

        fl_col1, fl_col2, fl_col3 = st.columns(3)
        with fl_col1:
            auto_main_flavor = main_ingredient.get("name") if main_ingredient else None
            if auto_main_flavor and st.session_state.get("_main_flavor_auto_src") != auto_main_flavor:
                st.session_state["main_flavor_input"] = auto_main_flavor
                st.session_state["_main_flavor_auto_src"] = auto_main_flavor
            main_flavor_kwargs = {} if "main_flavor_input" in st.session_state else {"value": ""}
            main_flavor = st.text_input("메인 플레이버명 (2️⃣ 선택 시 자동 반영 · 직접 수정 가능)",
                                         key="main_flavor_input", placeholder="예: 레몬탱", **main_flavor_kwargs)
        with fl_col2:
            support_flavor = ""
            if n_flavors >= 2:
                auto_support_flavor = support_ingredients[0].get("name") if support_ingredients else None
                if auto_support_flavor and st.session_state.get("_support_flavor_auto_src") != auto_support_flavor:
                    st.session_state["support_flavor_input"] = auto_support_flavor
                    st.session_state["_support_flavor_auto_src"] = auto_support_flavor
                support_flavor_kwargs = {} if "support_flavor_input" in st.session_state else {"value": ""}
                support_flavor = st.text_input("보조 플레이버명 (직접 수정 가능)",
                                                key="support_flavor_input", placeholder="예: 콩국물", **support_flavor_kwargs)
        with fl_col3:
            third_flavor = ""
            if n_flavors >= 3:
                third_flavor = st.text_input("3번째 플레이버명",
                                              key="third_flavor_input", placeholder="예: 흑임자")
        if main_flavor:
            selections["main_flavor"] = main_flavor
        if support_flavor:
            selections["support_flavor"] = support_flavor
        if third_flavor:
            selections["third_flavor"] = third_flavor

    # --- 텁 전용: 3갤런(11.35L) 기본 + 포션 구성 + 실시간 미리보기 ---
    if fmt["id"] == "tub":
        tv_col, pc_col, ly_col = st.columns(3)
        with tv_col:
            tub_volume = st.selectbox("텁 용량", ["3갤런 (11.35L, 기본)", "8L", "4L", "473ml 파인트"], index=0)
        with pc_col:
            portion_count = st.radio("텁 내부 포션 구성", ["1포션 (단일)", "2포션", "3포션"], index=1, horizontal=True)
        with ly_col:
            layout_name = st.selectbox("포션 배치", ["스월 결합 (회오리)", "세로 분할", "레이어 (수평)"], index=0)
        layout_map = {"세로 분할": "vertical", "레이어 (수평)": "layered", "스월 결합 (회오리)": "swirl"}
        n_portions = int(portion_count[0])

        default_flavors = [("바닐라", "#F5E6C8"), ("초콜릿", "#8B4A2F"), ("스트로베리", "#F2A6B8")]
        selected_ingredient_pool = ([main_ingredient] if main_ingredient else []) + support_ingredients
        _hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
        portions = []
        st.markdown("**포션별 플레이버 · 색상** (2️⃣에서 선택한 재료의 이름·고유색이 자동 반영되며, 직접 입력해 덮어쓸 수도 있습니다)")
        p_cols = st.columns(n_portions)
        for i in range(n_portions):
            with p_cols[i]:
                dn, dc = default_flavors[i]
                ing = selected_ingredient_pool[i] if i < len(selected_ingredient_pool) else None

                name_key, name_auto_src_key = f"p_name_{i}", f"_p_name_{i}_auto_src"
                auto_name = ing.get("name") if ing else None
                if auto_name and st.session_state.get(name_auto_src_key) != auto_name:
                    st.session_state[name_key] = auto_name
                    st.session_state[name_auto_src_key] = auto_name
                name_kwargs = {} if name_key in st.session_state else {"value": dn}
                name = st.text_input(f"포션 {i + 1} 플레이버", key=name_key, **name_kwargs)

                color_key, color_auto_src_key = f"p_color_{i}", f"_p_color_{i}_auto_src"
                auto_color = ing.get("color") if ing else None
                auto_color = auto_color if auto_color and _hex_re.match(auto_color) else None
                if auto_color and st.session_state.get(color_auto_src_key) != auto_color:
                    st.session_state[color_key] = auto_color
                    st.session_state[color_auto_src_key] = auto_color
                color_kwargs = {} if color_key in st.session_state else {"value": dc}
                color = st.color_picker(f"포션 {i + 1} 색상", key=color_key, **color_kwargs)

                portions.append({"name": name, "color": color})

        selections["tub_volume"] = tub_volume
        selections["portion_count"] = n_portions
        selections["portion_layout"] = layout_map[layout_name]
        selections["portions"] = portions

        if tub_volume.startswith("3갤런"):
            st.markdown("**🥡 TUB(3갤런/11.35L) 세부 구성** (스쿱 매장 카타리 텁)")
            extra_cols = st.columns(3)
            for i, br in enumerate(TUB_12L_EXTRA_BRANCHES):
                with extra_cols[i % 3]:
                    st.markdown(f"**{br['title']}**")
                    names = [o["name"] for o in br["options"]]
                    pick = st.selectbox(br["title"], names, key=f"tub12l_{br['id']}", label_visibility="collapsed")
                    opt = next(o for o in br["options"] if o["name"] == pick)
                    if opt["id"] != "none":
                        selections[f"tub12l_{br['id']}"] = opt["id"]
                    note = " · ".join(x for x in [opt.get("detail"), opt.get("chapter")] if x)
                    if note:
                        st.caption(note)

    branches = FORMAT_BRANCHES[fmt["id"]]
    branch_cols = st.columns(2)
    for i, br in enumerate(branches):
        with branch_cols[i % 2]:
            st.markdown(f"**{br['title']}**")
            names = [o["name"] for o in br["options"]]
            if br["type"] == "single":
                pick = st.selectbox(br["title"], names, key=f"br_{fmt['id']}_{br['id']}", label_visibility="collapsed")
                opt = next(o for o in br["options"] if o["name"] == pick)
                selections[br["id"]] = opt["id"]
                note = " · ".join(x for x in [opt.get("detail"), opt.get("chapter")] if x)
                if note:
                    st.caption(note)
            else:
                picks = st.multiselect(br["title"], names, key=f"br_{fmt['id']}_{br['id']}", label_visibility="collapsed")
                if picks:
                    selections[br["id"]] = [next(o["id"] for o in br["options"] if o["name"] == n) for n in picks]
                    for n in picks:
                        o = next(o for o in br["options"] if o["name"] == n)
                        if o.get("detail"):
                            st.caption(f"☑ {n} — {o['detail']}")
            st.write("")

    # --- 텁: 구성 실시간 미리보기 (텁 단면 + 스쿠핑 싱글콘) ---
    if fmt["id"] == "tub":
        st.markdown("#### 🖼️ 구성 미리보기")
        ribbon_sel = selections.get("ribbon", "none")
        conf_sel = selections.get("confection", [])
        conf_sel = [c for c in conf_sel if c != "none"]
        vol_label = tub_volume.split(" ")[0]
        prev1, prev2 = st.columns(2)
        with prev1:
            st.markdown(tub_svg(portions, layout_map[layout_name], ribbon_sel, conf_sel, vol_label),
                        unsafe_allow_html=True)
            st.caption("텁 단면 — 포션 배치 · 리본 · 컨펙션")
        with prev2:
            st.markdown(cone_svg(portions, ribbon_sel, conf_sel), unsafe_allow_html=True)
            st.caption("스쿠핑 시 싱글콘 — 포션이 한 스쿱에 섞인 모습")

    st.divider()

    # --- 4. 제약 조건 ---
    st.header("4️⃣ 제약 조건")
    common_cols = st.columns(3)
    for i, cm in enumerate(COMMON):
        with common_cols[i]:
            names = [o["name"] for o in cm["options"]]
            pick = st.selectbox(cm["title"], names, key=f"cm_{cm['id']}")
            opt_id = next(o["id"] for o in cm["options"] if o["name"] == pick)
            if opt_id != "unset":
                selections[cm["id"]] = opt_id

    extra_note = st.text_input("추가 메모 / 제약조건 (선택)",
        placeholder="예: 본체 원가 800원 이내, 콜드체인 -18℃, 알러지 표기 필요")

    st.divider()

    # --- 5. 검증 계획 ---
    st.header("5️⃣ 검증 계획")
    val_col1, val_col2, val_col3 = st.columns(3)
    with val_col1:
        val_sample = st.selectbox("가상 소비자 표본 수", ["미지정", "50명", "100명", "200명"], key="val_sample_size")
    with val_col2:
        val_kpis = st.multiselect("핵심 지표", ["외형 차별 인지", "구매 의향", "가격 수용 ceiling", "재구매 의향"],
                                   key="val_kpis")
    with val_col3:
        val_rounds = st.selectbox("배합비 테스트 라운드", ["미지정", "1라운드", "2~3라운드", "3라운드 이상"], key="val_rounds")
    val_note = st.text_area("검증 추가 메모 (선택)", height=70, key="val_note_input")

    st.divider()

    # --- 6. 기타 / 보충 ---
    st.header("6️⃣ 기타 / 보충")
    misc_note = st.text_area("마케팅 훅, 포토스팟, 콜라보 아이디어 등 (선택)", height=80, key="misc_note_input")

    st.divider()

    # --- 최종 컨셉 브리프 생성 ---
    st.subheader("📋 최종 컨셉 브리프 생성 (1~6 전체)")
    if st.button("📋 최종 제출 → 컨셉 브리프 생성", type="primary"):
        ws = {**workspace, "extraNote": extra_note}
        ingredient_ctx = {
            "main": main_ingredient,
            "support": support_ingredients,
        }
        validation_ctx = {
            "sample_size": val_sample if val_sample != "미지정" else None,
            "kpis": val_kpis,
            "test_rounds": val_rounds if val_rounds != "미지정" else None,
            "note": val_note,
        }
        supp_context = get_supplementary_context(selections.get("composition"), selections.get("format"))
        review_rows = build_category_review_table(selections, fmt["id"])
        review_table_md = render_review_table_md(review_rows)
        formulation_calc = calculate_formulation(selections.get("composition"), selections.get("quality_tier"))
        formulation_md = render_formulation_md(formulation_calc)

        prompt = f"""연구원이 [1.타겟정의 → 2.트렌드정의 → 3.컨셉정의(조성/형태/분기) → 4.제약조건 → 5.검증계획 → 6.기타]
순서로 아래와 같이 입력하고 최종 제출했다.

워크스페이스: {json.dumps(ws, ensure_ascii=False)}

[계산된 배합비] (4-1에 그대로 인용할 것 — 숫자를 임의로 바꾸지 말 것)
{formulation_md}

[카테고리별 기술 검토표] (4-2에 그대로 인용할 것 — 행을 임의로 줄이지 말 것)
{review_table_md}

[6번 기타/보충 전용 근거 — 이 조성·형태 조합에 해당하는 항목만 발췌됨]
{json.dumps(supp_context, ensure_ascii=False, indent=1) if supp_context else "(이 조합에 대한 보충 데이터 없음 — '책에 명시되지 않음'으로 표시할 것)"}

[한국(국내) 트렌드 원문 — 1순위]
{kr_trend_text or '(입력 없음)'}

[글로벌 트렌드 원문 — 2순위(보조)]
{global_trend_text or '(입력 없음)'}

선택된 메인/보조 재료: {json.dumps(ingredient_ctx, ensure_ascii=False)}

1. 타겟 정의(사용자 입력/수정본): {target_definition or '(입력 없음, 트렌드 신호로부터 도출할 것)'}
2. 트렌드 정의(사용자 입력/수정본): {trend_definition or '(입력 없음, 트렌드 원문으로부터 도출할 것)'}
3. 컨셉 정의 선택 (id 기준): {json.dumps(selections, ensure_ascii=False, indent=1)}
   {"포션별 고유 색상(hex): " + json.dumps([{"name": p["name"], "color": p["color"]} for p in selections.get("portions", [])], ensure_ascii=False) if selections.get("portions") else ""}
4. 제약조건 메모: {extra_note or '(입력 없음)'}
5. 검증계획 지정값: {json.dumps(validation_ctx, ensure_ascii=False)}
6. 기타/보충 메모: {misc_note or '(입력 없음)'}

system prompt의 "최종 컨셉 브리프 형식 (6개 섹션)"을 정확히 그 순서・제목으로 작성해줘."""
        with st.spinner("컨셉 브리프 생성 중... (약 30초~1분)"):
            st.session_state.brief_result = call_claude(prompt)

    if st.session_state.brief_result:
        # 브리프 본문을 먼저 전체 폭으로 출력 (구석 컬럼에 밀어넣지 않음)
        st.markdown(st.session_state.brief_result)

        # 텁이면 브리프 몇 줄 아래에 구성 미리보기 이미지를 별도 행으로 출력
        if fmt["id"] == "tub" and "portions" in selections:
            st.markdown("")
            st.markdown("")
            st.subheader("🧊 구성 미리보기")
            img1, img2 = st.columns(2)
            with img1:
                st.markdown(tub_svg(selections["portions"], selections["portion_layout"],
                                    selections.get("ribbon", "none"),
                                    [c for c in selections.get("confection", []) if c != "none"],
                                    selections["tub_volume"].split(" ")[0]), unsafe_allow_html=True)
            with img2:
                st.markdown(cone_svg(selections["portions"], selections.get("ribbon", "none"),
                                     [c for c in selections.get("confection", []) if c != "none"]),
                            unsafe_allow_html=True)

        st.download_button("⬇️ 컨셉 브리프 다운로드 (.md)", st.session_state.brief_result,
                           file_name=f"concept_brief_{today.strftime('%Y%m%d')}.md", mime="text/markdown")

        st.divider()
        st.subheader("📋 섹션별 복사")
        st.caption("각 코드 상자 우측 상단 복사 아이콘을 누르면 해당 섹션만 복사됩니다.")
        sections = split_brief_sections(st.session_state.brief_result)
        for num, title, content in sections:
            label = f"{num}. {title}" if num else title
            with st.expander(label, expanded=False):
                st.code(content, language="markdown")

        st.markdown("**전체 브리프 복사** (아래 상자 우측 상단 복사 아이콘)")
        st.code(st.session_state.brief_result, language="markdown")

st.divider()

# --- 대화로 다듬기 (탭 공통) ---
st.header("💬 대화로 다듬기")
st.caption("예: '텁 대신 스틱바로 바꾸면?', '카라멜 리본을 넣으면 빙점이 어떻게 달라져?'")

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_q = st.chat_input("질문 또는 조정 요청")
if user_q:
    st.session_state.chat_history.append({"role": "user", "content": user_q})
    with st.chat_message("user"):
        st.markdown(user_q)
    ctx = (f"\n\n현재 선택: {json.dumps(selections, ensure_ascii=False)}\n"
           f"워크스페이스: {json.dumps(workspace, ensure_ascii=False)}\n"
           f"타겟 정의: {target_definition or '(없음)'}\n트렌드 정의: {trend_definition or '(없음)'}\n"
           f"직전 브리프:\n{st.session_state.brief_result or '(없음)'}\n대화 맥락을 이어서 답변해줘.")
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in st.session_state.chat_history)
    with st.spinner("답변 생성 중..."):
        answer = call_claude(history_text, extra_system=ctx)
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)
