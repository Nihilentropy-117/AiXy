import json
import os
import re
import psycopg2
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from tqdm import tqdm
import keys
from sentence_transformers import SentenceTransformer, util

# Constants
MIN_PARAGRAPH_LENGTH = 100  # Minimum length of paragraph to consider
BATCH_SIZE = 250  # Size of each batch for database insertion

# Initialize the sentence transformer model
model = SentenceTransformer('llmrails/ember-v1')

# Define a class to represent a document
class Document:
    def __init__(self, text, author, source, part, json_data, embedding=None):
        self.text = text
        self.author = author
        self.source = source
        self.part = part
        self.json_data = json_data
        self.embedding = embedding

# Function to create embeddings from text
def create_embeddings(text):
    embeddings = model.encode(text, convert_to_tensor=True)
    embedding_list = embeddings.flatten().tolist()
    return embedding_list

# Function to open a database connection
def open_db():
    return psycopg2.connect(keys.postgres_connection_params)

# Function to normalize spaces in text
def normalize_spaces(text):
    return re.sub(r'\s+', ' ', text)

# Function to count the number of paragraphs in an EPUB book
def count_paragraphs(book):
    count = 0
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.content, 'html.parser')
            for p in soup.find_all('p'):
                if len(normalize_spaces(p.get_text().strip())) > MIN_PARAGRAPH_LENGTH:
                    count += 1
    return count

# Function to create vector lists from paragraphs in an EPUB file
def vector_lists_from_paragraphs_from_epub(epub_path):
    book = epub.read_epub(epub_path)
    total_paragraphs = count_paragraphs(book)
    paragraphs = []

    # Extracting global metadata
    author = book.get_metadata('DC', 'creator')
    title = book.get_metadata('DC', 'title')
    author = author[0][0] if author else "Unknown Author"
    title = title[0][0] if title else "Unknown Title"

    with tqdm(total=total_paragraphs, desc=f"Processing '{title}' by '{author}") as pbar:
        paragraph_counter = 1
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.content, 'html.parser')
                for p in soup.find_all('p'):
                    text = normalize_spaces(p.get_text().strip())
                    if len(text) > MIN_PARAGRAPH_LENGTH:
                        percent_through = (paragraph_counter / total_paragraphs) * 100
                        location = round(percent_through / 100, 2)  # Removed comma
                        embedding = create_embeddings(text)
                        pg = Document(text=text, author=author, source=title, part=location, json_data={}, embedding=embedding)
                        paragraphs.append(pg)
                        pbar.update(1)
                        paragraph_counter += 1

    return paragraphs

# Function to insert document data into a database
def put(documents):
    data_to_insert = [(doc.text, doc.author, doc.source, doc.part, json.dumps(doc.json_data), doc.embedding) for doc in documents]

    db = open_db()
    with db as conn:
        with conn.cursor() as cur:
            with tqdm(total=len(data_to_insert), desc="Inserting Data into Vector Storage") as pbar:
                for data_chunk in chunked(data_to_insert, BATCH_SIZE):
                    cur.executemany("""
                        INSERT INTO books (text, author, source, part, json_data, vector_embedding)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """, data_chunk)
                    conn.commit()
                    pbar.update(len(data_chunk))

# Helper function to yield chunks of data
def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

# Main function to embed and upload books
def embed_and_upload_books():
    # Create necessary directories if they don't exist
    os.makedirs('books', exist_ok=True)
    os.makedirs('finished_books', exist_ok=True)
    os.makedirs('error_books', exist_ok=True)

    failures = ""
    for book in os.listdir('books'):
        file_path = f'books/{book}'
        print(f"Starting '{book}'.")
        try:
            paragraphs = vector_lists_from_paragraphs_from_epub(file_path)
            if len(paragraphs) > 50:
                put(paragraphs)
                print(f"{len(paragraphs)} uploaded. {file_path}")
                os.rename(file_path, f'finished_books/{book}')
            else:
                fail = f"{file_path} too short\n"
                failures += fail
                print(fail)
                os.rename(file_path, f'error_books/{book}')

        except Exception as e:
            fail = f"Failure on '{file_path}': {e}\n"
            failures += fail
            print(fail)
            os.rename(file_path, f'error_books/{book}')

    print(failures)

# Execute the main function if the script is run directly
if __name__ == "__main__":
    embed_and_upload_books()
