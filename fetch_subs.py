from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled

def fetch_and_save(vid, filename):
    print(f"Пытаемся скачать транскрипт для видео {vid}...")
    try:
        # Пробуем русский, если нет - английский
        tx = YouTubeTranscriptApi.get_transcript(vid, languages=['ru', 'en'])
        text = " ".join([x['text'].replace('\n', ' ') for x in tx])
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Успех! Сохранено в {filename} ({len(text)} символов)")
    except TranscriptsDisabled:
        print(f"Ошибка {vid}: Субтитры отключены автором видео.")
    except Exception as e:
        print(f"Ошибка {vid}: {e}")

fetch_and_save('1yfk8kREZCo', 'v1.txt')
fetch_and_save('n4kDabvMHY8', 'v2.txt')
