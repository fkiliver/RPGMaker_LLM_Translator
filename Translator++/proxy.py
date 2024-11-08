from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

SOURCE_URL = "/v1/chat/completions"
TARGET_URL = "http://127.0.0.1:8848/v1/chat/completions"  # 转发的目标URL

@app.route(SOURCE_URL, methods=['POST'])
def capture_and_forward():
    # 捕获传入请求的数据
    incoming_data = request.get_json()
    if not incoming_data:
        return jsonify({"error": "No JSON data provided"}), 400

    # 输出收到的请求内容
    print("Received Request Data:")
    print(incoming_data)

    # 添加repeat_penalty参数
    incoming_data['repeat_penalty'] = 1
    incoming_data['do_sample'] = True

    incoming_data['num_beams'] = 1
    incoming_data['seed'] = -1

    if 'presence_penalty' in incoming_data:
        del incoming_data['presence_penalty']

    # 输出修改后的请求内容
    print("Modified Request Data:")
    print(incoming_data)

    # 转发请求到目标URL
    try:
        response = requests.post(TARGET_URL, json=incoming_data)
        response.raise_for_status()

        # 输出目标URL的响应
        print("Response from Target URL:")
        print(response.json())
    except requests.exceptions.RequestException as e:
        print("Error during request forwarding:", str(e))
        return jsonify({"error": str(e)}), 500

    # 返回目标URL的响应
    return jsonify(response.json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8849)
