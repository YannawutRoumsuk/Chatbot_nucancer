import mysql.connector
from mysql.connector import Error

def connect_to_database():
    """
    ฟังก์ชันนี้เชื่อมต่อกับฐานข้อมูลและส่งคืนการเชื่อมต่อและตัวชี้ cursor
    """
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="nucancer"
        )

        if connection.is_connected():
            print("เชื่อมต่อกับฐานข้อมูลสำเร็จ")
            return connection, connection.cursor()
    except Error as e:
        print("เกิดข้อผิดพลาดในการเชื่อมต่อกับฐานข้อมูล:", e)
        return None, None

# def insert_chat_result(data_to_insert):
#     """
#     ฟังก์ชันนี้ทำการแทรกข้อมูลลงในตาราง `chatresult`
#     """
#     connection, cursor = connect_to_database()
#     if connection is None or cursor is None:
#         return False
    
#     insert_query = """
#     INSERT INTO chatresult (
#         LineID, LineName, date, time_chat, chat_history, grade_symptom, grade_adl, grade_all, symptom, hospital_status, recording_date, updating_date
#     ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#     """

#     try:
#         cursor.execute(insert_query, data_to_insert)
#         connection.commit()
#         print("บันทึกข้อมูลลงในตารางสำเร็จ")
#         return True
#     except Error as e:
#         print("เกิดข้อผิดพลาดในการแทรกข้อมูล:", e)
#         return False
#     finally:
#         if connection.is_connected():
#             cursor.close()
#             connection.close()
#             print("การเชื่อมต่อถูกปิดแล้ว")
def insert_chat_result(data_to_insert):
    """
    ฟังก์ชันนี้ทำการแทรกข้อมูลลงในตาราง `chatresult`
    """
    connection, cursor = connect_to_database()
    if connection is None or cursor is None:
        return False
    
    # ตรวจสอบ LineID ในตาราง patient เพื่อดึง PatientNumber
    select_query = "SELECT PatientNumber FROM patient WHERE LineID = %s"
    cursor.execute(select_query, (data_to_insert[0],))
    result = cursor.fetchone()
    
    if result is None:
        print("ไม่พบข้อมูล PatientNumber สำหรับ LineID นี้")
        return False
    
    patient_number = result[0]
    
    # เพิ่มข้อมูลลงในตาราง chatresult และดึง chat_result_id
    insert_query = """
    INSERT INTO chatresult (
        LineID, LineName, date, time_chat, chat_history, grade_symptom, grade_adl, grade_all, symptom, hospital_status, recording_date, updating_date
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    try:
        cursor.execute(insert_query, data_to_insert)
        connection.commit()
        chat_result_id = cursor.lastrowid
        print("บันทึกข้อมูลลงในตาราง chatresult สำเร็จ")

        # เพิ่มข้อมูลลงในตาราง flow
        insert_flow_query = "INSERT INTO flowchat (PatientNumber, chat_result_id, Date, LineID) VALUES (%s, %s, %s, %s)"
        flow_data = (patient_number, chat_result_id, data_to_insert[2], data_to_insert[0])
        cursor.execute(insert_flow_query, flow_data)
        connection.commit()
        print("บันทึกข้อมูลลงในตาราง flow สำเร็จ")

        return True
    except Error as e:
        print("เกิดข้อผิดพลาดในการแทรกข้อมูล:", e)
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("การเชื่อมต่อถูกปิดแล้ว")
            
            
            
def insert_patient_to_database(patient_data):
    """
    ฟังก์ชันนี้ใช้ในการเพิ่มข้อมูลผู้ป่วยลงในฐานข้อมูล MySQL
    """
    # เรียกใช้ฟังก์ชัน connect_to_database เพื่อเชื่อมต่อฐานข้อมูล
    connection, cursor = connect_to_database()

    if connection is None or cursor is None:
        print("ไม่สามารถเชื่อมต่อกับฐานข้อมูลได้")
        return

    try:
        # SQL สำหรับเพิ่มข้อมูลผู้ป่วย โดยไม่เก็บ AddressID และเก็บ Register_date จากข้อมูลผู้ใช้
        sql_insert_query = """
        INSERT INTO patient (Name, Contact, Gender, AddressID, LineName, Register_date, LineID, IdCn)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        # จัดเตรียมข้อมูลสำหรับการเพิ่ม
        data_tuple = (
            patient_data.get('Name', None),
            patient_data.get('Contact', None),
            patient_data.get('Gender', None),
            patient_data.get('AddressID', None),
            patient_data.get('LineName', None),
            patient_data.get('Register_date', None),
            patient_data.get('LineID', None),
            patient_data.get('IdCn', None)  # เพิ่มการเก็บข้อมูล IdCn
        )

        # เรียกใช้ SQL query
        cursor.execute(sql_insert_query, data_tuple)
        connection.commit()

        print("ข้อมูลผู้ป่วยถูกบันทึกสำเร็จ")

    except mysql.connector.Error as error:
        print(f"เกิดข้อผิดพลาด: {error}")
    finally:
        # ปิดการเชื่อมต่อ
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection ถูกปิดแล้ว")


