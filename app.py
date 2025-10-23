import os
import requests
import uuid
import json
from urllib.parse import urljoin
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ---------------- Load Environment ----------------
load_dotenv(r"C:\Users\SarahAlqahtani\Documents\SerpAPI_Research\serpapi_shopping\.env")

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
GROQ_KEY = os.getenv("GROQ_KEY")
GROQ_URL = os.getenv("GROQ_URL")
GROQ_MODEL = os.getenv("GROQ_MODEL")

ALL_CHATS_FILE = "data_shopping.json"

# ---------------- FastAPI Setup ----------------
app = FastAPI(title="Shopping Chat Assistant (LLM Accuracy Evaluation Mode)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Language Detection ----------------
def detect_language(text):
    arabic_chars = sum([1 for c in text if "\u0600" <= c <= "\u06FF"])
    return "ar" if arabic_chars > 0 else "en"

def get_system_prompt(role="assistant", user_lang="en"):
    if user_lang == "ar":
        return f"أنت مساعد ذكي باللغة العربية. مهمتك: {role}."
    else:
        return f"You are a smart assistant in English. Your role: {role}."

# ---------------- SerpAPI Function ----------------
def fetch_products_serpapi(query, limit=5):
    if not SERPAPI_KEY:
        raise RuntimeError("Missing SERPAPI_KEY")

    ignore_words = {"which","is","the","or","and","vs","vs."}
    keywords = " ".join([w for w in query.split() if w.lower() not in ignore_words]).lower()

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_shopping",
        "q": keywords,
        "hl": "ar",
        "gl": "sa",
        "api_key": SERPAPI_KEY,
        "tbm": "shop",
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise RuntimeError(f"SerpAPI error {response.status_code}: {response.text}")

    data = response.json()
    results = data.get("shopping_results", [])

    filtered = []
    for item in results:
        title = item.get("title", "").lower()
        if any(word in title for word in keywords.split()):
            filtered.append(item)
        if len(filtered) >= limit:
            break

    formatted = []
    for item in filtered:
        # تصحيح روابط الصور إذا كانت غير مكتملة
        image_url = item.get("thumbnail") or (item.get("images")[0] if item.get("images") else None)
        if image_url:
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            elif not image_url.startswith("http"):
                image_url = urljoin("https://", image_url)

        # تصحيح الرابط
        link = item.get("link") or item.get("product_link") or item.get("source") or ""
        if link and not link.startswith("http"):
            link = "https://" + link.lstrip("/")

        formatted.append({
            "title": item.get("title", "N/A"),
            "price": item.get("price") or item.get("extracted_price") or "N/A",
            "source": item.get("source", "N/A"),
            "link": link,
            "image": image_url,
        })
    return formatted

# ---------------- Call Groq API ----------------
def call_groq(messages):
    if not GROQ_KEY or not GROQ_URL or not GROQ_MODEL:
        raise RuntimeError("Missing GROQ environment variables")

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
    }

    response = requests.post(GROQ_URL, headers=headers, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"GROQ API error {response.status_code}: {response.text}")

    data = response.json()
    return data["choices"][0]["message"]["content"]

# ---------------- Evaluate Accuracy Using LLM ----------------
def evaluate_accuracy_llm(query, context, final_answer):
    if not context:
        return {"faithfulness": 10, "relevance": 10, "completeness": 10, "total": 10}

    user_lang = detect_language(query)
    system_prompt = get_system_prompt(role="accuracy evaluation", user_lang=user_lang)

    context_text = ""
    for idx, p in enumerate(context, 1):
        context_text += f"{idx}. {p.get('title')} | {p.get('price')} | {p.get('source')}\n"

    if user_lang == "ar":
        prompt = f"""
أنت مساعد تقييم ذكي للإجابات.
السؤال: {query}
البيانات المتاحة:
{context_text}

الإجابة التي قدمها AI:
{final_answer}

قيم **Faithfulness** و **Completeness** و **Relevance** من 10 إلى 100 لكل معيار. 
حتى لو لم يكن التطابق كامل، أعطي درجة جزئية تعكس دقة الإجابة العامة. 
أعطني النتيجة بصيغة JSON: {{"faithfulness":..., "completeness":..., "relevance":..., "total":...}}
"""
    else:
        prompt = f"""
You are a smart answer evaluation assistant.
Question: {query}
Available data:
{context_text}

AI Answer:
{final_answer}

Rate **Faithfulness**, **Completeness**, and **Relevance** from 10 to 100 each.
Even if not perfect, provide partial scores reflecting overall accuracy.
Return JSON: {{"faithfulness":..., "completeness":..., "relevance":..., "total":...}}
"""

    try:
        llm_resp = call_groq([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ])
        scores = json.loads(llm_resp)

        for k in ["faithfulness", "relevance", "completeness"]:
            val = scores.get(k, 10)
            scores[k] = max(10, min(val, 100))

        total = round(
            0.4 * scores["faithfulness"]
            + 0.3 * scores["relevance"]
            + 0.3 * scores["completeness"],
            2
        )
        scores["total"] = max(10, min(total, 100))
        return scores
    except Exception as e:
        print(f"Error evaluating with LLM: {e}")
        return {"faithfulness": 10, "relevance": 10, "completeness": 10, "total": 10}

# ---------------- Filter Products by Context Using LLM (Enhanced Prompt) ----------------
def filter_products_by_context_llm(query, products):
    if not products:
        return []

    user_lang = detect_language(query)
    system_prompt = get_system_prompt(role="product filtering", user_lang=user_lang)

    products_text = ""
    for idx, p in enumerate(products, 1):
        products_text += f"- {p.get('title')} | {p.get('price')} | {p.get('source')}\n"

    if user_lang == "ar":
        prompt = f"""
أنت مساعد ذكي لتصفية وتصنيف المنتجات وفق سياق سؤال المستخدم. 

تعليمات:
1- أعد فقط المنتجات المتعلقة بالسؤال بشكل مباشر.
2- صنفها حسب الصلة (الأكثر صلة أولاً).
3- أعد النتيجة بصيغة JSON مع المفاتيح: title, price, source, link, image.

السؤال الحالي: {query}
المنتجات المسترجعة:
{products_text}

أعد فقط المنتجات المتعلقة بالسؤال وفق النمط أعلاه.
"""
    else:
        prompt = f"""
You are a smart assistant for filtering and classifying products based on the user's query.

Instructions:
1- Return only products directly relevant to the question.
2- Sort by relevance (most relevant first).
3- Return JSON with keys: title, price, source, link, image.

Current question: {query}
Retrieved products:
{products_text}

Return only products relevant to the question.
"""

    try:
        llm_resp = call_groq([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ])
        filtered = json.loads(llm_resp)
        return filtered
    except Exception as e:
        print(f"Error filtering products with LLM: {e}")
        return products

# ---------------- Unified JSON Logging (Updated to avoid duplicates) ----------------
def save_session_unified(data):
    all_data = []
    # تحميل الملف إذا موجود
    if os.path.exists(ALL_CHATS_FILE):
        with open(ALL_CHATS_FILE, "r", encoding="utf-8") as f:
            all_data = json.load(f)

    # تحقق إذا السؤال موجود مسبقًا
    found = False
    for idx, entry in enumerate(all_data):
        if entry["query"] == data["query"]:
            # استبدال السؤال القديم بالبيانات الجديدة
            all_data[idx] = data
            found = True
            break

    if not found:
        # إضافة سؤال جديد
        data["id"] = len(all_data) + 1
        all_data.append(data)

    # حفظ الملف مرة واحدة
    with open(ALL_CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

# ---------------- Main Search Endpoint (Optimized) ----------------
@app.get("/search")
def search_with_session(query: str = Query(...), session_id: str = Query(default=None)):
    if not session_id:
        session_id = str(uuid.uuid4())

    items = [x.strip() for x in query.replace("compare", "").split("and") if x.strip()]
    if not items:
        items = [query]

    products_by_item = {}
    filtered_by_context = {}

    for item in items:
        try:
            raw_products = fetch_products_serpapi(item)
            filtered_products = filter_products_by_context_llm(query, raw_products)
            products_by_item[item] = filtered_products
            filtered_by_context[item] = filtered_products
        except Exception as e:
            products_by_item[item] = [{"error": str(e)}]
            filtered_by_context[item] = [{"error": str(e)}]

    context_text = ""
    for name, products in products_by_item.items():
        context_text += f"\n\n📦 نتائج {name}:\n"
        for p in products:
            context_text += f"- {p.get('title')} | {p.get('price')} | {p.get('source')}\n"

    user_lang = detect_language(query)
    system_prompt = get_system_prompt(role="shopping assistant", user_lang=user_lang)

    if user_lang == "ar":
        prompt = f"""
أنت مساعد تسوق خبير لمقارنة المنتجات وتقديم التوصيات.
سؤال المستخدم: {query}

البيانات المتاحة:
{context_text}
"""
    else:
        prompt = f"""
You are a shopping assistant expert for product comparison and recommendations.
User question: {query}

Available data:
{context_text}
"""

    ai_reply = call_groq([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ])

    flat_context = [p for plist in filtered_by_context.values() for p in plist]
    evaluation_scores = evaluate_accuracy_llm(query, flat_context, ai_reply)

    json_products = [
        {
            "title": p.get("title"),
            "price": p.get("price"),
            "source": p.get("source"),
            "link": p.get("link"),
            "image": p.get("image") if p.get("image") and p.get("image").startswith("http") else None
        }
        for p in flat_context
    ]

    session_data = {
        "session_id": session_id,
        "query": query,
        "products": json_products,
        "products_by_item": products_by_item,
        "ai_reply": ai_reply,
        "evaluation_score": evaluation_scores,
    }

    save_session_unified(session_data)
    return session_data
