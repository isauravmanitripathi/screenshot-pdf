import os
import json
import openai
import logging
import time
import nltk
from typing import List
from nltk.tokenize import sent_tokenize
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("API key not found. Please set OPENAI_API_KEY in your .env file.")

openai.api_key = API_KEY

LOG_DIR = "./gpt-logs"
PROCESSED_JSON_DIR = "./processed-json"
CHUNK_SIZE = 4000
OVERLAP_SIZE = 200

# Create directories if they don't exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(PROCESSED_JSON_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "processing.log"), mode='a')
    ]
)

def preprocess_text(text: str) -> str:
    """Preprocess text to handle newlines and spacing properly."""
    text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
    text = text.replace('\n', ' <NEWLINE> ')
    text = ' '.join(text.split())
    return text

def postprocess_text(text: str) -> str:
    """Restore newlines and fix spacing in processed text."""
    text = text.replace(' <NEWLINE> ', '\n')
    text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
    return text

def split_into_sentences(text: str) -> List[str]:
    """Simple sentence splitter as backup if NLTK fails."""
    text = text.replace('!', '.').replace('?', '.')
    sentences = []
    for sentence in text.split('.'):
        sentence = sentence.strip()
        if sentence:
            sentences.append(sentence + '.')
    return sentences

def get_sentences(text: str) -> List[str]:
    """Split text into sentences while preserving newlines."""
    try:
        preprocessed_text = preprocess_text(text)
        paragraphs = preprocessed_text.split('<NEWLINE>')
        
        sentences = []
        for paragraph in paragraphs:
            if paragraph.strip():
                try:
                    # Try NLTK first
                    paragraph_sentences = sent_tokenize(paragraph.strip())
                except Exception as e:
                    # Fall back to simple splitting if NLTK fails
                    logging.warning(f"NLTK sentence tokenization failed, using fallback: {e}")
                    paragraph_sentences = split_into_sentences(paragraph.strip())
                
                for sentence in paragraph_sentences:
                    sentences.append(sentence.strip())
                sentences.append('<NEWLINE>')
        
        if sentences and sentences[-1] == '<NEWLINE>':
            sentences.pop()
        
        return sentences
    except Exception as e:
        logging.error(f"Error in sentence splitting: {e}")
        return [text]

def split_text_into_chunks(text: str) -> List[str]:
    """Split text into chunks while preserving complete sentences and newlines."""
    try:
        sentences = get_sentences(text)
        chunks = []
        current_chunk = []
        current_size = 0
        overlap_sentences = []
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            if sentence == '<NEWLINE>':
                if current_chunk:
                    current_chunk.append(sentence)
                    current_size += 1
                continue
                
            if current_size + sentence_size > CHUNK_SIZE and current_chunk:
                chunk_text = ' '.join(current_chunk)
                if overlap_sentences:
                    chunk_text = ' '.join([chunk_text] + overlap_sentences)
                chunks.append(postprocess_text(chunk_text))
                
                current_chunk = overlap_sentences + [sentence]
                current_size = sum(len(s) for s in current_chunk)
                
                overlap_sentences = []
                overlap_size = 0
                for s in reversed(current_chunk):
                    if s == '<NEWLINE>':
                        continue
                    if overlap_size + len(s) > OVERLAP_SIZE:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_size += len(s)
            else:
                current_chunk.append(sentence)
                current_size += sentence_size
        
        if current_chunk:
            chunks.append(postprocess_text(' '.join(current_chunk)))
        
        for i, chunk in enumerate(chunks):
            logging.info(f"Chunk {i+1} size: {len(chunk)} characters")
        
        return chunks
    except Exception as e:
        logging.error(f"Error in chunk splitting: {e}")
        return [text]

def process_chunk(client, chunk: str, chapter_name: str, section_name: str, chunk_num: int, total_chunks: int) -> str:
    """Process a single chunk of text through the GPT API."""
    prompt = f"You are an expert writer. Below is an excerpt from my book titled '{book_name}', specifically from Chapter '{chapter_name}', Section '{section_name}'. The original text is: '{chunk}'. Your task is to understand the content and the underlying message of the original text, write an entire story while keeping in mind that the original meaning remain intact. Expand the content by adding relevant and additional information to make the text more comprehensive, and enhance its readability and engagement without altering its fundamental purpose."

    max_retries = 5
    retry_attempts = 0

    while retry_attempts < max_retries:
        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": chunk}
                ],
                max_tokens=12000
            )
            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            retry_attempts += 1
            sleep_time = min(3 * retry_attempts, 60)
            logging.warning(f"Error processing chunk {chunk_num}: {e}. Retrying in {sleep_time}s...")
            time.sleep(sleep_time)
    
    logging.error(f"Failed to process chunk {chunk_num} after {max_retries} attempts")
    return None

def load_log(json_path: str) -> dict:
    """Load or create processing log."""
    log_file = os.path.join(LOG_DIR, f"{os.path.basename(json_path)}_log.json")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logging.info(f"Loading log for {json_path}")
            return json.load(f)
    logging.info(f"No log found for {json_path}. Starting fresh.")
    return {"processed_sections": []}

def save_log(json_path: str, log_data: dict):
    """Save processing log."""
    log_file = os.path.join(LOG_DIR, f"{os.path.basename(json_path)}_log.json")
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=4)
    logging.info(f"Log saved for {json_path}")

def save_processed_json(data: dict, original_json_path: str):
    """Save processed JSON data."""
    processed_json_path = os.path.join(PROCESSED_JSON_DIR, os.path.basename(original_json_path))
    with open(processed_json_path, 'w') as f:
        json.dump(data, f, indent=4)
    logging.info(f"Processed JSON saved to {processed_json_path}")

def process_section(client, chapter: dict, section: dict, log_data: dict, data: dict, original_json_path: str):
    """Process a single section of text."""
    section_identifier = f"{chapter['chapter_name']} - {section['section_name']}"
    
    if section_identifier in log_data["processed_sections"]:
        logging.info(f"Skipping already processed section: {section_identifier}")
        return

    if "extracted-text" in section:
        logging.info(f"Processing section '{section_identifier}'")
        try:
            chunks = split_text_into_chunks(section['extracted-text'])
            processed_chunks = []
            
            for i, chunk in enumerate(chunks, 1):
                processed_chunk = process_chunk(
                    client,
                    chunk,
                    chapter['chapter_name'],
                    section['section_name'],
                    i,
                    len(chunks)
                )
                
                if processed_chunk:
                    processed_chunks.append(processed_chunk)
                else:
                    logging.error(f"Failed to process chunk {i} for section: {section_identifier}")
                    return
            
            if processed_chunks:
                section["gpt-text-processed"] = "\n\n".join(processed_chunks)
                log_data["processed_sections"].append(section_identifier)
                save_processed_json(data, original_json_path)
                logging.info(f"Successfully processed section: {section_identifier}")
            else:
                logging.warning(f"No processed chunks for section: {section_identifier}")
        except Exception as e:
            logging.error(f"Error processing section {section_identifier}: {e}")

def process_json_file(json_path: str):
    """Main function to process the JSON file."""
    logging.info(f"Loading JSON file from {json_path}")
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        log_data = load_log(json_path)
        client = openai
        
        for chapter in data.get("chapters", []):
            logging.info(f"Processing chapter: {chapter['chapter_name']}")
            for section in chapter.get("sections", []):
                process_section(client, chapter, section, log_data, data, json_path)
        
        save_log(json_path, log_data)
        logging.info("Processing complete.")
    except Exception as e:
        logging.error(f"Error processing file: {e}")

if __name__ == "__main__":
    try:
        book_name = input("Enter the name of the book: ")
        json_path = input("Enter the path to your JSON file: ")
        
        if not os.path.exists(json_path):
            logging.error(f"File not found: {json_path}")
        else:
            process_json_file(json_path)
    except KeyboardInterrupt:
        logging.info("Processing interrupted by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
