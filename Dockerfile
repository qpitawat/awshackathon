# ใช้ base image ของ Python
FROM python:3.10-slim

# ตั้งค่า working directory ใน container
WORKDIR /app

# คัดลอกไฟล์ requirements.txt เข้าไปก่อนเพื่อ cache layer
COPY requirements.txt .

# ติดตั้ง dependencies
# --no-cache-dir เพื่อให้ image เล็กลง
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ดทั้งหมดของแอปพลิเคชันเข้าไปใน container
COPY . .

# บอกให้ Container เปิด Port 8080 รอรับ traffic
EXPOSE 8080

# คำสั่งที่จะรันเมื่อ container เริ่มทำงาน
# ใช้ gunicorn เป็น production server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "app:app"]