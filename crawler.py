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


def crawl_notices():
    # 세션 생성 (쿠키 및 연결 유지)
    session = requests.Session()

    # 더 상세한 헤더 설정
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1'
    }

    session.headers.update(headers)

    url = "https://www.jjss.or.kr/reserv/planweb/board/list.9is"
    params = {
        'contentUid': 'ff8080816c5f9de6016cd702efc70de1',
        'boardUid': 'ff8080816d4d1c03016d85eb2aff02cd',
        'categoryUid2': 'C1'
    }

    # 다중 재시도 로직
    max_retries = 5
    backoff_factor = 2

    for attempt in range(max_retries):
        try:
            print(f"크롤링 시도 {attempt + 1}/{max_retries}")

            # 첫 번째 시도에서는 메인 페이지에 먼저 접근
            if attempt == 0:
                try:
                    main_response = session.get(
                        "https://www.jjss.or.kr",
                        timeout=15
                    )
                    print(f"메인 페이지 접근 성공: {main_response.status_code}")
                    time.sleep(1)
                except:
                    print("메인 페이지 접근 실패, 직접 접근 시도")

            response = session.get(
                url,
                params=params,
                timeout=30,
                allow_redirects=True
            )

            response.raise_for_status()
            print(f"크롤링 성공: {response.status_code}")
            break

        except requests.exceptions.Timeout:
            print(f"타임아웃 발생 (시도 {attempt + 1})")
        except requests.exceptions.ConnectionError:
            print(f"연결 오류 발생 (시도 {attempt + 1})")
        except requests.exceptions.RequestException as e:
            print(f"요청 오류 발생 (시도 {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            wait_time = backoff_factor ** attempt
            print(f"{wait_time}초 대기 후 재시도...")
            time.sleep(wait_time)
        else:
            raise Exception(f"모든 재시도 실패. 사이트 접근 불가능")

    soup = BeautifulSoup(response.content, 'html.parser')

    # 공지사항 테이블에서 데이터 추출
    notices = []
    table = soup.find('table', class_='bbsList bbs01')

    if not table:
        print("공지사항 테이블을 찾을 수 없습니다.")
        return notices

    tbody = table.find('tbody')
    if not tbody:
        print("테이블 본문을 찾을 수 없습니다.")
        return notices

    rows = tbody.find_all('tr')

    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 6:
            title_cell = cells[2]
            title_link = title_cell.find('a')
            if title_link:
                title_span = title_link.find('span')
                if title_span:
                    title = title_span.get_text(strip=True)
                    link = 'https://www.jjss.or.kr/reserv/planweb/board/' + title_link['href']
                    date = cells[4].get_text(strip=True)

                    # "신규" 또는 "초급" 키워드 필터링
                    if "신규" in title or "초급" in title:
                        notices.append({
                            'title': title,
                            'link': link,
                            'date': date
                        })
                        print(f"발견된 공지: {title}")

    session.close()  # 세션 정리
    return notices


async def main():
    try:
        print("완산수영장 알림봇 시작...")

        current_notices = crawl_notices()

        # 이전 공지사항 데이터 로드
        try:
            with open('data/last_posts.json', 'r', encoding='utf-8') as f:
                last_notices = json.load(f)
        except FileNotFoundError:
            last_notices = []

        # 새로운 공지사항 찾기
        last_titles = {notice['title'] for notice in last_notices}
        new_notices = [notice for notice in current_notices
                       if notice['title'] not in last_titles]

        print(f"전체 공지: {len(current_notices)}개, 새 공지: {len(new_notices)}개")

        # 새 공지사항이 있으면 텔레그램 전송
        if new_notices:
            for notice in new_notices:
                message = f"""
🏊‍♀️ <b>완산수영장 신규/초급 공지</b>

📋 <b>{notice['title']}</b>
📅 등록일: {notice['date']}
🔗 <a href="{notice['link']}">공지사항 보기</a>
                """.strip()
                await send_telegram_message(message)
                time.sleep(1)
        else:
            # 정상 작동 확인 메시지 (선택사항)
            success_message = f"""
✅ <b>완산수영장 알림봇 정상 작동</b>

🔍 신규/초급 공지사항 {len(current_notices)}개 확인 완료
📅 확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔄 다음 확인: 2시간 후
            """.strip()
            await send_telegram_message(success_message)

        # 현재 공지사항 저장
        os.makedirs('data', exist_ok=True)
        with open('data/last_posts.json', 'w', encoding='utf-8') as f:
            json.dump(current_notices, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"오류 발생: {e}")
        error_message = f"""❌ 완산수영장 알림봇 오류 발생

오류: 사이트 접근 실패
시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

다음 실행 시 다시 시도됩니다."""

        await send_telegram_message(error_message, use_html=False)


if __name__ == "__main__":
    asyncio.run(main())
