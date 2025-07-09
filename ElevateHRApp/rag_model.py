import os
import sys
import glob
import getpass
import warnings
from typing import List, Union
from dotenv import load_dotenv
from langchain_community.document_loaders import (
    PyPDFLoader, CSVLoader
)
from langchain_core.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
warnings.filterwarnings("ignore")

# sys.path.insert(1, './src')
# print(sys.path.insert(1, '../src/'))

load_dotenv()

GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GEMINI_API_KEY:
  GEMINI_API_KEY = getpass.getpass("Enter you Google Gemini API key: ")



def load_model():
  """
  Func loads the model and embeddings
  """
  model = ChatGoogleGenerativeAI(
      model="models/gemini-2.0-flash",
      google_api_key=GEMINI_API_KEY,
      temperature=0.4,
      convert_system_message_to_human=True
  )
  embeddings = GoogleGenerativeAIEmbeddings(
      # model="models/embedding-004",
      model="models/text-embedding-004",
      google_api_key=GEMINI_API_KEY
  )
  return model, embeddings


def load_documents(source_dir: str):
    """
    Load documents from multiple sources
    """
    documents = []

    file_types = {
      "*.pdf": PyPDFLoader,
      "*.csv": CSVLoader
    }

    if os.path.isfile(source_dir):
        ext = os.path.splitext(source_dir)[1].lower()
        if ext == ".pdf":
            documents.extend(PyPDFLoader(source_dir).load())
        elif ext == ".csv":
            documents.extend(CSVLoader(source_dir).load())
    else:
        for pattern, loader in file_types.items():
            for file_path in glob.glob(os.path.join(source_dir, pattern)):
                documents.extend(loader(file_path).load())
    return documents


def create_vector_store(docs: List[Document], embeddings, chunk_size: int = 10000, chunk_overlap: int = 200):
  """
  Create vector store from documents
  """
  text_splitter = RecursiveCharacterTextSplitter(
      chunk_size=chunk_size,
      chunk_overlap=chunk_overlap
  )
  splits = text_splitter.split_documents(docs)
  # return Chroma.from_documents(splits, embeddings).as_retriever(search_kwargs={"k": 5}) 
  return FAISS.from_documents(splits, embeddings).as_retriever(search_kwargs={"k": 5})




PROMPT_TEMPLATE = """
  Use the following pieces of context to answer the question at the end.
  If you don't know the answer, just say that you don't know, don't try to make up an answer.
  
  NOTE: Return a well structured output that is readable to the user, with clear formatting
  {context}

  Question: {question}
  Answer:
  
  """



def get_qa_chain(source_dir):
  """Create QA chain with proper error handling"""

  try:
    docs = load_documents(source_dir)
    if not docs:
      raise ValueError("No documents found in the specified sources")

    llm, embeddings = load_model()
    # if not llm or not embeddings:model_type: str = "gemini",
    #   raise ValueError(f"Model {model_type} not configured properly")

    retriever = create_vector_store(docs, embeddings)

    prompt = PromptTemplate(
        template=PROMPT_TEMPLATE,
        input_variables=["context", "question"]
    )

    response = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt}
    )

    return response

  except Exception as e:
    # print(f"Error initializing QA system: {e}")
    return f"Error initializing QA system: {e}"



def query_system(query: str, qa_chain):
  if not qa_chain:
    return "System not initialized properly"

  try:
    result = qa_chain({"query": query})
    if not result["result"] or "don't know" in result["result"].lower():
      return "The answer could not be found in the provided documents"
    return f"ElevateHR Agent 👩‍💼: \n{result['result']}" #\nSources: {[s.metadata['source'] for s in result['source_documents']]}"
  except Exception as e:
    return f"Error processing query: {e}"



