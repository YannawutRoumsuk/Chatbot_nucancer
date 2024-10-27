from database_utils import insert_chat_result, insert_patient_to_database
import mysql.connector
import re
import json
import os
from flask import Flask,jsonify
from flask import request
from flask import Response
from flask import make_response
from datetime import datetime
from linebot import LineBotApi #import lineapi for params line ID
import gspread #import google sheet
from oauth2client.service_account import ServiceAccountCredentials #import api google sheet
from pythainlp import word_tokenize, Tokenizer
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

#Connect Google Sheet
scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets'
         ,"https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
cerds = ServiceAccountCredentials.from_json_keyfile_name("cerds.json", scope)
client = gspread.authorize(cerds)
Chat_History = client.open("ChatbotCancer").worksheet('Chat history') # เป็นการเปิดไปยังหน้าชีตนั้นๆ
Violence_of_symptom = client.open("ChatbotCancer").worksheet('Violence of symptom') # เป็นการเปิดไปยังหน้าชีตนั้นๆ
Comeback_Status = client.open("ChatbotCancer").worksheet('Comeback status') # เป็นการเปิดไปยังหน้าชีตนั้นๆ


######## กระบวนการ
#1####### เช็ค intent แรกของอาการ 
#2####### เพื่อรับจำนวนคำถาม 
#3####### ไปต่อที่ Main ว่าเหลือกี่คำถามที่ต้องถาม ถ้าเหลือ 1 คือหมดคำถามแล้ว 
#4####### ไปที่ต้อง ADL เมื่อจบ ADL จะมีการถามอาการอื่นๆต่อ ถ้าผู้ใช้บอกว่ามีด้วย จะวนไปที่กระบวนการลำดับ 2
#5####### หาก ADL เคยถามไปแล้ว ก็จะถามอาการอื่นเลย
#6####### เมื่อถามอาการที่จำเป็นอาหารหลักหมดแล้ว จะทำการสรุปความรุนแรงแต่ละอาการและรวบรวมคำแนพนำ

###### index ของการเก็บเกรดความรุนแรง
###### 0 คือ คลื่นไส้
###### 1 คือ อาเจียน
###### 2 คือ กลับมาจากโรงพยาบาลเนื่องจากอาการอาเจียน
###### 3 คือ ท้องเสีย
###### 4 คือ อาการอื่นๆทั่วไป
###### 5 คือ อาการอื่นๆฉุกเฉิน
###### 6 คือ ADL เปลื่ยนไปใช้ ADL_l/2/3 แล้ว

User_List = {"User000": 0,} 
User_ID = ""
Had_User = False

Dangerous_lv1 = [[0,0,0,0,0,0,0]] #ความรุนแรงระดับที่ 1 เป็นจริงจะเท่ากับ 1
Dangerous_lv2 = [[0,0,0,0,0,0,0]] #ความรุนแรงระดับที่ 2 เป็นจริงจะเท่ากับ 1
Dangerous_lv3 = [[0,0,0,0,0,0,0]] #ความรุนแรงระดับที่ 3 เป็นจริงจะเท่ากับ 1
Dangerous_lv4 = [[0,0,0,0,0,0,0]] #ความรุนแรงระดับที่ 4 เป็นจริงจะเท่ากับ 1
Point = [[0,0,0,0,0,0,0]] #ความรุนแรงแบบเก็บแต้ม ปัจจุบันอาการที่เก็บเต็มมีแค่ อาการคลื่นไส้ 
ADL_lv1 = [0] #ความรุนแรงระดับที่ 1 ของ ADL เป็นจริงจะเท่ากับ 1
ADL_lv2 = [0] #ความรุนแรงระดับที่ 2 ของ ADL เป็นจริงจะเท่ากับ 1
ADL_lv3 = [0] #ความรุนแรงระดับที่ 3 ของ ADL เป็นจริงจะเท่ากับ 1
No_Q_Nuasea = [0] #จำนวนคำถามของอาการคลื่นไส้
No_Q_Vomtting = [0] #จำนวนคำถามของ000000000000000000000อาการอาเจียน
No_Q_Comeback = [0] #จำนวนคำถามของอาการคลื่นไส้
No_Q_Nuasea_And_Vomtting = [0] #จำนวนคำถามของอาการคลื่นไส้อาเจียน
No_Q_Diarrhea = [0] #จำนวนคำถามของอาการท้องเสีย
No_Q_ADL = [0] #จำนวนคำถามของ ADL
Question = [""]             #ตัวแปรเก็บคำถามก่อนหน้า
Skip = [0]                  #เป็นจริงฏ้ต่อเมื่อตรวจสอบคำตอบแล้วว่าไม่ตรงกับคำถามที่ถามไป
loop_Question = [0]         #ได้เข้าคำถามย่อยของอาการหลักแล้ว
Answer_Miss = [0]           #ตัวแปรนับ ตอบไม่ตรงคำถาม
Text_answer = [""]          #ตัวแปรเก็บคำที่ตัดมาจากคำตอบของผู้ใช้
No = [0]

AB_All_Symptom = [[0,0,0,0,0,0,0]]    #ตัวแปรที่บอกว่าอาการไหนต้องประเมินบ้าง

All_Symptom = [[0,0,0,0,0,0,0]]       # ตัวแปรที่ใช้เก็บอาการทั้งหมด
                                    ### All_Symptom สถานะ 0 ผู้ใช้ไม่ได้บอกไว้ ถามไปเผื่อเป็น
                                    ### All_Symptom สถานะ 1 ผู้ใช้ได้บอกไว้แล้วว่ามีอาการเลยถามอีกครั้ง
                                    ### All_Symptom สถานะ 2 หมดธุระกับอาการนี้

Symptom_Processing = [[0,0,0,0,0,0,0]]        # ตัวแปรที่บอกว่าอยู่ที่อาการต่อไป
                                            ### Symptom_Processing สถานะ 0 ไม่ได้ไปยุ่งอะไร
                                            ### Symptom_Processing สถานะ 1 กำลังดำเนินการอาการนั้นอยู่
                                            ### Symptom_Processing สถานะ 2 กำลังถามว่ามีอาการนั้นด้วยรึป่าว

Question_Additional = [0]             #ตัวแปรที่ใช้ถามคำถามเพิ่มเติม                                            
Check_lv3 = [0]             #เช็คว่ามีอาการไหนที่รุนแรงถึงขั้น 3 แล้ว ถ้ามีก็ให้เท่ากับ 1 #ตอนนี้ตัวแปรที่ไม่ได้ใช่ เมื่อก่อนใช้กรณี ถ้ามีอาการใดอาการหนึ่งที่มีความรุนแรงระดับ 3 แล้วจะไม่สอบถามอาการอื่นๆต่อ
Get_Symptom = [["","","","","","","",""]]     #เก็บคำที่ตรงกับอาการ
data = [{}]
datagoogle = [""]
datag = [""]
symptom_s = [""]
grade_s = [""]
grade_adl = [""]
grade_all = [""]
row = [""]
hospital_status = [""]
data_sheet = [""]
found_row_index = [""]
found_row = [""]
find_userID = [""]
find_Symptom = [""]
find_Hospital = [""]
find_RecordingDate = [""]
find_Date_firsttime = [""]
go_hospital = [2] # 0 = go, 1 = not go, 2 = nothing
answer_str = [""]

conversation_data = {}

# สร้าง dictionary เพื่อเก็บข้อมูลการลงทะเบียนของผู้ใช้
registration_data = {}

# Flask
app = Flask(__name__)
@app.route('/', methods=['POST']) 

def MainFunction():

    #รับ intent จาก Dailogflow
    question_from_dailogflow_raw = request.get_json(silent=True, force=True)

    #เรียกใช้ฟังก์ชัน generate_answer เพื่อแยกส่วนของคำถาม
    answer_from_bot = generating_answer(question_from_dailogflow_raw)
    
    #ตอบกลับไปที่ Dailogflow
    r = make_response(answer_from_bot)
    r.headers['Content-Type'] = 'application/json'
    return r


def generating_answer(question_from_dailogflow_dict):

    global conversation_data 
    global registration_data
    global User_List
    global User_ID
    global Had_User

    global Dangerous_lv1
    global Dangerous_lv2
    global Dangerous_lv3
    global Dangerous_lv4
    global Point
    global ADL_lv1
    global ADL_lv2
    global ADL_lv3
    global No_Q_Nuasea
    global No_Q_Vomtting
    global No_Q_Comeback
    global No_Q_Nuasea_And_Vomtting
    global No_Q_Diarrhea
    global No_Q_ADL
    global Question
    global Skip             
    global loop_Question 
    global Answer_Miss 
    global Text_answer
    global No
    global AB_All_Symptom
    global All_Symptom
    global Question_Additional
    global Symptom_Processing
    global Check_lv3
    global Get_Symptom
    global data
    global datagoogle
    global datag
    global symptom_s
    global grade_s
    global grade_adl
    global grade_all
    global hospital_status
    global data_sheet
    global found_row_index
    global found_row
    global row
    global find_userID
    global find_Symptom
    global find_Hospital
    global find_RecordingDate
    global find_Date_firsttime
    global go_hospital

    global word_Vomtting
    global Index_word_Vomtting
    global answer_str
    

    #Print intent ที่รับมาจาก Dailogflow
    print(json.dumps(question_from_dailogflow_dict, indent=4 ,ensure_ascii=False))
    
    #เก็บต่า ชื่อของ intent ที่รับมาจาก Dailogflow
    intent_group_question_str = question_from_dailogflow_dict["queryResult"]["intent"]["displayName"] 
    
    #ตรวจสอบ User ที่กำลังถาม
    User_ID = question_from_dailogflow_dict["originalDetectIntentRequest"]["payload"]["data"]["source"]["userId"] #เก็บ User ID ของผู้ใช้

    Had_User = False
    for key in User_List.keys(): #ลูปเช็คว่ามีในลิสมีไอดีของผู้ใช้แล้วรึป่าว
        if key == User_ID: 
            Had_User = True #ถ้ามีให้เป็นจริงจะได้มีเพิ่มในลิสอีก

    
    
    print("Had", Had_User)
    if Had_User == False: #ถ้ายังไม่มี เพิ่มตัวแปรต่างๆในลิส 
        User_List[User_ID] = len(User_List)
        answer_str.insert(User_List[User_ID], "")
        Dangerous_lv1.insert(User_List[User_ID], [0,0,0,0,0,0,0])
        Dangerous_lv2.insert(User_List[User_ID], [0,0,0,0,0,0,0])
        Dangerous_lv3.insert(User_List[User_ID], [0,0,0,0,0,0,0])
        Dangerous_lv4.insert(User_List[User_ID], [0,0,0,0,0,0,0])
        Point.insert(User_List[User_ID], [0,0,0,0,0,0,0])
        ADL_lv1.insert(User_List[User_ID], 0)
        ADL_lv2.insert(User_List[User_ID], 0)
        ADL_lv3.insert(User_List[User_ID], 0)
        No_Q_Nuasea.insert(User_List[User_ID], 0)
        No_Q_Vomtting.insert(User_List[User_ID], 0)
        No_Q_Comeback.insert(User_List[User_ID], 0)
        No_Q_Nuasea_And_Vomtting.insert(User_List[User_ID], 0)
        No_Q_Diarrhea.insert(User_List[User_ID], 0)
        No_Q_ADL.insert(User_List[User_ID], 0)
        Question.insert(User_List[User_ID], "")
        Skip.insert(User_List[User_ID], 0)
        loop_Question.insert(User_List[User_ID], 0)
        Answer_Miss.insert(User_List[User_ID], 0)
        Text_answer.insert(User_List[User_ID], "")
        AB_All_Symptom.insert(User_List[User_ID], [0,0,0,0,0,0,0])
        All_Symptom.insert(User_List[User_ID], [0,0,0,0,0,0,0])
        Question_Additional.insert(User_List[User_ID], 0)
        Symptom_Processing.insert(User_List[User_ID], [0,0,0,0,0,0,0])
        Check_lv3.insert(User_List[User_ID], 0)
        Get_Symptom.insert(User_List[User_ID], ["","","","","","","",""])
        data.insert(User_List[User_ID], {})
        datagoogle.insert(User_List[User_ID], "")
        datag.insert(User_List[User_ID], "")
        No.insert(User_List[User_ID], 0)
        symptom_s.insert(User_List[User_ID], "")
        grade_s.insert(User_List[User_ID], "")
        grade_adl.insert(User_List[User_ID], "")
        grade_all.insert(User_List[User_ID], "")
        row.insert(User_List[User_ID], "")
        data_sheet.insert(User_List[User_ID], "")
        hospital_status.insert(User_List[User_ID], "ยังไม่ได้อัพเดท")
        found_row_index.insert(User_List[User_ID], "")
        found_row.insert(User_List[User_ID], "")
        find_userID.insert(User_List[User_ID], "")
        find_Symptom.insert(User_List[User_ID], "")
        find_Hospital.insert(User_List[User_ID], "")
        find_RecordingDate.insert(User_List[User_ID], "")
        find_Date_firsttime.insert(User_List[User_ID], "")
        go_hospital.insert(User_List[User_ID], 2)
    

        # ดึงค่าที่ผู้ใช้พิมพ์มา
    user_input = question_from_dailogflow_dict["queryResult"]["queryText"]

    # ตรวจสอบ Intent ที่เกี่ยวข้องกับการลงทะเบียน
    if intent_group_question_str == 'Register' or User_ID in registration_data:
        # ส่ง user_input แทน intent_group_question_str ในการเรียกใช้ handle_registration
        answer_from_bot = handle_registration(User_ID, user_input, question_from_dailogflow_dict)
        return answer_from_bot

    if Get_Symptom[User_List[User_ID]][2] != "ถามเรื่องไปโรงพยาบาลแล้ว" and intent_group_question_str != 'Say_Yes':# เงื่อนไขของ ประเมินความรุนแรงของอาการหลังจากกลับมาจากโรงพยาบาล #Say_Yes เผื่อกรณีผู้ใช้ตอบว่าเข้าใจหลังจากประเมินความรุนแรงของอาการแล้ว
        
        check_hospital()

        Get_Symptom[User_List[User_ID]][7] = intent_group_question_str #กรณีถามว่าไปโรงพยาบาลมารึยัง ผู้ใช้ตอบว่า "ยังไม่ได้ไป" ตัวแปรนี้ index ที่ 7 จะเก็บข้อความก่อนหน้าของผู้ใช้ แล้วเอาไปเช็ค intent ต่อ
        
    ############ ตัดคำหาคำว่า อาเจียน กรณีตอบว่า คลื่นไส้อาเจียน
    word_Vomtting = ""
    Index_word_Vomtting = 0
    Text_answer[User_List[User_ID]] = word_tokenize(question_from_dailogflow_dict["queryResult"]["queryText"]) #ตัดคำ คำตอบของผู้ใช้
    for word in Text_answer[User_List[User_ID]]: #ถ้ามีคำที่ตรงกับอาการหลัก จะมีการเก็บสถานะและคำของอาการ สถานะเป็น 1 คือยังไม่ถามหรือถามยังไม่จบ
        Index_word_Vomtting += 1
        if word == "อาเจียน" or word == "อ้วก":
            word_Vomtting = "อาเจียน"
            # ทำไมต้องมีตัวแปรตัวนี้
            # เพราะหากผู้ใช้พิมพ์มาหลายอาการแล้วพิมพ์ "คลื่นไส้อาเจียน" dialogFlow จะจัดให้อยู่ใน Intent คลื่อนไส้ แต่อาการอาเจียนคือขึ้นรุนแรงของคลื่นไส้เลยไม่ได้ต้องถามคลื่นไส้แต่ไปถามอาเจียนเลย
            
            # เงื่อนไขพวกนี้เอาไว้เช็กว่าผู้ใช้ตอบว่า "อาเจียน" หรือ "ไม่อาเจียน" กันแน่

            if(Index_word_Vomtting>2):
                if Text_answer[User_List[User_ID]][Index_word_Vomtting-1] == 'ไม่': #ไม่อาเจียน
                    word_Vomtting = ""
            if(Index_word_Vomtting>3):
                if Text_answer[User_List[User_ID]][Index_word_Vomtting-2] == 'ไม่': #ไม่ได้อาเจียน
                    word_Vomtting = ""
            if(Index_word_Vomtting>4):
                if Text_answer[User_List[User_ID]][Index_word_Vomtting-3] == 'ไม่': #ไม่รู้สึกอาเจียน
                    word_Vomtting = ""
            if(Index_word_Vomtting>5):
                if Text_answer[User_List[User_ID]][Index_word_Vomtting-4] == 'ไม่': #ไม่มีอาการอาเจียน
                    word_Vomtting = ""
            break

    ######### ลูปตัวเลือกของฟังก์ชั่นสำหรับตอบคำถามกลับ 
    ######## ลำดับที่ 3 คือการตรวจสอบว่าผู้ใช้ตอบตรงคำถามหรือไม่ หากไม่ต้องก็จะถามคำถามเดิม
    if No_Q_Nuasea[User_List[User_ID]] > 0:
        answer_str[User_List[User_ID]] = Intent_Nausea(intent_group_question_str, question_from_dailogflow_dict)
        
    if No_Q_Vomtting[User_List[User_ID]] > 0:
        answer_str[User_List[User_ID]] = Intent_Vomtting(intent_group_question_str, question_from_dailogflow_dict)

    if No_Q_Comeback[User_List[User_ID]] > 0 and No_Q_Comeback[User_List[User_ID]] != 5:
        answer_str[User_List[User_ID]] = Intent_Comeback(intent_group_question_str, question_from_dailogflow_dict)
        if No_Q_Comeback[User_List[User_ID]] == 0:
            intent_group_question_str = Get_Symptom[User_List[User_ID]][7]

    if No_Q_Nuasea_And_Vomtting[User_List[User_ID]] > 0:
        answer_str[User_List[User_ID]] = Intent_Nausea_And_Vomtting(intent_group_question_str)

    if No_Q_Diarrhea[User_List[User_ID]] > 0:
        answer_str[User_List[User_ID]] = Intent_Diarrhea(intent_group_question_str, question_from_dailogflow_dict)
    
    if No_Q_ADL[User_List[User_ID]] > 0 and No_Q_ADL[User_List[User_ID]] != 14:
        answer_str[User_List[User_ID]] = Intent_ADL(intent_group_question_str, question_from_dailogflow_dict)
    
    if Question_Additional[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = Intent_Question_Additional(intent_group_question_str, question_from_dailogflow_dict)

    ######## เงื่อนไขนี้ เปรียบเป็นการ Reset ระบบให้เริ่มใหม่ สามารถเข้าได้ตลอดเวลา
    if intent_group_question_str == 'Default Welcome Intent' and No_Q_Comeback[User_List[User_ID]] != 5:
        answer_str[User_List[User_ID]] = 'สวัสดีครับ ผู้ป่วยมีอาการผิดปกติ ภายหลังได้รับยาเคมีบำบัด ยามุ่งเป้า ยาปรับภูมิคุ้มกัน หรือมีความผิดปกติอื่นใดภายหลังได้รับยาที่ใช้รักษาโรคมะเร็ง\nกรุณาแจ้งอาการที่เกิดขึ้น เช่น \n- อาการคลื่นไส้\n- อาเจียน\n- ท้องเสีย\n- หรืออาการอื่นๆ\n-------------------------------------\nทั้งนี้ หากคุณมีสภาวะฉุกเฉิน เช่น หมดสติ อ่อนแรงแขนขา ปากเบี้ยวพูดไม่ชัด แน่นหน้าอกมาก หอบเหนื่อยมาก ความดันโลหิตต่ำ มีไข้สูง หรืออาการฉุกเฉินอื่นๆ\nให้ไปพบแพทย์ที่ห้องฉุกเฉินทันที โดยไม่จำเป็นต้องตอบคำถามจากระบบนี้แต่อย่างใด'
        
        Clear_Data_User()
        show_chat(answer_str[User_List[User_ID]])
        append_data_google(answer_str[User_List[User_ID]])
        No[User_List[User_ID]] = 1
    ######## ลำดับแรกสำหรับการทำงาน คือ เช็ค Intent ว่าผู้ป่วยมีอาการอะไรบ้าง
    if loop_Question[User_List[User_ID]] == 0:
        
        ######## Dialogflow ไม่สามารถบอกทุกอาการได้ หากผู้ใช้บอกมาทุกอาการในประโยคเดียว เลยต้องมีการเช็คแต่ละคำเองด้วย
        Text_answer[User_List[User_ID]] = word_tokenize(question_from_dailogflow_dict["queryResult"]["queryText"]) #ตัดคำ คำตอบของผู้ใช้
        for word in Text_answer[User_List[User_ID]]: #ถ้ามีคำที่ตรงกับอาการหลัก จะมีการเก็บสถานะและคำของอาการ สถานะเป็น 1 คือยังไม่ถามหรือถามยังไม่จบ
            if word == "คลื่นไส้" or word == "กรดไหลย้อน": #เดี่ยวต้องหาคำมาใส่เยอะๆ หรือเอามาจาก intent ใน Dialogflow
                All_Symptom[User_List[User_ID]][0] = 1
                Get_Symptom[User_List[User_ID]][0] = word
            if word == "อาเจียน" or word == "อ้วก": #เดี่ยวต้องหาคำมาใส่เยอะๆ หรือเอามาจาก intent ใน Dialogflow
                All_Symptom[User_List[User_ID]][1] = 1
                Get_Symptom[User_List[User_ID]][1] = word
            if word == "ท้องเสีย" or word == "ปวดท้อง" or word == "ถ่ายเหลว": #เดี่ยวต้องหาคำมาใส่เยอะๆ หรือเอามาจาก intent ใน Dialogflow
                All_Symptom[User_List[User_ID]][3] = 1
                Get_Symptom[User_List[User_ID]][3] = word
            if word == "ชา" or word == "มือชา"or word == "ปากเปิ่อย" or word == "หมดสติ" or word == "ความดันโลหิตต่ำ" or word == "หอบเหนื่อย" or word == "แน่นหน้าอก":
                Get_Symptom[User_List[User_ID]][4] = word
        if intent_group_question_str == 'อาการอื่นๆฉุกเฉิน' or intent_group_question_str == 'อ่อนเพลีย':
            answer_str[User_List[User_ID]] = 'อาการของคุณเข้าข่ายสภาวะฉุกเฉิน แนะนำให้ไปพบแพทย์ที่ห้องฉุกเฉินทันที โดยไม่จำเป็นต้องตอบคำถามจากระบบนี้แต่อย่างใด'
            symptom_s[User_List[User_ID]] = "อาการอื่นๆฉุกเฉิน"
            grade_s[User_List[User_ID]] = "-"
            grade_adl[User_List[User_ID]] = "-"
            grade_all[User_List[User_ID]] = "-"
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
            
            append_googlesheet()
            Clear_Data_User()
        elif intent_group_question_str == 'อาการอื่นๆทั่วไป' or Get_Symptom[User_List[User_ID]][4] == "ชา" or Get_Symptom[User_List[User_ID]][4] == "มือชา" or Get_Symptom[User_List[User_ID]][4] == "ปากเปิ่อย":
            All_Symptom[User_List[User_ID]][4] = 2
            AB_All_Symptom[User_List[User_ID]][4] = 1
            symptom_s[User_List[User_ID]] = "อาการอื่นๆทั่วไป"
            No_Q_ADL[User_List[User_ID]] = 15
            loop_Question[User_List[User_ID]] = 1
        elif word_Vomtting == 'อาเจียน' or intent_group_question_str == 'อาเจียน':  
            No_Q_Vomtting[User_List[User_ID]] = 8
            loop_Question[User_List[User_ID]] = 1
        elif intent_group_question_str == 'คลื่นไส้'or Get_Symptom[User_List[User_ID]][0] == "คลื่นไส้":  
            No_Q_Nuasea_And_Vomtting[User_List[User_ID]] = 3
            loop_Question[User_List[User_ID]] = 1
        elif intent_group_question_str == 'ท้องเสีย' or Get_Symptom[User_List[User_ID]][3] == "ท้องเสีย" or Get_Symptom[User_List[User_ID]][3] == "ถ่ายเหลว":
            Dangerous_lv1[User_List[User_ID]][3] = 1
            No_Q_Diarrhea[User_List[User_ID]] = 7
            loop_Question[User_List[User_ID]] = 1
        elif intent_group_question_str == 'กลับมาจากโรงพยาบาล' and find_Hospital[User_List[User_ID]] == 'ยังไม่ได้ไปโรงพยาบาล': # กรณีคุยๆกันอยู่ผู้ใช้บอกว่าไปโรงพยาบาลมาแล้วแต่ก่อนหน้าแชทบอทได้ถามไปแล้วว่าไปโรงพยาบาลมารึยังแต่ผู้ใช้ตอบว่า "ไม่" ทำให้ชีทเปลี่ยนสถานะไปแล้วเมื่อผู้ใช้ทักเข้ามมา แชทบอทจะไม่ถามว่าไปโรงพยาบาลมารึยัง
            Symptom_Processing[User_List[User_ID]][2] = 1
            No_Q_Comeback[User_List[User_ID]] = 5
            loop_Question[User_List[User_ID]] = 1
        
        elif Get_Symptom[User_List[User_ID]][6] == "อ้าว": # กรณีผู้ป่วยมีอาการคลื่นไส้อาเจียนหรือท้องเสียแต่ไม่ได้มาจากสาเหตุการใช้ยาเคมีบำบัด
            answer_str[User_List[User_ID]] = "อาการดังกล่าวไม่ได้อยู่ในอาการการประเมินหรือเป็นอาการที่ไม่ได้เกิดจากการรับยาเคมีบำบัด แนะนำให้พบแพทย์ที่โรงพยาบาลใกล้บ้านนะครับ"
            symptom_s[User_List[User_ID]] = "อาการดังกล่าวไม่ได้เกิดจากการได้รับยาเคมีบำบัด"
            Get_Symptom[User_List[User_ID]][6] = ""
            grade_s[User_List[User_ID]] = "-"
            grade_adl[User_List[User_ID]] = "-"
            grade_all[User_List[User_ID]] = "-"
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
            append_googlesheet()
            Clear_Data_User()
        elif Get_Symptom[User_List[User_ID]][6] == "ไม่ให้ข้อมูลต่อ": # กรณีผู้ป่วยไม่อยากให้ข้อมูลด้านชีวิตประจำวัน
            answer_str[User_List[User_ID]] = "ขอโทษที่ไม่สามารถประเมินอาการดังกล่าวได้โดยตรงนะครับแต่แนะนำให้พบแพทย์ที่โรงพยาบาลใกล้บ้านด้วยนะครับ"
            symptom_s[User_List[User_ID]] = "ไม่สามารถบอกกิจวัตรประจำวันได้"
            Get_Symptom[User_List[User_ID]][6] = ""
            grade_s[User_List[User_ID]] = "-"
            grade_adl[User_List[User_ID]] = "-"
            grade_all[User_List[User_ID]] = "-"
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
            append_googlesheet()
            Clear_Data_User()
        elif intent_group_question_str == 'Say_Yes': # กรณีที่แชทบอทประเมินความรุนแรงแล้วแต่ผู้ใช้ตอบรับ เช่น ครับ ค่ะ แชทบอทจะไม่ตอบอะไร
            answer_str[User_List[User_ID]] = ''
        elif intent_group_question_str == 'Say_No': 
            answer_str[User_List[User_ID]] = 'หากมีอาการอื่นๆสามารถแจ้งกับระบบได้เลยนะครับ พักผ่อนให้เพียงพอนะครับ'
        else:
            if No[User_List[User_ID]] == 0:
                answer_str[User_List[User_ID]] = "ขอโทษครับ ผมไม่เข้าใจประโยค \""+ question_from_dailogflow_dict["queryResult"]["queryText"] +"\" กรุณาตอบคำถามดังกล่าวใหม่อีกครั้งครับ"
                Answer_Miss[User_List[User_ID]] += 1
                # กรณีถามผู้ใช้ว่าไปโรงพยาบาลมารึยัง แต่ประโยคที่ทักเข้ามาไม่เข้า Intent อาการใดๆ ถ้าผู้ใช้ตอบ ไม่ จะเหมือนว่าจะทักทายกันใหม่
                if go_hospital[User_List[User_ID]] == 1:
                    Answer_Miss[User_List[User_ID]] -= 1
                    answer_str[User_List[User_ID]] = 'ผู้ป่วยมีอาการผิดปกติ ภายหลังได้รับยาเคมีบำบัด ยามุ่งเป้า ยาปรับภูมิคุ้มกัน หรือมีความผิดปกติอื่นใดภายหลังได้รับยาที่ใช้รักษาโรคมะเร็ง\nกรุณาแจ้งอาการที่เกิดขึ้น เช่น \n- อาการคลื่นไส้\n- อาเจียน\n- ท้องเสีย\n- หรืออาการอื่นๆ\n-------------------------------------\nทั้งนี้ หากคุณมีสภาวะฉุกเฉิน เช่น หมดสติ อ่อนแรงแขนขา ปากเบี้ยวพูดไม่ชัด แน่นหน้าอกมาก หอบเหนื่อยมาก ความดันโลหิตต่ำ มีไข้สูง หรืออาการฉุกเฉินอื่นๆ\nให้ไปพบแพทย์ที่ห้องฉุกเฉินทันที โดยไม่จำเป็นต้องตอบคำถามจากระบบนี้แต่อย่างใด'
                    show_chat(answer_str[User_List[User_ID]])
                    append_data_google(answer_str[User_List[User_ID]])
                else:
                    show_chat(answer_str[User_List[User_ID]])
                    append_data_google(answer_str[User_List[User_ID]])
        
    
    No[User_List[User_ID]] = 0

    ######## ลำดับที่ 2 หากรู้แล้วว่าต้องถามอาการไหน(ได้รับจำนวนคำถามอาการนั้นมาแล้ว) จะมาเรียกคำถามตามลำดับเพื่อนส่งไปถามผู้ใช้ และหากถามหมดก็จะไปที่ขั้นสรุป
    if No_Q_Nuasea[User_List[User_ID]] > 0 and Skip[User_List[User_ID]] == 0:
        answer_str[User_List[User_ID]] = Main_Q_Nuasea()
    elif No_Q_Vomtting[User_List[User_ID]] > 0 and Skip[User_List[User_ID]] == 0:
        answer_str[User_List[User_ID]] = Main_Q_Vomtting()
    elif No_Q_Comeback[User_List[User_ID]] > 0 and Skip[User_List[User_ID]] == 0:
        answer_str[User_List[User_ID]] = Main_Q_Comeback()
    elif No_Q_Nuasea_And_Vomtting[User_List[User_ID]] > 0 and Skip[User_List[User_ID]] == 0:
        answer_str[User_List[User_ID]] = Q_Nuasea_And_Vomtting()
    elif No_Q_Diarrhea[User_List[User_ID]] > 0 and Skip[User_List[User_ID]] == 0:
        answer_str[User_List[User_ID]] = Main_Q_Diarrhea()
    
    if No_Q_ADL[User_List[User_ID]] > 0 and Skip[User_List[User_ID]] == 0:
        answer_str[User_List[User_ID]] = Main_Q_ADL()

    ###### ตอบไม่ตรงคำถาม 3 ครั้ง เริ่มใหม่ทั้งหมด 
    if Answer_Miss[User_List[User_ID]] >= 3:
        if loop_Question[User_List[User_ID]] == 1: # กรณีสอบถามอาการเพิ่มเติ่มกันอยู่แต่ตอบไม่ตรง
            answer_str[User_List[User_ID]] = "ขออนุญาตสอบถามอาการใหม่ตั้งแต่แรกนะครับ\n" + "-----------------------------------------" + "\nผู้ป่วยมีอาการผิดปกติ ภายหลังได้รับยาเคมีบำบัด ยามุ้งเป้า ยาปรับภูมิคุ้มกัน หรือมีความผิดปกติอื่นใดภายหลังได้รับยาที่ใช้รักษาโรคมะเร็ง กรุณาแจ้งอาการที่เกิดขึ้น เช่น \n-อาการคลื่นไส้ \n-อาเจียน \n-ท้องเสีย \n-หรืออาการอื่นๆ"
        elif loop_Question[User_List[User_ID]] == 0: #กรณีผู้ใช้ยังไม่รู้เลยว่าแชทบอทนี้สำหรับอะไร
            answer_str[User_List[User_ID]] = "ผู้ป่วยมีอาการผิดปกติ ภายหลังได้รับยาเคมีบำบัด ยามุ่งเป้า ยาปรับภูมิคุ้มกัน หรือมีความผิดปกติอื่นใดภายหลังได้รับยาที่ใช้รักษาโรคมะเร็ง กรุณาแจ้งอาการที่เกิดขึ้น เช่น \n-อาการคลื่นไส้ \n-อาเจียน \n-ท้องเสีย \n-หรืออาการอื่นๆ"
        Answer_Miss[User_List[User_ID]] = 0
        loop_Question[User_List[User_ID]] = 0
        Clear_Data_User()

        show_chat(answer_str[User_List[User_ID]])
        append_data_google(answer_str[User_List[User_ID]])

    Skip[User_List[User_ID]] = 0 #ให้เป็นเท็จเพื่อที่จะตรวจสอบคำตอบในรอบต่อไป

    #สร้างการแสดงของ dict 
    answer_from_bot = {"fulfillmentText": answer_str[User_List[User_ID]]}
    
    #แปลงจาก dict ให้เป็น JSON
    answer_from_bot = json.dumps(answer_from_bot, indent=4) 
    
    print("No_Q_Nuasea", No_Q_Nuasea[User_List[User_ID]])
    print("No_Q_Vomtting", No_Q_Vomtting[User_List[User_ID]])
    print("No_Q_Comeback", No_Q_Comeback[User_List[User_ID]])
    print("No_Q_Nuasea_And_Vomtting", No_Q_Nuasea_And_Vomtting[User_List[User_ID]])
    print("No_Q_Diarrhea", No_Q_Diarrhea[User_List[User_ID]])
    print("No_Q_ADL", No_Q_ADL[User_List[User_ID]])
    print("Skip", Skip[User_List[User_ID]])
    print("loop_Question", loop_Question[User_List[User_ID]])
    print("                  [0, 1, 2, 3, 4, 5, 6]")
    print("Dangerous_lv1    ", Dangerous_lv1[User_List[User_ID]])
    print("Dangerous_lv2    ", Dangerous_lv2[User_List[User_ID]])
    print("Dangerous_lv3    ", Dangerous_lv3[User_List[User_ID]])
    print("Dangerous_lv4    ", Dangerous_lv4[User_List[User_ID]])
    print("Point            ", Point[User_List[User_ID]])
    print("ADL_lv1  ", ADL_lv1[User_List[User_ID]])
    print("ADL_lv2  ", ADL_lv2[User_List[User_ID]])
    print("ADL_lv3  ", ADL_lv3[User_List[User_ID]])
    print("Answer_Miss", Answer_Miss[User_List[User_ID]])
    print("Text", Text_answer[User_List[User_ID]])
    print("NO.User", User_List[User_ID])
    print("                      [0, 1, 2, 3, 4, 5, 6]")
    print("AB_All_Symptom       ", AB_All_Symptom[User_List[User_ID]])
    print("All_Symptom          ", All_Symptom[User_List[User_ID]])
    print("Symptom_Processing   ", Symptom_Processing[User_List[User_ID]])
    print("Get_Symptom[User_List[User_ID]][7] ", Get_Symptom[User_List[User_ID]][7])
    print("find_Hospital ", find_Hospital[User_List[User_ID]])
    print("find_Date_firsttime ", find_Date_firsttime[User_List[User_ID]])
    print("find_Symptom ", find_Symptom[User_List[User_ID]])
    print("symptom_s   ", symptom_s[User_List[User_ID]])

    return answer_from_bot

def Intent_Nausea(intent_group_question_str, question_from_dailogflow_dict):

    print('Intent_Nausea') 

    answer_str[User_List[User_ID]] = ""

    ########################## ข้าม ADL #########################
    if(intent_group_question_str == 'ข้าม'):
        No_Q_Nuasea[User_List[User_ID]] = 1
    elif (intent_group_question_str == 'เบื่ออาหาร' or intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'Say_No' )and No_Q_Nuasea[User_List[User_ID]] == 5:
        if(intent_group_question_str == 'Say_No'):
            Dangerous_lv1[User_List[User_ID]][0] = 1
            No_Q_Nuasea[User_List[User_ID]] -= 2
    elif (intent_group_question_str == 'มื้ออาหาร' or intent_group_question_str == 'Number') and No_Q_Nuasea[User_List[User_ID]] == 4:
        Times_Of_Eating(question_from_dailogflow_dict)
    elif (intent_group_question_str == 'กินข้าวได้น้อยลง' or intent_group_question_str == 'Number') and No_Q_Nuasea[User_List[User_ID]] == 3:
        Rice_Of_Eating(question_from_dailogflow_dict)
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'น้ำหนักลด' or intent_group_question_str == 'Say_No') and No_Q_Nuasea[User_List[User_ID]] == 2:
        if (intent_group_question_str == 'Say_No'):
            No_Q_Nuasea[User_List[User_ID]] = 1
    elif (intent_group_question_str == 'น้ำหนักตัว' or intent_group_question_str == 'Number' ) and No_Q_Nuasea[User_List[User_ID]] == 1:
        Lose_Weight(question_from_dailogflow_dict)
    else: 
        answer_str[User_List[User_ID]] = "กรุณาตอบใหม่นะครับ\n" + Question[User_List[User_ID]]
        show_chat(answer_str[User_List[User_ID]])
        append_data_google(answer_str[User_List[User_ID]])
        Skip[User_List[User_ID]] = 1
        Answer_Miss[User_List[User_ID]] += 1
    
    return answer_str[User_List[User_ID]]

def Intent_Vomtting(intent_group_question_str, question_from_dailogflow_dict):

    print('Intent_Vomtting')

    answer_str[User_List[User_ID]] = ""

    ########################## ข้าม ADL #########################
    if(intent_group_question_str == 'ข้าม'):
        No_Q_Vomtting[User_List[User_ID]] = 1
    elif(intent_group_question_str == 'Say_Yes' or word_Vomtting == "อาเจียน"or word_Vomtting == "อาเจียน") and No_Q_Vomtting[User_List[User_ID]] == 7:
        answer_str[User_List[User_ID]] = ""
    elif(intent_group_question_str == 'คลื่นไส้' or intent_group_question_str == 'Say_No') and No_Q_Vomtting[User_List[User_ID]] == 7:
        No_Q_Vomtting[User_List[User_ID]] = 0
        No_Q_Nuasea[User_List[User_ID]] = 6
        Dangerous_lv1[User_List[User_ID]][1] = 0
    elif  No_Q_Vomtting[User_List[User_ID]] >= 3 and No_Q_Vomtting[User_List[User_ID]] <= 6:
        answer_str[User_List[User_ID]] = ""
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'น้ำหนักลด') and No_Q_Vomtting[User_List[User_ID]] == 2:
        Dangerous_lv2[User_List[User_ID]][1] = 1
    elif ( intent_group_question_str == 'Say_No') and No_Q_Vomtting[User_List[User_ID]] == 2:
        Dangerous_lv1[User_List[User_ID]][1] = 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'อ่อนเพลีย') and No_Q_Vomtting[User_List[User_ID]] == 1:
        Dangerous_lv2[User_List[User_ID]][1] = 1
    elif ( intent_group_question_str == 'Say_No' ) and No_Q_Vomtting[User_List[User_ID]] == 1:
        Dangerous_lv1[User_List[User_ID]][1] = 1
    else: 
        answer_str[User_List[User_ID]] = "กรุณาตอบใหม่นะครับ\n" + Question[User_List[User_ID]]
        show_chat(answer_str[User_List[User_ID]])
        append_data_google(answer_str[User_List[User_ID]])
        Skip[User_List[User_ID]] = 1
        Answer_Miss[User_List[User_ID]] += 1
        print("Answer Print: ", Answer_Miss[User_List[User_ID]])
    
    return answer_str[User_List[User_ID]]

def Intent_Comeback(intent_group_question_str, question_from_dailogflow_dict):

    print('Intent_Comeback')
    
    date,time = timestamp()

    answer_str[User_List[User_ID]] = ""

    ########################## ข้าม ADL #########################
    if(intent_group_question_str == 'ข้าม'):
        No_Q_Comeback[User_List[User_ID]] = 1
    elif(intent_group_question_str == 'กลับมาจากโรงพยาบาล' or intent_group_question_str == 'Say_Yes') and No_Q_Comeback[User_List[User_ID]] == 4:
        answer_str[User_List[User_ID]] = ""
        go_hospital[User_List[User_ID]] = 0
    elif(intent_group_question_str == 'Say_No') and No_Q_Comeback[User_List[User_ID]] == 4:
        No_Q_Comeback[User_List[User_ID]] = 0
        Symptom_Processing[User_List[User_ID]][2] = 0
        loop_Question[User_List[User_ID]] = 0
        go_hospital[User_List[User_ID]] = 1
        # อัพเดทชีท3ไปก่อนแต่บทสนายังไม่จบ
        Comeback_Status.update_cell(found_row_index[User_List[User_ID]] + 1, 5, "ยังไม่ได้ไปโรงพยาบาล")
        Comeback_Status.update_cell(found_row_index[User_List[User_ID]] + 1, 7, date)
    elif (intent_group_question_str == 'Say_Yes' ) and No_Q_Comeback[User_List[User_ID]] == 3:
        Dangerous_lv3[User_List[User_ID]][2] = 1
    elif ( intent_group_question_str == 'Say_No') and No_Q_Comeback[User_List[User_ID]] == 3:
        Dangerous_lv2[User_List[User_ID]][2] = 1
        No_Q_Comeback[User_List[User_ID]] -= 1
    elif (intent_group_question_str == 'Say_Yes' ) and No_Q_Comeback[User_List[User_ID]] == 2:
        Dangerous_lv4[User_List[User_ID]][2] = 1 # เดี๋ยวเปลี่ยนเป็นความรุนแรงที่ 4 เป็นจริง
        No_Q_Comeback[User_List[User_ID]] -= 1
    elif ( intent_group_question_str == 'Say_No') and No_Q_Comeback[User_List[User_ID]] == 2:
        Dangerous_lv3[User_List[User_ID]][2] = 1
    elif (intent_group_question_str == 'Say_Yes' ) and No_Q_Comeback[User_List[User_ID]] == 1:
        Dangerous_lv3[User_List[User_ID]][2] = 1
    elif ( intent_group_question_str == 'Say_No') and No_Q_Comeback[User_List[User_ID]] == 1:
        Dangerous_lv2[User_List[User_ID]][2] = 1
    else: 
        answer_str[User_List[User_ID]] = "กรุณาตอบใหม่นะครับ\n" + Question[User_List[User_ID]]
        show_chat(answer_str[User_List[User_ID]])
        append_data_google(answer_str[User_List[User_ID]])
        Skip[User_List[User_ID]] = 1
        Answer_Miss[User_List[User_ID]] += 1
        print("Answer Print: ", Answer_Miss[User_List[User_ID]])
    
    return answer_str[User_List[User_ID]]

def Intent_Nausea_And_Vomtting(intent_group_question_str):

    print('Intent_Nausea_And_Vomtting')

    answer_str[User_List[User_ID]] = ""

    if (intent_group_question_str == 'คลื่นไส้' or intent_group_question_str == 'อาเจียน' )and No_Q_Nuasea_And_Vomtting[User_List[User_ID]] == 2:
        if(intent_group_question_str == 'อาเจียน' or word_Vomtting == "อาเจียน"):
            No_Q_Nuasea_And_Vomtting[User_List[User_ID]] = 0
            No_Q_Vomtting[User_List[User_ID]] = 7 
            Dangerous_lv1[User_List[User_ID]][0] = 0 #ถ้ามีอาการอาเจียนก็ไม่ต้องไปทำคลื่นไส้
    elif (intent_group_question_str == 'อาเจียน' or intent_group_question_str == 'Say_No')and No_Q_Nuasea_And_Vomtting[User_List[User_ID]] == 1:
        No_Q_Nuasea_And_Vomtting[User_List[User_ID]] = 0
        No_Q_Vomtting[User_List[User_ID]] = 7 
    elif (intent_group_question_str == 'คลื่นไส้' or intent_group_question_str == 'Say_Yes')and No_Q_Nuasea_And_Vomtting[User_List[User_ID]] == 1:
        No_Q_Nuasea[User_List[User_ID]] = 6
        No_Q_Nuasea_And_Vomtting[User_List[User_ID]] = 0
    else: 
        answer_str[User_List[User_ID]] = "กรุณาตอบใหม่นะครับ\n" + Question[User_List[User_ID]]
        show_chat(answer_str[User_List[User_ID]])
        append_data_google(answer_str[User_List[User_ID]])
        Skip[User_List[User_ID]] = 1
        Answer_Miss[User_List[User_ID]] += 1
    
    return answer_str[User_List[User_ID]]

def Intent_Diarrhea(intent_group_question_str, question_from_dailogflow_dict):

    print('Intent_diarrhea')

    answer_str[User_List[User_ID]] = ""

    ########################## ข้าม ADL #########################
    if(intent_group_question_str == 'ข้าม'):
        No_Q_Diarrhea[User_List[User_ID]] = 1
    elif No_Q_Diarrhea[User_List[User_ID]] >= 3:
        answer_str[User_List[User_ID]] = ""
    elif (intent_group_question_str == 'Number' or intent_group_question_str == 'ถ่ายวันละกี่ครั้ง')and No_Q_Diarrhea[User_List[User_ID]] == 2:
        excrete(question_from_dailogflow_dict)
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'Say_No')and No_Q_Diarrhea[User_List[User_ID]] == 1:
            if intent_group_question_str == 'Say_Yes':
                Get_Symptom[User_List[User_ID]][4] = "ไข้" # เมื่อมีไข้รวมกับท้องเสีย จะให้ผลลัพธ์อีกแบบหนึ่งที่รุนแรง
                symptom_s[User_List[User_ID]] += ", มีไข้"
    else: 
        answer_str[User_List[User_ID]] = "กรุณาตอบใหม่นะครับ\n" + Question[User_List[User_ID]]
        Skip[User_List[User_ID]] = 1
        Answer_Miss[User_List[User_ID]] += 1
    
    return answer_str[User_List[User_ID]]

def Intent_ADL(intent_group_question_str, question_from_dailogflow_dict):

    print('Intent_ADL')

    answer_str[User_List[User_ID]] = ""
    ########################## ข้าม ADL #########################
    if(intent_group_question_str == 'ข้าม'):
        No_Q_ADL[User_List[User_ID]] = 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'Say_No')and No_Q_ADL[User_List[User_ID]] == 14:
        if (intent_group_question_str == 'Say_No'): 
            Clear_Data_User()
            Get_Symptom[User_List[User_ID]][6] = "ไม่ให้ข้อมูลต่อ"
            go_hospital[User_List[User_ID]] = 2
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'Say_No')and No_Q_ADL[User_List[User_ID]] == 13:
        if (intent_group_question_str == 'Say_No'): 
            Clear_Data_User()
            Get_Symptom[User_List[User_ID]][6] = "อ้าว"
            go_hospital[User_List[User_ID]] = 2
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 12:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            No_Q_ADL[User_List[User_ID]] -= 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 11:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            ADL_lv3[User_List[User_ID]] = 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 10:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            No_Q_ADL[User_List[User_ID]] -= 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 9:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            ADL_lv3[User_List[User_ID]] = 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 8:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            No_Q_ADL[User_List[User_ID]] -= 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 7:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            ADL_lv3[User_List[User_ID]] = 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 6:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            No_Q_ADL[User_List[User_ID]] -= 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 5:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            ADL_lv2[User_List[User_ID]] = 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 4:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            No_Q_ADL[User_List[User_ID]] -= 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 3:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            ADL_lv2[User_List[User_ID]] = 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 2:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            No_Q_ADL[User_List[User_ID]] -= 1
            ADL_lv1[User_List[User_ID]] = 1
    elif (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes' or intent_group_question_str == 'Say_No' or intent_group_question_str == 'ADL-No')and No_Q_ADL[User_List[User_ID]] == 1:
        if (intent_group_question_str == 'Say_Yes' or intent_group_question_str == 'ADL-Yes'):
            ADL_lv2[User_List[User_ID]] = 1
    else: 
        answer_str[User_List[User_ID]] = "กรุณาตอบใหม่นะครับ\n" + Question[User_List[User_ID]]
        Skip[User_List[User_ID]] = 1
        Answer_Miss[User_List[User_ID]] += 1
    
    return answer_str[User_List[User_ID]]

def Intent_Question_Additional(intent_group_question_str, question_from_dailogflow_dict):

    print('Intent_Question_Additional')

    answer_str[User_List[User_ID]] = ""

    if( Symptom_Processing[User_List[User_ID]][0] == 2 ):
        if (intent_group_question_str == 'คลื่นไส้' or intent_group_question_str == 'Say_Yes'):
            No_Q_Nuasea_And_Vomtting[User_List[User_ID]] = 3
            Question_Additional[User_List[User_ID]] = 0
            Symptom_Processing[User_List[User_ID]][0] = 1
            All_Symptom[User_List[User_ID]][0] = 1
        elif(intent_group_question_str == 'Say_No'):
            No_Q_ADL[User_List[User_ID]] = 1
            Question_Additional[User_List[User_ID]] = 0
            Symptom_Processing[User_List[User_ID]][0] = 0
            All_Symptom[User_List[User_ID]][0] = 2
            All_Symptom[User_List[User_ID]][1] = 2
            Get_Symptom[User_List[User_ID]][6] = "ห่วงใย"
        elif(intent_group_question_str == 'อาเจียน' or word_Vomtting =='อาเจียน') :
            No_Q_Vomtting[User_List[User_ID]] = 8
            Question_Additional[User_List[User_ID]] = 0
            Symptom_Processing[User_List[User_ID]][1] = 1
            All_Symptom[User_List[User_ID]][1] = 1
            
        else:
            answer_str[User_List[User_ID]] = "กรุณาตอบใหม่นะครับ\n" + Question[User_List[User_ID]]
            Skip[User_List[User_ID]] = 1
            Answer_Miss[User_List[User_ID]] += 1
    
    if( Symptom_Processing[User_List[User_ID]][1] == 2 ):
        if (intent_group_question_str == 'อาเจียน' or word_Vomtting =='อาเจียน' or intent_group_question_str == 'Say_Yes'):
            No_Q_Vomtting[User_List[User_ID]] = 8
            Question_Additional[User_List[User_ID]] = 0
            Symptom_Processing[User_List[User_ID]][1] = 1
            All_Symptom[User_List[User_ID]][1] = 1
        elif(intent_group_question_str == 'Say_No'):
            No_Q_ADL[User_List[User_ID]] = 1
            Question_Additional[User_List[User_ID]] = 0
            Symptom_Processing[User_List[User_ID]][1] = 0
            All_Symptom[User_List[User_ID]][1] = 2
            Get_Symptom[User_List[User_ID]][6] = "ห่วงใย"
        else:
            answer_str[User_List[User_ID]] = "กรุณาตอบใหม่นะครับ\n" + Question[User_List[User_ID]]
            Skip[User_List[User_ID]] = 1
            Answer_Miss[User_List[User_ID]] += 1
    
    if( Symptom_Processing[User_List[User_ID]][3] == 2 ):
        if (intent_group_question_str == 'ท้องเสีย' or intent_group_question_str == 'Say_Yes'):
            No_Q_Diarrhea[User_List[User_ID]] = 7
            Question_Additional[User_List[User_ID]] = 0
            Symptom_Processing[User_List[User_ID]][3] = 1
            All_Symptom[User_List[User_ID]][3] = 1
        elif(intent_group_question_str == 'Say_No'):
            No_Q_ADL[User_List[User_ID]] = 1
            Question_Additional[User_List[User_ID]] = 0
            Symptom_Processing[User_List[User_ID]][3] = 0
            All_Symptom[User_List[User_ID]][3] = 2
            Get_Symptom[User_List[User_ID]][6] = "ห่วงใย"
        else:
            answer_str[User_List[User_ID]] = "กรุณาตอบใหม่นะครับ\n" + Question[User_List[User_ID]]
            Skip[User_List[User_ID]] = 1
            Answer_Miss[User_List[User_ID]] += 1

    return answer_str[User_List[User_ID]]

def Main_Q_Nuasea():

    print('Main_Q_Nuasea')

    if No_Q_Nuasea[User_List[User_ID]] > 1:
        answer_str[User_List[User_ID]] = Q_Nuasea()
        Dangerous_lv1[User_List[User_ID]][0] = 1
        Symptom_Processing[User_List[User_ID]][0] = 1

        All_Symptom[User_List[User_ID]][1] = 2 ########### จะไม่มีการไปถามอาเจียนอีก

        ##### เก็บเข้า DataSheet ว่าผู้ใช้เป็นอาการอะไรบ้าง
        if AB_All_Symptom[User_List[User_ID]][6] == 0 and No_Q_Nuasea[User_List[User_ID]] == 5:
            symptom_s[User_List[User_ID]] = "คลื่นไส้"
        elif AB_All_Symptom[User_List[User_ID]][6] == 1 and No_Q_Nuasea[User_List[User_ID]] == 5:
            symptom_s[User_List[User_ID]] += ", คลื่นไส้"

    elif No_Q_Nuasea[User_List[User_ID]] == 1:
        AB_All_Symptom[User_List[User_ID]][0] = 1
        if(AB_All_Symptom[User_List[User_ID]][6] == 0):
            No_Q_ADL[User_List[User_ID]] = 14
        else: 
            No_Q_ADL[User_List[User_ID]] = 1
        No_Q_Nuasea[User_List[User_ID]] = 0
        All_Symptom[User_List[User_ID]][0] = 2
        Symptom_Processing[User_List[User_ID]][0] = 0
        answer_str[User_List[User_ID]] = ""
    
    return answer_str[User_List[User_ID]]

def Main_Q_Vomtting():

    print('Main_Q_Vomtting')

    if No_Q_Vomtting[User_List[User_ID]] > 1:
        answer_str[User_List[User_ID]] = Q_Vomtting()
        Dangerous_lv1[User_List[User_ID]][1] = 1
        Symptom_Processing[User_List[User_ID]][1] = 1
        
        All_Symptom[User_List[User_ID]][0] = 2 ########### จะไม่มีการไปถามคลื่นไส้อีก

        ##### เก็บเข้า DataSheet ว่าผู้ใช้เป็นอาการอะไรบ้าง
        if AB_All_Symptom[User_List[User_ID]][6] == 0 and No_Q_Vomtting[User_List[User_ID]] == 6:
            symptom_s[User_List[User_ID]] = "อาเจียน"
        elif AB_All_Symptom[User_List[User_ID]][6] == 1 and No_Q_Vomtting[User_List[User_ID]] == 6:
            symptom_s[User_List[User_ID]] += ", อาเจียน"

    elif No_Q_Vomtting[User_List[User_ID]] == 1:
        AB_All_Symptom[User_List[User_ID]][1] = 1
        if(AB_All_Symptom[User_List[User_ID]][6] == 0):
            No_Q_ADL[User_List[User_ID]] = 14
        else: 
            No_Q_ADL[User_List[User_ID]] = 1
        No_Q_Vomtting[User_List[User_ID]] = 0
        All_Symptom[User_List[User_ID]][1] = 2
        Symptom_Processing[User_List[User_ID]][1] = 0
        answer_str[User_List[User_ID]] = ""
    
    return answer_str[User_List[User_ID]]

def Main_Q_Comeback():

    print('Main_Q_Comeback')

    if No_Q_Comeback[User_List[User_ID]] > 1:
        answer_str[User_List[User_ID]] = Q_Comeback()
        Dangerous_lv1[User_List[User_ID]][2] = 1

    elif No_Q_Comeback[User_List[User_ID]] == 1:

        ##### เก็บเข้า DataSheet ว่าผู้ใช้เป็นอาการอะไรบ้าง
        symptom_s[User_List[User_ID]] = "อัพเดทอาการหลังพบแพทย์"

        AB_All_Symptom[User_List[User_ID]][2] = 1
        No_Q_ADL[User_List[User_ID]] = 13
        No_Q_Comeback[User_List[User_ID]] = 0
        All_Symptom[User_List[User_ID]][2] = 2
        Symptom_Processing[User_List[User_ID]][2] = 0
        answer_str[User_List[User_ID]] = ""
    
    return answer_str[User_List[User_ID]]

def Main_Q_Diarrhea():

    print('Main_Q_diarrhea')

    if No_Q_Diarrhea[User_List[User_ID]] > 1:
        answer_str[User_List[User_ID]] = Q_Diarrhea()
        Dangerous_lv1[User_List[User_ID]][3] = 1
        Symptom_Processing[User_List[User_ID]][3] = 1

        ##### เก็บเข้า DataSheet ว่าผู้ใช้เป็นอาการอะไรบ้าง
        if AB_All_Symptom[User_List[User_ID]][6] == 0 and No_Q_Diarrhea[User_List[User_ID]] == 6:
            symptom_s[User_List[User_ID]] = "ท้องเสีย"
        elif AB_All_Symptom[User_List[User_ID]][6] == 1 and No_Q_Diarrhea[User_List[User_ID]] == 6:
            symptom_s[User_List[User_ID]] += ", ท้องเสีย"

    elif No_Q_Diarrhea[User_List[User_ID]] == 1:
        AB_All_Symptom[User_List[User_ID]][3] = 1
        if(AB_All_Symptom[User_List[User_ID]][6] == 0):
            No_Q_ADL[User_List[User_ID]] = 14
        else: 
            No_Q_ADL[User_List[User_ID]] = 1
        No_Q_Diarrhea[User_List[User_ID]] = 0
        All_Symptom[User_List[User_ID]][3] = 2
        Symptom_Processing[User_List[User_ID]][3] = 0
        answer_str[User_List[User_ID]] = ""
    
    return answer_str[User_List[User_ID]]

def Main_Q_ADL():

    print('Main_Q_ADL')

    check_Date()

    if No_Q_ADL[User_List[User_ID]] > 1:
        answer_str[User_List[User_ID]] = Q_ADL()
        
    elif No_Q_ADL[User_List[User_ID]] == 1:
        if ADL_lv3[User_List[User_ID]] == 1:
            grade_adl[User_List[User_ID]] = "ความรุนแรงระดับ 3"
        elif ADL_lv2[User_List[User_ID]] == 1:
            grade_adl[User_List[User_ID]] = "ความรุนแรงระดับ 2"
        else:
            grade_adl[User_List[User_ID]] = "ความรุนแรงระดับ 1"
        No_Q_ADL[User_List[User_ID]] = 0
        AB_All_Symptom[User_List[User_ID]][6] = 1
        
        #################### สรุปแต่ละอาการ
        if AB_All_Symptom[User_List[User_ID]][0] == 1 :
            answer_str[User_List[User_ID]] = AB_Nuasea() 
        elif AB_All_Symptom[User_List[User_ID]][1] == 1:
            answer_str[User_List[User_ID]] = AB_Vomtting() 
        elif AB_All_Symptom[User_List[User_ID]][2] == 1:
            answer_str[User_List[User_ID]] = AB_Comeback()
        elif AB_All_Symptom[User_List[User_ID]][3] == 1:
            answer_str[User_List[User_ID]] = AB_Diarrhea() 
        elif AB_All_Symptom[User_List[User_ID]][4] == 1:
            answer_str[User_List[User_ID]] = AB_Etc()
        

        ####### ถามอาการที่เหลือ
        if All_Symptom[User_List[User_ID]][0] == 1 and All_Symptom[User_List[User_ID]][1] == 0:
            Question_Additional[User_List[User_ID]] = 1
            Symptom_Processing[User_List[User_ID]][0] = 2
            answer_str[User_List[User_ID]] += '\n-------------------------------------\nคุณมีอาการคลื่นไส้ด้วยใช่ไหมครับ'
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
        elif All_Symptom[User_List[User_ID]][1] == 1:
            Question_Additional[User_List[User_ID]] = 1
            Symptom_Processing[User_List[User_ID]][1] = 2
            answer_str[User_List[User_ID]] += '\n-------------------------------------\nคุณมีอาการอาเจียนด้วยใช่ไหมครับ'
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
        elif All_Symptom[User_List[User_ID]][3] == 1:
            Question_Additional[User_List[User_ID]] = 1
            Symptom_Processing[User_List[User_ID]][3] = 2
            
            CountIndex = 0
            for Index in range(0,5):
                CountIndex += 1
                if AB_All_Symptom[User_List[User_ID]][Index] == 1:
                    answer_str[User_List[User_ID]] += '\n-------------------------------------\nคุณมีอาการท้องเสียด้วยใช่ไหมครับ'
                    CountIndex = 0
                if CountIndex == 5:
                    answer_str[User_List[User_ID]] = 'คุณมีอาการท้องเสียด้วยใช่ไหมครับ'

            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
        elif AB_All_Symptom[User_List[User_ID]][2] == 1 or AB_All_Symptom[User_List[User_ID]][4] == 1 or AB_All_Symptom[User_List[User_ID]][5] == 1:
            answer_str[User_List[User_ID]] = answer_str[User_List[User_ID]]
        elif All_Symptom[User_List[User_ID]][0] == 0 and All_Symptom[User_List[User_ID]][1] == 0:
            Question_Additional[User_List[User_ID]] = 1
            Symptom_Processing[User_List[User_ID]][0] = 2
            answer_str[User_List[User_ID]] += '\n-------------------------------------\nคุณมีอาการคลื่นไส้ด้วยหรือเปล่าครับ'
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
        elif All_Symptom[User_List[User_ID]][1] == 0:
            Question_Additional[User_List[User_ID]] = 1
            Symptom_Processing[User_List[User_ID]][1] = 2
            answer_str[User_List[User_ID]] += '\n-------------------------------------\nคุณมีอาการอาเจียนด้วยหรือเปล่าครับ'
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
        elif All_Symptom[User_List[User_ID]][3] == 0:
            Question_Additional[User_List[User_ID]] = 1
            Symptom_Processing[User_List[User_ID]][3] = 2
            
            CountIndex = 0
            for Index in range(0,5):
                CountIndex += 1
                print("CountIndex", CountIndex)
                if AB_All_Symptom[User_List[User_ID]][Index] == 1:
                    answer_str[User_List[User_ID]] += '\n-------------------------------------\nคุณมีอาการท้องเสียด้วยหรือเปล่าครับ'
                    CountIndex = 0
                if CountIndex == 5:
                    answer_str[User_List[User_ID]] = 'คุณมีอาการท้องเสียด้วยหรือเปล่าครับ'

            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
        elif(Get_Symptom[User_List[User_ID]][6] == "ห่วงใย"): #กรณีผู้ใช้ตอบ "ไม่" ของการถามว่ามีอาการที่ 2 รึป่าว(ไม่คลื่นไส้อาเจียน ก็ท้องเสีย)
            answer_str[User_List[User_ID]] = 'หากมีอาการอื่นๆสามารถแจ้งกับระบบได้เลยนะครับ พักผ่อนให้เพียงพอนะครับ'
            Get_Symptom[User_List[User_ID]][6] = ""

        AB_All_Symptom[User_List[User_ID]][0] = 0
        AB_All_Symptom[User_List[User_ID]][1] = 0
        AB_All_Symptom[User_List[User_ID]][2] = 0
        AB_All_Symptom[User_List[User_ID]][3] = 0
        AB_All_Symptom[User_List[User_ID]][4] = 0

        
        ################### รวมคำแนะนำ
        if((All_Symptom[User_List[User_ID]][0] == 2 or All_Symptom[User_List[User_ID]][1] == 2)and All_Symptom[User_List[User_ID]][3] == 2):
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
            append_googlesheet()
            Clear_Data_User()
        
        if(All_Symptom[User_List[User_ID]][2] == 2 ):
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
            append_googlesheet()
            Clear_Data_User()

        if(All_Symptom[User_List[User_ID]][4] == 2 and All_Symptom[User_List[User_ID]][0] != 1 and All_Symptom[User_List[User_ID]][1] != 1 and All_Symptom[User_List[User_ID]][2] != 1):
            show_chat(answer_str[User_List[User_ID]])
            append_data_google(answer_str[User_List[User_ID]])
            append_googlesheet()
            Clear_Data_User()
        
    return answer_str[User_List[User_ID]]

def Q_Nuasea():

    print('Q_Nuasea')

    if No_Q_Nuasea[User_List[User_ID]] == 6:
        answer_str[User_List[User_ID]] = 'คุณมีอาการเบื่ออาหารหรือรู้สึกว่าตัวเองมีความอยากอาหารน้อยลงไหมครับ'
    elif No_Q_Nuasea[User_List[User_ID]] == 5:
        answer_str[User_List[User_ID]] = 'ใน 1 วันรับประทานทานอาหารกี่มื้อครับ'
    elif No_Q_Nuasea[User_List[User_ID]] == 4:
        answer_str[User_List[User_ID]] = 'มื้อละประมาณกี่คำครับ'
    elif No_Q_Nuasea[User_List[User_ID]] == 3:
        answer_str[User_List[User_ID]] = 'น้ำหนักตัวลดด้วยหรือเปล่าครับ'
    elif No_Q_Nuasea[User_List[User_ID]] == 2:
        answer_str[User_List[User_ID]] = 'กี่กิโลกรัมครับ'
        
    show_chat(answer_str[User_List[User_ID]])
    append_data_google(answer_str[User_List[User_ID]])
    
    Answer_Miss[User_List[User_ID]] = 0
    No_Q_Nuasea[User_List[User_ID]] -= 1
    Question[User_List[User_ID]] = answer_str[User_List[User_ID]]

    return answer_str[User_List[User_ID]]

def Q_Vomtting():

    print('Q_Vomtting')

    if No_Q_Vomtting[User_List[User_ID]] == 8:
        answer_str[User_List[User_ID]] = 'คุณไม่เพียงแต่รู้สึกคลื่นไส้แต่มีการอาเจียนออกมาด้วยใช่ไหมครับ'
    elif No_Q_Vomtting[User_List[User_ID]] == 7:
        answer_str[User_List[User_ID]] = 'อาเจียนออกมาเป็นแบบไหนครับ(มีแต่น้ำ หรือ มีเศษอาหารด้วย)'
    elif No_Q_Vomtting[User_List[User_ID]] == 6:
        answer_str[User_List[User_ID]] = 'อาเจียนติดต่อกันมานานกี่วันแล้วครับ'
    elif No_Q_Vomtting[User_List[User_ID]] == 5:
        answer_str[User_List[User_ID]] = 'เฉลี่ยต่อวันมีอาการอาเจียนกี่ครั้งครับ'
    elif No_Q_Vomtting[User_List[User_ID]] == 4:
        answer_str[User_List[User_ID]] = 'ได้รับยาที่รักษาเกี่ยวกับโรคมะเร็งครั้งสุดท้ายวันที่เท่าไหร่ครับ'
    elif No_Q_Vomtting[User_List[User_ID]] == 3:
        answer_str[User_List[User_ID]] = 'ถ้าให้คุณประเมินตัวเอง คิดว่าอาการอาเจียนดังกล่าว ไม่สามารถหยุดเองได้ ต้องการยาหรือการรักษาเพิ่มเติม ใช่หรือไม่'
    elif No_Q_Vomtting[User_List[User_ID]] == 2:
        answer_str[User_List[User_ID]] = 'ถ้าให้คุณประเมินตัวเอง คิดว่าอาการอาเจียนดังกล่าว ทำให้คุณอ่อนเพลียมาก จนต้องได้รับน้ำเกลือแร่หรือสารน้ำทางหลอดเลือดดำ ใช่หรือไม่'
    
    show_chat(answer_str[User_List[User_ID]])
    append_data_google(answer_str[User_List[User_ID]])

    Answer_Miss[User_List[User_ID]] = 0
    No_Q_Vomtting[User_List[User_ID]] -= 1
    Question[User_List[User_ID]] = answer_str[User_List[User_ID]]

    return answer_str[User_List[User_ID]]

def Q_Comeback():

    print('Q_Comeback')

    if No_Q_Comeback[User_List[User_ID]] == 5:
        if find_Symptom[User_List[User_ID]] == 'อาเจียน':
            answer_str[User_List[User_ID]] = 'ผู้ป่วยไปพบแพทย์ที่โรงพยาบาลใกล้บ้านเนื่องจากอาการอาเจียนมาแล้วใช่ไหมครับ'
        elif find_Symptom[User_List[User_ID]] == 'ท้องเสีย' or find_Symptom[User_List[User_ID]] == 'ท้องเสีย, คลื่นไส้' or find_Symptom[User_List[User_ID]] == 'คลื่นไส้, ท้องเสีย':
            answer_str[User_List[User_ID]] = 'ผู้ป่วยไปพบแพทย์ที่โรงพยาบาลใกล้บ้านเนื่องจากอาการท้องเสียมาแล้วใช่ไหมครับ'
        elif find_Symptom[User_List[User_ID]] == 'อาเจียน, ท้องเสีย' or find_Symptom[User_List[User_ID]] == 'ท้องเสีย, อาเจียน' or find_Symptom[User_List[User_ID]] == 'อาเจียน, ท้องเสีย, มีไข้' or find_Symptom[User_List[User_ID]] == 'ท้องเสีย, มีไข้, อาเจียน':
            answer_str[User_List[User_ID]] = 'ผู้ป่วยไปพบแพทย์ที่โรงพยาบาลใกล้บ้านเนื่องจากอาการอาเจียนและท้องเสียมาแล้วใช่ไหมครับ'
    elif No_Q_Comeback[User_List[User_ID]] == 4:
        answer_str[User_List[User_ID]] = 'ผู้ป่วยต้องนอนโรงพยาบาลไหมครับ'
    elif No_Q_Comeback[User_List[User_ID]] == 3:
        answer_str[User_List[User_ID]] = 'ผู้ป่วยต้องนอนที่หอผู้ป่วยวิกฤติไอซียู (ICU) หรือไม่ครับ'
    elif No_Q_Comeback[User_List[User_ID]] == 2:
        answer_str[User_List[User_ID]] = 'อาการของผู้ป่วยรุนแรงจนต้องได้ใส่สายให้อาหารเหลว(NG tube) ทางจมูกหรือไม่ครับ'

    show_chat(answer_str[User_List[User_ID]])
    append_data_google(answer_str[User_List[User_ID]])
    
    No_Q_Comeback[User_List[User_ID]] -= 1
    Question[User_List[User_ID]] = answer_str[User_List[User_ID]]

    return answer_str[User_List[User_ID]]

def Q_Nuasea_And_Vomtting():

    if No_Q_Nuasea_And_Vomtting[User_List[User_ID]] == 3:
        answer_str[User_List[User_ID]] = 'ผู้ป่วยมีอาการคลื่นไส้อย่างเดียว หรือคลื่นไส้ร่วมกับอาเจียนครับ'
    elif No_Q_Nuasea_And_Vomtting[User_List[User_ID]] == 2:
        answer_str[User_List[User_ID]] = 'มีอาการคลื่นไส้อย่างเดียว โดยไม่มีอาเจียนใช่ไหมครับ'

    show_chat(answer_str[User_List[User_ID]])
    append_data_google(answer_str[User_List[User_ID]])
    
    Answer_Miss[User_List[User_ID]] = 0
    No_Q_Nuasea_And_Vomtting[User_List[User_ID]] -= 1
    Question[User_List[User_ID]] = answer_str[User_List[User_ID]]

    return answer_str[User_List[User_ID]]

def Q_Diarrhea():

    print('Q_Diarrhea')
    if No_Q_Diarrhea[User_List[User_ID]] == 7:
        answer_str[User_List[User_ID]] = 'มีท้องเสียถ่ายเหลวเป็นน้ำหรือเป็นมูกเลือดไหมครับ'
    elif No_Q_Diarrhea[User_List[User_ID]] == 6:
        answer_str[User_List[User_ID]] = 'มีอาการปวดท้องร่วมด้วยหรือไม่'
    elif No_Q_Diarrhea[User_List[User_ID]] == 5:
        answer_str[User_List[User_ID]] = 'อาการท้องเสียถ่ายเหลวดังกล่าวเป็นมากี่วันแล้วครับ'
    elif No_Q_Diarrhea[User_List[User_ID]] == 4:
        answer_str[User_List[User_ID]] = 'ผู้ป่วยมีถุงหน้าท้องหรือไม่ครับ'
    elif No_Q_Diarrhea[User_List[User_ID]] == 3:
        answer_str[User_List[User_ID]] = 'ผู้ป่วยถ่ายหรือเปลี่ยนถุงหน้าท้องจำนวนกี่ครั้งต่อวันครับ'
    elif No_Q_Diarrhea[User_List[User_ID]] == 2:
        answer_str[User_List[User_ID]] = 'มีไข้ร่วมด้วยหรือไม่'

    show_chat(answer_str[User_List[User_ID]])
    append_data_google(answer_str[User_List[User_ID]])

    Answer_Miss[User_List[User_ID]] = 0
    No_Q_Diarrhea[User_List[User_ID]] -= 1
    Question[User_List[User_ID]] = answer_str[User_List[User_ID]]

    return answer_str[User_List[User_ID]]

def Q_ADL(): 

    if No_Q_ADL[User_List[User_ID]] == 15:
        answer_str[User_List[User_ID]] = 'อาการดังกล่าวยังไม่มีข้อมูลในการประเมินแต่ของสอบถามการใช่ชีวิตประจำของผู้ป่วยได้หรือไม่ครับ'
    elif No_Q_ADL[User_List[User_ID]] == 14:
        answer_str[User_List[User_ID]] = 'อาการที่เกิดขึ้นเป็นช่วงเวลาหลังจากที่ได้ใช้ยาเคมีบำบัด ยามุ่งเป้า ยาปรับภูมิคุ้มกัน หรือยาที่ใช้รักษาโรคมะเร็ง ใช่ไหมครับ'
    elif No_Q_ADL[User_List[User_ID]] == 13:
        answer_str[User_List[User_ID]] = 'ปัจจุบันคุณอาบน้ำหรือแปรงฟันด้วยได้ตัวเองหรือเปล่าครับ'
    elif No_Q_ADL[User_List[User_ID]] == 12:
        answer_str[User_List[User_ID]] = 'แล้วก่อนได้รับยาเคมีบำบัด คุณสามารถอาบน้ำหรือแปรงฟันได้ด้วยตัวเองไหมครับ'
    elif No_Q_ADL[User_List[User_ID]] == 11:
        answer_str[User_List[User_ID]] = 'ปัจจุบันคุณทานอาหารได้ด้วยตัวเองหรือเปล่าครับ'
    elif No_Q_ADL[User_List[User_ID]] == 10:
        answer_str[User_List[User_ID]] = 'แล้วก่อนได้รับยาเคมีบำบัด คุณสามารถทานอาหารได้ด้วยตัวเองไหมครับ'
    elif No_Q_ADL[User_List[User_ID]] == 9:
        answer_str[User_List[User_ID]] = 'ปัจจุบันคุณสวมใส่เสื้อผ้าได้ด้วยตัวเองหรือเปล่าครับ'
    elif No_Q_ADL[User_List[User_ID]] == 8:
        answer_str[User_List[User_ID]] = 'แล้วก่อนได้รับยาเคมีบำบัด คุณสามารถสวมใส่เสื้อผ้าได้ด้วยตัวเองไหมครับ'
    elif No_Q_ADL[User_List[User_ID]] == 7:
        answer_str[User_List[User_ID]] = 'ปัจจุบันคุณทำกับข้าวได้ด้วยตัวเองหรือเปล่าครับ'
    elif No_Q_ADL[User_List[User_ID]] == 6:
        answer_str[User_List[User_ID]] = 'แล้วก่อนได้รับยาเคมีบำบัด คุณสามารถทำกับข้าวได้ด้วยตัวเองไหมครับ'
    elif No_Q_ADL[User_List[User_ID]] == 5:
        answer_str[User_List[User_ID]] = 'ปัจจุบันคุณทำงานบ้านได้ด้วยตัวเองหรือเปล่าครับ'
    elif No_Q_ADL[User_List[User_ID]] == 4:
        answer_str[User_List[User_ID]] = 'แล้วก่อนได้รับยาเคมีบำบัด คุณสามารถทำงานบ้านได้ด้วยตัวเองไหมครับ'
    elif No_Q_ADL[User_List[User_ID]] == 3:
        answer_str[User_List[User_ID]] = 'ปัจจุบันคุณหยิบจับโทรศัพท์และใช้งานโทรศัพท์ได้ด้วยตัวเองหรือเปล่าครับ'
    elif No_Q_ADL[User_List[User_ID]] == 2:
        answer_str[User_List[User_ID]] = 'แล้วก่อนได้รับยาเคมีบำบัด คุณสามารถหยิบจับโทรศัพท์และใช้งานโทรศัพท์ได้ด้วยตัวเองไหมครับ'

    show_chat(answer_str[User_List[User_ID]])
    append_data_google(answer_str[User_List[User_ID]])
    
    Answer_Miss[User_List[User_ID]] = 0
    No_Q_ADL[User_List[User_ID]] -= 1
    Question[User_List[User_ID]] = answer_str[User_List[User_ID]]

    return answer_str[User_List[User_ID]]

def AB_Nuasea():

    print('AB_Nuasea')

    if Dangerous_lv3[User_List[User_ID]][0] == 1 or Point[User_List[User_ID]][0] >= 6 or ADL_lv3[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = 'ตรวจสอบพบว่าอาการดังกล่าวเป็นรุนแรง แนะนำให้พบแพทย์ที่ห้องฉุกเฉิน โรงพยาบาลใกล้บ้านทันที'
        Check_lv3[User_List[User_ID]] = 1
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 3"
    elif Dangerous_lv2[User_List[User_ID]][0] == 1 or Point[User_List[User_ID]][0] >= 1 or ADL_lv2[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = 'ขอให้คำแนะนำให้ทานยาแก้คลื่นไส้อาเจียนเพิ่มเติมดื่มน้ำที่มีส่วนผสมของเกลือแร่ โดยผสมเกลือแร่ผง 1 ซอง ในน้ำ 200 ถึง 250 ซีซีต่อแก้ว ดื่มวันละ 2 – 4 แก้วสังเกตอาการคลื่นไส้ หากมีอาการมากขึ้น ให้แจ้งมาในระบบหรือพบแพทย์ที่โรงพยาบาลใกล้บ้าน'
        if grade_all[User_List[User_ID]] != "ความรุนแรงระดับ 3":
            grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    else:
        answer_str[User_List[User_ID]] = 'ขอให้คำแนะนำให้ทานยาแก้คลื่นไส้อาเจียนเพิ่มเติมดื่มน้ำที่มีส่วนผสมของเกลือแร่แร่ โดยผสมเกลือแร่ผง 1 ซอง ในน้ำ 200 ถึง 250 ซีซีต่อแก้ว ให้จิบบ่อยๆสังเกตอาการคลื่นไส้ หากมีอาการมากขึ้น ให้แจ้งมาในระบบหรือพบแพทย์ที่โรงพยาบาลใกล้บ้าน'
        if grade_all[User_List[User_ID]] != "ความรุนแรงระดับ 2" and grade_all[User_List[User_ID]] != "ความรุนแรงระดับ 3":
            grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 1"

    Get_Symptom[User_List[User_ID]][0] = answer_str[User_List[User_ID]]

    if Dangerous_lv3[User_List[User_ID]][0] == 1 or Point[User_List[User_ID]][0] >= 6:
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 3"
        Check_lv3[User_List[User_ID]] = 1
    elif (Dangerous_lv2[User_List[User_ID]][0] == 1 or Point[User_List[User_ID]][0] >= 1)  and grade_s[User_List[User_ID]] != "ความรุนแรงระดับ 3":
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    elif (Dangerous_lv1[User_List[User_ID]][0] == 1 or Point[User_List[User_ID]][0] == 0) and grade_s[User_List[User_ID]] != "ความรุนแรงระดับ 2" and grade_s[User_List[User_ID]] != "ความรุนแรงระดับ 3":
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 1"

    return answer_str[User_List[User_ID]]

def AB_Vomtting():

    print('AB_Vomtting')
    
    if Dangerous_lv3[User_List[User_ID]][1] == 1 or Point[User_List[User_ID]][1] >= 6 or ADL_lv3[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = 'ตรวจสอบพบว่าอาการดังกล่าวเป็นรุนแรง แนะนำให้พบแพทย์ที่ห้องฉุกเฉิน โรงพยาบาลใกล้บ้านทันที หากท่านได้พบแพทย์ที่โรงพยาบาลใกล้บ้านแล้ว ช่วยแจ้งกลับมาในระบบว่าได้รับการรักษาแบบใดบ้าง'
        Check_lv3[User_List[User_ID]] = 1
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 3"
    elif Dangerous_lv2[User_List[User_ID]][1] == 1 or Point[User_List[User_ID]][1] >= 1 or ADL_lv2[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = 'ขอให้คำแนะนำให้ทานยาแก้คลื่นไส้อาเจียนเติมเพิ่มเติม ดื่มน้ำที่มีส่วนผสมของเกลือแร่ โดยผสมเกลือแร่ผง 1 ซอง ในน้ำ 200 ถึง 250 ซีซีต่อแก้ว ดื่มวันละ 2 - 4 แก้ว - แนะนำให้พบแพทย์ที่โรงพยาบาลใกล้บ้านเพื่อประเมินความรุนแรงของอาการอาเจียนดังกล่าว - หากท่านได้พบแพทย์ที่โรงพยาบาลใกล้บ้านแล้ว ช่วยแจ้งกลับมาในระบบว่าได้รับการรักษาแบบใดบ้าง'
        if  grade_all[User_List[User_ID]] != "ความรุนแรงระดับ 3":
            grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    else:
        answer_str[User_List[User_ID]] = 'ขอให้คำแนะนำให้สังเกตอาการคลื่นไส้ หากมีอาการมากขึ้น ให้แจ้งมาในระบบหรือพบแพทย์ที่โรงพยาบาลใกล้บ้าน'
        if grade_all[User_List[User_ID]] != "ความรุนแรงระดับ 2" and grade_all[User_List[User_ID]] != "ความรุนแรงระดับ 3":
            grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 1"

    
    Get_Symptom[User_List[User_ID]][1] = answer_str[User_List[User_ID]]

    if Dangerous_lv3[User_List[User_ID]][1] == 1 or Point[User_List[User_ID]][1] >= 6:
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 3"
        Check_lv3[User_List[User_ID]] = 1
    elif (Dangerous_lv2[User_List[User_ID]][1] == 1 or Point[User_List[User_ID]][1] >= 1) and grade_s[User_List[User_ID]] != "ความรุนแรงระดับ 3":
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    elif (Dangerous_lv1[User_List[User_ID]][1] == 1 or Point[User_List[User_ID]][1] == 0) and grade_s[User_List[User_ID]] != "ความรุนแรงระดับ 2" and grade_s[User_List[User_ID]] != "ความรุนแรงระดับ 3":
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 1"

    return answer_str[User_List[User_ID]]

def AB_Comeback():

    print('AB_Comeback')
    
    if Dangerous_lv4[User_List[User_ID]][2] == 1:
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 4"
    elif Dangerous_lv3[User_List[User_ID]][2] == 1 or Point[User_List[User_ID]][2] >= 6 or ADL_lv3[User_List[User_ID]] == 1:
        Check_lv3[User_List[User_ID]] = 1
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 3"
    elif Dangerous_lv2[User_List[User_ID]][2] == 1 or Point[User_List[User_ID]][2] >= 1 or ADL_lv2[User_List[User_ID]] == 1:
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    else:
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 1"
    
    answer_str[User_List[User_ID]] = "ขอบคุณที่กลับมาแจ้งอาการเพิ่มเติมหลังจากไปพบแพทย์มาแล้วนะครับ \nพักผ่อนให้เพียงพอด้วยนะครับ"

    
    Get_Symptom[User_List[User_ID]][2] = answer_str[User_List[User_ID]][User_List[User_ID]]

    if Dangerous_lv4[User_List[User_ID]][2] == 1:
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 4"
    elif Dangerous_lv3[User_List[User_ID]][2] == 1 or Point[User_List[User_ID]][2] >= 6:
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 3"
        Check_lv3[User_List[User_ID]] = 1
    elif (Dangerous_lv2[User_List[User_ID]][2] == 1 or Point[User_List[User_ID]][2] >= 1) :
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    elif (Dangerous_lv1[User_List[User_ID]][2] == 1 or Point[User_List[User_ID]][2] == 0) :
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 1"

    return answer_str[User_List[User_ID]]

def AB_Diarrhea():


    print('AB_Diarrhea')
    
    if Dangerous_lv3[User_List[User_ID]][3] == 1 or Point[User_List[User_ID]][3] >= 6 or ADL_lv3[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = 'ตรวจสอบพบว่าอาการดังกล่าวเป็นรุนแรง แนะนำให้พบแพทย์ที่ห้องฉุกเฉิน โรงพยาบาลใกล้บ้านทันที หากท่านได้พบแพทย์ที่โรงพยาบาลใกล้บ้านแล้ว ช่วยแจ้งกลับมาในระบบว่าได้รับการรักษาแบบใดบ้าง'
        Check_lv3[User_List[User_ID]] = 1
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 3"
    elif Dangerous_lv2[User_List[User_ID]][3] == 1 or Point[User_List[User_ID]][3] >= 1 or ADL_lv2[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = 'ขอให้คำแนะนำ\n- หากมียาแก้อาการท้องเสียที่แพทย์เคยให้ไว้ แนะนำให้ทานยาดังกล่าวได้\n- ดื่มน้ำที่มีส่วนผสมของเกลือแร่ โดยผสมเกลือแร่ผง 1 ซอง ในน้ำ 200 ถึง 250 ซีซีต่อแก้ว ดื่มวันละ 2 – 4 แก้ว\n- แนะนำให้พบแพทย์ที่โรงพยาบาลใกล้บ้านเพื่อประเมินความรุนแรงของอาการอาเจียนดังกล่าว\n- หากท่านได้พบแพทย์ที่โรงพยาบาลใกล้บ้านแล้ว ช่วยแจ้งกลับมาในระบบว่าได้รับการรักษาแบบใดบ้าง'
        if grade_all[User_List[User_ID]] != "ความรุนแรงระดับ 3":
            grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    elif Dangerous_lv1[User_List[User_ID]][3] == 1 or Point[User_List[User_ID]][3] == 0 or ADL_lv1[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = 'ขอให้คำแนะนำ\n- หากมียาแก้อาการท้องเสียที่แพทย์เคยให้ไว้ แนะนำให้ทานยาดังกล่าวได้\n- ดื่มน้ำที่มีส่วนผสมของเกลือแร่ โดยผสมเกลือแร่ผง 1 ซอง ในน้ำ 200 ถึง 250 ซีซีต่อแก้ว ดื่มวันละ 2 – 4 แก้ว\n- สังเกตอาการถ่ายเหลวอย่างใกล้ชิด หากมีอาการมากขึ้นให้แจ้งมาในระบบหรือพบแพทย์ที่โรงพยาบาลใกล้บ้าน'
        if grade_all[User_List[User_ID]] != "ความรุนแรงระดับ 2" and grade_all[User_List[User_ID]] != "ความรุนแรงระดับ 3":
            grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 1"

    if Get_Symptom[User_List[User_ID]][4] == "ไข้":
        answer_str[User_List[User_ID]] = 'สงสัยภาวะลำไส้อักเสบติดเชื้อ แนะนำให้พบแพทย์ที่ห้องฉุกเฉิน โรงพยาบาลใกล้บ้านทันที\nหากมีอาการอื่นๆสามารถแจ้งกับระบบได้เลยนะครับ พักผ่อนให้เพียงพอนะครับ'
        Get_Symptom[User_List[User_ID]][4] = ""
    
    Get_Symptom[User_List[User_ID]][3] = answer_str[User_List[User_ID]]

    if Dangerous_lv3[User_List[User_ID]][3] == 1 or Point[User_List[User_ID]][3] >= 6:
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 3"
        Check_lv3[User_List[User_ID]] = 1
    elif (Dangerous_lv2[User_List[User_ID]][3] == 1 or Point[User_List[User_ID]][3] >= 1) and grade_s[User_List[User_ID]] != "ความรุนแรงระดับ 3":
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    elif (Dangerous_lv1[User_List[User_ID]][3] == 1 or Point[User_List[User_ID]][3] == 0) and grade_s[User_List[User_ID]] != "ความรุนแรงระดับ 2" and grade_s[User_List[User_ID]] != "ความรุนแรงระดับ 3":
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 1"

    return answer_str[User_List[User_ID]]

def AB_Etc():

    print('AB_Etc')
    
    if Dangerous_lv3[User_List[User_ID]][4] == 1 or Point[User_List[User_ID]][4] >= 6 or ADL_lv3[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = 'ตรวจสอบพบว่าอาการดังกล่าวเป็นรุนแรง แนะนำให้พบแพทย์ที่ห้องฉุกเฉิน โรงพยาบาลใกล้บ้านทันที'
        Check_lv3[User_List[User_ID]] = 1
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 3"
    elif Dangerous_lv2[User_List[User_ID]][4] == 1 or Point[User_List[User_ID]][4] >= 1 or ADL_lv2[User_List[User_ID]] == 1:
        answer_str[User_List[User_ID]] = 'ขอให้คำแนะนำ\n- ดูแลติดตามอาการอย่างใกล้ชิด\n- หากมียาเดิมที่แพทย์ได้ให้ไว้แล้วให้ทานยาเดิมเพิ่มเติม\n- หากมีอาการมากขึ้น ให้แจ้งมาในระบบหรือพบแพทย์ที่โรงพยาบาลใกล้บ้าน'
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    elif Dangerous_lv1[User_List[User_ID]][4] == 1 or Point[User_List[User_ID]][4] == 0 or ADL_lv1[User_List[User_ID]] == 1 :
        answer_str[User_List[User_ID]] = 'ขอให้คำแนะนำ\n- สังเกตผลข้างเคียงดังกล่าวเพิ่มเติม หากมีอาการมากขึ้น ให้แจ้งมาในระบบหรือพบแพทย์ที่โรงพยาบาลใกล้บ้าน'
        grade_all[User_List[User_ID]] = "ความรุนแรงระดับ 1"
    
    Get_Symptom[User_List[User_ID]][4] = answer_str[User_List[User_ID]]

    if Dangerous_lv3[User_List[User_ID]][4] == 1 or Point[User_List[User_ID]][4] >= 6:
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 3"
        Check_lv3[User_List[User_ID]] = 1
    elif (Dangerous_lv2[User_List[User_ID]][4] == 1 or Point[User_List[User_ID]][4] >= 1) :
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 2"
    elif (Dangerous_lv1[User_List[User_ID]][4] == 1 or Point[User_List[User_ID]][4] == 0) :
        grade_s[User_List[User_ID]] = "ความรุนแรงระดับ 1"
    
    return answer_str[User_List[User_ID]]

def Clear_Data_User(): #ทำให้ตัวแปรทุกตัวของผู้ใช้เป็นค่าเริ่มต้น 
    Dangerous_lv1[User_List[User_ID]] = [0, 0, 0, 0, 0, 0, 0]
    Dangerous_lv2[User_List[User_ID]] = [0, 0, 0, 0, 0, 0, 0]
    Dangerous_lv3[User_List[User_ID]] = [0, 0, 0, 0, 0, 0, 0]
    Point[User_List[User_ID]] = [0, 0, 0, 0, 0, 0, 0]
    ADL_lv1[User_List[User_ID]] = 0 
    ADL_lv2[User_List[User_ID]] = 0 
    ADL_lv3[User_List[User_ID]] = 0 
    No_Q_Nuasea[User_List[User_ID]] = 0
    No_Q_Vomtting[User_List[User_ID]] = 0
    No_Q_Nuasea_And_Vomtting[User_List[User_ID]] = 0
    No_Q_Comeback[User_List[User_ID]] = 0
    No_Q_Diarrhea[User_List[User_ID]] = 0
    No_Q_ADL[User_List[User_ID]] = 0
    Question[User_List[User_ID]] = ""
    Skip[User_List[User_ID]] = 0
    loop_Question[User_List[User_ID]] = 0
    Answer_Miss[User_List[User_ID]] = 0
    Text_answer[User_List[User_ID]] = ""
    AB_All_Symptom[User_List[User_ID]] = [0, 0, 0, 0, 0, 0, 0]
    All_Symptom[User_List[User_ID]] = [0, 0, 0, 0, 0, 0, 0]
    Symptom_Processing[User_List[User_ID]] = [0, 0, 0, 0, 0, 0, 0]
    Get_Symptom[User_List[User_ID]] = ["","","","","","","",""]
    symptom_s[User_List[User_ID]] = ""
    grade_s[User_List[User_ID]] = ""
    grade_adl[User_List[User_ID]] = ""
    grade_all[User_List[User_ID]] = ""
    row[User_List[User_ID]] = ""
    data_sheet[User_List[User_ID]] = ""
    #hospital_status[User_List[User_ID]] = ""
    #found_row_index[User_List[User_ID]] = ""
    #found_row[User_List[User_ID]] = ""
    find_userID[User_List[User_ID]] = ""
    #find_Hospital[User_List[User_ID]] = ""
    find_RecordingDate[User_List[User_ID]] = ""

    
    #User_ID = "User000"
    #Had_User = False

def Times_Of_Eating(respond_dict):
    print("Times_Of_Eating")

    times = int(respond_dict["queryResult"]["outputContexts"][0]["parameters"]["number.original"])

    if(times < 1):
        Point[User_List[User_ID]][0] += 4
        No_Q_Nuasea[User_List[User_ID]] -= 1
    elif(times <= 1):
        Point[User_List[User_ID]][0] += 2
    elif(times <= 3):
        Point[User_List[User_ID]][0] += 1
    else:
        Point[User_List[User_ID]][0] += 0

def Rice_Of_Eating(respond_dict):

    print("Rice_Of_Eating")

    rice = float(respond_dict["queryResult"]["outputContexts"][0]["parameters"]["number.original"])

    if(rice < 3):
        Point[User_List[User_ID]][0] += 2
    elif(rice <= 10):
        Point[User_List[User_ID]][0] += 1
    else:
        Point[User_List[User_ID]][0] += 0

def Lose_Weight(respond_dict):

    print("Lose_Weight")

    weight = float(respond_dict["queryResult"]["outputContexts"][0]["parameters"]["number.original"])

    if(weight == 0):
        Point[User_List[User_ID]][0] += 0
    elif(weight <= 2):
        Point[User_List[User_ID]][0] += 1
    elif(weight <= 4):
        Point[User_List[User_ID]][0] += 2
    else:
        Dangerous_lv3[User_List[User_ID]][0] = 1
    
def excrete(respond_dict):

    excrete = float(respond_dict["queryResult"]["outputContexts"][0]["parameters"]["number.original"])

    if excrete <= 6 and excrete >= 4:
        Dangerous_lv2[User_List[User_ID]][3] = 1
    elif excrete >= 7:
        Dangerous_lv3[User_List[User_ID]][3] = 1

#---------------Database MongoDB---------------

def show_chat(answer_str_sent):
    # รับข้อมูลจาก request
    req = request.get_json(force=True)
    
    # รับข้อความจากผู้ใช้
    query = req['queryResult']['queryText']
    
    # รับเวลาปัจจุบัน
    date, time = timestamp()

    # เก็บข้อมูลการสนทนาใน data
    data[User_List[User_ID]][" User "] = query
    data[User_List[User_ID]][" Bot "] = answer_str_sent

    # เรียกฟังก์ชัน update_conversation_data พร้อมส่งค่าที่ต้องการ
    user_id = User_List[User_ID]  # User ID ของผู้ใช้
    user_query = query  # ข้อความที่ผู้ใช้ส่งเข้ามา
    bot_response = answer_str_sent  # คำตอบของบอท
    
    insert_chat_to_database()
    
    

    
def timestamp():
    request_json = request.get_json()
    original_request = request_json['originalDetectIntentRequest']
    payload = original_request['payload']
    dataline = payload['data']
    unix_timestamp = dataline['timestamp']
    int_timestamp = int(unix_timestamp)
    timestamp_dt = datetime.fromtimestamp(int_timestamp / 1000)
    timestamp_str_time = timestamp_dt.strftime("%H:%M:%S")
    timestamp_str_date = timestamp_dt.strftime("%Y-%m-%d")
    print("time ",timestamp_str_time)
    print("date ",timestamp_str_date)
    return timestamp_str_date, timestamp_str_time

def userId():
    request_json = request.get_json()
    original_request = request_json['originalDetectIntentRequest']
    payload = original_request['payload']
    dataline = payload['data']
    source = dataline['source']
    userId = source['userId']
    line_bot_api = LineBotApi("xKoR+obbdN1n7T+eNJP/fIoiBlhNeEmDlyXDBfjM8x9PdOx1qzMIsSz7a6k+mObPx1qhFjl+HBZU4pXwMTIlmz7D/e39zNgESYIWVMtNjXSIbn8Vweu89NThQuW8Z236S3GA7aQd/hJfNS88cDXjKgdB04t89/1O/w1cDnyilFU=")
    profile = line_bot_api.get_profile(userId)
    #print("profile_display ",profile.display_name)
    print("userId ",userId)
    return userId, profile.display_name

def append_googlesheet():
    date, time = timestamp()
    lineuserId, name = userId()
    document = {'userId' : User_ID,
                'Name' : name,
                'Date' : date,
                'chat': data[User_List[User_ID]]}
    #col = db['chat_data']
    #col.insert_one(document)
    Chat_History.insert_row([lineuserId, name, date, datagoogle[User_List[User_ID]]],2)
    Violence_of_symptom.insert_row([lineuserId, name, date, symptom_s[User_List[User_ID]], grade_s[User_List[User_ID]], grade_adl[User_List[User_ID]], grade_all[User_List[User_ID]]],2)
    print("symptom_s : ", symptom_s[User_List[User_ID]])
    if go_hospital[User_List[User_ID]] == 0:
        Comeback_Status.update_cell(found_row_index[User_List[User_ID]] + 1, 5, "ไปโรงพยาบาลแล้ว")
        Comeback_Status.update_cell(found_row_index[User_List[User_ID]] + 1, 7, date)
        Comeback_Status.update_cell(found_row_index[User_List[User_ID]] + 1, 4, grade_all[User_List[User_ID]])
    elif go_hospital[User_List[User_ID]] == 1:
        Comeback_Status.update_cell(found_row_index[User_List[User_ID]] + 1, 5, "ยังไม่ได้ไปโรงพยาบาล")
        Comeback_Status.update_cell(found_row_index[User_List[User_ID]] + 1, 7, date)
    if symptom_s[User_List[User_ID]] == "อาเจียน" or symptom_s[User_List[User_ID]] == "ท้องเสีย" or symptom_s[User_List[User_ID]] == "อาเจียน, ท้องเสีย" or symptom_s[User_List[User_ID]] == "ท้องเสีย, อาเจียน" or symptom_s[User_List[User_ID]] == "อาเจียน, ท้องเสีย, มีไข้" or symptom_s[User_List[User_ID]] == "ท้องเสีย, มีไข้, อาเจียน" or symptom_s[User_List[User_ID]] == "ท้องเสีย, คลื่นไส้" or  symptom_s[User_List[User_ID]] == "คลื่นไส้, ท้องเสีย":
        if grade_all[User_List[User_ID]] == "ความรุนแรงระดับ 2" or grade_all[User_List[User_ID]] == "ความรุนแรงระดับ 3":
            Comeback_Status.insert_row([lineuserId, name, symptom_s[User_List[User_ID]], grade_all[User_List[User_ID]], hospital_status[User_List[User_ID]], date],2)
    
    

    data[User_List[User_ID]] = {}
    datagoogle[User_List[User_ID]] = ""
    datag[User_List[User_ID]] = ""
    hospital_status[User_List[User_ID]] = "ยังไม่ได้อัพเดท"
    found_row_index[User_List[User_ID]] = ""
    found_row[User_List[User_ID]] = ""
    Get_Symptom[User_List[User_ID]][2] = ""
    go_hospital[User_List[User_ID]] = 2


def check_hospital():
    data_sheet[User_List[User_ID]] = Comeback_Status.get_all_values()
    found_row[User_List[User_ID]] = None
    for row[User_List[User_ID]] in data_sheet[User_List[User_ID]]:
        if row[User_List[User_ID]][0] == User_ID: # หา UserID ใน Google Sheet จาก Column A โดยไล่ตั้งแต่ Row 0 ถ้า UserID ใน Code ตรงกับใน Google Sheet จะหยุดหาแล้วเก็บค่า Row นั้นทั้งหมดลงในตัวแปร found_row หรือก็คือจะเก็บ UserID, LineName, Symptom, etc. มาด้วย
            found_row[User_List[User_ID]] = row[User_List[User_ID]]
            break
    if found_row[User_List[User_ID]] is not None:
        found_row_index[User_List[User_ID]] = data_sheet[User_List[User_ID]].index(found_row[User_List[User_ID]])
        print("found_row is in row: ", found_row_index[User_List[User_ID]] + 1)
        find_userID[User_List[User_ID]] = found_row[User_List[User_ID]][0] # found_row[0] คือ เอาค่าเฉพาะใน Column A หรือก็คือ index 0 = Column A, index 1 = Column B, index 2 = Column C ไปเรื่อยๆ
        print("UserID_from_Google_Sheet :", find_userID[User_List[User_ID]])
        if find_userID[User_List[User_ID]] == User_ID: # ถ้า UserID ใน Code ตรงกับ UserID ใน Sheet
            find_Symptom[User_List[User_ID]] = found_row[User_List[User_ID]][2] # found_row[2] คือ เอาค่าเฉพาะใน Column C
            find_Hospital[User_List[User_ID]] = found_row[User_List[User_ID]][4] # found_row[4] คือ เอาค่าเฉพาะใน Column E
            find_RecordingDate[User_List[User_ID]] = found_row[User_List[User_ID]][5] # found_row[5] คือ เอาค่าเฉพาะใน Column F
            if find_Hospital[User_List[User_ID]] == "ยังไม่ได้อัพเดท": # ถ้า Hospital Status ใน Sheet ตรงกับคำว่า ยังไม่ได้อัพเดท
                print("Hospital_Status_from_Google_Sheet :", find_Hospital[User_List[User_ID]])
                print("Recording_Date_from_Google_Sheet :", find_RecordingDate[User_List[User_ID]])
                Symptom_Processing[User_List[User_ID]][2] = 1
                No_Q_Comeback[User_List[User_ID]] = 5
                loop_Question[User_List[User_ID]] = 1
                Get_Symptom[User_List[User_ID]][2] = "ถามเรื่องไปโรงพยาบาลแล้ว"
    else:
        print("Dont have user ID")

def check_Date():
    date, time = timestamp()
    data_sheet[User_List[User_ID]] = Violence_of_symptom.get_all_values()
    found_row[User_List[User_ID]] = None
    for row[User_List[User_ID]] in data_sheet[User_List[User_ID]]:
        if row[User_List[User_ID]][0] == User_ID: # หา UserID ใน Google Sheet จาก Column A โดยไล่ตั้งแต่ Row 0 ถ้า UserID ใน Code ตรงกับใน Google Sheet จะหยุดหาแล้วเก็บค่า Row นั้นทั้งหมดลงในตัวแปร found_row หรือก็คือจะเก็บ UserID, LineName, Symptom, etc. มาด้วย
            found_row[User_List[User_ID]] = row[User_List[User_ID]]
            break
    if found_row[User_List[User_ID]] is not None:
        found_row_index[User_List[User_ID]] = data_sheet[User_List[User_ID]].index(found_row[User_List[User_ID]])
        print("found_row is in row: ", found_row_index[User_List[User_ID]] + 1)
        find_userID[User_List[User_ID]] = found_row[User_List[User_ID]][0] # found_row[0] คือ เอาค่าเฉพาะใน Column A หรือก็คือ index 0 = Column A, index 1 = Column B, index 2 = Column C ไปเรื่อยๆ
        print("UserID_from_Google_Sheet :", find_userID[User_List[User_ID]])
        if find_userID[User_List[User_ID]] == User_ID: # ถ้า UserID ใน Code ตรงกับ UserID ใน Sheet
            find_Date_firsttime[User_List[User_ID]] = found_row[User_List[User_ID]][2] # found_row[2] คือ เอาค่าเฉพาะใน Column C
            if find_Date_firsttime[User_List[User_ID]] == date: # ถ้า Hospital Status ใน Sheet ตรงกับคำว่า ยังไม่ได้อัพเดท

                No_Q_ADL[User_List[User_ID]] = 1

                if found_row[User_List[User_ID]][5] == "ความรุนแรงระดับ 3":
                    ADL_lv3[User_List[User_ID]] = 1 
                elif found_row[User_List[User_ID]][5] == "ความรุนแรงระดับ 2":
                    ADL_lv2[User_List[User_ID]] = 1
                elif found_row[User_List[User_ID]][5] == "ความรุนแรงระดับ 1":
                    ADL_lv1[User_List[User_ID]] = 1
    else:
        print("Dont have user ID")

#----------------Google Sheet---------------

def append_data_google(answer_str_sent):
    global datagoogle
    global datag
    date,time = timestamp()
    lineuserId,name = userId()
    req = request.get_json(force = True)
    query = req['queryResult']['queryText']

    #จัดรูปแบบข้อความในรูปแบบ '14:38:03 User : ท้องเสีย'
    user_query = f"{time} User : {query}"
    bot_response = f"{time} Bot : {answer_str[User_List[User_ID]]}"

    datagoogle[User_List[User_ID]] = user_query + "\n" + bot_response + "\n"
    datagoogle[User_List[User_ID]] = time + " User : " + query + "\n" + time + " Bot : " + answer_str[User_List[User_ID]] + "\n"
    datag[User_List[User_ID]] = "".join([datag[User_List[User_ID]], datagoogle[User_List[User_ID]]])
    datagoogle[User_List[User_ID]] = datag[User_List[User_ID]]
   
    print("user_chat : ",user_query)
    print("bot_chat : ",bot_response)
    
#----------------------------------------------------------------  Register User ----------------------------------------------

def handle_registration(User_ID, user_input, question_from_dailogflow_dict):
    global registration_data

    # ดึง intent จาก question_from_dailogflow_dict
    intent = question_from_dailogflow_dict["queryResult"]["intent"]["displayName"]

    # ตรวจสอบ intent ว่าตรงกับการลงทะเบียนหรือไม่
    if intent == 'Register':
        if User_ID not in registration_data:
            registration_data[User_ID] = {
                'step': 1,
                'data': {}
            }
            question = 'กรุณาพิมพ์ชื่อของคุณ(นายสมศรี มีสาย)'
            return json.dumps({"fulfillmentText": question}, ensure_ascii=False)

    elif intent in ['Register_Patient_Name', 'Register_Patient_Contact', 'Register_Patient_Gender', 'Register_Patient_Address', 'Register_Patient_IdCn']:
        user_registration = registration_data[User_ID]
        step = user_registration['step']

        registration_steps = [
            ('กรุณาพิมพ์ชื่อจริงและนามสกุลของคุณ(นายสมศรี มีสาย)', 'Name'),
            ('กรุณาพิมพ์เบอร์โทรศัพท์ของคุณ (พิมพ์คำว่า เบอร์ นำหน้าด้วย เช่น เบอร์ 0638631903)', 'Contact'),
            ('กรุณาพิมพ์เพศของคุณ (ชาย/หญิง)', 'Gender'),
            ('กรุณาพิมพ์ที่อยู่ของคุณ (เช่น 11/111 ต.เมือง อ.เมือง จ.เมือง)', 'AddressID'),
            ('กรุณาพิมพ์เลขบัตรประชาชน13หลักของคุณ (เช่น 1234567890123)', 'IdCn')
        ]

        if 1 <= step <= len(registration_steps):
            key = registration_steps[step - 1][1]
            user_registration['data'][key] = user_input.strip()
            user_registration['step'] += 1

            if user_registration['step'] <= len(registration_steps):
                next_question, _ = registration_steps[user_registration['step'] - 1]
                return json.dumps({"fulfillmentText": next_question}, ensure_ascii=False)
            else:
                lineuserId, name = userId()
                Register_date, Register_time = timestamp()

                user_registration['data']['LineName'] = name
                user_registration['data']['LineID'] = lineuserId
                user_registration['data']['Register_date'] = Register_date
                user_registration['data']['StatusMember'] = 0

                print(user_registration['data'])  # ตรวจสอบข้อมูลก่อนบันทึก

                try:
                    insert_patient_to_database(user_registration['data'])
                    confirmation_message = "ลงทะเบียนสำเร็จ ขอบคุณที่ให้ข้อมูลครับ"
                except Exception as e:
                    confirmation_message = f"เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}"

                del registration_data[User_ID]
                return json.dumps({"fulfillmentText": confirmation_message}, ensure_ascii=False)

    return json.dumps({"fulfillmentText": "ขออภัย ไม่สามารถดำเนินการได้"}, ensure_ascii=False)


#----------------------------------------------------------------  database ----------------------------------------------------

def format_conversation(conversation: str): # แยก User bot ก่อนเก็บ
    # Pattern to extract time, position, and text
    pattern = r'(\d{2}:\d{2}:\d{2})\s(User|Bot)\s:\s(.+?)(?=\d{2}:\d{2}:\d{2}\s|$)'

    # Extracting information
    matches = re.findall(pattern, conversation, re.DOTALL)

    # Creating the desired format
    formatted_conversation = []
    for match in matches:
        time, position, text = match
        formatted_conversation.append({"text": text.strip(), "time": time, "position": position})
    
    return formatted_conversation
    
def insert_chat_to_database():
    # เรียกใช้งานฟังก์ชันเพื่อนำค่ามาใช้
    lineuserId, name = userId()
    date, time = timestamp()
    conversation = datagoogle[User_List[User_ID]]
    format_con_json = format_conversation(conversation)
    format_con = json.dumps(format_con_json, ensure_ascii=False)  # ใช้ ensure_ascii=False เพื่อให้ได้ผลลัพธ์ที่เป็น string ปกติ
    print(format_con)
    # ข้อมูลที่ต้องการแทรกลงในตาราง
    data_to_insert = (
        lineuserId,  # จากฟังก์ชัน userId()
        name,  # จากฟังก์ชัน userId()
        date,  # จากฟังก์ชัน timestamp()
        time,  # จากฟังก์ชัน timestamp()
        format_con,  # ประวัติการแชท
        grade_s[User_List[User_ID]],  # ระดับความรุนแรงของอาการ
        grade_adl[User_List[User_ID]],  # การประเมินผลกระทบต่อการใช้ชีวิต
        grade_all[User_List[User_ID]],  # ความรุนแรงรวม
        symptom_s[User_List[User_ID]],  # อาการที่ได้รับ
        hospital_status[User_List[User_ID]],  # สถานะการไปโรงพยาบาล 
        find_RecordingDate[User_List[User_ID]],  # วันที่บันทึกครั้งแรก
        date  # วันที่อัปเดตล่าสุด
    )

    # เรียกใช้ฟังก์ชันเพื่อบันทึกข้อมูลลงในตาราง
    success = insert_chat_result(data_to_insert)
    if success:
        print("บันทึกข้อมูลลงฐานข้อมูลสำเร็จ")
    else:
        print("เกิดข้อผิดพลาดในการบันทึกข้อมูล")




#Flask
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print("Starting app on port %d" % port)
    app.run(debug=False, port=port, host='0.0.0.0', threaded=True)


