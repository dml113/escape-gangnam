"""
강남 방탈출 예약 가능 시간 조회
- 제로월드 강남점
- CODE-K 강남점
- 미스터리룸 강남점
- 이룸에이트 (신논현)

사용법: python3 escape_gangnam.py [날짜]
예시:   python3 escape_gangnam.py 2026-03-12
날짜 생략 시 오늘 날짜 사용
"""

import sys
import re
import requests
import warnings
from urllib.parse import unquote
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

TARGET_DATE = sys.argv[1] if len(sys.argv) > 1 else __import__("datetime").date.today().isoformat()
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def print_result(name, url, themes: list[tuple]):
    """themes: [(테마명, [가능시간], [마감시간]), ...]"""
    print(f"\n{'='*55}")
    print(f"  {name}")
    print(f"  {url}")
    print(f"{'='*55}")
    if not themes:
        print("  데이터 없음 (예약 가능 기간 초과 또는 접근 불가)")
        return
    for theme_name, available, closed in themes:
        if available:
            print(f"  [{theme_name}]")
            print(f"    예약 가능: {', '.join(available)}")
            if closed:
                print(f"    마    감: {', '.join(closed)}")
        else:
            print(f"  [{theme_name}] 전체 마감")


# ── 1. 제로월드 강남점 ──────────────────────────────────────────
def check_zerogangnam():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://zerogangnam.com/reservation")
    xsrf = unquote(s.cookies.get("XSRF-TOKEN", ""))

    r = s.post(
        "https://zerogangnam.com/reservation/theme",
        json={"date": TARGET_DATE},
        headers={
            "X-XSRF-TOKEN": xsrf,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://zerogangnam.com/reservation",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    data = r.json()
    themes_info = {t["PK"]: t["title"] for t in data["data"]}
    themes = []
    for pk_str, slots in data.get("times", {}).items():
        name = themes_info.get(int(pk_str), f"테마{pk_str}")
        available = [s["timeKO"] for s in slots if not s["reservation"]]
        closed = [s["timeKO"] for s in slots if s["reservation"]]
        themes.append((name, available, closed))

    print_result("제로월드 강남점", "https://zerogangnam.com/reservation", themes)


# ── 2. CODE-K 강남점 ────────────────────────────────────────────
def check_codek():
    r = requests.post(
        "http://www.code-k.co.kr/sub/code_sub04_1.html",
        data={"R_JIJEM": "S1", "chois_date": TARGET_DATE},
        headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        verify=False,
    )
    r.encoding = "euc-kr"
    soup = BeautifulSoup(r.text, "html.parser")

    reser3 = soup.find(id="reser3")
    if not reser3:
        print_result("CODE-K 강남점", "http://www.code-k.co.kr", [])
        return

    themes = []
    # li.thema1 = 테마 이름, 다음 li[id=CQN] = 슬롯
    for thema_li in reser3.find_all("li", class_="thema1"):
        name = thema_li.get_text(strip=True)
        slot_li = thema_li.find_next_sibling("li", id=re.compile(r"CQ\d+"))
        if not slot_li:
            continue
        available = [
            re.sub(r"[★☆\s]", "", t.get_text())
            for t in slot_li.find_all("li", class_="timeOn")
        ]
        closed = [
            re.sub(r"[★☆\s]", "", t.get_text())
            for t in slot_li.find_all("li", class_="timeOff")
        ]
        themes.append((name, available, closed))

    print_result("CODE-K 강남점", "http://www.code-k.co.kr", themes)


# ── 3. 미스터리룸 강남점 ─────────────────────────────────────────
def check_mysteryroom():
    r = requests.get(
        "http://mysteryroomescape-gn.com/reservation/reservation.html",
        params={"a": "27", "select_date": TARGET_DATE},
        headers=HEADERS,
    )
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    themes = []

    for list_div in soup.find_all(class_="list_div"):
        title_con = list_div.find(class_="title_con")
        texts = [t.strip() for t in title_con.stripped_strings] if title_con else []
        theme_name = next(
            (t for t in texts if t and "ROOM" not in t and len(t) > 1), f"룸{len(themes)+1}"
        )
        # select_room(code, stype, date, time, ...) — stype='0' → 가능
        calls = re.findall(r"select_room\('([^']*)','([^']*)','([^']*)','([^']*)'", str(list_div))
        available = [time for _, stype, _, time in calls if stype == "0"]
        closed = [time for _, stype, _, time in calls if stype != "0"]
        themes.append((theme_name, available, closed))

    print_result("미스터리룸 강남점", "http://mysteryroomescape-gn.com", themes)


# ── 4. 이룸에이트 ───────────────────────────────────────────────
def check_eroom8():
    r = requests.get(
        "https://eroom8.co.kr/layout/res/home.php",
        params={"go": "rev.make", "rev_days": TARGET_DATE},
        headers=HEADERS,
        verify=False,
    )
    r.encoding = "utf-8"

    if "예약가능일이 아닙니다" in r.text:
        print_result("이룸에이트 (신논현)", "https://eroom8.co.kr", [])
        return

    soup = BeautifulSoup(r.text, "html.parser")
    themes = []

    for box in soup.find_all(class_="theme_box"):
        title_el = box.find(class_="h3_theme")
        title = title_el.get_text(strip=True) if title_el else f"테마{len(themes)+1}"

        available = []
        closed = []
        for a in box.find_all("a", href=True):
            if "theme_time_num" not in a["href"]:
                continue
            time_text = re.search(r"\d{2}:\d{2}", a.get_text())
            if not time_text:
                continue
            t = time_text.group()
            if "마감" in a.get_text() or "close" in " ".join(a.get("class", [])):
                closed.append(t)
            else:
                available.append(t)

        themes.append((title, available, closed))

    print_result("이룸에이트 (신논현)", "https://eroom8.co.kr", themes)


# ── 메인 ────────────────────────────────────────────────────────
def main():
    print(f"\n강남 방탈출 예약 조회 — {TARGET_DATE}")

    for fn in [check_zerogangnam, check_codek, check_mysteryroom, check_eroom8]:
        try:
            fn()
        except Exception as e:
            print(f"\n[오류] {fn.__name__}: {e}")

    print(f"\n{'='*55}")


if __name__ == "__main__":
    main()
