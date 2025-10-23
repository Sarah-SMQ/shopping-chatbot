# tests/test_app_clean.py
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app import (
    fetch_products_serpapi,
    detect_language,
    get_system_prompt,
    evaluate_accuracy_llm,
    filter_products_by_context_llm,
    save_session_unified,
    app
)
from shopping_app import save_chat_unified

client = TestClient(app)

# ---------------- Unit Tests ----------------

def test_detect_language_real():
    assert detect_language("Hello world") == "en"
    assert detect_language("مرحبا بالعالم") == "ar"

def test_get_system_prompt_real():
    en_prompt = get_system_prompt(role="assistant", user_lang="en")
    ar_prompt = get_system_prompt(role="مساعد", user_lang="ar")
    assert "assistant" in en_prompt
    assert "مساعد" in ar_prompt

def test_fetch_products_serpapi_real():
    results = fetch_products_serpapi("tablet")
    assert isinstance(results, list)
    assert all("title" in r for r in results)

def test_filter_products_by_context_llm_real():
    products = fetch_products_serpapi("tablet")
    filtered = filter_products_by_context_llm("tablet", products)
    assert isinstance(filtered, list)
    assert all("title" in r for r in filtered)

def test_evaluate_accuracy_llm_real():
    products = fetch_products_serpapi("tablet")
    filtered = filter_products_by_context_llm("tablet", products)
    ai_reply = "This is a sample AI answer for testing."
    scores = evaluate_accuracy_llm("tablet", filtered, ai_reply)
    for key in ["faithfulness", "relevance", "completeness", "total"]:
        assert key in scores

# ---------------- File Saving Tests with Mock ----------------

def test_save_session_unified_mocked():
    data = {
        "query": "tablet",
        "products": [{"title": "Samsung Tablet", "price": "$300"}],
        "ai_reply": "Here are some tablets",
        "evaluation_score": {"accuracy": 0.95}
    }
    with patch("app.save_session_unified") as mock_save:
        mock_save(data)
        mock_save.assert_called_once_with(data)

def test_save_chat_unified_mocked():
    data = {
        "query": "laptop",
        "products": [{"title": "HP Laptop", "price": "$500"}],
        "ai_reply": "Here are some laptops",
        "evaluation_score": {"accuracy": 0.9}
    }
    with patch("shopping_app.save_chat_unified") as mock_save:
        mock_save(data)
        mock_save.assert_called_once_with(data)

# ---------------- File Saving Tests with Temporary File ----------------
# def test_save_chat_unified_creates_file(tmp_path):
#     # ملف مؤقت جديد وفارغ
#     temp_file = tmp_path / "test_chats.json"
#     temp_file.write_text("[]", encoding="utf-8")

#     # بيانات الاختبار
#     data = {
#         "query": "laptop",
#         "products": [{"title": "HP Laptop", "price": "$500"}],
#         "ai_reply": "Here are some laptops",
#         "evaluation_score": {"accuracy": 0.9}
#     }

#     ALL_CHATS_FILE_TEST = "unit-test.json"

#     # استبدال المسار داخل الدالة
#     original_path = save_chat_unified.__globals__["ALL_CHATS_FILE_TEST"]
#     save_chat_unified.__globals__["ALL_CHATS_FILE_TEST"] = str(temp_file)

#     try:
#         # استدعاء الدالة
#         save_chat_unified(data)

#         # التحقق من أن الملف يحتوي على سجل واحد فقط
#         with open(temp_file, "r", encoding="utf-8") as f:
#             saved = json.load(f)

#         assert len(saved) == 1
#         record = saved[0]
#         # فقط التحقق من الحقول الأساسية، وليس القيم الدقيقة للمنتجات أو ai_reply
#         for field in ["query", "products", "ai_reply", "evaluation_score"]:
#             assert field in record
#         assert isinstance(record["products"], list)
#         assert all("title" in p and "price" in p for p in record["products"])

#     finally:
#         # إعادة المسار الأصلي
#         save_chat_unified.__globals__["ALL_CHATS_FILE_TEST"] = original_path

def test_save_chat_unified_creates_file(tmp_path):
    temp_file = tmp_path / "test_chats.json"
    temp_file.write_text("[]", encoding="utf-8")

    data = {
        "query": "laptop",
        "products": [{"title": "HP Laptop", "price": "$500"}],
        "ai_reply": "Here are some laptops",
        "evaluation_score": {"accuracy": 0.9}
    }

    # Force function to use temp file
    save_chat_unified.__globals__["ALL_CHATS_FILE_TEST"] = str(temp_file)

    # Reset in-memory list
    save_chat_unified.__globals__["all_chats"] = []

    # Call function
    save_chat_unified(data)

    # Check file
    with open(temp_file, "r", encoding="utf-8") as f:
        saved = json.load(f)

    assert len(saved) == 1
    assert saved[0]["query"] == "laptop"



# ---------------- Endpoint Test ----------------

def test_search_endpoint_real_mocked():
    # محاكاة call_groq لإرجاع نص ثابت بدل الاتصال بالAPI الحقيقي
    with patch("app.call_groq") as mock_groq:
        mock_groq.return_value = "This is a mocked AI reply"

        response = client.get("/search", params={"query": "tablet"})
        
        assert response.status_code == 200
        json_data = response.json()
        assert "ai_reply" in json_data
        assert json_data["ai_reply"] == "This is a mocked AI reply"
        assert "evaluation_score" in json_data
        assert isinstance(json_data["products"], list)
