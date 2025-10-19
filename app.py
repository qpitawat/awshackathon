import os
import boto3
import tempfile
import traceback
from flask import Flask, request, jsonify, render_template
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI

# --- AWS Configuration ---
S3_BUCKET_NAME = "hackathondataq" # <<<<<<< เปลี่ยนชื่อ Bucket ของคุณ
S3_VECTOR_STORE_KEY = "vector_store/faiss_index" # ที่เก็บ Vector Store ใน S3
SECRET_NAME = "hackathon/gemini/api_key" # <<<<<<< ชื่อ Secret ใน Secrets Manager
# -------------------------

def get_gemini_key_from_secrets_manager():
    """ดึง API Key จาก AWS Secrets Manager"""
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager')
    try:
        get_secret_value_response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = get_secret_value_response['SecretString']
        return secret
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการดึง Secret: {e}")
        raise e

def download_s3_folder(bucket_name, s3_folder, local_dir):
    """ดาวน์โหลดทั้งโฟลเดอร์จาก S3"""
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    for obj in bucket.objects.filter(Prefix=s3_folder):
        target = os.path.join(local_dir, os.path.relpath(obj.key, s3_folder))
        if not os.path.exists(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))
        if obj.key[-1] != '/':
            print(f"กำลังดาวน์โหลด {obj.key} -> {target}")
            bucket.download_file(obj.key, target)


def setup_components():
    """ตั้งค่า LLM และ Retriever โดยโหลดข้อมูลจาก S3"""
    try:
        gemini_key = get_gemini_key_from_secrets_manager()
    except Exception:
        return None, None, None

    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash", # แก้ไขเป็น 1.5 flash ตามที่ใช้ได้
        temperature=0,
        google_api_key=gemini_key,
        max_output_tokens=500
    )
    
    with tempfile.TemporaryDirectory() as temp_dir:
        local_vector_store_path = os.path.join(temp_dir, "faiss_index_local")
        os.makedirs(local_vector_store_path, exist_ok=True)
        
        print("กำลังดาวน์โหลด Vector Store จาก S3...")
        download_s3_folder(S3_BUCKET_NAME, S3_VECTOR_STORE_KEY, local_vector_store_path)
        print("ดาวน์โหลด Vector Store สำเร็จ")

        if not os.path.exists(local_vector_store_path) or not os.listdir(local_vector_store_path):
            print(f"ไม่พบ Vector Store ใน S3 path: s3://{S3_BUCKET_NAME}/{S3_VECTOR_STORE_KEY}")
            return None, None, None

        embedding = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        vectordb = FAISS.load_local(
            local_vector_store_path, 
            embedding, 
            allow_dangerous_deserialization=True
        )

    retriever = vectordb.as_retriever(search_kwargs={"k": 12})
    return llm, vectordb, retriever

# (ส่วนของฟังก์ชัน ask_llm และตัวแปร app, message_history เหมือนเดิม)
# ...

app = Flask(__name__)
message_history = [] 

print("กำลังเริ่มต้นและตั้งค่า Components...")
LLM, VDB, RET = setup_components()
if not all([LLM, VDB, RET]):
    print("="*50)
    print("ERROR: ไม่สามารถตั้งค่า Components หลักได้ กรุณาตรวจสอบ S3 และ Secrets Manager")
    print("="*50)
# (ส่วนของ @app.route("/", ...) และ @app.route("/chat", ...) เหมือนเดิมทั้งหมด)
# ... (ใส่โค้ดจากไฟล์เดิมของคุณที่นี่) ...

# ลบ if __name__ == "__main__": ออก เพราะ Gunicorn จะเป็นคนรัน app object นี้