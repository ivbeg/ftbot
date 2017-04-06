import flickrapi
from telepot import Bot
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.expression import func

from settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from settings import FLICKR_API_KEY, FLICKR_API_SECRET, FLICKR_SEARCH_TAGS, FLICKR_SEARCH_LICENSE_ID, FLICKR_SEARCH_SORT, FLICKR_SEARCH_PRIVACY_FILTER
from settings import FLICKR_SEARCH_TEXT, FLICKR_SEARCH_TAGS_MODE, FLICKR_SEARCH_SAFE, FLICKR_SEARCH_CONTENT_TYPE
from database import PostImg, engine

import json
import os
import requests
from tempfile import TemporaryFile


##################################################################        

fflickr = flickrapi.FlickrAPI(FLICKR_API_KEY, FLICKR_API_SECRET, format='json')
bot = Bot(TELEGRAM_BOT_TOKEN)

sqlite_session = sessionmaker(bind=engine)
sqlite_session = sqlite_session()

##################################################################        


# Формируем ссылку на изображение flick для объекта из API
def flickrObj2Link(farm, server, id, secret):
    return "https://farm{farm}.staticflickr.com/{server}/{id}_{secret}_z.jpg".format(farm=farm, server=server, id=id, secret=secret)

# Выбираем в бд изображения, которые еще не постились в канал
dbGetFreshImg = lambda: sqlite_session.query(PostImg).filter_by(posted='0').order_by(func.random()).first()

# Добавляем изображение в бд, если его еще нет
def dbAddImg (flickr_id, owner):
    # Проверяем существование в базе данных
    if not sqlite_session.query(PostImg).filter_by(flickr_id=flickr_id,owner=owner).first():
        # Добавляем
        newImg = PostImg(flickr_id=flickr_id, owner=owner)
        sqlite_session.add(newImg)
        sqlite_session.commit();
        return True
    else:
        return False


# Вытаскиваем последние ссылки на фото и заносим в бд
def flickrRefresh (offset=0):
    data = json.loads(fflickr.photos.search(
        media='photos', 
        per_page=30, 
        tags=FLICKR_SEARCH_TAGS, 
        license=FLICKR_SEARCH_LICENSE_ID, 
        page=offset, sort=FLICKR_SEARCH_SORT, 
        privacy_filter=FLICKR_SEARCH_PRIVACY_FILTER, 
        content_type=FLICKR_SEARCH_CONTENT_TYPE, 
        safe_search=FLICKR_SEARCH_SAFE, 
        tag_mode=FLICKR_SEARCH_TAGS_MODE, 
        text=FLICKR_SEARCH_TEXT))
    for x in data['photos']['photo']:
        dbAddImg(x['id'], x['owner'])

# Скачиваем изображение по url и отправляем в Telegram
def telegramImgSend (url):
    with TemporaryFile() as f:
        f.write(requests.get(url).content)
        f.seek(0)
        bot.sendPhoto(TELEGRAM_CHAT_ID, f)

# Информация по ID о фото
def flickrPhotoInfo (flickr_id):
    d = fflickr.photos.getInfo(photo_id=flickr_id)
    try:
        data = json.loads(d)
    except TypeError as e:
        data = json.loads(d.decode())
    return data['photo'] if data else False

##################################################################        

# Ищем фото в базе, в случае необходимости пробуем найти новые фото, 
# которые еще не постили, до тех пор, пока не будет найдено новое изображение для постинга

# Считаем количество запросов новых фотографий
refreshCount = 0
# Смещение поиска при запросе новых фотографий с Flickr
offset = 0
while refreshCount < 9999:

    ## Проверяем, есть ли в базе фото, которые еще не постили
    freshImg = dbGetFreshImg()
    if not freshImg:
        if refreshCount == 1:
            # Свежие фотографии запросили, но они уже были опубликованы раньше, поэтому считаем количество существующих
            # фото в базе и отправляем запрос на поиск со смещением, чтобы выбрать более старые фотографии
            offset = sqlite_session.query(PostImg).count() / 100
        flickrRefresh(offset)   
        refreshCount += 1
        offset += 1
    else:
        # Получаем с Flickr инфу и фотографии
        photo = flickrPhotoInfo(freshImg.flickr_id)
        # Формируем линк на фото
        url = flickrObj2Link(photo['farm'], photo['server'], photo['id'], photo['secret'])
        # Отправляем в Telegram
        telegramImgSend(url)
        # Помечаем фото в базе отправленным
        freshImg.make_posted()
        sqlite_session.commit()
        # Обрываем бесконечный цикл
        break
