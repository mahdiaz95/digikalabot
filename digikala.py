import re
import os
import io
import json
import copy
import pickle
import asyncio
import logging
import aiohttp
import aiofiles
import pandas as pd
import pytz
from datetime import datetime, timedelta
from persiantools.jdatetime import JalaliDateTime
from playwright.async_api import async_playwright
from telegram import (
    Update, InputFile, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler,
    ConversationHandler,  filters, CallbackContext
)
from telegram.ext.filters import MessageFilter
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils import ( CleanedDigitsFilter , filtermablagh,regex_patternmablagh,profile
,get_digikala_productsversion1 , get_digikala_productspricesversion1 , makeexcel , viewvariant , updatevariant
,get_digikala_productsprices , sendapi )
bottoken="token"
AUTHORIZED_USERS = {}
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)
playwright_instances = {}
ASK_TOKEN, ASK_ORDER_TYPE, ASK_DESCRIPTION, ASK_TIME, ASK_MABLAGH, \
ASK_RESTART,ASK_EXCEL,ASK_LOGIN1,ASK_LOGIN2,ASK_LOGIN3,SET_TIMERPROMO= range(11)
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

ASK_TOKEN = 0
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    if user_id in AUTHORIZED_USERS:
        reply = (
            "سلام به ربات قیمت‌گذاری رقابتی دیجی‌کالا خوش آمدید!\n"
            "🌟 لطفاً توکن فروشگاه خود را ارسال کنید. 🔑"
        )
        await update.message.reply_text(reply)
        return ASK_TOKEN
    else:
        reply = "سلام ❗ شما مجاز به استفاده از ربات نیستید."
        await update.message.reply_text(reply)
        return ConversationHandler.END
async def token(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    text = update.message.text
    context.user_data['token'] = text
    status, data = await profile(text)
    if status:
        reply = data
        reply += "\n" + "منتظر بمانید تا اکسل آماده شود ⏳📊."

        await update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
        context.user_data['all_items'] = await get_digikala_productsversion1(context.user_data['token'])

        excel_file = makeexcel(context.user_data['all_items'], user.id)
        with open(excel_file, 'rb') as file:
            await update.message.reply_document(document=InputFile(file))
        await asyncio.sleep(1)
        reply += "لطفاً اکسل را دریافت و آن را ویرایش کنید. 📝 محصولاتی که قرار است در لوپ قیمت‌گذاری قرار گیرند را در قسمت activation مقدار 1 وارد کنید. ✅" + "\n"
        reply += "دقت شود کالا باید از قبل در سیستم فروشندگان دیجی‌کالا فعال باشد. ⚠️" + "\n"
        reply += "همچنین در قسمت DecreamentPrice مبلغی به ریال که باید کمتر از کمینه قیمت رقبا باشد را مشخص کنید. 💰" + "\n"
        reply += "در قسمت minprice قیمت کمترین حالت سوددهی محصول را وارد کنید. 📉" + "\n"
        reply += "دقت فرمایید هیچ گونه تغییر دیگری در اکسل ایجاد نکنید، خصوصاً در قسمت نام ستون‌ها. 🚫" + "\n"
        reply += "پس از اعمال تغییرات در اکسل، آن را دوباره بفرستید. 📤"

        await update.message.reply_text(reply)
        return ASK_ORDER_TYPE
    else:
        reply = "🔴 توکن اشتباه است. لطفاً توکن را دوباره وارد نمایید."
        if 'token' in context.user_data:
            del context.user_data['token']
        await update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
        return ASK_TOKEN


async def products(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    try:
        file = await context.bot.getFile(update.message.document.file_id)

        file_path = f'{user_id}__price.xlsx'
        await file.download_to_drive(file_path)

        df = pd.read_excel(file_path)
        for index, row in df.iterrows():
            item_id = row['ID']
            activation_value = row['Activation']
            minprice = row['minprice']
            DecreamentPrice = row['DecreamentPrice']
            activation_valuepromotion=row['Activationpromotion']
            if item_id in context.user_data['all_items']:
                context.user_data['all_items'][item_id]['Activation'] = activation_value
                context.user_data['all_items'][item_id]['minprice'] = minprice
                context.user_data['all_items'][item_id]['DecreamentPrice'] = DecreamentPrice
                context.user_data['all_items'][item_id]['Activationpromotion']=activation_valuepromotion
        await update.message.reply_text(
            'فایل ذخیره شد. 📁 حال زمان تکرار قیمت‌گذاری را به ثانیه وارد کنید ⏳ دقت کنید این زمان باید بین 600 تا 20000 باشد.')

        return ASK_TIME
    except:
        await update.message.reply_text(
            'اشتباهی در فایل آپلود شده موجود است لطفا دوباره بفرستید.')
        return ASK_ORDER_TYPE


def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


async def alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    allitems, promoitems, promotahlil = await sendapi(context)
    df_allitems = pd.DataFrame(allitems).T.reset_index()
    df_allitems.rename(columns={'index': 'ID'}, inplace=True)

    with io.BytesIO() as buffer:
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_allitems.to_excel(writer, sheet_name='gheimat', index=False)
        buffer.seek(0)
        

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await context.bot.send_document(
            chat_id=job.chat_id,
            document=buffer,
            filename=f'all_items_{current_time}.xlsx',
            caption="All Items Data"
        )
    
    df_promotahlil = pd.DataFrame.from_dict(promotahlil, orient='index')
    with io.BytesIO() as buffer:
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_promotahlil.to_excel(writer, sheet_name='Promo Tahlil', index=False)  # Remove index
        buffer.seek(0)
        await context.bot.send_document(
            chat_id=job.chat_id,
            document=buffer,
            filename=f'promo_tahlil_{current_time}.xlsx',
            caption="Promo Tahlil Data"
        )
    df_promoitems = pd.DataFrame.from_dict(promoitems, orient='index')
    script_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(script_dir, f'{job.name}_price.xlsx')
    df_promoitems.to_excel(file_path, index=False)
    with io.BytesIO() as buffer:    
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_promoitems.to_excel(writer, sheet_name='Promo Items', index=False)
        buffer.seek(0)
        
        await context.bot.send_document(
            chat_id=job.chat_id,
            document=buffer,
            filename=f'promo_items_{current_time}.xlsx',
            caption="Promo Items Data"
            )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                playwright_context = await browser.new_context()
                script_dir = os.path.dirname(os.path.abspath(__file__))
                cookie_dir = os.path.join(script_dir, f"{job.name}.digikala_cookies.pkl")
                with open(cookie_dir, "rb") as file:
                    cookies = pickle.load(file)
                await playwright_context.add_cookies(cookies)
                page = await playwright_context.new_page()
            
            
                await page.goto('https://seller.digikala.com/pwa/smart-discount-flow/add-product')
                await page.wait_for_selector(
                    'xpath=//*[@id="app"]/section/main/div[1]/div/section[2]/div[1]/div[2]/div[1]/div/button/div'
                    )

                await page.click(
                    'xpath=//*[@id="app"]/section/main/div[1]/div/section[2]/div[1]/div[2]/div[1]/div/button/div'
                     )
                await page.wait_for_selector("input[type='file']", state='attached')
                screenshot_path = os.path.join(os.getcwd(), f"screenshot_takhfif_{job.chat_id}.png")
                await page.screenshot(path=screenshot_path)
                async with aiofiles.open(screenshot_path, 'rb') as photo_file:
                    photo_bytes = await photo_file.read()
                    await context.bot.send_photo(chat_id=job.chat_id, photo=photo_bytes)
           
                await page.set_input_files("input[type='file']",file_path)
              
                await asyncio.sleep(5)
                screenshot_path = os.path.join(os.getcwd(), f"screenshot_takhfif_{job.chat_id}.png")
                await page.screenshot(path=screenshot_path)
                async with aiofiles.open(screenshot_path, 'rb') as photo_file:
                    photo_bytes = await photo_file.read()
                    await context.bot.send_photo(chat_id=job.chat_id, photo=photo_bytes)
                await browser.close()

                await context.bot.send_message(chat_id=job.chat_id,text="تخفیف هوشمند با موفقیت بارگزاری شد.")
        except Exception as e :
            await context.bot.send_message(chat_id=job.chat_id,text=f"خطا بارگزاری تخفیف هوشمند رخ داد.{e}")
        




async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    text = update.message.text
    chat_id = update.effective_message.chat_id
    if int(text) > 20000 or int(text) < 600:
        await update.message.reply_text("لطفا ⏳ زمان بین 600 تا 20000 انتخاب کنید.")
        return ASK_TIME

    try:
        job_removed = remove_job_if_exists(str(chat_id), context)

        context.job_queue.run_repeating(
            alarm, int(text), user_id=user_id, chat_id=chat_id, first=2, name=str(chat_id)
        )

        text = "جاب با موفقیت بارگذاری شد. ✅" + "\n"
        if job_removed:
            text += "جاب قبلی از بین رفت. ❌"
        await update.effective_message.reply_text(text)


    except (IndexError, ValueError):
        await update.effective_message.reply_text("خطا داریم.")


async def unset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = "🔄 لوپ از بین رفت." if job_removed else "⚠️ لوپ فعالی موجود نیست."

    await update.message.reply_text(text)


async def excel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    await update.message.reply_text(
        "💰 لطفاً مقداری به ریال که کمتر از رقیب برای ساخت اکسل تخفیف هوشمند باید بزند را وارد کنید.")

    return ASK_EXCEL


async def excel1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    text = update.message.text
    dec = int(text)
    web_app_button = InlineKeyboardButton(
        text="سایت فروشندگان دیجی کالا",
        web_app=WebAppInfo(url='https://seller.digikala.com/pwa/smart-discount-flow/add-product'),
    )
    reply_markup = InlineKeyboardMarkup([[web_app_button]])
    reply = "⏳ لطفاً منتظر بمانید تا فایل اکسل فرستاده شود. سپس از لینک شیشه‌ای زیر وب‌اپ را باز کنید و فایل را آپلود کنید. 📤"
    await update.message.reply_text(reply, reply_markup=reply_markup)
    try:
    
        tehran_tz = pytz.timezone('Asia/Tehran')
        tehran_time = datetime.now(tehran_tz)
        tehran_time_plus_3_hours = tehran_time + timedelta(hours=2)
        jalali_datetime = JalaliDateTime.fromtimestamp(tehran_time_plus_3_hours.timestamp())
        tehran_time_plus_3_days = tehran_time + timedelta(hours=2, days=3)
        jalali_datetime_plus_3_days = JalaliDateTime.fromtimestamp(tehran_time_plus_3_days.timestamp())
        formatted_jalali_datetime_plus_3_days = jalali_datetime_plus_3_days.strftime('%Y/%m/%d %H:%M:%S')
        formatted_jalali_datetime = jalali_datetime.strftime('%Y/%m/%d %H:%M:%S')

        if 'token' in context.user_data:
            keys_to_delete = []
            product_data = await get_digikala_productsversion1(context.user_data['token'])

            for key, value in product_data.items():
                if value.get('promo_price') == '' or not value.get('is_active'):
                    keys_to_delete.append(key)
            for key in keys_to_delete:
                del product_data[key]

            product_id_to_variants = {}
            columns = [
                'کد تنوع (الزامی)', 'کد محصول', 'گروه کالایی', 'عنوان تنوع', 'قیمت در بازار',
                'قیمت فروش', 'موجودی نزد دیجی کالا', 'موجودی نزد فروشنده', 'حداقل تخفیف مجاز',
                'مقدار تخفیف (ریال)', 'حداکثر قیمت مجاز (ریال)', 'قیمت پیشنهادی در پروموشن - ریال (الزامی)',
                'تعداد در پروموشن (الزامی)', 'تعداد در سبد (الزامی)', 'شروع (الزامی)', 'پایان (الزامی)'
            ]
            columnsanalyze = [
                'کد محصول', 'کد تنوع های فروشگاه با قیمت', 'کد تنوع های رقیب با قیمت', 'قیمت کمینه رقبا',
                'قیمت کمینه فروشگاه', 'قیمت کمینه بهینه', 'کد تنوع های همه با قیمت'
            ]
            df = pd.DataFrame(columns=columns)
            dfanalyze = pd.DataFrame(columns=columnsanalyze)

            for variant_id, product in product_data.items():
                product_id = product['product_id']
                product['variant_id'] = variant_id
                del product['product_id']
                if product_id not in product_id_to_variants:
                    product_id_to_variants[product_id] = []
                product_id_to_variants[product_id].append(product)

            for key, value in product_id_to_variants.items():
                DecreamentPricePromo = dec
                productdata = await get_digikala_productsprices(key)
                transformed_listour = [{'variant_id': item['variant_id'], 'promo_price': item['promo_price']} for item
                                       in value]
                transformed_listcom = [{'variant_id': item['variant_id'], 'promo_price': item['selling_price']} for item
                                       in productdata]
                variant_ids_to_subtract = {item['variant_id'] for item in transformed_listour}
                resultcom = [item for item in transformed_listcom if item['variant_id'] not in variant_ids_to_subtract]

                if resultcom:
                    min_pricecom = min(item['promo_price'] for item in resultcom)
                    min_priceour = min(item['promo_price'] for item in transformed_listour)
                    minprice = min_pricecom - DecreamentPricePromo
                else:
                    min_pricecom = None
                    min_priceour = min(item['promo_price'] for item in transformed_listour)
                    minprice = min_priceour

                for val in value:
                    new_row = {
                        'کد تنوع (الزامی)': val['variant_id'],
                        'عنوان تنوع': val['title'],
                        'کد محصول': key,
                        'قیمت پیشنهادی در پروموشن - ریال (الزامی)': minprice,
                        'تعداد در پروموشن (الزامی)': 10,
                        'تعداد در سبد (الزامی)': 1,
                        'شروع (الزامی)': formatted_jalali_datetime,
                        'پایان (الزامی)': formatted_jalali_datetime_plus_3_days,
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                    new_row_analyze = {
                        'کد تنوع': val['variant_id'],
                        'کد محصول': key,
                        'عنوان تنوع': val['title'],
                        'کد تنوع های فروشگاه با قیمت': transformed_listour,
                        'کد تنوع های رقیب با قیمت': resultcom,
                        'کد تنوع های همه با قیمت': transformed_listcom,
                        'قیمت کمینه رقبا': min_pricecom,
                        'قیمت کمینه فروشگاه': min_priceour,
                        'قیمت کمینه بهینه': minprice,
                    }
                    dfanalyze = pd.concat([dfanalyze, pd.DataFrame([new_row_analyze])], ignore_index=True)

            formatted_str = formatted_jalali_datetime.replace('/', '-').replace(':', '-').replace(' ', '')

            with io.BytesIO() as output_buffer, io.BytesIO() as analyze_output_buffer:
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                output_buffer.seek(0)
                await context.bot.send_document(
                    user_id,
                    caption="این فایل طبق الگو تخفیف هوشمند دیجی کالا است.",
                    document=output_buffer,
                    filename=f'{user_id}.{formatted_str}.digikala_output.xlsx'
                )

                with pd.ExcelWriter(analyze_output_buffer, engine='openpyxl') as writer:
                    dfanalyze.to_excel(writer, index=False)
                analyze_output_buffer.seek(0)
                await context.bot.send_document(
                    user_id,
                    caption="این فایل تحلیل قیمت گذاری تخفیف هوشمند محصولات شماست.",
                    document=analyze_output_buffer,
                    filename=f'{user_id}.{formatted_str}.analyze_output.xlsx'
                )
        else:
            await update.message.reply_text("توکنی موجود نیست. لطفا ابتدا استارت کنید و توکن خود را بفرستید.")
    except Exception as e:
        print(e)
        await update.message.reply_text("خطای دیجی کالا. لطفا چند دقیقه دیگر دوباره تلاش کنید.")

async def login1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("لطفا شماره دیجی کالا را وارد کنید")
    return ASK_LOGIN1

 

async def login2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_message = update.message.text
    chat_id = update.message.chat.id

    await update.message.reply_text("در حال ورود به دیجی کالا.")

    playwright_context, screenshot_path = await initiate_playwright_login(user_id, user_message,context)

    if playwright_context and screenshot_path:
        context.user_data[user_id] = {'playwright_context': playwright_context}

        async with aiofiles.open(screenshot_path, 'rb') as photo_file:
            photo_bytes = await photo_file.read()
            await context.bot.send_photo(chat_id=chat_id, photo=photo_bytes)

        await update.message.reply_text("لطفاً رمز فرستاده شده از دیجی کالا را وارد کنید.")
        return ASK_LOGIN2
    else:
        await update.message.reply_text("خطا. عدم موفقیت آمیز بودن ورود")
        return -1
async def initiate_playwright_login(user_id, user_message,context:ContextTypes.DEFAULT_TYPE):
    if user_id not in playwright_instances:
        playwright = await async_playwright().start()
        playwright_instances[user_id] = playwright

    playwright_instance = playwright_instances[user_id]
    browser = await playwright_instance.chromium.launch(headless=True)
    playwright_context = await browser.new_context()
    page = await playwright_context.new_page()
    try:
        url = "https://seller.digikala.com/pwa/account/sign-in"
        await page.goto(url,timeout=60000)
        await page.fill("input[type='text']", user_message,timeout=50000)

        screenshot_path = os.path.join(os.getcwd(), f"screenshot_{user_id}.png")
        await page.screenshot(path=screenshot_path)
        async with aiofiles.open(screenshot_path, 'rb') as photo_file:
            photo_bytes = await photo_file.read()
            await context.bot.send_photo(chat_id=user_id, photo=photo_bytes)
        button_xpath = '//*[@id="app"]/section/div[1]/form/div/button/div'
        await page.wait_for_selector(button_xpath, state='visible')
        await page.click(button_xpath)
        
        await asyncio.sleep(3)
        screenshot_path = os.path.join(os.getcwd(), f"screenshot_{user_id}.png")
        await page.screenshot(path=screenshot_path)
        
        return playwright_context, screenshot_path
    except Exception as e:
        await context.bot.send_message(chat_id=user_id,text=f"خطای ورود دیجی کالا: {e}")
        await playwright_context.close()
        return None, None

async def submit_otp(playwright_context, user_id, otp,update):
    try:
        page = playwright_context.pages[0]
    
        
        for i in range(6):
            otp_xpath = f'//*[@id="app"]/section/div[1]/form/div[2]/div/div[{i + 1}]/input'
            await page.fill(otp_xpath, otp[i])
        print(page.url)
        await page.wait_for_url("https://seller.digikala.com/")
        
        await page.goto('https://seller.digikala.com/pwa/smart-discount-flow/add-product')
    
        cookies = await playwright_context.cookies()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cookie_dir = os.path.join(script_dir, f"{user_id}.digikala_cookies.pkl")
        with open(cookie_dir, "wb") as file:
            pickle.dump(cookies, file)

        await playwright_context.close() 
    
        if user_id in playwright_instances:
            playwright_instance = playwright_instances[user_id]
            await playwright_instance.stop() 
            del playwright_instances[user_id] 
        return True
    except Exception as e:
        await update.message.reply_text(f"خطا .لاگین موفقیت آمیز نبود.{e}")
        return False
async def login3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    otp = update.message.text
    chat_id = update.message.chat.id


    user_data = context.user_data.get(user_id)
    if not user_data or 'playwright_context' not in user_data:
        await update.message.reply_text("درایور موجود نیست.")
        return -1

    playwright_context = user_data['playwright_context']

    try:
        status=await submit_otp(playwright_context, user_id, otp,update)
        if status:
            await update.message.reply_text("ورود موفقیت آمیز بود و کوکی ها ذخیره شد.")
            return ASK_TOKEN
        else:
           await update.message.reply_text("خطا . لاگین موفقیت آمیز نبود.")
           return ASK_TOKEN 
    except Exception as e:
        await update.message.reply_text(f"خطا رخ داد: {str(e)}")
        await playwright_context.close() 
        return -1
def main() -> None:

    application = Application.builder().token(bottoken).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, token),
                        CommandHandler('unset', unset),
                        CommandHandler('excel', excel),


                        CommandHandler('login', login1),
                        ],
            ASK_LOGIN1:[
                CommandHandler('unset', unset),
                CommandHandler('excel', excel),

                MessageHandler(filters.TEXT & ~filters.COMMAND, login2),

            ],
            ASK_LOGIN2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login3),
                CommandHandler('unset', unset),
                CommandHandler('excel', excel),


            ],
            ASK_LOGIN3: [

                CommandHandler('unset', unset),
                CommandHandler('excel', excel),


            ],
            ASK_ORDER_TYPE: [MessageHandler(
                filters.Document.MimeType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), products),
                             MessageHandler(filters.Regex(r"^(🔙)?بازگشت$"), start),
                CommandHandler('unset', unset),
                CommandHandler('excel', excel),

                ],
            ASK_EXCEL:[
                MessageHandler(filtermablagh, excel1),
                MessageHandler(filters.Regex(r"^(🔙)?بازگشت$"), start),
                CommandHandler('unset', unset),
                CommandHandler('excel', excel),

            ],
            ASK_TIME:[MessageHandler(filtermablagh, set_timer),
                      MessageHandler(filters.Regex(r"^(🔙)?بازگشت$"), start),
                      CommandHandler('unset', unset),
                      CommandHandler('excel', excel),

                      ],
        },
        fallbacks=[CommandHandler('start', start)],
    )
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
