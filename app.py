import os
import uuid
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import fitz  
import google.generativeai as genai
from dotenv import load_dotenv
UPLOAD_FOLDER = "uploads"
ALLOWED_EXT = {"pdf"}
MAX_PDF_CHARS = 12000       
MAX_HISTORY_MESSAGES = 8    
MODEL_NAME = "gemini-2.0-flash"  


genai.configure(api_key=os.getenv("GENAI_API_KEY"))


SESSIONS = {}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def extract_text_from_pdf(path):
    text_chunks = []
    with fitz.open(path) as pdf:
        for page in pdf:
            text = page.get_text()
            if text:
                text_chunks.append(text)
    full_text = "\n".join(text_chunks)
    if len(full_text) > MAX_PDF_CHARS:
        head = full_text[: MAX_PDF_CHARS // 2]
        tail = full_text[-(MAX_PDF_CHARS // 2) :]
        full_text = head + "\n\n[...middle truncated...]\n\n" + tail
    return full_text

def make_prompt(pdf_text, history, question):
    """
    Construct the system prompt that instructs the model to only use PDF content
    and the recent conversation.
    """
    system = ("""
    You are an AI assistant that analyzes documents.
Rules:
- No generic intros like 'This PDF is...'
- Go straight to the point.
- Use bullet points with short, crisp sentences.
- If the content is boring or obvious, say it bluntly.
- Keep it human, not corporate.
"""
    )
    
    trimmed_history = history[-MAX_HISTORY_MESSAGES:]
    convo = ""
    for m in trimmed_history:
        role = "User" if m["role"] == "user" else "Assistant"
        convo += f"{role}: {m['content']}\n"
    prompt = (
        f"{system}\n\nPDF CONTENT:\n{pdf_text}\n\nRECENT CONVERSATION:\n{convo}\nUser: {question}\nAssistant:"
    )
    return prompt


def ask_gemini(pdf_context, history, question):
    prompt = f"""
You are a PDF-specific Q&A bot.
Rules:
- Answer ONLY using the PDF content.
- Be concise (1-2 sentences).
- Avoid generic advice.
- Always provide concrete, relevant details from the PDF.
- Keep answers crisp, no filler.

PDF CONTEXT:
{pdf_context}

CHAT HISTORY:
{history}

USER QUESTION:
{question}
"""
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text.strip()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():
    """
    Accepts file upload, extracts text, creates a session and returns session_id.
    """
    if "pdf" not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400

    file = request.files["pdf"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid.uuid4().hex}_{filename}")
        file.save(save_path)

        pdf_text = extract_text_from_pdf(save_path)
        session_id = uuid.uuid4().hex
        SESSIONS[session_id] = {"pdf_text": pdf_text, "history": []}

        return jsonify({"success": True, "message": "PDF uploaded and processed", "session_id": session_id})

    return jsonify({"success": False, "message": "Invalid file"}), 400


@app.route("/chat", methods=["POST"])
def chat():
    """
    Expects JSON: { session_id: str, message: str }
    Returns assistant reply and updated history length.
    """
    data = request.get_json() or {}
    session_id = data.get("session_id")
    message = data.get("message", "").strip()

    if not session_id or session_id not in SESSIONS:
        return jsonify({"success": False, "error": "Invalid or missing session_id. Upload a PDF first."}), 400
    if not message:
        return jsonify({"success": False, "error": "Empty message"}), 400

    session = SESSIONS[session_id]
    pdf_text = session["pdf_text"]
    history = session["history"]

    history.append({"role": "user", "content": message})

    chat_history = ""
    for m in history[-MAX_HISTORY_MESSAGES:]:
        role = "User" if m["role"] == "user" else "Assistant"
        chat_history += f"{role}: {m['content']}\n"

    try:
        assistant_text = ask_gemini(pdf_text, chat_history, message)

        history.append({"role": "assistant", "content": assistant_text})

        if len(history) > MAX_HISTORY_MESSAGES * 2:
            SESSIONS[session_id]["history"] = history[-(MAX_HISTORY_MESSAGES * 2) :]

        return jsonify({"success": True, "answer": assistant_text, "history_len": len(session["history"])})
    except Exception as e:
        return jsonify({"success": False, "error": f"Model error: {str(e)}"}), 500


@app.route("/reset_session", methods=["POST"])
def reset_session():
    data = request.get_json() or {}
    session_id = data.get("session_id")
    if not session_id or session_id not in SESSIONS:
        return jsonify({"success": False, "message": "Invalid session"}), 400
    del SESSIONS[session_id]
    return jsonify({"success": True, "message": "Session reset"})

if __name__ == "__main__":
    app.run(debug=True)
