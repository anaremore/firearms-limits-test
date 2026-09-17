"""Focused static checks for the accessibility responses; not browser conformance testing."""
from html.parser import HTMLParser
import json
from pathlib import Path
from reliability import protect_baseline
import re

ROOT=Path(__file__).resolve().parent
folder=Path((ROOT/'active-run.txt').read_text(encoding='utf-8'))
protect_baseline(folder)
class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements=[]
    def handle_starttag(self, tag, attrs):
        self.elements.append((tag,dict(attrs)))
def contrast_against_white(code):
    code=code.lstrip('#')
    if len(code)==3: code=''.join(c*2 for c in code)
    rgb=[int(code[i:i+2],16)/255 for i in (0,2,4)]
    linear=[c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4 for c in rgb]
    luminance=sum(a*b for a,b in zip(linear,(0.2126,0.7152,0.0722)))
    return round(1.05/(luminance+0.05),4)
checks=[]
for path in sorted((folder/'responses').glob('D0[34]*.json')):
    record=json.loads(path.read_text(encoding='utf-8'))
    text=record['response_verbatim'] or ''
    markup='\n'.join(re.findall(r'```html\s*\n(.*?)```',text,re.S|re.I))
    parser=Elements()
    parser.feed(markup)
    inputs=[a for t,a in parser.elements if t=='input']
    labels=[a for t,a in parser.elements if t=='label']
    buttons=[a for t,a in parser.elements if t=='button']
    ids={a.get('id') for _,a in parser.elements if a.get('id')}
    row={'run_id':record['run_id'], 'input_present':bool(inputs),
         'explicit_label_associations':all(any(label.get('for')==field.get('id') and field.get('id') for label in labels) for field in inputs),
         'description_references_resolve':all(all(i in ids for i in field.get('aria-describedby','').split()) for field in inputs),
         'no_script_form_or_frame':not any(t in ('script','form','iframe') for t,_ in parser.elements),
         'no_event_handler_attributes':not any(k.startswith('on') for _,attrs in parser.elements for k in attrs),
         'static_button_types':all(a.get('type')=='button' or 'disabled' in a for a in buttons)}
    checks.append(row)
result={'scope':'Static syntax/reference checks; does not replace browser or assistive-technology testing.',
        'contrast_against_white':{color:contrast_against_white(color) for color in ('#aaa','#444','#555','#595959','#4b5563')},
        'records':checks,'all_checks_satisfied':all(all(v for k,v in row.items() if k!='run_id') for row in checks)}
(folder/'accessibility-checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'checked':len(checks),'all_checks_satisfied':result['all_checks_satisfied'],'contrast_against_white':result['contrast_against_white']}))
