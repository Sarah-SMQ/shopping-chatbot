import os
import json
import time
import uuid
from app import call_groq, ALL_CHATS_FILE  # استدعاء الدوال والملف الرئيسي

# ---------------- Load existing chats ----------------
if os.path.exists(ALL_CHATS_FILE):
    with open(ALL_CHATS_FILE, "r", encoding="utf-8") as f:
        all_chats = json.load(f)
else:
    print(f"File {ALL_CHATS_FILE} not found!")
    all_chats = []

# ---------------- Modified evaluation function ----------------
def evaluate_accuracy_llm(query, context, final_answer, max_retries=5, retry_delay=5):
    """
    تقييم إجابة AI باستخدام GROQ مع التعامل مع Rate Limit.
    """
    if not context:
        return {"faithfulness": 10, "relevance": 10, "completeness": 10, "total": 10}

    context_text = ""
    for idx, p in enumerate(context, 1):
        context_text += f"{idx}. {p.get('title')} | {p.get('price')} | {p.get('source')}\n"

    prompt = f"""
أنت مساعد تقييم ذكي للإجابات.
السؤال: {query}
البيانات المتاحة:
{context_text}

الإجابة التي قدمها AI:
{final_answer}

قيم **Faithfulness** و **Completeness** و **Relevance** من 10 إلى 100 لكل معيار.
أعطني النتيجة بصيغة JSON: {{"faithfulness":..., "completeness":..., "relevance":..., "total":...}}
"""

    for attempt in range(max_retries):
        try:
            llm_resp = call_groq([
                {"role": "system", "content": "أنت مساعد تقييم دقيق للإجابات."},
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
            if "rate_limit" in str(e).lower():
                print(f"Rate limit reached. Waiting {retry_delay} seconds before retry ({attempt+1}/{max_retries})...")
                time.sleep(retry_delay)
                continue
            else:
                print(f"Error evaluating with LLM: {e}")
                return {"faithfulness": 10, "relevance": 10, "completeness": 10, "total": 10}

    print("Max retries reached. Returning default scores.")
    return {"faithfulness": 10, "relevance": 10, "completeness": 10, "total": 10}


# ---------------- Re-evaluate all chats ----------------
for chat in all_chats:
    query = chat.get("query")
    ai_reply = chat.get("ai_reply")
    products = chat.get("products", [])

    new_scores = evaluate_accuracy_llm(query, products, ai_reply)
    chat["evaluation_score"] = new_scores
    print(f"✅ Re-evaluated: {query} → Total Score: {new_scores['total']}")

# ---------------- Save back to JSON ----------------
with open(ALL_CHATS_FILE, "w", encoding="utf-8") as f:
    json.dump(all_chats, f, ensure_ascii=False, indent=2)

print(f"\nتم تحديث جميع الدرجات في {ALL_CHATS_FILE} بنجاح!")
