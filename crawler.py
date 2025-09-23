import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import asyncio
from telegram import Bot

# GitHub Secrets에서 환경변수 가져오기
BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']


async def send_telegram_message(message):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='HTML')


def crawl_notices():
    url = "https://www.jjss.or.kr/reserv/planweb/board/list.9is"
    params = {
        'contentUid': 'ff8080816c5f9de6016cd702efc70de1',
        'boardUid': 'ff8080816d4d1c03016d85eb2aff02cd',
        'categoryUid2': 'C1'  # 완산수영장
    }

    response = requests.get(url, params=params)
    soup = BeautifulSoup(response.content, 'html.parser')

    # 공지사항 테이블에서 데이터 추출
    notices = []
    table = soup.find('table', class_='bbsList bbs01')
    rows = table.find('tbody').find_all('tr')

    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 6:
            title_cell = cells[2]  # 제목 컬럼
            title_link = title_cell.find('a')
            if title_link:
                title = title_link.find('span').get_text(strip=True)
                link = 'https://www.jjss.or.kr/reserv/planweb/board/' + title_link['href']
                date = cells[4].get_text(strip=True)  # 등록일

                # "신규" 또는 "초급" 키워드 필터링
                if "신규" in title or "초급" in title:
                    notices.append({
                        'title': title,
                        'link': link,
                        'date': date
                    })

    return notices


async def main():
    try:
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

        # 현재 공지사항 저장
        os.makedirs('data', exist_ok=True)
        with open('data/last_posts.json', 'w', encoding='utf-8') as f:
            json.dump(current_notices, f, ensure_ascii=False, indent=2)

    except Exception as e:
        error_message = f"❌ 크롤링 오류 발생: {str(e)}"
        await send_telegram_message(error_message)


if __name__ == "__main__":
    asyncio.run(main())
