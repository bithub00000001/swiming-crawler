import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import asyncio
from telegram import Bot
import time

# GitHub Secrets에서 환경변수 가져오기
BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
SCRAPER_API_KEY = os.environ['SCRAPER_API_KEY']


async def send_telegram_message(message, use_html=True):
    bot = Bot(token=BOT_TOKEN)
    try:
        parse_mode = 'HTML' if use_html else None
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode=parse_mode
        )
    except Exception as e:
        if use_html:
            await send_telegram_message(message, use_html=False)
        else:
            print(f"텔레그램 전송 실패: {e}")


def crawl_notices_with_scraperapi():
    """ScraperAPI를 사용한 크롤링"""
    print("ScraperAPI를 사용하여 크롤링 시작...")

    # ScraperAPI 요청 파라미터 [web:229][web:231]
    payload = {
        'api_key': SCRAPER_API_KEY,
        'url': 'https://www.jjss.or.kr/reserv/planweb/board/list.9is?contentUid=ff8080816c5f9de6016cd702efc70de1&boardUid=ff8080816d4d1c03016d85eb2aff02cd&categoryUid2=C1',
        'country_code': 'kr',  # 한국 IP 사용 [web:231]
        'follow_redirect': 'true',
        'render': 'false',  # JavaScript 렌더링 불필요
        'timeout': '30000',  # 30초 타임아웃
        'retry_404': 'true'
    }

    try:
        response = requests.get(
            'https://api.scraperapi.com/',
            params=payload,
            timeout=60  # 충분한 타임아웃
        )

        print(f"ScraperAPI 응답 상태: {response.status_code}")

        if response.status_code == 200:
            return parse_notices_from_html(response.text)
        else:
            print(f"ScraperAPI 오류: {response.status_code} - {response.text}")
            raise Exception(f"ScraperAPI 요청 실패: {response.status_code}")

    except Exception as e:
        print(f"ScraperAPI 크롤링 실패: {e}")
        raise


def parse_notices_from_html(html_content):
    """HTML에서 공지사항 추출"""
    print("HTML 파싱 시작...")

    soup = BeautifulSoup(html_content, 'html.parser')
    notices = []

    # 공지사항 테이블 찾기
    table = soup.find('table', class_='bbsList bbs01')
    if not table:
        print("공지사항 테이블을 찾을 수 없습니다.")
        print("받은 HTML 일부:")
        print(html_content[:500])
        return notices

    tbody = table.find('tbody')
    if not tbody:
        print("테이블 본문을 찾을 수 없습니다.")
        return notices

    rows = tbody.find_all('tr')
    print(f"총 {len(rows)}개 행 발견")

    for i, row in enumerate(rows):
        cells = row.find_all('td')
        if len(cells) >= 6:
            try:
                # 제목 추출
                title_cell = cells[2]
                title_link = title_cell.find('a')
                if title_link:
                    title_span = title_link.find('span')
                    if title_span:
                        title = title_span.get_text(strip=True)

                        # 링크 추출
                        href = title_link.get('href', '')
                        if href.startswith('./'):
                            href = href[2:]  # ./ 제거
                        link = f'https://www.jjss.or.kr/reserv/planweb/board/{href}'

                        # 날짜 추출
                        date = cells[4].get_text(strip=True)

                        # "신규" 또는 "초급" 키워드 필터링
                        if "신규" in title or "초급" in title:
                            notices.append({
                                'title': title,
                                'link': link,
                                'date': date
                            })
                            print(f"✓ 발견된 공지 [{i + 1}]: {title}")
                        else:
                            print(f"  일반 공지 [{i + 1}]: {title}")
            except Exception as e:
                print(f"행 파싱 오류 [{i + 1}]: {e}")
                continue

    print(f"총 {len(notices)}개 신규/초급 공지 발견")
    return notices


async def main():
    start_time = datetime.now()
    try:
        print("=" * 50)
        print(f"완산수영장 알림봇 시작 - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        # ScraperAPI로 크롤링
        current_notices = crawl_notices_with_scraperapi()

        # 이전 공지사항 데이터 로드
        try:
            with open('data/last_posts.json', 'r', encoding='utf-8') as f:
                last_notices = json.load(f)
        except FileNotFoundError:
            print("이전 데이터 없음. 새로 시작합니다.")
            last_notices = []

        # 새로운 공지사항 찾기
        last_titles = {notice['title'] for notice in last_notices}
        new_notices = [notice for notice in current_notices
                       if notice['title'] not in last_titles]

        print(f"전체 신규/초급 공지: {len(current_notices)}개")
        print(f"새로운 공지: {len(new_notices)}개")

        # 새 공지사항이 있으면 텔레그램 전송
        if new_notices:
            print("새 공지사항 텔레그램 전송 시작...")
            for i, notice in enumerate(new_notices):
                message = f"""
🏊‍♀️ <b>완산수영장 신규/초급 공지</b>

📋 <b>{notice['title']}</b>
📅 등록일: {notice['date']}
🔗 <a href="{notice['link']}">공지사항 보기</a>

🤖 ScraperAPI를 통한 자동 알림
                """.strip()

                await send_telegram_message(message)
                print(f"  ✓ 전송 완료 [{i + 1}/{len(new_notices)}]: {notice['title']}")

                if i < len(new_notices) - 1:  # 마지막이 아니면 대기
                    time.sleep(2)
        else:
            # 정상 작동 확인 메시지
            end_time = datetime.now()
            duration = (end_time - start_time).seconds

            success_message = f"""
✅ <b>완산수영장 알림봇 정상 작동</b>

🔍 신규/초급 공지사항 {len(current_notices)}개 확인 완료
⏱️ 실행시간: {duration}초
📅 확인 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
🔄 다음 확인: 2시간 후

🌐 ScraperAPI 사용 (한국 IP)
            """.strip()
            await send_telegram_message(success_message)

        # 현재 공지사항 저장
        os.makedirs('data', exist_ok=True)
        with open('data/last_posts.json', 'w', encoding='utf-8') as f:
            json.dump(current_notices, f, ensure_ascii=False, indent=2)

        print("=" * 50)
        print("작업 완료!")
        print("=" * 50)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        error_message = f"""❌ 완산수영장 알림봇 오류 발생

🔧 ScraperAPI 사용 중 오류
⚠️ 오류 내용: {str(e)[:150]}...
📅 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔄 다음 실행 시 다시 시도됩니다.
💡 지속적 오류 시 GitHub Actions 로그를 확인하세요.
        """.strip()

        await send_telegram_message(error_message, use_html=False)


if __name__ == "__main__":
    asyncio.run(main())
