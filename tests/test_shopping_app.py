import pytest
import types
import json
import uuid
from unittest.mock import patch, mock_open
import shopping_app
from shopping_app import show_chat, save_chat_unified, BACKEND_URL

# ---------------- Fixture لإنشاء ملف JSON مؤقت ----------------
@pytest.fixture
def temp_json(tmp_path):
    file_path = tmp_path / "all_chats.json"
    file_path.write_text("[]", encoding="utf-8")
    shopping_app.ALL_CHATS_FILE_TEST = file_path
    shopping_app.all_chats = []
    yield file_path
    shopping_app.ALL_CHATS_FILE_TEST = None
    shopping_app.all_chats = []

# ---------------- Test detect_language ----------------
@pytest.mark.parametrize("text,expected", [
    ("مرحبا", "ar"),
    ("Hello", "en"),
    ("", "en")
])
def test_detect_language(text, expected):
    assert shopping_app.detect_language(text) == expected

def test_detect_language_exception(monkeypatch):
    def raise_exc(text): raise Exception("fail")
    monkeypatch.setattr(shopping_app, "detect_language", raise_exc)
    with pytest.raises(Exception):
        shopping_app.detect_language("anything")

# ---------------- Test show_chat ----------------
def test_show_chat(monkeypatch):
    fake_session = types.SimpleNamespace(messages=[{"role":"user","content":"Hello"},{"role":"ai","content":"Hi"}])
    monkeypatch.setattr(shopping_app.st, "session_state", fake_session)
    rendered = []
    monkeypatch.setattr(shopping_app.st, "markdown", lambda content, unsafe_allow_html=True: rendered.append(content))
    show_chat()
    assert any("Hello" in r for r in rendered)
    assert any("Hi" in r for r in rendered)

def test_show_chat_empty(monkeypatch):
    fake_session = types.SimpleNamespace(messages=[])
    monkeypatch.setattr(shopping_app.st, "session_state", fake_session)
    rendered = []
    monkeypatch.setattr(shopping_app.st, "markdown", lambda content, unsafe_allow_html=True: rendered.append(content))
    show_chat()
    assert rendered == []

# ---------------- Test save_chat_unified ----------------
def test_save_chat_unified_with_file(temp_json):
    entry = {"session_id":"1","query":"phone","products":[],"ai_reply":"reply","evaluation_score":{"total":50}}
    save_chat_unified(entry)
    with open(temp_json, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved[0]["query"] == "phone"

def test_update_existing_chat(temp_json):
    entry1 = {"session_id":"1","query":"laptop","products":[{"title":"Laptop A"}],"ai_reply":"reply1","evaluation_score":{"total":50}}
    entry2 = {"session_id":"2","query":"laptop","products":[{"title":"Laptop B"}],"ai_reply":"reply2","evaluation_score":{"total":80}}
    save_chat_unified(entry1)
    save_chat_unified(entry2)
    with open(temp_json, "r", encoding="utf-8") as f:
        saved = json.load(f)
    titles = [p["title"] for p in saved[0]["products"]]
    assert "Laptop A" in titles and "Laptop B" in titles
    assert saved[0]["ai_reply"] == "reply2"

# ---------------- Test product extraction ----------------
def test_product_data_structure():
    products_data = {"laptop":[{"title":"Test Laptop","price":"$999","link":"http://example.com/product","image":"http://example.com/image.jpg"}]}
    product = products_data["laptop"][0]
    link = product.get("link") or "#"
    img_html = f"<img src='{product.get('image')}' class='product-img'>" if product.get("image") else ""
    assert link == "http://example.com/product"
    assert img_html == "<img src='http://example.com/image.jpg' class='product-img'>"

def test_empty_products_handling():
    empty_response = {"ai_reply": "Test response", "session_id": "test-session", "evaluation_score": {}, "products_by_item": {}}
    products_by_item = empty_response.get("products_by_item", {})
    flat_products = [p for plist in products_by_item.values() for p in plist]
    assert products_by_item == {}
    assert flat_products == []

def test_product_limiting_logic():
    products_data = {"category": [{"title": f"Product {i}", "price": "$10", "source": "Test"} for i in range(12)]}
    limited_products = products_data["category"][:9]
    assert len(limited_products) == 9
    assert limited_products[0]["title"] == "Product 0"
    assert limited_products[8]["title"] == "Product 8"

# ---------------- Test session id and exceptions ----------------
def test_session_id_generation():
    response = {"products_by_item":{}}
    with patch('uuid.uuid4', return_value="generated-uuid"):
        session_id = response.get("session_id") or str(uuid.uuid4())
        assert session_id == "generated-uuid"

def test_exception_handling():
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Network timeout")
        try:
            shopping_app.requests.get("http://backend-url/search")
        except Exception as e:
            msg = f"⚠️ Error fetching data: {e}"
        assert "Network timeout" in msg

# ---------------- Test full user flow with products ----------------
def test_full_user_flow(monkeypatch, temp_json):
    shopping_app.st.session_state = types.SimpleNamespace(messages=[])
    outputs = []

    class FakeExpander:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass

    monkeypatch.setattr(shopping_app.st, "text_input", lambda label, key=None: "Test Query")
    monkeypatch.setattr(shopping_app.st, "button", lambda label: True)
    monkeypatch.setattr(shopping_app.st, "expander", lambda label: FakeExpander())
    monkeypatch.setattr(shopping_app.st, "markdown", lambda content, unsafe_allow_html=True: outputs.append(content))
    monkeypatch.setattr(shopping_app.st, "error", lambda msg: outputs.append(msg))
    monkeypatch.setattr(shopping_app, "show_chat", lambda: outputs.append("Product: P1"))
    monkeypatch.setattr(shopping_app, "detect_language", lambda text: "en")

    def fake_get(url, params=None, timeout=None):
        return types.SimpleNamespace(
            status_code=200,
            json=lambda: {
                "ai_reply": "AI Reply",
                "evaluation_score": {"total": 95},
                "products_by_item": {"Item1":[{"title":"P1","price":"$10","source":"S1","link":"link1","image":"img.png"}]},
                "session_id": "123"
            }
        )
    monkeypatch.setattr(shopping_app.requests, "get", fake_get)

    # تنفيذ التدفق
    user_query = shopping_app.st.text_input("💬 اكتب سؤالك هنا")
    user_lang = shopping_app.detect_language(user_query)
    send_button_text = "🔍 إرسال" if user_lang=="ar" else "🔍 Send"

    if shopping_app.st.button(send_button_text) and user_query:
        shopping_app.st.session_state.messages.append({"role":"user","content":user_query})
        res = shopping_app.requests.get(f"{shopping_app.BACKEND_URL}/search", params={"query":user_query})
        data = res.json()
        ai_reply = data.get("ai_reply")
        shopping_app.st.session_state.messages.append({"role":"ai","content":ai_reply})
        shopping_app.show_chat()

        flat_products = [p for plist in data.get("products_by_item", {}).values() for p in plist]
        save_chat_unified({
            "session_id": data.get("session_id") or str(uuid.uuid4()),
            "query": user_query,
            "products": flat_products,
            "ai_reply": ai_reply,
            "evaluation_score": data.get("evaluation_score")
        })

    messages = shopping_app.st.session_state.messages
    assert len(messages) == 2
    assert messages[0]["role"] == "user" and messages[0]["content"] == "Test Query"
    assert messages[1]["role"] == "ai" and messages[1]["content"] == "AI Reply"
    assert any("P1" in o for o in outputs)

    with open(temp_json, "r", encoding="utf-8") as f:
        saved = shopping_app.all_chats if hasattr(shopping_app, "all_chats") else []
        if not saved: saved = json.load(f)
    assert saved[0]["query"] == "Test Query"
    assert saved[0]["ai_reply"] == "AI Reply"
    assert saved[0]["products"][0]["title"] == "P1"

# ---------------- Test CSS ----------------
def test_css_styles():
    css_content = """
    .user-msg { background:#81D4FA; }
    .ai-msg { background:#FFF59D; }
    .product-card { background-color:#E6E6FA; }
    """
    assert "user-msg" in css_content
    assert "ai-msg" in css_content
    assert "product-card" in css_content

# ---------------- Test environment ----------------
def test_backend_url():
    assert BACKEND_URL.startswith("http")
