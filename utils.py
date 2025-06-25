import re
from telegram.ext.filters import MessageFilter
import aiohttp
import asyncio
import pandas as pd
import os
class CleanedDigitsFilter(MessageFilter):
    def __init__(self, pattern):
        self.pattern = pattern

    def filter(self, message):
        if message.text:
            cleaned_input = ''.join(filter(str.isdigit, message.text))
            return bool(re.match(self.pattern, cleaned_input))
        return False
regex_patternmablagh = r"\b\d+\b"
filtermablagh = CleanedDigitsFilter(regex_patternmablagh)


async def profile(api_key):
    url = "https://seller.digikala.com/api/v1/profile/"
    headers = {'Authorization': api_key}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()

            if data.get('status') == 'ok':
                d = data.get('data', {})
                rate = d.get('seller_rate', {})
                satisfaction = d.get('satisfaction_rate', {})

                def safe(val, default="نامشخص"):
                    return str(val) if val is not None else default

                reply = "📊 اطلاعات فروشنده:\n"
                reply += f"🆔 آیدی فروشنده: {safe(d.get('id'))}\n"
                reply += f"🏢 نام کسب‌و‌کار: {safe(d.get('business_name'))}\n"
                reply += f"📄 وضعیت قرارداد: {safe(d.get('contract_status'))}\n"
                reply += f"🎓 وضعیت آموزش: {safe(d.get('training_status'))}\n"

                reply += "\n📈 امتیازات عملکرد:\n"
                reply += f"🔁 لغو سفارش: {safe(rate.get('cancel_percentage'), '۰')}٪ ({safe(rate.get('cancel_summarize'))})\n"
                reply += f"↩️ مرجوعی: {safe(rate.get('return_percentage'), '۰')}٪ ({safe(rate.get('return_summarize'))})\n"
                reply += f"🚚 ارسال به‌موقع: {safe(rate.get('ship_on_time_percentage'), '۰')}٪ ({safe(rate.get('ship_on_time_summarize'))})\n"
                reply += f"🌟 امتیاز نهایی: {safe(rate.get('final_score'), '۰')} / 5 ({safe(rate.get('final_percentage'), '۰')}٪)\n"

                reply += "\n🙋‍♂️ رضایت مشتری:\n"
                reply += f"✅ تعداد نظرسنجی: {safe(satisfaction.get('count'), '۰')}\n"
                reply += f"⭐️ امتیاز رضایت: {safe(satisfaction.get('rate'), '۰')} / 5\n"

                return True, reply
            else:
                return False, "❌ فروشنده یافت نشد یا کلید نامعتبر است."
async def seller_id(api_key):
    url = "https://seller.digikala.com/api/v1/profile/"
    headers = {'Authorization': api_key}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            if data['status'] == 'ok':
                return data['data']['id']
            else:
                return None
async def get_digikala_productsversion1(api_key):
    url = "https://seller.digikala.com/api/v1/variants/"
    headers = {'Authorization': api_key}
    current_page = 1
    all_items = {}

    async with aiohttp.ClientSession() as session:
        while True:
            page_url = f"{url}?page={current_page}"
            async with session.get(page_url, headers=headers) as response:
                data = await response.json()

            if 'data' not in data or 'items' not in data['data']:
                break

            for item in data['data']['items']:
                if item['is_active']:
                    id = item['id']
                    all_items[id] = {
                        'product_id': item['product']['id'],
                        'title': item['title'],
                        'is_active': item['is_active'],
                        'promo_price': item['extra']['promotion_data']['promo_price'],
                        'pricesell': item['price']['selling_price'],
                        'refprice': item['price']['reference_price'],
                        'rrp_price': item['price']['rrp_price'],
                        'buy_box_price': item['extra']['buy_box']['buy_box_price'],
                        'is_buy_box_winner': item['extra']['buy_box']['is_buy_box_winner'],
                        'is_seller_buy_box_winner': item['extra']['buy_box']['is_seller_buy_box_winner'],
                    }

            if current_page >= data['data']['pager']['total_page']:
                break
            current_page += 1

        sellerid = await seller_id(api_key)
        product_ids = [item['product_id'] for item in all_items.values()]
        unique_product_ids = list(set(product_ids))
        allofthem = {}

        tasks = []
        for id in unique_product_ids:
            tasks.append(asyncio.create_task(get_digikala_productspricesversion1(session, id)))
            await asyncio.sleep(0.1)
        results = await asyncio.gather(*tasks)
        allofthem = dict(zip(unique_product_ids, results))
        for item in all_items.values():
            product_id = item['product_id']
            com = []
            our = []
            if product_id in allofthem:
                for a in allofthem[product_id]:
                    if a['seller_id'] == sellerid:
                        our.append(a)
                    else:
                        com.append(a)
                item['قیمت رقبا'] = com
                item['قیمت ها فروشگاه'] = our

        for item in all_items.values():
            comp_prices = item.get('قیمت رقبا', [])
            our_prices = item.get('قیمت ها فروشگاه', [])
            com_pricesselling = [v['selling_price'] for v in comp_prices if v['selling_price'] is not None]
            our_pricesselling = [v['selling_price'] for v in our_prices if v['selling_price'] is not None]
            item['min_competitor_price'] = min(com_pricesselling) if com_pricesselling else None
            item['min_our_price'] = min(our_pricesselling) if our_pricesselling else None

    return all_items
async def get_digikala_productspricesversion1(session, product_id):
    url = f"https://api.digikala.com/v2/product/{product_id}/"
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
    except aiohttp.ClientError as e:
        return None
    except json.JSONDecodeError as e:
        return None

    variants = data.get('data', {}).get('product', {}).get('variants', [])
    productid = data.get('data', {}).get('product', {}).get('id', None)
    variant_data = []
    for variant in variants:
        variant_info = {
            'variant_id': variant.get('id', None),
            'seller_id': variant.get('seller').get('id', None),
            'selling_price': variant.get('price', None).get('selling_price', {}),
        }
        variant_data.append(variant_info)

    if not variant_data:
        return None
    return variant_data
def makeexcel(products, user_id):
    df = pd.DataFrame(products).T.reset_index()
    df.rename(columns={'index': 'ID'}, inplace=True)
    df['Activation'] = '0'
    df['minprice'] = ''
    df['DecreamentPrice'] = ''
    df['نتیجه عملیات قیمت گذاری'] = ''
    df['Activationpromotion']='0'
    script_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(script_dir, f'{user_id}_price.xlsx')
    df.to_excel(file_path, index=False)

    return file_path

async def viewvariant(session, api_key, variant_id):
    varianturl = f"https://seller.digikala.com/api/v1/variants/{variant_id}/"
    headers = {'Authorization': api_key}
    async with session.get(varianturl, headers=headers) as response:
        data = await response.json()
        if data['status'] == 'ok':
            data = data['data']
            isbuyboxwinner = data['extra']['buy_box']['is_buy_box_winner']
            is_seller_buy_box_winner = data['extra']['buy_box']['is_seller_buy_box_winner']
            buy_box_price = int(data['extra']['buy_box']['buy_box_price'])
            pricesell = int(data['price']['selling_price'])
            return isbuyboxwinner, is_seller_buy_box_winner, buy_box_price, pricesell, data['is_active']
        else:
            return None,None,None,None,None


async def updatevariant(session, api_key, variant_id, price):
    varianturl = f"https://seller.digikala.com/api/v1/variants/{variant_id}/"
    payload = {"price": price}
    headers = {'Authorization': api_key}
    async with session.put(varianturl, headers=headers, json=payload) as response:
        data = await response.json()
        if data['status'] == 'ok':
            data = data['data']
            reply = f"آیدی واریانت : {data['id']}" + "\n" + f"قیمت فروش : {data['price']['selling_price']}" + "\n"
            return reply
        else:
            return data
async def sendapi(context):
    token = context.user_data['token']
    allitems = copy.deepcopy(context.user_data['all_items'])
    sellerid = await seller_id(token)
    promoitems={}
    promotahlil={}
    async with aiohttp.ClientSession() as session:
        url = "https://seller.digikala.com/api/v1/variants/"
        headers = {'Authorization': token}
        current_page = 1
        allitemsnew = {}
        while True:
            await asyncio.sleep(1)
            page_url = f"{url}?page={current_page}"
            async with session.get(page_url, headers=headers) as response:
                data = await response.json()

            if 'data' not in data or 'items' not in data['data']:
                break

            for item in data['data']['items']:
                if item['is_active']:
                    id = item['id']
                    allitemsnew[id] = {
                        'product_id': item['product']['id'],
                        'promo_price': item['extra']['promotion_data']['promo_price'],
                        'pricesell': item['price']['selling_price'],
                        'refprice': item['price']['reference_price'],
                        'rrp_price': item['price']['rrp_price'],
                        'buy_box_price': item['extra']['buy_box']['buy_box_price'],
                        'is_buy_box_winner': item['extra']['buy_box']['is_buy_box_winner'],
                        'is_seller_buy_box_winner': item['extra']['buy_box']['is_seller_buy_box_winner'],
                        }

            if current_page >= data['data']['pager']['total_page']:
                break
            current_page += 1
        product_ids = [item['product_id'] for item in allitemsnew.values()]
        unique_product_ids = list(set(product_ids))
        productdata={}
        for id in unique_product_ids:
            productdata[id]=await get_digikala_productspricesversion1(session, id)
            await asyncio.sleep(2)
        for item in allitemsnew.values():
            product_id = item['product_id']
            com = []
            our = []
            if product_id in productdata:
                for a in productdata[product_id]:
                    if a['seller_id'] == sellerid:
                        our.append(a)
                    else:
                        com.append(a)
                item['قیمت رقبا'] = com
                item['قیمت ها فروشگاه'] = our
        for item in allitemsnew.values():
            comp_prices = item.get('قیمت رقبا', [])
            our_prices = item.get('قیمت ها فروشگاه', [])
            com_pricesselling = [v['selling_price'] for v in comp_prices if v['selling_price'] is not None]
            our_pricesselling = [v['selling_price'] for v in our_prices if v['selling_price'] is not None]
            item['min_competitor_price'] = min(com_pricesselling) if com_pricesselling else None
            item['min_our_price'] = min(our_pricesselling) if our_pricesselling else None
        for key, value in allitems.items():
            try:
                variant_id = key
                product_id = value['product_id']
                if not value['is_active']:
                    value['نتیجه عملیات قیمت گذاری'] = "محصول غیر فعال است."
                    continue
                if value['Activation'] != 1:
                    value['نتیجه عملیات قیمت گذاری'] = "محصول غیر فعال است."
                    continue
                minprice = int(value['minprice'])
                DecreamentPrice = int(value['DecreamentPrice'])
                isbuyboxwinner=allitemsnew[key]['is_buy_box_winner']
                is_seller_buy_box_winner=allitemsnew[key]['is_seller_buy_box_winner']
                buy_box_price=allitemsnew[key]['buy_box_price']
                pricesell=allitemsnew[key]['pricesell']
                value['قیمت رقبا']= allitemsnew[key]['قیمت رقبا']
                value['قیمت ها فروشگاه']=allitemsnew[key]['قیمت ها فروشگاه']
                value['pricesell'] = int(pricesell)
                value['buy_box_price'] = buy_box_price
                value['is_buy_box_winner'] = isbuyboxwinner
                value['is_seller_buy_box_winner'] = is_seller_buy_box_winner


                value['min_competitor_price'] = allitemsnew[key]['min_competitor_price']
                value['min_our_price'] =allitemsnew[key]['min_our_price']

                if value['min_competitor_price']:
                    if value['min_competitor_price']== value['min_our_price']:
                        minpriceupdate = value['min_competitor_price'] - DecreamentPrice
                    elif value['min_our_price'] > value['min_competitor_price']:
                        minpriceupdate = value['min_competitor_price'] - DecreamentPrice
                    elif value['min_our_price'] < value['min_competitor_price']:
                        minpriceupdate = value['min_competitor_price'] - DecreamentPrice

                else:
                    value['نتیجه عملیات قیمت گذاری'] = "قیمت فروشگاه بدون رقیب است."
                    continue

                if minpriceupdate < minprice:
                    value['نتیجه عملیات قیمت گذاری'] = "قیمت از قیمت کمینه کمتر است."
                    continue
                elif minpriceupdate >= minprice:
                    if minpriceupdate == pricesell:
                        value['نتیجه عملیات قیمت گذاری'] = "قیمت کالا بهینه است."
                    else:
                        await asyncio.sleep(2)
                        data = await updatevariant(session, token, variant_id, minpriceupdate)
                        value['نتیجه عملیات قیمت گذاری'] = data
            except Exception as e:
                text = "خطا داریم. " + "\n" + "خطا:" + f" {e} "
                value['نتیجه عملیات قیمت گذاری'] = text
    for key, value in allitems.items():
        if value.get('Activationpromotion') == 1 and key in allitemsnew:
            tehran_tz = pytz.timezone('Asia/Tehran')
            tehran_time = datetime.now(tehran_tz)
            tehran_time_plus_3_hours = tehran_time + timedelta(minutes=15)
            jalali_datetime = JalaliDateTime.fromtimestamp(tehran_time_plus_3_hours.timestamp())
            tehran_time_plus_3_days = tehran_time + timedelta(hours=3)
            jalali_datetime_plus_3_days = JalaliDateTime.fromtimestamp(tehran_time_plus_3_days.timestamp())
            formatted_jalali_datetime_plus_3_days = jalali_datetime_plus_3_days.strftime('%Y/%m/%d %H:%M:%S')
            formatted_jalali_datetime = jalali_datetime.strftime('%Y/%m/%d %H:%M:%S')
            DecreamentPrice = int(value['DecreamentPrice'])
            if allitemsnew[key]['min_competitor_price']:
                behine = allitemsnew[key]['min_competitor_price'] - DecreamentPrice
            else:
                behine=int(allitemsnew[key]['pricesell'])
            if behine < int(value['minprice']):
                behine=int(value['minprice'])

            promotahlil[key] = {
                "کد تنوع":key,
                "عنوان تنوع":value['title'],
                "کد محصول":value['product_id'],
                "کد تنوع های فروشگاه با قیمت":allitemsnew[key]['قیمت ها فروشگاه'],
                "کد تنوع های رقیب با قیمت":allitemsnew[key]['قیمت رقبا'],
                "قیمت کمینه رقبا":allitemsnew[key]['min_competitor_price'],
                "قیمت کمینه فروشگاه":allitemsnew[key]['min_our_price'],
                "قیمت کمینه مجاز":value['minprice'],
                "قیمت بهینه":behine,

            }
            promoitems[key] = {
                "کد تنوع (الزامی)":key,
                "کد محصول":value['product_id'],
                "گروه کالایی":"",
                "عنوان تنوع":value['title'],
                "قیمت در بازار":"",
                "قیمت فروش":"",
                "موجودی نزد دیجی کالا":"",
                "موجودی نزد فروشنده":"",
                "حداقل تخفیف مجاز":"",
                "مقدار تخفیف (ریال)":"",
                "حداکثر قیمت مجاز (ریال)":"",
                "قیمت پیشنهادی در پروموشن - ریال (الزامی)":int(behine),
                'تعداد در پروموشن (الزامی)': 10,
                'تعداد در سبد (الزامی)': 1,
                'شروع (الزامی)': formatted_jalali_datetime,
                'پایان (الزامی)': formatted_jalali_datetime_plus_3_days,

            }




    return allitems,promoitems,promotahlil


async def get_digikala_productsprices(product_id: str):
    url = f"https://api.digikala.com/v2/product/{product_id}/"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
        except aiohttp.ClientError as e:
            print(f"Request failed: {e}")
            return None
        except aiohttp.ContentTypeError as e:
            print(f"Invalid JSON response: {e}")
            return None

    variants = data.get('data', {}).get('product', {}).get('variants', [])
    product_id = data.get('data', {}).get('product', {}).get('id', None)

    variant_data = []
    for variant in variants:
        variant_info = {
            'product_id': product_id,
            'variant_id': variant.get('id', None),
            'selling_price': variant.get('price', {}).get('selling_price', None),
            'discount_percent': variant.get('price', {}).get('discount_percent', None),
        }
        variant_data.append(variant_info)

    if not variant_data:
        return None
    return variant_data