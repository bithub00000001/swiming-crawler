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
        # HTML 파싱 에러 시 일반 텍스트로 재시도
        if use_html:
            await send_telegram_message(message, use_html=False)
        else:
            print(f"텔레그램 전송 실패: {e}")


def crawl_notices():
    url = "https://www.jjss.or.kr/reserv/planweb/board/list.9is"
    params = {
        'contentUid': 'ff8080816c5f9de6016cd702efc70de1',
        'boardUid': 'ff8080816d4d1c03016d85eb2aff02cd',
        'categoryUid2': 'C1'  # 완산수영장
    }

    # User-Agent 헤더 추가 (크롤링 차단 방지)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    # 재시도 로직 추가
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"크롤링 시도 {attempt + 1}/{max_retries}")
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=30  # 30초 타임아웃 설정
            )
            response.raise_for_status()  # HTTP 에러 확인
            break
        except Exception as e:
            print(f"시도 {attempt + 1} 실패: {e}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(2)  # 2초 대기 후 재시도

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
            title_cell = cells[2]  # 제목 컬럼
            title_link = title_cell.find('a')
            if title_link:
                title_span = title_link.find('span')
                if title_span:
                    title = title_span.get_text(strip=True)
                    link = 'https://www.jjss.or.kr/reserv/planweb/board/' + title_link['href']
                    date = cells[4].get_text(strip=True)  # 등록일

                    # "신규" 또는 "초급" 키워드 필터링
                    if "신규" in title or "초급" in title:
                        notices.append({
                            'title': title,
                            'link': link,
                            'date': date
                        })
                        print(f"발견된 공지: {title}")

    return notices


async def main():
    try:
        # 시작 메시지 전송
        start_message = """
🏊‍♀️ <b>완산수영장 신규/초급 알림봇 시작!</b>

✅ 봇이 정상적으로 작동 중입니다.
🔍 "신규" 또는 "초급" 키워드가 포함된 공지사항을 모니터링합니다.
⏰ 2시간마다 확인합니다.

📅 시작 시간: {}
        """.format(datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")).strip()

        await send_telegram_message(start_message)

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
                time.sleep(1)  # 메시지 간 1초 간격
        else:
            print("새로운 공지사항이 없습니다.")

        # 현재 공지사항 저장
        os.makedirs('data', exist_ok=True)
        with open('data/last_posts.json', 'w', encoding='utf-8') as f:
            json.dump(current_notices, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"오류 발생: {e}")
        # 오류 메시지를 일반 텍스트로 전송 (HTML 파싱 에러 방지)
        error_message = f"""❌ 완산수영장 알림봇 오류 발생

오류 내용: {str(e)[:200]}
시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

다음 실행 시 다시 시도됩니다."""

        await send_telegram_message(error_message, use_html=False)


if __name__ == "__main__":
    asyncio.run(main())
