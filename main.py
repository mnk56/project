import cv2
import os
import io
import re
import sqlite3
import threading
from google.cloud import vision
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# --- Өгөгдлийн сангийн тохиргоо ---
def init_db():
    conn = sqlite3.connect('hotel.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            car_number TEXT,
            status TEXT DEFAULT '予約済み',
            is_vip INTEGER DEFAULT 0,
            special_needs TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("!!! АНХААР: hotel.db файл амжилттай үүсэж, холбогдлоо !!!")



# --- Google Cloud Vision тохиргоо ---
# Файлын замыг өөрийн компьютер дээрх замаар солихыг анхаарна уу
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'c:\Users\User\OneDrive\Desktop\project\車A12.03\車A12.03\New folder\project-pjwork1-ai06bd-653e09464dee.json'
client = vision.ImageAnnotatorClient()

# --- Flask Routes ---

@app.route('/')
def index():
    """Үндсэн захиалгын хуудас"""
    return render_template('booking.html')

@app.route('/register', methods=['POST'])
def register():
    """Формын өгөгдлийг хадгалах хэсэг"""
    try:
        name = request.form.get('name')
        phone = request.form.get('phone')
        
        # Машины дугаар нэгтгэх
        car_area = request.form.get('carArea', '')
        car_class = request.form.get('carClass', '')
        car_kana = request.form.get('carKana', '')
        car_num = request.form.get('carNumber', '')
        full_car_number = f"{car_area} {car_class} {car_kana} {car_num}"

        is_vip = 1 if 'vip' in request.form else 0
        special_needs = request.form.get('other_requests', '')

        conn = sqlite3.connect('hotel.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (name, phone, car_number, is_vip, special_needs, status) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, phone, full_car_number, is_vip, special_needs, '予約済み'))
        conn.commit()
        conn.close()

        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Алдаа гарлаа: {str(e)}"

@app.route('/dashboard')
def dashboard():
    conn = sqlite3.connect('hotel.db')
    conn.row_factory = sqlite3.Row
    users = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('dashboard.html', users=users)

# --- Япон улсын дугаар таних функц ---
def extract_japanese_plate(text):
    # Япон дугаар таних Regex
    pattern = r"([一-龠ぁ-んァ-ヶ]+)\s*(\d{3})\s*([ぁ-ん])\s*(\d{1,2}[-ー]\d{2}|\d{1,4})"
    clean_text = text.replace('\n', ' ')
    match = re.search(pattern, clean_text)
    
    if match:
        data = {
            'prefecture': match.group(1),
            'class_code': match.group(2),
            'hiragana': match.group(3),
            'number': match.group(4),
            'full': f"{match.group(1)} {match.group(2)} {match.group(3)} {match.group(4)}",
        }
        return data
    return None

# --- Камер болон OCR-ын үндсэн цикл ---
def camera_worker():
    cap = cv2.VideoCapture(0)
    print("Камер ажиллаж байна... 's' дээр дарж скан хийнэ үү.")
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        cv2.imshow('AI06 Hotel - Plate Scanner', frame)
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('s'):
            print("Скан хийж байна...")
            # 1. Зургийн хэмжээг багасгах (Хурд нэмнэ)
            small_frame = cv2.resize(frame, (800, 600))
            
            # 2. Зургийг санах ойд шахах
            success, encoded_image = cv2.imencode('.jpg', small_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            content = encoded_image.tobytes()
            image = vision.Image(content=content)
            
            # 3. Google рүү илгээх (Сүлжээний хурднаас хамаарна)
            response = client.text_detection(image=image)
            texts = response.text_annotations

            if texts:
                raw_text = texts[0].description
                plate_data = extract_japanese_plate(raw_text) # Одоо энэ нь Dictionary авна
                
                if plate_data:
                    # ТАНЫ ХҮССЭН ХЭВЛЭХ ХЭСЭГ
                    print("==============================")
                    print(f"Full: {plate_data['full']}")
                    print(f"prefecture: {plate_data['prefecture']}")
                    print(f"class_code: {plate_data['class_code']}")
                    print(f"Hiragana: {plate_data['hiragana']}")
                    print(f"Number: {plate_data['number']}")
                    print("==============================")
                    
                    # Өгөгдлийн сан шинэчлэх
                    conn = sqlite3.connect('hotel.db')
                    cursor = conn.cursor()
                    
                    cursor.execute("UPDATE users SET status = '到着済み' WHERE car_number LIKE ?", (plate_data['full'],))
                    
                    if cursor.rowcount > 0:
                        print(f"Систем: Зочин хүрэлцэн ирлээ! ({plate_data['full']})")
                    else:
                        print(f"Систем: {plate_data['full']} дугаартай захиалга олдсонгүй.")
                    
                    conn.commit()
                    conn.close()
            else:
                print("Бичиг танигдсангүй.")
        
        elif key == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

# Камерыг тусад нь thread дээр ажиллуулах
threading.Thread(target=camera_worker, daemon=True).start()

if __name__ == '__main__':
    init_db()
    # use_reloader=False байх нь чухал, үгүй бол камерын thread хоёр удаа ажиллах магадлалтай
    app.run(debug=True, use_reloader=False)