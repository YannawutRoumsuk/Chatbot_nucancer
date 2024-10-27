Python
1.ติดตั้ง Python เวอร์ชั่นล่าสุด หรือ เวอร์ชั่น 3.11.4
2.ไฟล์  cerds.json ให้แทนที่ด้วยไฟล์ที่ได้จาก Google APIs สามารถดูวิที่ทำได้จาก : https://www.youtube.com/watch?v=ISOd3D7Oik0#t=7m37s
สามารถ Duplicate google sheet ได้จาก : 
3.เปิดไฟล์  config.json ด้วย Notepad จากนั้นแก้ parameter client_url ให้เป็นลิงค์ mongoDB อันใหม่
ใน mongoDB ให้สร้าง Database ชื่อ chatbot_to_db
4.เปิดไฟล์ Run.py ไปที่ function userID() ตรง parameter line_bot_api ให้แทนที่ด้วย channel access token อันใหม่
5.ใช้ ngrok ในการจำลองเซิฟเวอร์โดยใช้คำสั่ง ngrok http 5000 (หมายเหตุ : ต้องทำการสมัคร ngrok ก่อนใช้งาน https://ngrok.com/)
6.รันไฟล์ Run.py ด้วย VSCode