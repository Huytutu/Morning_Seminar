import json
import time
import os
import google.generativeai as genai
from tqdm import tqdm
import datetime

# Initialize the Gemini client
genai.configure(api_key="AIzaSyA6rFZ6GXLOV521BziBkqKCHqwagWnYlJc")

log_path = "./log/"
log_file = ""

# Add rate limiting functionality
class RateLimiter:
    def __init__(self, max_requests_per_minute):
        self.max_requests = max_requests_per_minute
        self.request_timestamps = []
        
    def wait_if_needed(self):
        """Wait if necessary to comply with rate limit"""
        current_time = time.time()
        
        # Remove timestamps older than 1 minute
        one_minute_ago = current_time - 60
        self.request_timestamps = [ts for ts in self.request_timestamps if ts > one_minute_ago]
        
        # If at rate limit, wait until we can make another request
        if len(self.request_timestamps) >= self.max_requests:
            # Calculate time to wait - based on when the oldest request will "expire"
            wait_time = self.request_timestamps[0] - one_minute_ago + 0.1
            print(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
            time.sleep(wait_time)
            # After waiting, remove expired timestamps again
            current_time = time.time()
            one_minute_ago = current_time - 60
            self.request_timestamps = [ts for ts in self.request_timestamps if ts > one_minute_ago]
        
        # Record this request
        self.request_timestamps.append(current_time)
        
        # For stricter rate limiting, add a small fixed delay between requests
        if self.max_requests < 10:  # For lower rate limits, add a small delay between all requests
            time.sleep(60/self.max_requests * 0.8)  # 80% of theoretical time between requests
        
    def log_request_info(self):
        """Log information about current request count"""
        current_count = len(self.request_timestamps)
        remaining = self.max_requests - current_count
        print(f"Requests in last minute: {current_count}/{self.max_requests} (Remaining: {remaining})")

def retry_until_expected(chat_session, expect):
    # Note: Gemini doesn't have the same polling mechanism as OpenAI
    # This is a simplified version that mimics similar functionality
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Check the status of the last response
            # In Gemini, we would need to implement our own status checking
            # For this example, we'll assume success after waiting
            time.sleep(10)
            return True
        except Exception as e:
            print(f"Error occurred, retrying in 60s... Error: {e}")
            time.sleep(60)
            retry_count += 1
    
    raise Exception("Maximum retries reached")

def get_last_text_message(chat_session):
    # In Gemini, we'll need to track the last response
    # This is a simplified implementation
    if hasattr(chat_session, 'last_response'):
        return chat_session.last_response
    return "No messages available"

def log_to_file(type, message):
    if type == "input":
        message = (
            ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
            + "\n"
        ) + message
    elif type == "output":
        message = (
            "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
            + "\n"
        ) + message
    os.makedirs(log_path, exist_ok=True)
    with open(log_path + log_file, "a", encoding="utf-8") as file:
        file.write(message + "\n")

def compare(index1_path, index2_path, rate_limiter):
    # Create a model instance that can use code interpreter
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash"
        #,
        # generation_config={
        #     "temperature": 0.2,
        #     "top_p": 0.95,
        #     "top_k": 40,
       # }
    )
    
    # Gemini doesn't have a direct equivalent to OpenAI's Assistant API
    # We'll use a chat session to maintain context
    chat_session = model.start_chat(history=[])
    
    # Read the instruction file
    with open("./data/prompt/0-instruction.md", "r", encoding="utf-8") as file:
        instruction = file.read()
    
    # Initialize the chat with instructions
    rate_limiter.wait_if_needed()
    print(f"[{datetime.datetime.now()}] Sending system instruction...")
    response = chat_session.send_message(f"System: {instruction}")
    chat_session.last_response = response.text
    rate_limiter.log_request_info()
    
    # First message
    with open("./data/prompt/1-preamble.md", "r", encoding="utf-8") as file:
        content = file.read()
    log_to_file("input", content)
    
    rate_limiter.wait_if_needed()
    print(f"[{datetime.datetime.now()}] Sending preamble message...")
    response = chat_session.send_message(content)
    chat_session.last_response = response.text
    log_to_file("output", get_last_text_message(chat_session))
    rate_limiter.log_request_info()
     
    # Second message - 奻痐50
    with open("./data/prompt/2-奻痐50.md", "r", encoding="utf-8") as file:
        content = file.read()
    log_to_file("input", content)
    log_to_file("input", "./data/奻痐50.xlsx")
    
    # For file handling, we need to describe the file content
    # since Gemini doesn't have the same file handling capabilities
    content += "\n\nI'm providing an Excel file '奻痐50.xlsx' with market data for analysis."
    
    rate_limiter.wait_if_needed()
    print(f"[{datetime.datetime.now()}] Sending 奻痐50 data message...")
    response = chat_session.send_message(content)
    chat_session.last_response = response.text
    log_to_file("output", get_last_text_message(chat_session))
    rate_limiter.log_request_info()
    
    # Third message - index 1
    with open("./data/prompt/3-index1.md", "r", encoding="utf-8") as file:
        content = file.read()
    log_to_file("input", content)
    log_to_file("input", index1_path)
    
    # Describe the file since we can't directly attach it
    file_name = os.path.basename(index1_path)
    content += f"\n\nI'm providing an Excel file '{file_name}' with index data for analysis."
    
    rate_limiter.wait_if_needed()
    print(f"[{datetime.datetime.now()}] Sending index 1 data message...")
    response = chat_session.send_message(content)
    chat_session.last_response = response.text
    log_to_file("output", get_last_text_message(chat_session))
    rate_limiter.log_request_info()
    
    # Fourth message - index 2
    with open("./data/prompt/4-index2.md", "r", encoding="utf-8") as file:
        content = file.read()
    log_to_file("input", content)
    log_to_file("input", index2_path)
    
    # Describe the file since we can't directly attach it
    file_name = os.path.basename(index2_path)
    content += f"\n\nI'm providing an Excel file '{file_name}' with index data for analysis."
    
    rate_limiter.wait_if_needed()
    print(f"[{datetime.datetime.now()}] Sending index 2 data message...")
    response = chat_session.send_message(content)
    chat_session.last_response = response.text
    log_to_file("output", get_last_text_message(chat_session))
    rate_limiter.log_request_info()
    
    # Ask the model to make a decision
    decision_prompt = "Based on the analysis of both indices, please select the better alpha index. Respond with only '1' or '2'."
    
    rate_limiter.wait_if_needed()
    print(f"[{datetime.datetime.now()}] Requesting final decision...")
    response = chat_session.send_message(decision_prompt)
    decision = response.text.strip()
    rate_limiter.log_request_info()
    
    # Extract the index from the response
    if "1" in decision:
        index = "1"
    elif "2" in decision:
        index = "2"
    else:
        # Default to 1 if unclear
        index = "1"
        
    log_to_file("output", f"The selected better alpha's index is: {index}")
    return index

# list files in ./data/alpha-result/
import os

files = os.listdir("./data/alpha-result/")
files = [f for f in files if f.endswith(".xlsx")]

# Initialize rate limiter with 7 rpm limit instead of 15
rate_limiter = RateLimiter(max_requests_per_minute=7)

best_file = files[0]
best_file_index = 1
round = 1

print(f"Starting comparison of {len(files)-1} files against the current best")
for i, file in enumerate(tqdm(files[1:])):
    index = i + 2
    log_file = f"round-{round}-{best_file_index}-{index}.log"
    print(f"\n[{datetime.datetime.now()}] Round {round}: Comparing current best ({best_file_index}: {best_file}) vs challenger ({index}: {file})")
    
    best_index = compare(
        f"./data/alpha-result/{best_file}", 
        f"./data/alpha-result/{file}",
        rate_limiter
    )
    
    if best_index == "2":
        print(f"[{datetime.datetime.now()}] New best found! File {file} (index {index}) is better than previous best.")
        best_file = file
        best_file_index = index
    else:
        print(f"[{datetime.datetime.now()}] Current best remains: {best_file} (index {best_file_index})")
    
    round += 1

print(f"\n=== FINAL RESULT ===")
print(f"The best alpha is: {best_file} (index {best_file_index})")