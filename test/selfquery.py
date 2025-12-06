from src.copilot.tools.qdrantretriever import retriever, get_incident_report;

def test_qdrant_retriever():
    docs = retriever.invoke("How did Merchant Refund API Timeout get solved?")
    for doc in docs:
        print(doc.page_content)
        print(doc.metadata)
    

def test_get_incident_report():
    result = get_incident_report("How did Merchant Refund API Timeout get solved?", lambda x: print(x))
    print(result)

test_get_incident_report()