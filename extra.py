import os
import subprocess
import threading
import queue
import re
import sys
import time
import logging
import traceback
from datetime import datetime

# NLP and Voice Processing Libraries
import spacy
import speech_recognition as sr
import pyttsx3

# Import custom modules
from model import FirstLayerDMM
from RealTime import RealtimeSearchEngine
from SpeechToText import SpeechRecognition

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AndroidAIAgent:
    def __init__(self, adb_path=None):
        # NLP Setup
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
            self.nlp = spacy.load("en_core_web_sm")
        
        # Voice Recognition Setup
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Text-to-Speech Setup
        self.tts_engine = pyttsx3.init()
        
        # Command Queue for thread-safe processing
        self.command_queue = queue.Queue()
        
        # ADB Configuration
        self.adb_path = adb_path or self.find_adb_path()
        logger.info(f"Using ADB path: {self.adb_path}")

        # Predefined app packages for easier launching
        self.app_packages = {
            'messages': 'com.google.android.apps.messaging',
            'messaging': 'com.google.android.apps.messaging',
            'sms': 'com.google.android.apps.messaging',
            'contacts': 'com.google.android.contacts',
            'phone': 'com.google.android.dialer',
            'dialer': 'com.google.android.dialer',
            'call': 'com.google.android.dialer',
            'browser': 'com.android.chrome',
            'chrome': 'com.android.chrome',
            'web': 'com.android.chrome',
            'camera': 'com.android.camera2',
            'photo': 'com.android.camera2',
            'settings': 'com.android.settings',
            'setting': 'com.android.settings',
            'config': 'com.android.settings',
            'google pay': 'com.google.android.apps.nbu.paisa.user',
            'pay': 'com.google.android.apps.nbu.paisa.user',
            'gpay': 'com.google.android.apps.nbu.paisa.user',
            'payment': 'com.google.android.apps.nbu.paisa.user',
            'calendar': 'com.google.android.calendar',
            'schedule': 'com.google.android.calendar',
            'youtube': 'com.google.android.youtube',
            'video': 'com.google.android.youtube',
            'maps': 'com.google.android.apps.maps',
            'map': 'com.google.android.apps.maps',
            'google maps': 'com.google.android.apps.maps',
            'navigation': 'com.google.android.apps.maps',
            'gmail': 'com.google.android.gm',
            'mail': 'com.google.android.gm',
            'email': 'com.google.android.gm',
            'photos': 'com.google.android.apps.photos',
            'gallery': 'com.google.android.apps.photos',
            'play store': 'com.android.vending',
            'store': 'com.android.vending',
            'play': 'com.android.vending',
            'apps': 'com.android.vending',
            'facebook': 'com.facebook.katana',
            'instagram': 'com.instagram.android',
            'whatsapp': 'com.whatsapp',
            'twitter': 'com.twitter.android',
            'x': 'com.twitter.android',
            'spotify': 'com.spotify.music',
            'music': 'com.spotify.music',
            'netflix': 'com.netflix.mediaclient',
            'amazon': 'com.amazon.mShop.android.shopping',
            'calculator': 'com.google.android.calculator',
            'clock': 'com.google.android.deskclock',
            'alarm': 'com.google.android.deskclock',
            'files': 'com.google.android.apps.nbu.files',
            'file': 'com.google.android.apps.nbu.files',
            'notes': 'com.google.android.keep',
            'note': 'com.google.android.keep'
        }
        
        # Threading lock for text-to-speech
        self.speak_lock = threading.Lock()

    def find_adb_path(self):
        """Locate ADB executable"""
        # Check if ADB is in system PATH first
        try:
            # Windows
            if sys.platform == 'win32':
                result = subprocess.run(['where', 'adb'], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().split('\n')[0]
            # macOS/Linux
            else:
                result = subprocess.run(['which', 'adb'], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
        except Exception as e:
            logger.debug(f"ADB not found in PATH: {e}")
        
        # Environment variable check
        env_adb_path = os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME')
        if env_adb_path:
            platform_tools = os.path.join(env_adb_path, 'platform-tools')
            if sys.platform == 'win32':
                adb_path = os.path.join(platform_tools, 'adb.exe')
            else:
                adb_path = os.path.join(platform_tools, 'adb')
            
            if os.path.exists(adb_path):
                return adb_path
        
        # Comprehensive list of potential paths
        potential_paths = [
            "C:\adb\platform-tools\adb.exe"
            '/usr/local/android-sdk/platform-tools/adb',
            '/opt/android-sdk/platform-tools/adb',
            os.path.expanduser('~/Android/Sdk/platform-tools/adb'),
            os.path.expanduser('~/Library/Android/sdk/platform-tools/adb'),
            'C:/Android/platform-tools/adb.exe',
            'C:/Android/sdk/platform-tools/adb.exe',
            'C:/Program Files/Android/platform-tools/adb.exe',
            'C:/Program Files (x86)/Android/platform-tools/adb.exe',
            os.path.expanduser('~/AppData/Local/Android/Sdk/platform-tools/adb.exe'),
            'C:/Users/%USERNAME%/AppData/Local/Android/Sdk/platform-tools/adb.exe'
        ]
        
        for path in potential_paths:
            expanded_path = os.path.expandvars(path)
            if os.path.exists(expanded_path):
                return expanded_path
        
        raise RuntimeError("""
ADB executable not found. 
Please install Android SDK Platform Tools and ensure ADB is in your PATH,
or set the ANDROID_SDK_ROOT or ANDROID_HOME environment variable.
Alternatively, provide ADB path explicitly when creating the agent instance.
""")

    def verify_device_connection(self):
        """
        Verify that at least one Android device is connected
        
        Returns:
            bool: True if connected, False otherwise
        """
        try:
            result = subprocess.run(
                [self.adb_path, 'devices'], 
                capture_output=True, 
                text=True,
                check=True
            )
            
            # Parse the output to check for connected devices
            lines = result.stdout.strip().split('\n')
            # First line is the header, so we skip it
            device_lines = [line for line in lines[1:] if line.strip() and not line.endswith('offline')]
            
            if device_lines:
                logger.info(f"Connected devices: {len(device_lines)}")
                return True
            else:
                logger.warning("No Android devices connected")
                return False
                
        except Exception as e:
            logger.error(f"Error checking device connection: {e}")
            return False

    def listen_for_voice_command(self):
        """
        Continuous voice command listening thread.
        Captures voice input, categorizes it, and puts recognized commands into the queue.
        """
        while True:
            try:
                with self.microphone as source:
                    logger.info("Listening for command...")
                    self.recognizer.adjust_for_ambient_noise(source)
                    audio = self.recognizer.listen(source)
                
                try:
                    # Recognize speech using Google Speech Recognition
                    command = self.recognizer.recognize_google(audio).lower()
                    logger.info(f"Recognized command: {command}")

                    # Categorize the command using FirstLayerDMM
                    try:
                        categorized_commands = FirstLayerDMM(command)
                        logger.info(f"Categorized commands: {categorized_commands}")
                        
                        # Extract the first category (default behavior)
                        category = categorized_commands[0]
                        category_type = category.split()[0]
                        query = " ".join(category.split()[1:])

                        # Handle real-time queries immediately
                        if category_type == 'realtime':
                            answer = RealtimeSearchEngine(query)
                            self.speak(answer)
                            continue  # Skip adding to the queue for real-time queries

                        # Handle special commands (exit, quit, stop)
                        if command == 'exit' or command == 'quit' or command == 'stop':
                            self.speak("Shutting down.")
                            os._exit(0)  # Forcefully exit the program

                        # Add the categorized command to the queue
                        self.command_queue.put({
                            'raw_command': command,
                            'category_type': category_type,
                            'query': query
                        })
                        logger.info(f"Added command to queue: {command}. Queue size: approximately {self.command_queue.qsize()}")

                    except Exception as e:
                        logger.error(f"Command categorization error: {e}")
                        # Fallback to adding the raw command to the queue
                        self.command_queue.put({
                            'raw_command': command,
                            'category_type': 'general',
                            'query': command
                        })
                        logger.info(f"Added raw command to queue: {command}. Queue size: approximately {self.command_queue.qsize()}")

                except sr.UnknownValueError:
                    self.speak("Sorry, I didn't catch that. Could you repeat?")
                except sr.RequestError as e:
                    logger.error(f"Could not request results from Google Speech Recognition service; {e}")
            
            except Exception as e:
                logger.error(f"Error in voice recognition: {e}")
                time.sleep(1)  # Prevent tight loop if errors occur repeatedly

    def speak(self, text):
        """
        Speak the given text while preventing multiple threads from interfering.
        """
        def _speak():
            with self.speak_lock:  # Lock to prevent multiple runAndWait() calls
                logger.info(f"Speaking: {text}")
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()

        threading.Thread(target=_speak, daemon=True).start()

    def process_command(self, command):
        """
        Process and interpret the voice command using the FirstLayerDMM model.
        
        :param command: Voice command string
        :return: Structured command interpretation
        """
        try:
            # Use FirstLayerDMM to categorize the command
            categorized_commands = FirstLayerDMM(command)
            logger.info(f"Categorized commands: {categorized_commands}")
            
            # Extract the first category (default behavior)
            category = categorized_commands[0]
            
            # Split the category into type and query
            category_type = category.split()[0]
            query = " ".join(category.split()[1:])
            
            return {
                'raw_command': command,
                'category_type': category_type,
                'query': query
            }
        except Exception as e:
            logger.error(f"Command categorization error: {e}")
            return {
                'raw_command': command,
                'category_type': 'general',
                'query': command
            }

    def execute_android_command(self, command):
        """
        Execute Android-specific commands based on the categorized command.
        
        :param command: Voice command to execute
        :return: Command execution result
        """
        try:
            # Verify device connection
            if not self.verify_device_connection():
                self.speak("No Android device connected. Please connect a device and try again.")
                return None
                
            processed_cmd = self.process_command(command)
            logger.info(f"Processed command: {processed_cmd}")

            if not processed_cmd:
                self.speak("Sorry, I couldn't understand.")
                return None

            category_type = processed_cmd.get('category_type')
            query = processed_cmd.get('query')

            # Handle different categories
            if category_type == 'general':
                # Use the RealtimeSearchEngine to handle general queries
                answer = RealtimeSearchEngine(query)
                self.speak(answer)
                return answer

            elif category_type == 'realtime':
                # Use the RealtimeSearchEngine to handle real-time queries
                answer = RealtimeSearchEngine(query)
                self.speak(answer)
                return answer

            elif category_type == 'open':
                # Extract the app name from the query and open it
                app_name = query
                if app_name in self.app_packages:
                    return self.open_app(self.app_packages[app_name], app_name)
                else:
                    self.speak(f"Sorry, I couldn't find the app {app_name}.")
                    return None

            elif category_type == 'close':
                # Extract the app name from the query and close it
                app_name = query
                self.speak(f"Closing {app_name} is not supported yet.")
                return None

            elif category_type == 'play':
                # Extract the song name from the query and play it
                song_name = query
                self.speak(f"Playing {song_name} is not supported yet.")
                return None

            elif category_type == 'system':
                # Handle system-related tasks (e.g., volume, brightness)
                if 'volume up' in query:
                    return self.adjust_volume('up')
                elif 'volume down' in query:
                    return self.adjust_volume('down')
                elif 'home' in query or 'go home' in query:
                    return self.navigate_home()
                elif 'back' in query or 'go back' in query:
                    return self.navigate_back()
                elif 'screenshot' in query or 'take a screen' in query or 'capture screen' in query:
                    return self.take_screenshot()
                else:
                    self.speak(f"System command {query} is not supported yet.")
                    return None

            elif category_type == 'content':
                # Handle content generation requests
                self.speak(f"Content generation for {query} is not supported yet.")
                return None

            elif category_type == 'google search':
                # Perform a Google search
                answer = RealtimeSearchEngine(query)
                self.speak(answer)
                return answer

            elif category_type == 'youtube search':
                # Perform a YouTube search
                answer = RealtimeSearchEngine(query)
                self.speak(answer)
                return answer

            elif category_type == 'exit':
                # Handle exit command
                self.speak("Shutting down.")
                os._exit(0)

            else:
                # Fallback for unrecognized categories
                self.speak("I'm not sure how to handle that command.")
                return None

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            self.speak("An error occurred while processing the command.")
            return None

    def take_screenshot(self):
        """
        Take a screenshot on the connected Android device.
        
        :return: Path to the saved screenshot or None if failed
        """
        try:
            # Create screenshots directory if it doesn't exist
            screenshots_dir = os.path.join(os.getcwd(), 'screenshots')
            os.makedirs(screenshots_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(screenshots_dir, f'screenshot_{timestamp}.png')

            # Execute screenshot command
            cmd = [self.adb_path, 'shell', 'screencap', '-p', '/sdcard/screenshot.png']
            logger.info(f"Executing command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)

            # Pull screenshot to local machine
            pull_cmd = [self.adb_path, 'pull', '/sdcard/screenshot.png', screenshot_path]
            logger.info(f"Executing command: {' '.join(pull_cmd)}")
            result = subprocess.run(pull_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.speak(f"Screenshot taken and saved")
                logger.info(f"Screenshot saved successfully: {screenshot_path}")
                return screenshot_path
            else:
                self.speak("Failed to take screenshot")
                logger.error(f"Error saving screenshot: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            self.speak("An error occurred while taking the screenshot.")
            return None

    def initiate_google_pay_transaction(self, recipient, amount):
        """
        Initiate a Google Pay transaction using ADB commands.
        
        :param recipient: Recipient's phone number or UPI ID
        :param amount: Amount to send
        :return: Command execution result
        """
        try:
            # Open Google Pay
            self.open_app(self.app_packages['google pay'], 'Google Pay')
            logger.info("Opened Google Pay")

            # Wait for the app to load
            time.sleep(5)

            # Navigate to "Send Money" section - try multiple potential coordinates
            logger.info("Navigating to Send Money section")
            # Different devices might have the UI elements in different positions
            # Try a few common positions
            potential_send_money_positions = [(500, 1000), (500, 800), (300, 1200)]
            for x, y in potential_send_money_positions:
                self.adb_tap(x, y)
                time.sleep(1)
            
            # Wait for the recipient field to appear
            time.sleep(2)

            # Enter recipient
            logger.info(f"Entering recipient: {recipient}")
            self.adb_input_text(recipient)
            time.sleep(2)

            # Tap on what would likely be the first suggestion
            potential_contact_positions = [(500, 300), (300, 400), (400, 350)]
            for x, y in potential_contact_positions:
                self.adb_tap(x, y)
                time.sleep(1)

            # Enter amount
            logger.info(f"Entering amount: {amount}")
            # Clean the amount string from any currency symbols
            clean_amount = re.sub(r'[^\d.]', '', amount.split()[0])
            self.adb_input_text(clean_amount)
            time.sleep(2)

            # Try various positions for "Pay" or "Send" button
            pay_button_positions = [(500, 1500), (500, 1300), (300, 1400)]
            for x, y in pay_button_positions:
                self.adb_tap(x, y)
                time.sleep(1)

            # Try various positions for confirmation buttons
            confirm_positions = [(500, 1200), (500, 1000), (300, 1100)]
            for x, y in confirm_positions:
                self.adb_tap(x, y)
                time.sleep(1)

            self.speak(f"I've attempted to send {amount} to {recipient}. Please check if the transaction was successful.")
            return True

        except Exception as e:
            logger.error(f"Error initiating Google Pay transaction: {e}")
            self.speak("Failed to initiate the transaction. Please try again manually.")
            return False

    def schedule_google_calendar_event(self, event_name, event_date):
        """
        Schedule an event in Google Calendar using ADB commands.
        
        :param event_name: Name of the event
        :param event_date: Date of the event
        :return: Command execution result
        """
        try:
            # Open Google Calendar
            self.open_app(self.app_packages['calendar'], 'Google Calendar')
            logger.info("Opened Google Calendar")

            # Wait for the app to load
            time.sleep(5)

            # Try various positions for "Create" or "+" button
            create_positions = [(500, 1600), (500, 1500), (300, 1600), (900, 1600)]
            logger.info("Attempting to create new event")
            for x, y in create_positions:
                self.adb_tap(x, y)
                time.sleep(1)

            # Try to find and tap the "Event" option (if there's a menu)
            event_positions = [(500, 700), (500, 800), (500, 600)]
            for x, y in event_positions:
                self.adb_tap(x, y)
                time.sleep(1)

            # Enter event name
            logger.info(f"Entering event name: {event_name}")
            self.adb_input_text(event_name)
            time.sleep(2)

            # Try to find and tap date field
            date_field_positions = [(500, 900), (500, 1000), (500, 800)]
            for x, y in date_field_positions:
                self.adb_tap(x, y)
                time.sleep(1)

            # Clear existing text and enter event date
            self.adb_key_event(67)  # Delete key to clear
            self.adb_key_event(67)  # Multiple times to ensure clearing
            logger.info(f"Entering event date: {event_date}")
            self.adb_input_text(event_date)
            time.sleep(2)

            # Try to find and tap save button
            save_positions = [(900, 100), (800, 200), (700, 100)]
            for x, y in save_positions:
                self.adb_tap(x, y)
                time.sleep(1)

            self.speak(f"I've attempted to schedule '{event_name}' on {event_date}. Please check your calendar.")
            return True

        except Exception as e:
            logger.error(f"Error scheduling Google Calendar event: {e}")
            self.speak("Failed to schedule the event. Please try again manually.")
            return False

    def adb_tap(self, x, y):
        """
        Simulate a tap at (x, y) coordinates using ADB.
        
        :param x: X coordinate
        :param y: Y coordinate
        """
        try:
            cmd = [self.adb_path, 'shell', 'input', 'tap', str(x), str(y)]
            logger.info(f"Executing command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            logger.error(f"Tap error at ({x}, {y}): {e}")
            return False

    def adb_key_event(self, key_code):
        """
        Send a key event using ADB.
        
        :param key_code: Android key code
        """
        try:
            cmd = [self.adb_path, 'shell', 'input', 'keyevent', str(key_code)]
            logger.info(f"Executing command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            logger.error(f"Key event error ({key_code}): {e}")
            return False

    def adb_input_text(self, text):
        """
        Simulate text input using ADB.
        
        :param text: Text to input
        """
        try:
            # Escape special characters for different platforms
            if sys.platform == 'win32':
                # Windows needs different escaping
                escaped_text = text.replace(' ', '%s')
            else:
                escaped_text = re.sub(r'(["\'\s])', r'\\\1', text)
                
            cmd = [self.adb_path, 'shell', 'input', 'text', escaped_text]
            logger.info(f"Executing command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            logger.error(f"Text input error: {e}")
            # Try alternate method for text input (character by character)
            try:
                logger.info("Trying character-by-character input as fallback")
                for char in text:
                    if char == ' ':
                        char_cmd = [self.adb_path, 'shell', 'input', 'text', '%s']
                    else:
                        char_cmd = [self.adb_path, 'shell', 'input', 'text', char]
                    subprocess.run(char_cmd, check=True)
                    time.sleep(0.1)  # Small delay between characters
                return True
            except Exception as inner_e:
                logger.error(f"Character-by-character input failed: {inner_e}")
                return False

    def open_app(self, app_package, app_name=None):
        """
        Open a specific Android app.
        
        :param app_package: Package name of the app
        :param app_name: Friendly name of the app (for TTS)
        :return: Command execution result
        """
        try:
            display_name = app_name or app_package
            
            # Check if app is installed
            check_cmd = [self.adb_path, 'shell', 'pm', 'list', 'packages', app_package]
            logger.info(f"Checking if app is installed: {' '.join(check_cmd)}")
            check_result = subprocess.run(check_cmd, capture_output=True, text=True)
            
            app_installed = False
            # Check if package is in the output
            if app_package in check_result.stdout:
                app_installed = True
            else:
                # Try a more flexible search (partial package match)
                packages_list = subprocess.run(
                    [self.adb_path, 'shell', 'pm', 'list', 'packages'], 
                    capture_output=True, 
                    text=True
                )
                
                # Extract package names from output
                packages = [line.replace("package:", "").strip() for line in packages_list.stdout.splitlines()]
                
                # Find closest matching package
                matching_packages = [pkg for pkg in packages if app_package in pkg]
                if matching_packages:
                    app_package = matching_packages[0]
                    app_installed = True
                    logger.info(f"Found similar package: {app_package}")
            
            if not app_installed:
                self.speak(f"The app {display_name} doesn't seem to be installed on the device.")
                logger.warning(f"App not installed: {app_package}")
                return None
            
            # Try multiple methods to open the app
            success = False
            
            # Method 1: Using monkey
            try:
                monkey_cmd = [self.adb_path, 'shell', 'monkey', '-p', app_package, '-c', 'android.intent.category.LAUNCHER', '1']
                logger.info(f"Trying to open app with monkey: {' '.join(monkey_cmd)}")
                result = subprocess.run(monkey_cmd, capture_output=True, text=True)
                
                if "No activities found to run" not in result.stdout and "No activities found" not in result.stderr:
                    success = True
                else:
                    logger.info("Monkey launch failed, trying alternate methods")
            except Exception as e:
                logger.error(f"Monkey launch error: {e}")
            
            # Method 2: Using am start with main activity
            if not success:
                try:
                    # Try default MainActivity first
                    main_activity_cmd = [self.adb_path, 'shell', 'am', 'start', '-n', f"{app_package}/.MainActivity"]
                    logger.info(f"Trying to open app with main activity: {' '.join(main_activity_cmd)}")
                    result = subprocess.run(main_activity_cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0 and "Error" not in result.stdout:
                        success = True
                    else:
                        logger.info("Main activity launch failed, trying more generic approach")
                except Exception as e:
                    logger.error(f"Main activity launch error: {e}")
            
            # Method 3: Using am start without specific activity
            if not success:
                try:
                    start_cmd = [self.adb_path, 'shell', 'am', 'start', '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.LAUNCHER', '-n', f"{app_package}/"]
                    logger.info(f"Trying generic app launch: {' '.join(start_cmd)}")
                    result = subprocess.run(start_cmd, capture_output=True, text=True)
                    
                    if "Error" not in result.stdout:
                        success = True
                except Exception as e:
                    logger.error(f"Generic launch error: {e}")

            # Method 4: Using dumpsys to find the main activity
            if not success:
                try:
                    # Get package info to find main activity
                    dumpsys_cmd = [self.adb_path, 'shell', 'dumpsys', 'package', app_package]
                    logger.info(f"Getting package info: {' '.join(dumpsys_cmd)}")
                    dumpsys_result = subprocess.run(dumpsys_cmd, capture_output=True, text=True)
                    
                    # Extract main activity
                    activity_pattern = re.compile(fr'{app_package}/[\w\.]+Activity')
                    activities = activity_pattern.findall(dumpsys_result.stdout)
                    
                    if activities:
                        main_activity = activities[0]
                        launch_cmd = [self.adb_path, 'shell', 'am', 'start', '-n', main_activity]
                        logger.info(f"Launching found activity: {' '.join(launch_cmd)}")
                        subprocess.run(launch_cmd)
                        success = True
                except Exception as e:
                    logger.error(f"Activity search error: {e}")
            
            if success:
                self.speak(f"Opening {display_name}")
                return True
            else:
                self.speak(f"I had trouble opening {display_name}. The app might be installed but not accessible.")
                return False
                
        except Exception as e:
            logger.error(f"App launch error: {e}")
            self.speak(f"Failed to open {display_name}")
            return False

    def navigate_home(self):
        """
        Navigate to the home screen.
        
        :return: Command execution result
        """
        try:
            cmd = [self.adb_path, 'shell', 'input', 'keyevent', '3']  # KEYCODE_HOME
            logger.info(f"Navigating to home: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            self.speak("Going to home screen")
            return True
        except Exception as e:
            logger.error(f"Home navigation error: {e}")
            self.speak("Failed to go to home screen")
            return False

    def navigate_back(self):
        """
        Navigate back.
        
        :return: Command execution result
        """
        try:
            cmd = [self.adb_path, 'shell', 'input', 'keyevent', '4']  # KEYCODE_BACK
            logger.info(f"Navigating back: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            self.speak("Going back")
            return True
        except Exception as e:
            logger.error(f"Back navigation error: {e}")
            self.speak("Failed to go back")
            return False

    def adjust_volume(self, direction):
        """
        Adjust device volume.
        
        :param direction: 'up' or 'down'
        :return: Command execution result
        """
        try:
            if direction.lower() == 'up':
                key_code = '24'  # KEYCODE_VOLUME_UP
                message = "Increasing volume"
            else:
                key_code = '25'  # KEYCODE_VOLUME_DOWN
                message = "Decreasing volume"
                
            cmd = [self.adb_path, 'shell', 'input', 'keyevent', key_code]
            logger.info(f"Adjusting volume {direction}: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            self.speak(message)
            return True
        except Exception as e:
            logger.error(f"Volume adjustment error: {e}")
            self.speak(f"Failed to adjust volume {direction}")
            return False

    def start_listening_thread(self):
        """
        Start a background thread for continuous voice command listening.
        """
        try:
            # Start voice recognition in a separate thread
            self.voice_thread = threading.Thread(target=self.listen_for_voice_command, daemon=True)
            self.voice_thread.start()
            logger.info("Voice recognition thread started")
            
            # Start command processing thread
            self.processing_thread = threading.Thread(target=self.command_processing_loop, daemon=True)
            self.processing_thread.start()
            logger.info("Command processing thread started")
            
            return True
        except Exception as e:
            logger.error(f"Failed to start listening thread: {e}")
            return False

    def command_processing_loop(self):
        """
        Process commands from the queue in a separate thread.
        """
        while True:
            try:
                # Add logging to show the loop is running
                logger.info(f"Command processing loop running. Queue size: approximately {self.command_queue.qsize()}")
            
                # Get command from queue with a timeout to allow for clean shutdown
                try:
                    command = self.command_queue.get(timeout=1)
                    logger.info(f"Dequeued command for processing: {command}")
                except queue.Empty:
                    continue
            
                # Process and execute command
                logger.info(f"Processing command from queue: {command}")
                result = self.execute_android_command(command)
            
                # Log the result for debugging
                logger.info(f"Command execution result: {result}")
            
                # Mark as done
                self.command_queue.task_done()
                logger.info("Command processing completed. Ready for next command.")
            
            except Exception as e:
                logger.error(f"Error in command processing loop: {e}")
                logger.error(f"Exception details: {str(e)}")
                logger.error(f"Exception traceback: {traceback.format_exc()}")
                time.sleep(1)  # Prevent tight loop if errors occur repeatedly

    def run(self):
        """
        Start the Android AI Agent.
        """
        try:
            # Verify device connection
            if not self.verify_device_connection():
                print("No Android device connected. Please connect a device and try again.")
                return False
                
            # Start listening thread
            if not self.start_listening_thread():
                print("Failed to start listening thread. Exiting.")
                return False
                
            self.speak("Android AI Agent is now active and listening for commands.")
            
            # Keep the main thread alive
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down Android AI Agent...")
                self.speak("Shutting down. Goodbye!")
                return True
                
        except Exception as e:
            logger.error(f"Error running Android AI Agent: {e}")
            return False

if __name__ == "__main__":
    try:
        # Create and run the agent
        agent = AndroidAIAgent()
        agent.run()
    except Exception as e:
        print(f"Error initializing Android AI Agent: {e}")
        sys.exit(1)