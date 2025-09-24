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


def crawl_all_notices():
    """ScraperAPI를 사용해서 1페이지의 모든 공지사항 가져오기"""
    print("ScraperAPI를 사용하여 크롤링 시작...")

    payload = {
        'api_key': SCRAPER_API_KEY,
        'url': 'https://www.jjss.or.kr/reserv/planweb/board/list.9is?contentUid=ff8080816c5f9de6016cd702efc70de1&boardUid=ff8080816d4d1c03016d85eb2aff02cd&categoryUid2=C1',
        'country_code': 'kr',
        'follow_redirect': 'true',
        'render': 'false',
        'timeout': '30000',
        'retry_404': 'true'
    }

    try:
        response = requests.get(
            'https://api.scraperapi.com/',
            params=payload,
            timeout=60
        )

        print(f"ScraperAPI 응답 상태: {response.status_code}")

        if response.status_code == 200:
            return parse_all_notices_from_html(response.text)
        else:
            print(f"ScraperAPI 오류: {response.status_code} - {response.text}")
            raise Exception(f"ScraperAPI 요청 실패: {response.status_code}")

    except Exception as e:
        print(f"ScraperAPI 크롤링 실패: {e}")
        raise


def parse_all_notices_from_html(html_content):
    """HTML에서 모든 공지사항 추출 (필터링 없이)"""
    print("HTML 파싱 시작 - 모든 게시글 추출...")

    soup = BeautifulSoup(html_content, 'html.parser')
    all_notices = []

    table = soup.find('table', class_='bbsList bbs01')
    if not table:
        print("공지사항 테이블을 찾을 수 없습니다.")
        return all_notices

    tbody = table.find('tbody')
    if not tbody:
        print("테이블 본문을 찾을 수 없습니다.")
        return all_notices

    rows = tbody.find_all('tr')
    print(f"총 {len(rows)}개 행 발견")

    for i, row in enumerate(rows):
        cells = row.find_all('td')
        if len(cells) >= 6:
            try:
                title_cell = cells[2]
                title_link = title_cell.find('a')
                if title_link:
                    title_span = title_link.find('span')
                    if title_span:
                        title = title_span.get_text(strip=True)

                        href = title_link.get('href', '')
                        if href.startswith('./'):
                            href = href[2:]
                        link = f'https://www.jjss.or.kr/reserv/planweb/board/{href}'

                        date = cells[4].get_text(strip=True)

                        # 모든 게시글 저장 (필터링 없이)
                        all_notices.append({
                            'title': title,
                            'link': link,
                            'date': date
                        })

                        print(f"📋 공지 [{i + 1}]: {title}")

            except Exception as e:
                print(f"행 파싱 오류 [{i + 1}]: {e}")
                continue

    print(f"총 {len(all_notices)}개 공지사항 추출 완료")
    return all_notices


def load_previous_notices():
    """이전 공지사항 안전하게 로드"""
    try:
        if not os.path.exists('data/last_posts.json'):
            print("이전 데이터 파일이 없습니다. 새로 시작합니다.")
            return []

        with open('data/last_posts.json', 'r', encoding='utf-8') as f:
            content = f.read().strip()

            if not content:
                print("이전 데이터 파일이 비어있습니다. 새로 시작합니다.")
                return []

            try:
                last_notices = json.loads(content)
                print(f"이전 데이터 로드 성공: {len(last_notices)}개 공지")
                return last_notices
            except json.JSONDecodeError as json_error:
                print(f"JSON 파싱 에러: {json_error}")
                print("손상된 데이터를 무시하고 새로 시작합니다.")
                return []

    except Exception as e:
        print(f"이전 데이터 로드 실패: {e}")
        print("새로 시작합니다.")
        return []


def find_new_notices(current_notices, last_notices):
    """새로운 게시글 찾기"""
    print("새로운 게시글 검색 중...")

    # 이전 게시글 제목들을 set으로 변환
    last_titles = {notice['title'] for notice in last_notices}

    # 새로운 게시글 찾기
    new_notices = [notice for notice in current_notices
                   if notice['title'] not in last_titles]

    print(f"새로운 게시글: {len(new_notices)}개")

    if new_notices:
        print("발견된 새 게시글:")
        for i, notice in enumerate(new_notices):
            print(f"  📋 [{i + 1}] {notice['title']}")

    return new_notices


def save_current_notices(notices):
    """현재 공지사항 안전하게 저장"""
    try:
        os.makedirs('data', exist_ok=True)

        json_content = json.dumps(notices, ensure_ascii=False, indent=2)

        with open('data/last_posts.json', 'w', encoding='utf-8') as f:
            f.write(json_content)

        print(f"데이터 저장 완료: {len(notices)}개 공지")

    except Exception as e:
        print(f"데이터 저장 실패: {e}")


async def main():
    start_time = datetime.now()
    try:
        print("=" * 60)
        print(f"완산수영장 알림봇 시작 - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1단계: 현재 모든 공지사항 가져오기
        current_notices = crawl_all_notices()

        # 2단계: 이전 공지사항 로드
        last_notices = load_previous_notices()

        # 3단계: 새로운 게시글 찾기
        new_notices = find_new_notices(current_notices, last_notices)

        print("=" * 30)
        print(f"📊 결과 요약:")
        print(f"  전체 공지사항: {len(current_notices)}개")
        print(f"  새로운 게시글: {len(new_notices)}개")
        print("=" * 30)

        # 4단계: 새로운 게시글이 있으면 모두 텔레그램 전송
        if new_notices:
            print("🚨 새로운 공지사항 발견! 텔레그램 전송 시작...")

            for i, notice in enumerate(new_notices):
                message = f"""
🏊‍♀️ <b>완산수영장 새 공지사항!</b>

📋 <b>{notice['title']}</b>
📅 등록일: {notice['date']}
🔗 <a href="{notice['link']}">공지사항 보기</a>

✨ 새로 등록된 공지사항입니다!
🤖 ScraperAPI 자동 모니터링
                """.strip()

                await send_telegram_message(message)
                print(f"  ✅ 알림 전송 완료 [{i + 1}/{len(new_notices)}]: {notice['title']}")

                if i < len(new_notices) - 1:
                    time.sleep(2)  # 메시지 간 2초 간격

        else:
            # 새로운 게시글이 없는 경우
            end_time = datetime.now()
            duration = (end_time - start_time).seconds

            success_message = f"""
✅ <b>완산수영장 알림봇 정상 작동</b>

📋 전체 공지사항 {len(current_notices)}개 확인 완료
🆕 새로운 게시글 없음
⏱️ 실행시간: {duration}초
📅 확인 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
🔄 다음 확인: 2시간 후

🌐 ScraperAPI 모니터링 중
            """.strip()
            await send_telegram_message(success_message)

        # 5단계: 현재 모든 공지사항 저장 (다음번 비교용)
        save_current_notices(current_notices)

        print("=" * 60)
        print("✅ 작업 완료!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        error_message = f"""❌ 완산수영장 알림봇 오류 발생

🔧 오류 내용: {str(e)[:150]}...
📅 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔄 다음 실행 시 다시 시도됩니다.
        """.strip()

        await send_telegram_message(error_message, use_html=False)


if __name__ == "__main__":
    asyncio.run(main())
