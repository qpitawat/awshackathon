import os
import ifcopenshell
from glob import glob
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import boto3
import tempfile

# --- AWS Configuration ---
S3_BUCKET_NAME = "hackathondataq" # <<<<<<< เปลี่ยนชื่อ Bucket ของคุณ
S3_IFC_PREFIX = "ifc-data/" # โฟลเดอร์ใน S3 ที่เก็บไฟล์ .ifc
S3_VECTOR_STORE_KEY = "vector_store/faiss_index" # ที่จะเซฟ Vector Store ใน S3
# -------------------------

# (ส่วนของฟังก์ชัน normalize_value และ extract_kg_triples เหมือนเดิม)
# ... (ใส่โค้ดจากไฟล์เดิมของคุณที่นี่) ...

def create_vector_store():
    s3_client = boto3.client("s3")
    
    # 1. ดาวน์โหลดไฟล์ .ifc จาก S3 มาไว้ที่ Temporary Directory
    ifc_files = []
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=S3_IFC_PREFIX)
    with tempfile.TemporaryDirectory() as temp_dir:
        for page in pages:
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('.ifc'):
                    file_name = os.path.basename(obj['Key'])
                    local_path = os.path.join(temp_dir, file_name)
                    print(f"กำลังดาวน์โหลด {obj['Key']} -> {local_path}")
                    s3_client.download_file(S3_BUCKET_NAME, obj['Key'], local_path)
                    ifc_files.append(local_path)

        if not ifc_files:
            print("ไม่เจอไฟล์ IFC ใน S3 path:", S3_IFC_PREFIX)
            return

        # 2. ประมวลผลไฟล์และสร้าง Documents (เหมือนเดิม)
        docs = []
        kg_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

        for f in ifc_files:
            kg_triples = extract_kg_triples(f)
            if not kg_triples:
                continue
            
            kg_string_list = [f"{s} {p.upper()} {o}." for s, p, o in kg_triples]
            content_str = "\n".join(kg_string_list)
            doc = Document(page_content=content_str, metadata={"file": os.path.basename(f)})
            chunks = kg_splitter.split_documents([doc])
            docs.extend(chunks)

        if not docs:
            print("ไม่สามารถประมวลผลไฟล์ IFC ได้เลย")
            return
            
        print(f"\nโหลดมาแล้ว {len(docs)} chunks จาก KG Triple")

        # 3. สร้าง Vector Store และเซฟลง Temporary Directory
        emb = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
        vectordb = FAISS.from_documents(docs, emb)
        
        local_vector_store_path = os.path.join(temp_dir, "faiss_index_local")
        vectordb.save_local(local_vector_store_path)
        print(f"สร้าง Vector Store ที่ {local_vector_store_path} สำเร็จ")

        # 4. อัปโหลดไฟล์ Vector Store ทั้งหมดกลับไปที่ S3
        for root, dirs, files in os.walk(local_vector_store_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                # สร้าง S3 key ให้สอดคล้องกับโครงสร้าง local
                relative_path = os.path.relpath(local_file_path, local_vector_store_path)
                s3_key = f"{S3_VECTOR_STORE_KEY}/{relative_path}"
                
                print(f"กำลังอัปโหลด {local_file_path} -> s3://{S3_BUCKET_NAME}/{s3_key}")
                s3_client.upload_file(local_file_path, S3_BUCKET_NAME, s3_key)

    print(f"บันทึก Vector Store ไปที่ s3://{S3_BUCKET_NAME}/{S3_VECTOR_STORE_KEY} เรียบร้อย")

if __name__ == "__main__":
    create_vector_store()