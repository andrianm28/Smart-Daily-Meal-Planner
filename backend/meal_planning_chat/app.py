import json
import boto3
from flask import Flask, request, Response, stream_with_context

app = Flask(__name__)

BEDROCK_CLIENT = boto3.client("bedrock-runtime", region_name="ap-southeast-1")
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0-20260217-v1:0"

SYSTEM_PROMPT = (
    "You are a friendly and knowledgeable personal meal planning assistant. "
    "You help users with recipe ideas, meal substitutions, nutritional advice, "
    "grocery lists, cooking tips, and anything related to food and nutrition. "
    "Be concise, practical, and encouraging. When generating grocery lists or "
    "meal swaps, be specific and actionable."
)

OPENING_MESSAGE = (
    "Hello! I'm your personal meal planning assistant 🍽️ I can help you with "
    "recipe ideas, substitutions, nutritional advice, grocery lists, and more. "
    "What would you like help with today?"
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}


def make_cors_response(status=200, body=""):
    resp = Response(body, status=status)
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp


@app.route("/", methods=["OPTIONS"])
def options():
    return make_cors_response(200, "")


@app.route("/opening", methods=["GET"])
def opening():
    """Returns the chatbot opening message."""
    resp = Response(
        json.dumps({"message": OPENING_MESSAGE}),
        content_type="application/json",
    )
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp


@app.route("/", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}

    # history: list of {role, content} dicts from prior turns
    history = data.get("history", [])
    message = data.get("message", "")
    # Optional context about current meal plan
    meal_plan_context = data.get("meal_plan_context", "")

    # Build messages: inject meal plan context as a system-level note if present
    messages = []

    # Replay conversation history
    for turn in history:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": [{"text": content}]})

    # Append the new user message, optionally prefixed with meal plan context
    user_text = message
    if meal_plan_context and not history:
        # First message — include current plan so the bot has context
        user_text = (
            f"[Current meal plan context]\n{meal_plan_context}\n\n"
            f"[User question]\n{message}"
        )

    # Handle optional file upload
    file_data = data.get("file_data")
    file_mime = data.get("file_mime")
    user_content = []

    if file_data and file_mime:
        if file_mime.startswith("image/"):
            img_format = file_mime.split("/")[-1]
            if img_format == "jpg":
                img_format = "jpeg"
            user_content.append({
                "image": {
                    "format": img_format,
                    "source": {"bytes": file_data, "mediaType": file_mime},
                }
            })
        else:
            doc_format = file_mime.split("/")[-1]
            user_content.append({
                "document": {
                    "format": doc_format,
                    "name": "uploaded_document",
                    "source": {"bytes": file_data, "mediaType": file_mime},
                }
            })

    user_content.append({"text": user_text})
    messages.append({"role": "user", "content": user_content})

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }

    def generate():
        try:
            response = BEDROCK_CLIENT.invoke_model_with_response_stream(
                modelId=MODEL_ID,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )
            stream = response.get("body")
            if stream:
                for event in stream:
                    chunk = event.get("chunk")
                    if chunk:
                        chunk_data = json.loads(chunk["bytes"].decode("utf-8"))
                        if chunk_data.get("type") == "content_block_delta":
                            delta = chunk_data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
        except Exception as e:
            yield f"\n\n[Error: {str(e)}]"

    resp = Response(
        stream_with_context(generate()),
        content_type="text/plain; charset=utf-8",
    )
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
