from app.analysis import page_extract, make_summary,seo_audit,question_answer
HTML='''<!DOCTYPE html><html lang="en"><head><title>Bright Future</title><meta name="description" content="We build excellent products."></head><body><nav><p>Ignore navigation</p></nav><main><h1>Welcome to Bright Future</h1><p>Our technology studio builds secure and accessible products for modern businesses.</p><h2>Automation</h2><p>We automate operational reporting and create reliable tools for growing teams.</p></main></body></html>'''

def test_extraction_removes_navigation():
    p=page_extract(HTML,'https://example.com')
    assert p['title']=='Bright Future'
    assert p['description']=='We build excellent products.'
    assert p['h1_count']==1
    assert p['word_count']>10
    assert 'Ignore navigation' not in p['excerpt']

def test_summary_and_seo():
    p=page_extract(HTML,'https://example.com')
    assert 'excellent products' in make_summary([p],'https://example.com')['overview']
    assert seo_audit([p])['score']==100
    assert seo_audit([p])['issues']==[]

def test_grounded_qa_and_no_hallucination():
    p=page_extract(HTML,'https://example.com')
    result={'pages':[p], 'summary':make_summary([p],'https://example.com'),'seo':seo_audit([p])}
    assert 'automate' in question_answer('Tell me about automation',result)['text'].lower()
    assert 'could not find reliable evidence' in question_answer('How many elephants are in the office?',result)['text'].lower()
