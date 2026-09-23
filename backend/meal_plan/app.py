import json
import boto3
from flask import Flask, request, Response, stream_with_context

app = Flask(__name__)

BEDROCK_CLIENT = boto3.client("bedrock-runtime", region_name="ap-southeast-5")
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

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


@app.route("/", methods=["POST"])
def generate_meal_plan():
    data = request.get_json(force=True, silent=True) or {}

    dietary_preference = data.get("dietary_preference", "None")
    num_days = data.get("num_days", 1)

    prompt = (
        f"You are a friendly and knowledgeable nutritionist. Generate a simple, "
        f"easy-to-follow meal plan based on the following preferences:\n\n"
        f"Dietary Preference: {dietary_preference}\n"
        f"Number of Days: {num_days}\n\n"
        f"For each day, provide breakfast, lunch, dinner, and one snack. "
        f"Keep meals practical, delicious, and aligned with the dietary preference. "
        f"Format each day clearly with the day number as a header, followed by the "
        f"four meals. Keep descriptions concise but appetizing."
    )

    # Build the messages list
    content = []

    # Handle optional file upload (document/image)
    file_data = data.get("file_data")
    file_mime = data.get("file_mime")
    if file_data and file_mime:
        if file_mime.startswith("image/"):
            img_format = file_mime.split("/")[-1]
            if img_format == "jpg":
                img_format = "jpeg"
            content.append({
                "image": {
                    "format": img_format,
                    "source": {"bytes": file_data, "mediaType": file_mime},
                }
            })
        else:
            doc_format = file_mime.split("/")[-1]
            content.append({
                "document": {
                    "format": doc_format,
                    "name": "uploaded_document",
                    "source": {"bytes": file_data, "mediaType": file_mime},
                }
            })

    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
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
