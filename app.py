# In your main Python file (app.py)
from flask import Flask, request, jsonify
from agent import app as langgraph_app # Import your compiled graph

# Create a Flask app
app = Flask(__name__)

@app.route('/generate-idea', methods=['POST'])
def generate_idea():
    # 1. Get the topic from the frontend's request
    data = request.get_json()
    topic = data.get('topic')

    if not topic:
        return jsonify({"error": "No topic provided"}), 400

    # 2. Run your LangGraph workflow
    inputs = {"topic": topic, "messages": []}
    final_state = None
    for step in langgraph_app.stream(inputs):
        final_state = step

    # 3. Get the final report
    final_report = final_state["idea_generator"]["final_report"]

    # 4. Send the result back to the frontend
    return jsonify({"final_report": final_report})

if __name__ == '__main__':
    # Run the server
    app.run(port=5000, debug=True)