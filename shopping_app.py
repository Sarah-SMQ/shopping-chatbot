import os
import requests
import streamlit as st
from dotenv import load_dotenv
import json
import uuid
from langdetect import detect

# ---------------- Load Environment ----------------
load_dotenv(r"C:\Users\SarahAlqahtani\Documents\SerpAPI_Research\.env")
BACKEND_URL = "http://127.0.0.1:8000"
ALL_CHATS_FILE = "all_chats_unified.json"
ALL_CHATS_FILE_TEST = None


# ---------------- Load existing chats ----------------
if os.path.exists(ALL_CHATS_FILE):
    with open(ALL_CHATS_FILE, "r", encoding="utf-8") as f:
        all_chats = json.load(f)
else:
    all_chats = []

# ---------------- Streamlit Setup ----------------
st.set_page_config(page_title="🛒 Shopping Chat Assistant", layout="wide")

st.markdown("""
<style>
/* ===== الصفحة ===== */
body { background-color: #FFF8E1; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif'; }
/* ===== عنوان التطبيق ===== */
h1 { color: #FF6F61; text-align: center; font-size: 42px; margin-bottom: 10px; }
/* ===== الأزرار ===== */
.stButton>button { font-size:16px; font-weight:bold; color:white; background: linear-gradient(90deg, #FF8A65, #FFB74D); border-radius:12px; padding:8px 20px; transition:0.3s; }
.stButton>button:hover { background: linear-gradient(90deg, #FFB74D, #FF8A65); }
/* ===== فقاعات الدردشة ===== */
.user-msg { background:#81D4FA; color:#000; padding:12px; border-radius:16px; max-width:65%; margin:6px 0; text-align:right; box-shadow:0 2px 8px rgba(0,0,0,0.15); }
.ai-msg { background:#FFF59D; color:#000; padding:12px; border-radius:16px; max-width:65%; margin:6px 0; text-align:left; box-shadow:0 2px 8px rgba(0,0,0,0.15); }
/* ===== منتجات ===== */
.product-card { background-color:#E6E6FA; border-radius:12px; padding:10px; margin:5px; text-align:center; box-shadow:0 3px 6px rgba(0,0,0,0.1); transition:0.3s; display:inline-block; vertical-align:top; width:30%; }
.product-card:hover { background-color:#D8BFD8; }
.product-img { width: 150px; border-radius:8px; margin-bottom:8px; object-fit: contain; }
.product-link { font-weight:bold; color:#F06292; text-decoration:none; }
.product-link:hover { text-decoration:underline; }

/* ===== Responsive for mobile ===== */
@media screen and (max-width: 480px) {
    .user-msg, .ai-msg { max-width: 95%; font-size: 14px; }
    .product-card { width: 95%; margin: 5px auto; display:block; }
    .product-img { width: 100%; max-width: 200px; height: auto; margin-bottom: 8px; }
}
</style>
""", unsafe_allow_html=True)

st.title("🛒✨ مساعد التسوق الذكي - Chat & Discover")

# ---------------- Initialize session ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------- Detect language ----------------
def detect_language(text):
    try:
        lang = detect(text)
        return "ar" if lang.startswith("ar") else "en"
    except:
        return "en"

# ---------------- Display Chat ----------------
def show_chat():
    for msg in st.session_state.messages:
        role = msg["role"]
        color_class = "user-msg" if role=="user" else "ai-msg"
        content = msg["content"]
        st.markdown(f"<div class='{color_class}'>{content}</div>", unsafe_allow_html=True)

# ---------------- Save chat ----------------
def save_chat_unified(data):
    file_path = ALL_CHATS_FILE_TEST or ALL_CHATS_FILE
    for entry in all_chats:
        if entry["query"] == data["query"]:
            existing_titles = {p["title"] for p in entry["products"]}
            for p in data["products"]:
                if p["title"] not in existing_titles:
                    entry["products"].append(p)
            entry["ai_reply"] = data["ai_reply"]
            entry["evaluation_score"] = data["evaluation_score"]
            break
    else:
        all_chats.append(data)
    
    with open(file_path,"w",encoding="utf-8") as f:
        json.dump(all_chats,f,ensure_ascii=False, indent=2)

    # with open(ALL_CHATS_FILE,"w",encoding="utf-8") as f:
    #     json.dump(all_chats,f,ensure_ascii=False, indent=2)

# ---------------- User Input ----------------
user_query = st.text_input("💬 اكتب سؤالك هنا", key="unique_user_query_key")
user_lang = detect_language(user_query)
send_button_text = "🔍 إرسال" if user_lang=="ar" else "🔍 Send"

if st.button(send_button_text) and user_query:
    # أضف السؤال مباشرة
    st.session_state.messages.append({"role":"user","content":user_query})

    try:
        # ---------------- GET request with max_tokens=1000 ----------------
        res = requests.get(f"{BACKEND_URL}/search", params={"query":user_query, "max_tokens":1000}, timeout=20)
        if res.status_code == 200:
            data = res.json()
            ai_reply = data.get("ai_reply", "لا توجد إجابة من AI" if user_lang=="ar" else "No AI reply available")
            
            # أضف الرد مباشرة
            st.session_state.messages.append({"role":"ai","content":ai_reply})
            show_chat()

            # ---------------- Hide evaluation from frontend ----------------
            eval_scores = data.get("evaluation_score", {})  # still saved in JSON

            # ---------------- Display products ----------------
            products_by_item = data.get("products_by_item", {})
            flat_products = [p for plist in products_by_item.values() for p in plist]

            if products_by_item:
                with st.expander("🛍️ منتجات مرتبطة بالسؤال" if user_lang=="ar" else "🛍️ Related Products"):
                    for item_name, products in products_by_item.items():
                        st.markdown(f"### 🔎 {'منتجات مرتبطة بـ:' if user_lang=='ar' else 'Products related to:'} {item_name}")
                        for p in products[:9]:
                            link = p.get("link") or p.get("product_link") or "#"
                            img_html = f"<img src='{p.get('image')}' class='product-img'>" if p.get('image') else ""
                            link_html = f"<a href='{link}' target='_blank' class='product-link'>{'رابط المنتج' if user_lang=='ar' else 'Product Link'}</a>"
                            st.markdown(f"""
                            <div class='product-card'>
                                {img_html}<br>
                                <b>{p.get('title')}</b><br>
                                السعر: {p.get('price')}<br>
                                المصدر: {p.get('source')}<br>
                                {link_html}
                            </div>
                            """, unsafe_allow_html=True)

            # ---------------- Save chat ----------------
            chat_entry = {
                "session_id": data.get("session_id") or str(uuid.uuid4()),
                "query": user_query,
                "products": flat_products,
                "ai_reply": ai_reply,
                "evaluation_score": eval_scores,
            }
            save_chat_unified(chat_entry)

        else:
            st.error(f"Server Error: {res.status_code} - {res.text}")

    except Exception as e:
        st.error(f"⚠️ Error fetching data: {e}")
