from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import SentenceTransformerEmbeddings
from langchain.vectorstores import Chroma

# Load PDF document
pdf_path = "C:/Users/somia.kumari/Downloads/Untitled document.pdf"
loader = PyPDFLoader(pdf_path)
documents = loader.load()

# Split text into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
texts = text_splitter.split_documents(documents)

# Generate embeddings using Sentence Transformer
embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

# Store embeddings in ChromaDB
persist_directory = "chroma_db"
chroma_db = Chroma.from_documents(
    documents=texts,
    embedding=embeddings,
    persist_directory=persist_directory
)

# Persist the database
chroma_db.persist()

print("Vector embeddings stored successfully in ChromaDB.")
