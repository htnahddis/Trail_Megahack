from flask import Flask, request, jsonify, render_template
from extra import AndroidAIAgent  # Import the AndroidAIAgent class from extra.py
import speech_recognition as sr  # For speech-to-text conversion
import os

app = Flask(__name__)

# Initialize the AndroidAIAgent
agent = AndroidAIAgent()

# Initialize the speech recognizer
recognizer = sr.Recognizer()

# Variable to store the last command result
last_command_result = None

@app.route('/')
def index():
    """ Serve the index.html page """
    return render_template("index.html")

@app.route('/voice')
def voice():
    """ Serve the Voice.html page """
    return render_template("Voice.html")

@app.route('/response')
def response():
    """ Serve the response.html page """
    return render_template("response.html")

@app.route('/api/process_voice', methods=['POST'])
def process_voice():
    """
    Endpoint to process voice commands sent from the website.
    """
    global last_command_result
    try:
        # Check if the request contains text or an audio file
        if 'command' in request.json:
            # Text input
            command = request.json['command']
        elif 'file' in request.files:
            # Audio file input
            audio_file = request.files['file']

            # Save the audio file temporarily
            audio_path = "temp_audio.wav"
            audio_file.save(audio_path)

            # Transcribe the audio file to text
            with sr.AudioFile(audio_path) as source:
                audio = recognizer.record(source)  # Read the entire audio file
                try:
                    command = recognizer.recognize_google(audio)  # Use Google Speech Recognition
                    logger.info(f"Recognized command: {command}")
                except sr.UnknownValueError:
                    return jsonify({"error": "Could not understand the audio"}), 400
                except sr.RequestError as e:
                    return jsonify({"error": f"Speech recognition service error: {e}"}), 500

            # Delete the temporary audio file
            os.remove(audio_path)
        else:
            return jsonify({"error": "No command or audio file provided"}), 400

        # Send the command to AndroidAIAgent
        result = agent.execute_android_command(command)

        if result is None:
            last_command_result = {"error": "Failed to process command"}
            return jsonify({"error": "Failed to process command"}), 500
        
        # Store the result for the response page
        last_command_result = {"result": result}
        return jsonify({"result": result}), 200

    except Exception as e:
        last_command_result = {"error": str(e)}
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_response', methods=['GET'])
def get_response():
    """
    Endpoint to retrieve the last command result as an HTML page.
    """
    if last_command_result:
        return render_template('response.html', result=last_command_result["result"])
    else:
        return render_template('response.html', result="No command has been processed yet.")

@app.route('/api/status', methods=['GET', 'POST'])
def status():
    """
    Endpoint to check the status of the AndroidAIAgent.
    """
    try:
        # Check if the agent is running
        return jsonify({"status": "running"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)